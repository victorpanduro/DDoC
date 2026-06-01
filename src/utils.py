from datetime import date, datetime, timezone, timedelta
from io import BytesIO as BIO
import json
from pathlib import Path
import re
import os
import dotenv
from requests import Response, Session
from requests.adapters import HTTPAdapter
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    HTTPError,
    JSONDecodeError,
    RequestException,
    Timeout,
    TooManyRedirects,
)
from urllib3.util.retry import Retry
from PIL import Image
from datatypes import APODCache, APODData
from path_utils import (
    PRIVATE_DIR,
    ENV_PATH,
    TEMP_DATA_PATH,
    TEMP_DATA_DIR,
    TEMP_IMAGE_DIR,
    TEMP_DATA_SUFFIXES,
    TEMP_DIR,
    TEMP_IMAGE_SUFFIXES
)

UNWANTED_MARKERS = [
    "Free Presentation:",
    "Tomorrow's picture:",
    "Explore the Universe:",
    "New:",
    "Follow APOD in English on:",
    "Almost Hyperspace:",
    "Portal Universe:",
    "(Editor's note:",
    "Jigsaw Galaxy:",
    "Sky Surprise:",
    "Celebrate:",
    "Jigsaw Vistas:",
    "Growing Gallery:",
    "Artemis II:",
    "Jigsaw Nebula:",
    "Almost Hyperspace:",
    "Interstellar Jigsaw:",
    "Jigsaw Universe:"
]


def data_exists(requested_date: str, cache: APODCache) -> bool:
    return (
        cache is not None
        and requested_date is not None
        and requested_date in cache
        and requested_date == cache[requested_date]["date"]
    )


def create_apod_session() -> Session:
    retry_strategy = Retry(
        total = 3,
        connect = 3,
        read = 3,
        redirect = False,
        status = 3,
        other = None,
        backoff_factor = 0.1,
        backoff_jitter = 0.1,
        backoff_max = 2,
        allowed_methods = ["GET"],
    )
    adapter = HTTPAdapter(max_retries = retry_strategy)
    session = Session()
    session.mount("https://", adapter)
    return session


def fetch_apod_data(key: str, requested_date: str, cache: APODCache, session: Session) -> APODData:
    if data_exists(requested_date, cache):
        return cache[requested_date]

    try:
        response = session.get(
            "https://api.nasa.gov/planetary/apod",
            params = {
                "api_key" : key,
                "thumbs" : True,
                "date" : requested_date
            },
            timeout = (5, 5),
            allow_redirects = True
        )
        response.raise_for_status()
    except (RequestException, RequestsConnectionError, HTTPError, TooManyRedirects, Timeout) as ex:
        error_response = getattr(ex, "response", None)
        status_code = getattr(error_response, "status_code", "Unknown")
        reason = getattr(error_response, "reason", str(ex) or "Unknown reason")
        raise RuntimeError(f"Code: {status_code}. Reason: {reason}.") from ex

    try:
        cache = parse_response_to_cache(response, cache)
        return cache[requested_date]
    except (RuntimeError, ValueError) as ex:
        raise RuntimeError("Could not load or save data.") from ex


def parse_response_to_cache(response: Response, cache: APODCache) -> APODCache:
    try:
        json_data = response.json()
        cache[json_data.get("date", "Unknown date")] = APODData(
                title = json_data.get("title", "Unknown title"),
                date = json_data.get("date", "Unknown date"),
                explanation = clean_explanation(
                    json_data.get("explanation", "No explanation available"), UNWANTED_MARKERS),
                url = json_data.get("hdurl") or json_data.get("url", ""),
                media_type = json_data.get("media_type", "Unknown media type"),
                copyright = remove_newline(
                    json_data.get("copyright", "Unknown copyrighter")
                )
            )
    except JSONDecodeError as ex:
        raise RuntimeError("Could not decode text into valid JSON.") from ex
    except (KeyError, AttributeError) as ex:
        raise ValueError("Could not insert new key-value pair") from ex

    try:
        save_cache(cache)
    except RuntimeError as ex:
        raise RuntimeError("Could not load data from data.json to runtime cache.") from ex

    return cache


def load_saved_data_to_runtime_cache(cache: APODCache) -> APODCache:
    if not TEMP_DATA_PATH.is_file():
        return {}

    try:
        cache = json.loads(
            TEMP_DATA_PATH.read_text(encoding = "utf-8")
        )
    except (OSError, json.JSONDecodeError) as ex:
        raise RuntimeError("Could not load data from data.json to runtime cache.") from ex

    return {
        index : data
        for index, data in cache.items()
        if isinstance(index, str) and isinstance(data, dict)
    }


def save_cache(cache: APODCache) -> None:
    # write results to json file
    try:
        TEMP_DATA_DIR.mkdir(parents = True, exist_ok = True)
        TEMP_DATA_PATH.write_text(
            json.dumps(cache, indent = 4, sort_keys = True),
            encoding = "utf-8"
        )
    except (OSError, RuntimeError, ValueError) as ex:
        raise RuntimeError("Could not save cache to data.json.") from ex

    try:
        load_saved_data_to_runtime_cache(cache)
    except RuntimeError as ex:
        raise RuntimeError("Could not load data from data.json to runtime cache.") from ex


def fetch_and_save_image(data: APODData, session: Session) -> Path | None:
    if data["media_type"] != "image":
        return None

    if not data["url"]:
        raise ValueError("No image URL was returned by the API.")

    TEMP_IMAGE_DIR.mkdir(parents = True, exist_ok = True)
    temp_png_image_path = TEMP_IMAGE_DIR / f"{data['date']}.png"

    if temp_png_image_path.is_file():
        return temp_png_image_path

    try:
        response = session.get(
            data["url"],
            timeout = (5, 5),
            allow_redirects = True
        )
        response.raise_for_status()
    except (RequestException, RequestsConnectionError, HTTPError, TooManyRedirects, Timeout) as ex:
        error_response = getattr(ex, "response", None)
        status_code = getattr(error_response, "status_code", "Unknown")
        reason = getattr(error_response, "reason", str(ex) or "Unknown reason")
        raise RuntimeError(f"Code: {status_code}. Reason: {reason}.") from ex

    try:
        with Image.open(BIO(response.content)) as image:
            image.save(temp_png_image_path)
    except OSError as ex:
        temp_png_image_path.unlink(missing_ok = True)
        raise ValueError("Downloaded file could not be opened as an image.") from ex

    return temp_png_image_path


def use_regex_and_datetime(input_text: str) -> bool:
    # check input string against regular expression
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if not pattern.fullmatch(input_text):
        return False

    # check if the date is a valid apod date
    try:
        parsed_date = datetime.strptime(input_text, "%Y-%m-%d").date()
        return (
            date(1995, 6, 16) <= parsed_date
            and date_is_not_in_future_globally(parsed_date.isoformat())
        )
    except ValueError:
        return False


def get_minimum_global_date() -> str:
    return datetime.now(timezone(timedelta(hours = -12))).date().isoformat()


def date_is_not_in_future_globally(requested_date: str) -> bool:
    return requested_date <= get_minimum_global_date()


def get_api_key() -> str:
    # loads the api key from local env to os env
    if dotenv.load_dotenv(ENV_PATH, verbose = True, encoding = "utf-8"):
        return os.environ.get("NASA_API_KEY", "")

    try:
        new_path = dotenv.find_dotenv(".env", True)
        if not new_path.strip():
            return ""
        if dotenv.load_dotenv(new_path, verbose = True, encoding = "utf-8"):
            return os.environ.get("NASA_API_KEY", "")
        return ""
    except OSError:
        return ""


def save_api_key(key: str) -> None:
    # save the api key to local enviroment variables
    if not key.strip():
        raise ValueError("API key cannot be empty.")

    try:
        PRIVATE_DIR.mkdir(parents = True, exist_ok = True)
        ENV_PATH.write_text(f"NASA_API_KEY={key}\n", encoding = "utf-8")
    except OSError as ex:
        raise OSError("OS error",
                      "Could not open .env file and save API key as variable.") from ex


def clear_cache() -> None:
    clear_tmp_data()
    clear_tmp_images()
    if TEMP_DIR.exists():
        TEMP_DIR.rmdir()


def clear_tmp_images() -> None:
    if not TEMP_IMAGE_DIR.exists():
        return

    for image_path in TEMP_IMAGE_DIR.iterdir():
        if image_path.is_file() and image_path.suffix.lower() in TEMP_IMAGE_SUFFIXES:
            image_path.unlink(missing_ok = True)

    TEMP_IMAGE_DIR.rmdir()


def clear_tmp_data() -> None:
    if not TEMP_DATA_DIR.exists():
        return

    for data_file_path in TEMP_DATA_DIR.iterdir():
        if data_file_path.is_file() and data_file_path.suffix.lower() in TEMP_DATA_SUFFIXES:
            data_file_path.unlink(missing_ok = True)

    TEMP_DATA_DIR.rmdir()


def clean_explanation(explanation: str, markers: list[str]) -> str:
    for marker in markers:
        index = explanation.find(marker)
        if index != -1:
            explanation = explanation[:index]

    return explanation.strip().replace("  ", " ")


def remove_newline(text: str) -> str:
    index = text.find("\n")
    if index != -1:
        text = text[:index]
    return text.strip()

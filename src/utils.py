from datetime import datetime, date
from io import BytesIO
import json
from pathlib import Path
import re
import os
import dotenv
import requests
from PIL import Image

type Data = dict[str, str]

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PRIVATE_DIR = PROJECT_ROOT / "private"
ENV_PATH = PRIVATE_DIR / ".env"

TEMP_DIR = PROJECT_ROOT / "temp"
TEMP_DATA_DIR = TEMP_DIR / "data"
TEMP_DATA_PATH = TEMP_DATA_DIR / "data.json"
TEMP_DATA_SUFFIXES = {".json", ".jsonc", ".toml"}

TEMP_IMAGE_DIR = TEMP_DIR / "imgs"
TEMP_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

ICON_DIR = PROJECT_ROOT / "icon"
ICON_PATH = ICON_DIR / "ddoc-icon.png"

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


def use_regex_and_datetime(input_text: str) -> bool:
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    if not pattern.fullmatch(input_text):
        return False

    try:
        parsed_date = datetime.strptime(input_text, "%Y-%m-%d").date()
        return date(1995, 6, 16) <= parsed_date <= date.today()
    except ValueError:
        return False


def get_api_key() -> str:
    dotenv.load_dotenv(ENV_PATH)
    return os.getenv("NASA_API_KEY", "")


def save_api_key(key: str) -> None:
    if not key.strip():
        raise ValueError("API key cannot be empty.")

    try:
        PRIVATE_DIR.mkdir(parents = True, exist_ok = True)
        ENV_PATH.write_text(f"NASA_API_KEY={key}\n", encoding = "utf-8")
    except OSError as ex:
        raise ValueError("Environment error",
                         "Could not open .env file and save API key as variable.") from ex


def fetch_and_parse_response_to_data(
        key: str | None,
        temp_storage: bool = True,
        requested_date: str | None = None) -> Data | None:

    if not key or not key.strip():
        raise ValueError("API key is missing.")

    if temp_storage:
        cached_data = get_saved_data(requested_date)
        if cached_data is not None:
            return cached_data

    params = {
        "api_key" : key,
        "thumbs" : True
    }
    if requested_date:
        params["date"] = requested_date

    try:
        response = requests.get(
            "https://api.nasa.gov/planetary/apod",
            params = params,
            timeout = 30,
            allow_redirects = True
        )
        response.raise_for_status()

    except requests.exceptions.HTTPError as ex:
        raise RuntimeError(f"NASA API returned HTTP error code {response.status_code}.",
                           str(ex)) from ex

    except requests.exceptions.RequestException as ex:
        raise RuntimeError("Could not contact NASA APOD API.") from ex

    try:
        api_data = response.json()
        data = parse_response_to_data(api_data)
        if temp_storage:
            save_data(data)

    except requests.exceptions.JSONDecodeError as ex:
        raise ValueError("NASA APOD API did not return valid JSON.") from ex

    return data


def parse_response_to_data(data) -> Data:
    return {
        "title" : data.get("title", "Unknown title"),
        "date" : data.get("date", "Unknown date"),
        "explanation" : clean_explanation(
            data.get("explanation", "No explanation available"), UNWANTED_MARKERS),
        "url" : data.get("hdurl") or data.get("url", ""),
        "media_type" : data.get("media_type", "Unknown media type"),
        "copyright" : data.get("copyright", "Unknown copyrighter")
    }


def get_data_date(requested_date: str | None = None) -> str:
    return requested_date or date.today().isoformat()


def load_saved_data() -> dict[str, Data]:
    if not TEMP_DATA_PATH.is_file():
        return {}

    try:
        data = json.loads(TEMP_DATA_PATH.read_text(encoding = "utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(data, dict):
        return {}

    return {
        saved_date: saved_data
        for saved_date, saved_data in data.items()
        if isinstance(saved_date, str) and isinstance(saved_data, dict)
    }


def get_saved_data(requested_date: str | None = None) -> Data | None:
    saved_data = load_saved_data()
    return saved_data.get(get_data_date(requested_date))


def save_data(data: Data) -> None:
    if data_exists(data["date"]):
        return

    saved_data = load_saved_data()
    saved_data[data["date"]] = data

    TEMP_DATA_DIR.mkdir(parents = True, exist_ok = True)
    TEMP_DATA_PATH.write_text(
        json.dumps(saved_data, indent = 4),
        encoding = "utf-8"
    )


def data_exists(requested_date: str | None = None) -> bool:
    return get_saved_data(requested_date) is not None


def fetch_and_save_image(data: Data) -> Path | None:
    if data["media_type"] != "image":
        return None

    if not data["url"]:
        raise ValueError("No image URL was returned by the API.")

    TEMP_IMAGE_DIR.mkdir(parents = True, exist_ok = True)
    TEMP_PNG_IMAGE_PATH = TEMP_IMAGE_DIR / f"{data['date']}.png"

    if TEMP_PNG_IMAGE_PATH.is_file():
        return TEMP_PNG_IMAGE_PATH

    try:
        response = requests.get(
            data["url"],
            timeout = 30,
            allow_redirects = True
        )
        response.raise_for_status()

    except requests.exceptions.RequestException as ex:
        raise ValueError("Could not download image.") from ex

    try:
        with Image.open(BytesIO(response.content)) as image:
            image.save(TEMP_PNG_IMAGE_PATH)

    except OSError as ex:
        TEMP_PNG_IMAGE_PATH.unlink(missing_ok = True)
        raise ValueError("Downloaded file could not be opened as an image.") from ex

    return TEMP_PNG_IMAGE_PATH


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

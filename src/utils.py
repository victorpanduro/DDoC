from datetime import datetime, date
from io import BytesIO
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
TMP_IMAGE_DIR = PROJECT_ROOT / "tmp" / "imgs"
ICON_PATH = PROJECT_ROOT / "icon" / "ddoc-icon.png"
TEMP_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


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
                         "Could not open .env file and save API key as varibale.") from ex


def fetch_and_parse_response_to_data(key: str | None, date: str | None = None) -> Data | None:
    if not key or not key.strip():
        raise ValueError("API key is missing.")

    params = {
        "api_key" : key,
        "thumbs" : True
    }
    if date:
        params["date"] = date

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
        data = response.json()
    except requests.exceptions.JSONDecodeError as ex:
        raise ValueError("NASA APOD API did not return valid JSON.") from ex

    return {
        "title" : data.get("title", "Unknown title"),
        "date" : data.get("date", "Unknown date"),
        "explanation" : clean_explanation(data.get("explanation", "No explanation available")),
        "url" : data.get("hdurl") or data.get("url", ""),
        "media_type" : data.get("media_type", "Unknown media type"),
        "copyright" : data.get("copyright", "Unknown copyrighter")
    }


def fetch_and_save_image(data: Data) -> Path | None:
    if data["media_type"] != "image":
        return None

    if not data["url"]:
        raise ValueError("No image URL was returned by the API.")

    TMP_IMAGE_DIR.mkdir(parents = True, exist_ok = True)
    png_path = TMP_IMAGE_DIR / f"{data['date']}.png"

    if png_path.is_file():
        return png_path

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
            image.save(png_path)
    except OSError as ex:
        png_path.unlink(missing_ok = True)
        raise ValueError("Downloaded file could not be opened as an image.") from ex

    return png_path


def clear_tmp_images() -> None:
    if not TMP_IMAGE_DIR.exists():
        return

    for image_path in TMP_IMAGE_DIR.iterdir():
        if image_path.is_file() and image_path.suffix.lower() in TEMP_IMAGE_SUFFIXES:
            image_path.unlink(missing_ok = True)


def clean_explanation(explanation: str) -> str:
    unwanted_markers = [
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
        "Almost Hyperspace:"
    ]

    for marker in unwanted_markers:
        index = explanation.find(marker)
        if index != -1:
            explanation = explanation[:index]

    return explanation.strip()

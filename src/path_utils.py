from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PRIVATE_DIR = PROJECT_ROOT / "private"
ENV_PATH = PRIVATE_DIR / ".env"

TEMP_DIR = PROJECT_ROOT / "temp"
TEMP_DATA_DIR = TEMP_DIR / "data"
TEMP_DATA_PATH = TEMP_DATA_DIR / "data.json"
TEMP_DATA_SUFFIXES = {".json", ".jsonc", ".toml"}

TEMP_IMAGE_DIR = TEMP_DIR / "imgs"
TEMP_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

ICON_DIR = PROJECT_ROOT / "assets" / "dan_wiersema_icons"
ICON_PATH = ICON_DIR / "mercury.png"

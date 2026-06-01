import json
import importlib
import shutil
import sys
import unittest
from dataclasses import dataclass
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4
import requests
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

utils = importlib.import_module("utils")

@contextmanager
def project_temporary_directory():
    temp_dir = PROJECT_ROOT / "test" / f"_tmp_{uuid4().hex}"
    temp_dir.mkdir()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@dataclass
class FakeResponse:
    data: object | None = None
    content: bytes = b""
    error: Exception | None = None
    status_code: int = 200
    reason: str = "OK"

    def json(self):
        if isinstance(self.data, Exception):
            raise self.data
        return self.data

    def raise_for_status(self):
        if self.error:
            if getattr(self.error, "response", None) is None:
                self.error.response = self
            raise self.error


def make_fake_session(response=None, error=None):
    session = Mock()
    if error:
        session.get.side_effect = error
    else:
        session.get.return_value = response
    return session


class UtilsDateValidationTests(unittest.TestCase):
    def test_accepts_apod_start_date_and_global_today(self):
        with patch.object(utils, "get_minimum_global_date", return_value="2026-05-26"):
            self.assertTrue(utils.use_regex_and_datetime("1995-06-16"))
            self.assertTrue(utils.use_regex_and_datetime("2026-05-26"))

    def test_rejects_invalid_dates(self):
        with patch.object(utils, "get_minimum_global_date", return_value="2026-05-26"):
            self.assertFalse(utils.use_regex_and_datetime("1995-06-15"))
            self.assertFalse(utils.use_regex_and_datetime("2026-05-27"))
            self.assertFalse(utils.use_regex_and_datetime("2026/05/26"))
            self.assertFalse(utils.use_regex_and_datetime("not-a-date"))

    def test_get_minimum_global_date_returns_iso_date(self):
        self.assertRegex(utils.get_minimum_global_date(), r"^\d{4}-\d{2}-\d{2}$")

    def test_date_is_not_in_future_globally_uses_minimum_global_date(self):
        with patch.object(utils, "get_minimum_global_date", return_value="2026-05-26"):
            self.assertTrue(utils.date_is_not_in_future_globally("2026-05-26"))
            self.assertFalse(utils.date_is_not_in_future_globally("2026-05-27"))


class UtilsCacheTests(unittest.TestCase):
    def setUp(self):
        self.apod_data = {
            "title": "Test APOD",
            "date": "2026-05-26",
            "explanation": "A test entry",
            "url": "https://example.com/apod.png",
            "media_type": "image",
            "copyright": "Test Author",
        }
        self.cache = {"2026-05-26": self.apod_data}

    def test_data_exists_finds_matching_date(self):
        self.assertTrue(utils.data_exists("2026-05-26", self.cache))

    def test_data_exists_rejects_missing_or_mismatched_date(self):
        mismatched_cache = {
            "2026-05-26": {
                **self.apod_data,
                "date": "2026-05-25",
            }
        }

        self.assertFalse(utils.data_exists("2026-05-25", self.cache))
        self.assertFalse(utils.data_exists("2026-05-26", mismatched_cache))
        self.assertFalse(utils.data_exists("2026-05-26", {}))

    def test_fetch_apod_data_uses_runtime_cache_before_network(self):
        session = make_fake_session()

        result = utils.fetch_apod_data("KEY", "2026-05-26", self.cache, session)

        self.assertIs(result, self.cache["2026-05-26"])
        session.get.assert_not_called()

    @patch("utils.save_cache")
    def test_fetch_apod_data_fetches_and_caches_missing_date(self, save_cache_mock):
        response_data = {
            "title": "Fresh APOD",
            "date": "2026-05-27",
            "explanation": "Fresh explanation",
            "url": "https://example.com/fresh.png",
            "media_type": "image",
        }
        session = make_fake_session(FakeResponse(response_data))

        result = utils.fetch_apod_data("KEY", "2026-05-27", {}, session)

        self.assertEqual(result["title"], "Fresh APOD")
        self.assertEqual(result["copyright"], "This APOD is public domain")
        session.get.assert_called_once()
        args, kwargs = session.get.call_args
        self.assertEqual(args, ("https://api.nasa.gov/planetary/apod",))
        self.assertEqual(
            kwargs["params"],
            {"api_key": "KEY", "thumbs": True, "date": "2026-05-27"},
        )
        save_cache_mock.assert_called_once()

    def test_fetch_apod_data_wraps_http_errors(self):
        session = make_fake_session(FakeResponse(
            error=requests.exceptions.HTTPError("server error"),
            status_code=500,
            reason="Server Error",
        ))

        with self.assertRaisesRegex(RuntimeError, "Code: 500"):
            utils.fetch_apod_data("KEY", "2026-05-27", {}, session)

    def test_fetch_apod_data_wraps_request_errors(self):
        session = make_fake_session(error=requests.exceptions.Timeout("timed out"))

        with self.assertRaisesRegex(RuntimeError, "timed out"):
            utils.fetch_apod_data("KEY", "2026-05-27", {}, session)

    @patch("utils.save_cache")
    def test_parse_response_to_cache_prefers_hdurl_and_cleans_explanation(self, save_cache_mock):
        response = FakeResponse({
            "title": "Parsed APOD",
            "date": "2026-05-28",
            "explanation": "Keep this. Tomorrow's picture: Remove this.",
            "url": "https://example.com/preview.png",
            "hdurl": "https://example.com/full.png",
            "media_type": "image",
            "copyright": "NASA",
        })

        result = utils.parse_response_to_cache(response, {})

        self.assertEqual(result["2026-05-28"]["url"], "https://example.com/full.png")
        self.assertEqual(result["2026-05-28"]["explanation"], "Keep this.")
        save_cache_mock.assert_called_once_with(result)

    def test_parse_response_to_cache_rejects_invalid_json(self):
        response = FakeResponse(requests.exceptions.JSONDecodeError("bad json", "", 0))

        with self.assertRaisesRegex(RuntimeError, "valid JSON"):
            utils.parse_response_to_cache(response, {})

    def test_save_cache_writes_json_file(self):
        with project_temporary_directory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_path = data_dir / "data.json"

            with patch.object(utils, "TEMP_DATA_DIR", data_dir), patch.object(
                utils, "TEMP_DATA_PATH", data_path
            ):
                utils.save_cache(self.cache)

            self.assertEqual(json.loads(data_path.read_text(encoding="utf-8")), self.cache)

    def test_load_saved_data_to_runtime_cache_reads_json_file(self):
        with project_temporary_directory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_path = data_dir / "data.json"
            data_dir.mkdir()
            data_path.write_text(json.dumps(self.cache), encoding="utf-8")

            with patch.object(utils, "TEMP_DATA_PATH", data_path):
                result = utils.load_saved_data_to_runtime_cache({})

            self.assertEqual(result, self.cache)

    def test_load_saved_data_to_runtime_cache_returns_empty_cache_for_missing_file(self):
        with project_temporary_directory() as temp_dir:
            data_path = Path(temp_dir) / "missing.json"

            with patch.object(utils, "TEMP_DATA_PATH", data_path):
                self.assertEqual(utils.load_saved_data_to_runtime_cache({}), {})


class UtilsImageTests(unittest.TestCase):
    def setUp(self):
        self.apod_data = {
            "title": "Image APOD",
            "date": "2026-05-26",
            "explanation": "Image entry",
            "url": "https://example.com/image.png",
            "media_type": "image",
            "copyright": "NASA",
        }

    def test_fetch_and_save_image_returns_none_for_non_image_media(self):
        data = {
            **self.apod_data,
            "media_type": "video",
        }

        self.assertIsNone(utils.fetch_and_save_image(data, make_fake_session()))

    def test_fetch_and_save_image_rejects_missing_url(self):
        data = {
            **self.apod_data,
            "url": "",
        }

        with self.assertRaisesRegex(ValueError, "No image URL"):
            utils.fetch_and_save_image(data, make_fake_session())

    def test_fetch_and_save_image_reuses_existing_file(self):
        session = make_fake_session()
        with project_temporary_directory() as temp_dir:
            image_dir = Path(temp_dir) / "imgs"
            image_dir.mkdir()
            existing_image = image_dir / "2026-05-26.png"
            existing_image.write_bytes(b"already cached")

            with patch.object(utils, "TEMP_IMAGE_DIR", image_dir):
                result = utils.fetch_and_save_image(self.apod_data, session)

        self.assertEqual(result, existing_image)
        session.get.assert_not_called()

    def test_fetch_and_save_image_downloads_valid_image(self):
        image_bytes = BytesIO()
        Image.new("RGB", (1, 1), "black").save(image_bytes, format="PNG")
        session = make_fake_session(FakeResponse(content=image_bytes.getvalue()))

        with project_temporary_directory() as temp_dir:
            image_dir = Path(temp_dir) / "imgs"

            with patch.object(utils, "TEMP_IMAGE_DIR", image_dir):
                result = utils.fetch_and_save_image(self.apod_data, session)

                self.assertTrue(result.is_file())
                self.assertEqual(result.name, "2026-05-26.png")

        session.get.assert_called_once_with(
            "https://example.com/image.png",
            timeout = (5, 5),
            allow_redirects = True,
        )

    def test_fetch_and_save_image_rejects_invalid_image_bytes(self):
        session = make_fake_session(FakeResponse(content=b"not an image"))

        with project_temporary_directory() as temp_dir:
            image_dir = Path(temp_dir) / "imgs"

            with patch.object(utils, "TEMP_IMAGE_DIR", image_dir):
                with self.assertRaisesRegex(ValueError, "could not be opened"):
                    utils.fetch_and_save_image(self.apod_data, session)

                self.assertFalse((image_dir / "2026-05-26.png").exists())


class UtilsFileCleanupTests(unittest.TestCase):
    def test_clear_cache_removes_temp_data_and_images(self):
        with project_temporary_directory() as temp_dir:
            temp_path = Path(temp_dir) / "temp"
            data_dir = temp_path / "data"
            image_dir = temp_path / "imgs"
            data_dir.mkdir(parents=True)
            image_dir.mkdir(parents=True)
            (data_dir / "data.json").write_text("{}", encoding="utf-8")
            (image_dir / "2026-05-26.png").write_bytes(b"image")

            with patch.object(utils, "TEMP_DIR", temp_path), patch.object(
                utils, "TEMP_DATA_DIR", data_dir
            ), patch.object(utils, "TEMP_IMAGE_DIR", image_dir):
                utils.clear_cache()

            self.assertFalse(temp_path.exists())


class UtilsTextCleanupTests(unittest.TestCase):
    def test_clean_explanation_removes_marker_text_and_extra_spaces(self):
        explanation = "Keep this.  Tomorrow's picture: Remove this."

        self.assertEqual(
            utils.clean_explanation(explanation, utils.UNWANTED_MARKERS),
            "Keep this.",
        )

    def test_clean_explanation_returns_stripped_text_without_markers(self):
        self.assertEqual(
            utils.clean_explanation("  Keep this text.  ", utils.UNWANTED_MARKERS),
            "Keep this text.",
        )


if __name__ == "__main__":
    unittest.main()

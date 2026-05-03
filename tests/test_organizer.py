import json
import pytest
from pathlib import Path
from insta_loader.organizer import sanitize_name, slide_filename, slide_exists, highlight_dir, write_metadata


def test_sanitize_name_replaces_spaces():
    assert sanitize_name("Summer 2024") == "Summer_2024"


def test_sanitize_name_replaces_slashes():
    assert sanitize_name("Travel/Europe") == "Travel-Europe"


def test_sanitize_name_plain_name_unchanged():
    assert sanitize_name("Travel") == "Travel"


def test_sanitize_name_both_space_and_slash():
    assert sanitize_name("Travel/Europe 2024") == "Travel-Europe_2024"


def test_sanitize_name_strips_apostrophe():
    assert sanitize_name("Czechia '26") == "Czechia_26"


def test_sanitize_name_strips_ampersand_and_collapses():
    assert sanitize_name("Gdansk & Hel") == "Gdansk_Hel"


def test_sanitize_name_keeps_emoji():
    assert sanitize_name("🇨🇿 Czechia '25") == "🇨🇿_Czechia_25"


def test_sanitize_name_keeps_accented_chars():
    assert sanitize_name("Iguazú") == "Iguazú"


def test_sanitize_name_strips_leading_trailing_underscores():
    assert sanitize_name("'Travel'") == "Travel"


def test_slide_filename_zero_pads_single_digit():
    assert slide_filename("Travel", 1) == "Travel_01"


def test_slide_filename_two_digit_index():
    assert slide_filename("Travel", 12) == "Travel_12"


def test_slide_filename_sanitizes_title():
    assert slide_filename("Summer 2024", 3) == "Summer_2024_03"


def test_slide_exists_false_when_folder_empty(tmp_path):
    assert slide_exists(tmp_path, "Travel", 1) is False


def test_slide_exists_true_when_file_present(tmp_path):
    (tmp_path / "Travel_01_20230415_143200.mp4").touch()
    assert slide_exists(tmp_path, "Travel", 1) is True


def test_slide_exists_false_for_different_index(tmp_path):
    (tmp_path / "Travel_01_20230415_143200.mp4").touch()
    assert slide_exists(tmp_path, "Travel", 2) is False


def test_slide_exists_false_for_different_name(tmp_path):
    (tmp_path / "Travel_01_20230415_143200.mp4").touch()
    assert slide_exists(tmp_path, "Summer", 1) is False


def test_slide_exists_no_false_positive_on_longer_index(tmp_path):
    # Travel_010_* must not match the glob for idx=1 (Travel_01_*)
    (tmp_path / "Travel_010_20230415_143200.mp4").touch()
    assert slide_exists(tmp_path, "Travel", 1) is False


def test_highlight_dir_creates_folder(tmp_path):
    result = highlight_dir(tmp_path, "Travel")
    assert result.exists()
    assert result.name == "Travel"


def test_highlight_dir_returns_correct_path(tmp_path):
    result = highlight_dir(tmp_path, "Travel")
    assert result == tmp_path / "Travel"


def test_highlight_dir_sanitizes_name(tmp_path):
    result = highlight_dir(tmp_path, "Summer 2024")
    assert result.name == "Summer_2024"


def test_highlight_dir_is_idempotent(tmp_path):
    highlight_dir(tmp_path, "Travel")
    highlight_dir(tmp_path, "Travel")  # second call must not raise
    assert (tmp_path / "Travel").exists()


def test_write_metadata_creates_file(tmp_path):
    write_metadata(tmp_path, "Travel", total=5, downloaded=5, videos=3, images=2)
    assert (tmp_path / "metadata.json").exists()


def test_write_metadata_complete_status(tmp_path):
    write_metadata(tmp_path, "Travel", total=5, downloaded=5, videos=3, images=2)
    data = json.loads((tmp_path / "metadata.json").read_text())
    assert data["status"] == "complete"


def test_write_metadata_partial_status(tmp_path):
    write_metadata(tmp_path, "Travel", total=5, downloaded=3, videos=2, images=1)
    data = json.loads((tmp_path / "metadata.json").read_text())
    assert data["status"] == "partial"


def test_write_metadata_fields(tmp_path):
    write_metadata(tmp_path, "Travel", total=4, downloaded=4, videos=1, images=3)
    data = json.loads((tmp_path / "metadata.json").read_text())
    assert data["highlight_title"] == "Travel"
    assert data["total_items"] == 4
    assert data["downloaded"] == 4
    assert data["videos"] == 1
    assert data["images"] == 3
    assert "last_updated" in data


def test_write_metadata_slides_empty_by_default(tmp_path):
    write_metadata(tmp_path, "Travel", total=2, downloaded=2, videos=1, images=1)
    data = json.loads((tmp_path / "metadata.json").read_text())
    assert data["slides"] == []


def test_write_metadata_slides_written(tmp_path):
    slides = [
        {"index": 1, "filename": "Travel_01", "type": "video", "date_utc": "2025-01-01T00:00:00+00:00", "mediaid": "111"},
        {"index": 2, "filename": "Travel_02", "type": "image", "date_utc": "2025-01-02T00:00:00+00:00", "mediaid": "222"},
    ]
    write_metadata(tmp_path, "Travel", total=2, downloaded=2, videos=1, images=1, slides=slides)
    data = json.loads((tmp_path / "metadata.json").read_text())
    assert len(data["slides"]) == 2
    assert data["slides"][0]["filename"] == "Travel_01"
    assert data["slides"][1]["type"] == "image"
    assert data["slides"][1]["mediaid"] == "222"


def test_write_metadata_overwrites_on_rerun(tmp_path):
    write_metadata(tmp_path, "Travel", total=5, downloaded=3, videos=1, images=2)
    write_metadata(tmp_path, "Travel", total=5, downloaded=5, videos=2, images=3)
    data = json.loads((tmp_path / "metadata.json").read_text())
    assert data["downloaded"] == 5
    assert data["status"] == "complete"

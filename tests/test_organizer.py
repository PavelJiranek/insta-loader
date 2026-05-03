import pytest
from pathlib import Path
from insta_loader.organizer import sanitize_name, slide_filename, slide_exists, highlight_dir


def test_sanitize_name_replaces_spaces():
    assert sanitize_name("Summer 2024") == "Summer_2024"


def test_sanitize_name_replaces_slashes():
    assert sanitize_name("Travel/Europe") == "Travel-Europe"


def test_sanitize_name_plain_name_unchanged():
    assert sanitize_name("Travel") == "Travel"


def test_sanitize_name_both_space_and_slash():
    assert sanitize_name("Travel/Europe 2024") == "Travel-Europe_2024"


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

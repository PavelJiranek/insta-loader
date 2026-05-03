import pytest
import instaloader as _il
from unittest.mock import MagicMock, patch
from pathlib import Path

from insta_loader.cli import Config
from insta_loader.downloader import run


def make_config(username="natgeo", output_dir=None, highlight=None):
    return Config(username=username, output_dir=output_dir, highlight=highlight)


def make_mock_highlight(title, num_items=2):
    h = MagicMock()
    h.title = title
    h.unique_id = "hl_123"
    h.get_items.return_value = [MagicMock() for _ in range(num_items)]
    return h


@patch("insta_loader.downloader.instaloader")
def test_private_account_exits_1(mock_il):
    mock_il.Instaloader.return_value = MagicMock()
    mock_profile = MagicMock()
    mock_profile.is_private = True
    mock_il.Profile.from_username.return_value = mock_profile

    with pytest.raises(SystemExit) as exc:
        run(make_config())
    assert exc.value.code == 1


@patch("insta_loader.downloader.instaloader")
def test_account_not_found_exits_1(mock_il):
    mock_il.Instaloader.return_value = MagicMock()
    # Map the mock exception to the real one so the except clause catches it
    mock_il.exceptions.ProfileNotExistsException = _il.exceptions.ProfileNotExistsException
    mock_il.Profile.from_username.side_effect = _il.exceptions.ProfileNotExistsException("natgeo")

    with pytest.raises(SystemExit) as exc:
        run(make_config())
    assert exc.value.code == 1


@patch("insta_loader.downloader.instaloader")
def test_highlight_not_found_exits_1(mock_il):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_loader.get_highlights.return_value = [make_mock_highlight("Summer")]

    with pytest.raises(SystemExit) as exc:
        run(make_config(highlight="Travel"))
    assert exc.value.code == 1


@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_skips_already_downloaded_slides(mock_organizer, mock_il, mock_prog, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_loader.get_highlights.return_value = [make_mock_highlight("Travel", num_items=1)]

    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = True  # slide already on disk

    run(make_config(highlight="Travel", output_dir=str(tmp_path)))

    mock_loader.download_storyitem.assert_not_called()


@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_downloads_missing_slides(mock_organizer, mock_il, mock_prog, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_loader.get_highlights.return_value = [make_mock_highlight("Travel", num_items=1)]

    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = False  # not yet downloaded

    run(make_config(highlight="Travel", output_dir=str(tmp_path)))

    mock_loader.download_storyitem.assert_called_once()


@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_highlight_match_is_case_insensitive(mock_organizer, mock_il, mock_prog, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    # Stored as "Travel", queried as "travel"
    mock_loader.get_highlights.return_value = [make_mock_highlight("Travel", num_items=0)]
    mock_organizer.highlight_dir.return_value = tmp_path

    # Should NOT exit — "travel" matches "Travel"
    run(make_config(highlight="travel", output_dir=str(tmp_path)))

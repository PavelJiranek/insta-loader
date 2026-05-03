import pytest
import instaloader as _il
from unittest.mock import MagicMock, patch

from insta_loader.cli import Config
from insta_loader.downloader import run


def make_config(username="natgeo", output_dir=None, highlight=None, login_user=None):
    return Config(username=username, output_dir=output_dir, highlight=highlight, login_user=login_user)


def make_mock_item(is_video=False):
    item = MagicMock()
    item.is_video = is_video
    return item


def make_mock_highlight(title, num_items=2):
    h = MagicMock()
    h.title = title
    h.unique_id = "hl_123"
    h.get_items.return_value = [make_mock_item() for _ in range(num_items)]
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


@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_download_error_exits_1(mock_organizer, mock_il, mock_prog, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_loader.get_highlights.return_value = [make_mock_highlight("Travel", num_items=1)]

    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = False
    mock_loader.download_storyitem.side_effect = Exception("network error")

    with pytest.raises(SystemExit) as exc:
        run(make_config(highlight="Travel", output_dir=str(tmp_path)))
    assert exc.value.code == 1


@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_downloads_all_highlights_when_none_specified(mock_organizer, mock_il, mock_prog, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_loader.get_highlights.return_value = [
        make_mock_highlight("Travel", num_items=0),
        make_mock_highlight("Summer", num_items=0),
    ]
    mock_organizer.highlight_dir.return_value = tmp_path

    # highlight=None — should process both without exiting
    run(make_config(output_dir=str(tmp_path)))


@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_write_metadata_called_after_highlight(mock_organizer, mock_il, mock_prog, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    items = [make_mock_item(is_video=True), make_mock_item(is_video=False)]
    highlight = MagicMock()
    highlight.title = "Travel"
    highlight.unique_id = "hl_123"
    highlight.get_items.return_value = items
    mock_loader.get_highlights.return_value = [highlight]
    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = False

    run(make_config(highlight="Travel", output_dir=str(tmp_path)))

    mock_organizer.write_metadata.assert_called_once_with(
        tmp_path, "Travel", 2, 2, 1, 1
    )


@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_write_metadata_called_on_error(mock_organizer, mock_il, mock_prog, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_loader.get_highlights.return_value = [make_mock_highlight("Travel", num_items=1)]
    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = False
    mock_loader.download_storyitem.side_effect = Exception("network error")

    with pytest.raises(SystemExit):
        run(make_config(highlight="Travel", output_dir=str(tmp_path)))

    mock_organizer.write_metadata.assert_called_once()


@patch("insta_loader.downloader.instaloader")
def test_loads_saved_session_when_login_user_given(mock_il):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = True
    mock_il.Profile.from_username.return_value = mock_profile

    with pytest.raises(SystemExit):
        run(make_config(login_user="myuser"))

    mock_loader.load_session_from_file.assert_called_once()
    args = mock_loader.load_session_from_file.call_args[0]
    assert args[0] == "myuser"
    assert "session-myuser" in args[1]


@patch("insta_loader.downloader.instaloader")
def test_interactive_login_when_no_session_file(mock_il):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_loader.load_session_from_file.side_effect = FileNotFoundError
    mock_profile = MagicMock()
    mock_profile.is_private = True
    mock_il.Profile.from_username.return_value = mock_profile

    with pytest.raises(SystemExit):
        run(make_config(login_user="myuser"))

    mock_loader.interactive_login.assert_called_once_with("myuser")


@patch("insta_loader.downloader.instaloader")
def test_bad_credentials_exits_1(mock_il):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_loader.load_session_from_file.side_effect = FileNotFoundError
    mock_il.exceptions.BadCredentialsException = _il.exceptions.BadCredentialsException
    mock_loader.interactive_login.side_effect = _il.exceptions.BadCredentialsException

    with pytest.raises(SystemExit) as exc:
        run(make_config(login_user="myuser"))
    assert exc.value.code == 1


@patch("insta_loader.downloader.instaloader")
def test_no_login_attempt_when_login_user_not_set(mock_il):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = True
    mock_il.Profile.from_username.return_value = mock_profile

    with pytest.raises(SystemExit):
        run(make_config())

    mock_loader.load_session_from_file.assert_not_called()
    mock_loader.interactive_login.assert_not_called()

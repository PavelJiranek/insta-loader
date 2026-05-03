import json
import pytest
import instaloader as _il
from unittest.mock import MagicMock, patch

from insta_loader.cli import Config
from insta_loader.downloader import run, _resolve_highlight, _get_all_highlights


def make_highlight(title):
    h = MagicMock()
    h.title = title
    return h


def make_config(username="natgeo", output_dir=None, highlight=None, login_user=None, update=False):
    return Config(username=username, output_dir=output_dir, highlight=highlight, login_user=login_user, update=update)


def make_mock_item(is_video=False):
    from datetime import datetime, timezone
    item = MagicMock()
    item.is_video = is_video
    item.date_utc = datetime(2025, 1, 1, tzinfo=timezone.utc)
    item.mediaid = 123456
    return item


def make_mock_highlight(title, num_items=2):
    h = MagicMock()
    h.title = title
    h.unique_id = "hl_123"
    h.get_items.return_value = [make_mock_item() for _ in range(num_items)]
    return h


@patch("insta_loader.downloader.instaloader")
def test_private_account_exits_1(mock_il):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = True
    mock_il.Profile.from_username.return_value = mock_profile

    with pytest.raises(SystemExit) as exc:
        run(make_config())
    assert exc.value.code == 1


@patch("insta_loader.downloader.instaloader")
def test_account_not_found_exits_1(mock_il):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    # Map the mock exception to the real one so the except clause catches it
    mock_il.exceptions.ProfileNotExistsException = _il.exceptions.ProfileNotExistsException
    mock_il.Profile.from_username.side_effect = _il.exceptions.ProfileNotExistsException("natgeo")

    with pytest.raises(SystemExit) as exc:
        run(make_config())
    assert exc.value.code == 1


@patch("insta_loader.downloader._get_all_highlights")
@patch("insta_loader.downloader.instaloader")
def test_highlight_not_found_exits_1(mock_il, mock_get_all):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_get_all.return_value = [make_mock_highlight("Summer")]

    with pytest.raises(SystemExit) as exc:
        run(make_config(highlight="Travel"))
    assert exc.value.code == 1


@patch("insta_loader.downloader._get_all_highlights")
@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_skips_already_downloaded_slides(mock_organizer, mock_il, mock_prog, mock_get_all, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_get_all.return_value = [make_mock_highlight("Travel", num_items=1)]

    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = True  # slide already on disk

    run(make_config(highlight="Travel", output_dir=str(tmp_path)))

    mock_loader.download_storyitem.assert_not_called()


@patch("insta_loader.downloader._get_all_highlights")
@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_downloads_missing_slides(mock_organizer, mock_il, mock_prog, mock_get_all, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_get_all.return_value = [make_mock_highlight("Travel", num_items=1)]

    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = False  # not yet downloaded

    run(make_config(highlight="Travel", output_dir=str(tmp_path)))

    mock_loader.download_storyitem.assert_called_once()


@patch("insta_loader.downloader._get_all_highlights")
@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_highlight_match_is_case_insensitive(mock_organizer, mock_il, mock_prog, mock_get_all, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    # Stored as "Travel", queried as "travel"
    mock_get_all.return_value = [make_mock_highlight("Travel", num_items=0)]
    mock_organizer.highlight_dir.return_value = tmp_path

    # Should NOT exit — "travel" matches "Travel"
    run(make_config(highlight="travel", output_dir=str(tmp_path)))


@patch("insta_loader.downloader._get_all_highlights")
@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_download_error_skips_slide_and_continues(mock_organizer, mock_il, mock_prog, mock_get_all, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_get_all.return_value = [make_mock_highlight("Travel", num_items=2)]

    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = False
    # First slide fails, second succeeds
    mock_loader.download_storyitem.side_effect = [Exception("network error"), None]

    run(make_config(highlight="Travel", output_dir=str(tmp_path)))

    assert mock_loader.download_storyitem.call_count == 2
    slides = mock_organizer.write_metadata.call_args[0][6]
    statuses = [s["status"] for s in slides]
    assert "failed" in statuses
    assert "downloaded" in statuses


@patch("insta_loader.downloader._get_all_highlights")
@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_downloads_all_highlights_when_none_specified(mock_organizer, mock_il, mock_prog, mock_get_all, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_get_all.return_value = [
        make_mock_highlight("Travel", num_items=0),
        make_mock_highlight("Summer", num_items=0),
    ]
    mock_organizer.highlight_dir.return_value = tmp_path

    # highlight=None — should process both without exiting
    run(make_config(output_dir=str(tmp_path)))


@patch("insta_loader.downloader._get_all_highlights")
@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_write_metadata_called_after_highlight(mock_organizer, mock_il, mock_prog, mock_get_all, tmp_path):
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
    mock_get_all.return_value = [highlight]
    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = False

    run(make_config(highlight="Travel", output_dir=str(tmp_path)))

    args = mock_organizer.write_metadata.call_args
    assert args[0][:6] == (tmp_path, "Travel", 2, 2, 1, 1)
    slides = args[0][6]
    assert len(slides) == 2
    types = {s["type"] for s in slides}
    assert types == {"video", "image"}
    assert all("date_utc" in s and "mediaid" in s for s in slides)


@patch("insta_loader.downloader._get_all_highlights")
@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_write_metadata_records_failed_slide(mock_organizer, mock_il, mock_prog, mock_get_all, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_get_all.return_value = [make_mock_highlight("Travel", num_items=1)]
    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = False
    mock_loader.download_storyitem.side_effect = Exception("network error")

    run(make_config(highlight="Travel", output_dir=str(tmp_path)))

    slides = mock_organizer.write_metadata.call_args[0][6]
    assert slides[0]["status"] == "failed"


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


# --- update mode ---

@patch("insta_loader.downloader.organizer")
@patch("insta_loader.downloader._get_all_highlights")
@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
def test_update_skips_complete_highlight(mock_il, mock_prog, mock_get_all, mock_organizer, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_get_all.return_value = [make_mock_highlight("Travel", num_items=2)]
    mock_organizer.sanitize_name.return_value = "Travel"

    folder = tmp_path / "Travel"
    folder.mkdir()
    (folder / "metadata.json").write_text(json.dumps({"status": "complete"}))

    run(make_config(highlight="Travel", output_dir=str(tmp_path), update=True))

    mock_loader.download_storyitem.assert_not_called()
    mock_prog.log_video_skip.assert_called_once()


@patch("insta_loader.downloader.organizer")
@patch("insta_loader.downloader._get_all_highlights")
@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
def test_update_processes_partial_highlight(mock_il, mock_prog, mock_get_all, mock_organizer, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_get_all.return_value = [make_mock_highlight("Travel", num_items=1)]
    mock_organizer.sanitize_name.return_value = "Travel"
    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = False

    folder = tmp_path / "Travel"
    folder.mkdir()
    (folder / "metadata.json").write_text(json.dumps({"status": "partial"}))

    run(make_config(highlight="Travel", output_dir=str(tmp_path), update=True))

    mock_loader.download_storyitem.assert_called_once()


@patch("insta_loader.downloader.organizer")
@patch("insta_loader.downloader._get_all_highlights")
@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
def test_update_processes_highlight_with_no_metadata(mock_il, mock_prog, mock_get_all, mock_organizer, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_get_all.return_value = [make_mock_highlight("Travel", num_items=1)]
    mock_organizer.sanitize_name.return_value = "Travel"
    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = False
    # No metadata.json at all — new highlight, should be downloaded

    run(make_config(highlight="Travel", output_dir=str(tmp_path), update=True))

    mock_loader.download_storyitem.assert_called_once()


# --- _resolve_highlight ---

def test_resolve_exact_match():
    highlights = [make_highlight("Travel"), make_highlight("Summer")]
    result = _resolve_highlight("Travel", highlights)
    assert result[0].title == "Travel"


def test_resolve_exact_match_case_insensitive():
    highlights = [make_highlight("Travel"), make_highlight("Summer")]
    result = _resolve_highlight("travel", highlights)
    assert result[0].title == "Travel"


def test_resolve_single_partial_match(capsys):
    highlights = [make_highlight("Czech Republic"), make_highlight("Summer")]
    result = _resolve_highlight("czech", highlights)
    assert result[0].title == "Czech Republic"
    assert "Matched" in capsys.readouterr().out


def test_resolve_no_match_exits_1():
    highlights = [make_highlight("Travel"), make_highlight("Summer")]
    with pytest.raises(SystemExit) as exc:
        _resolve_highlight("xyz", highlights)
    assert exc.value.code == 1


def test_resolve_multiple_partial_matches_prompts(monkeypatch):
    highlights = [make_highlight("Czech Republic"), make_highlight("Czech Brno"), make_highlight("Summer")]
    monkeypatch.setattr("builtins.input", lambda _: "2")
    result = _resolve_highlight("czech", highlights)
    assert result[0].title == "Czech Brno"


def test_resolve_invalid_selection_exits_1(monkeypatch):
    highlights = [make_highlight("Czech Republic"), make_highlight("Czech Brno")]
    monkeypatch.setattr("builtins.input", lambda _: "99")
    with pytest.raises(SystemExit) as exc:
        _resolve_highlight("czech", highlights)
    assert exc.value.code == 1


def test_resolve_non_numeric_selection_exits_1(monkeypatch):
    highlights = [make_highlight("Czech Republic"), make_highlight("Czech Brno")]
    monkeypatch.setattr("builtins.input", lambda _: "abc")
    with pytest.raises(SystemExit) as exc:
        _resolve_highlight("czech", highlights)
    assert exc.value.code == 1


# --- _get_all_highlights ---

def make_tray_item(highlight_id, title):
    return {
        "id": f"highlight:{highlight_id}",
        "title": title,
        "cover_media": {},
        "cover_media_cropped_thumbnail": {},
    }


def test_get_all_highlights_single_page():
    mock_L = MagicMock()
    mock_profile = MagicMock()
    mock_profile.userid = 12345
    mock_L.context.get_iphone_json.return_value = {
        "tray": [make_tray_item("100", "Travel"), make_tray_item("101", "Summer")],
        "cursor": None,
    }

    with patch("insta_loader.downloader.instaloader.Highlight") as mock_hl:
        mock_hl.side_effect = lambda ctx, node, profile: node
        results = _get_all_highlights(mock_L, mock_profile)

    assert len(results) == 2
    mock_L.context.get_iphone_json.assert_called_once_with(
        path="api/v1/highlights/12345/highlights_tray/",
        params={},
    )


def test_get_all_highlights_paginates_with_cursor():
    mock_L = MagicMock()
    mock_profile = MagicMock()
    mock_profile.userid = 99

    pages = [
        {"tray": [make_tray_item("1", "A")] * 100, "cursor": "cursor_abc"},
        {"tray": [make_tray_item("2", "B")] * 34, "cursor": None},
    ]
    mock_L.context.get_iphone_json.side_effect = pages

    with patch("insta_loader.downloader.instaloader.Highlight") as mock_hl:
        mock_hl.side_effect = lambda ctx, node, profile: node
        results = _get_all_highlights(mock_L, mock_profile)

    assert len(results) == 134
    assert mock_L.context.get_iphone_json.call_count == 2
    second_call_params = mock_L.context.get_iphone_json.call_args_list[1][1]["params"]
    assert second_call_params == {"cursor": "cursor_abc"}


def test_get_all_highlights_strips_highlight_prefix():
    mock_L = MagicMock()
    mock_profile = MagicMock()
    mock_profile.userid = 1

    captured_nodes = []

    def capture_highlight(ctx, node, profile):
        captured_nodes.append(node)
        return node

    mock_L.context.get_iphone_json.return_value = {
        "tray": [{"id": "highlight:999", "title": "Test", "cover_media": {}, "cover_media_cropped_thumbnail": {}}],
        "cursor": "",
    }

    with patch("insta_loader.downloader.instaloader.Highlight", side_effect=capture_highlight):
        _get_all_highlights(mock_L, mock_profile)

    assert captured_nodes[0]["id"] == "999"


def test_get_all_highlights_empty_cursor_stops_pagination():
    mock_L = MagicMock()
    mock_profile = MagicMock()
    mock_profile.userid = 1
    mock_L.context.get_iphone_json.return_value = {
        "tray": [],
        "cursor": "",
    }

    with patch("insta_loader.downloader.instaloader.Highlight"):
        results = _get_all_highlights(mock_L, mock_profile)

    assert results == []
    assert mock_L.context.get_iphone_json.call_count == 1

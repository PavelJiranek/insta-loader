import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from insta_loader.youtube_uploader import (
    _get_credentials,
    _resolve_secrets_path,
    _get_or_create_playlist,
    _upload_video,
    _add_to_playlist,
    _mark_uploaded,
)


def test_resolve_secrets_path_uses_arg():
    assert _resolve_secrets_path("/tmp/secrets.json") == Path("/tmp/secrets.json")


def test_resolve_secrets_path_uses_env(monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRETS", "/env/secrets.json")
    assert _resolve_secrets_path(None) == Path("/env/secrets.json")


def test_resolve_secrets_path_default(monkeypatch):
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRETS", raising=False)
    result = _resolve_secrets_path(None)
    assert result == Path.home() / ".config" / "instaloader" / "youtube_client_secrets.json"


def test_get_credentials_loads_existing_token(tmp_path):
    token_path = tmp_path / "token.json"
    fake_creds = MagicMock()
    fake_creds.valid = True

    secrets_path = tmp_path / "client_secrets.json"
    secrets_path.touch()
    with patch("insta_loader.youtube_uploader.TOKEN_PATH", token_path), \
         patch("insta_loader.youtube_uploader.Credentials") as mock_creds_cls:
        token_path.write_text('{"token": "fake"}')
        mock_creds_cls.from_authorized_user_file.return_value = fake_creds

        result = _get_credentials(secrets_path)

        mock_creds_cls.from_authorized_user_file.assert_called_once()
        assert result is fake_creds


def test_get_credentials_triggers_browser_flow_when_no_token(tmp_path):
    token_path = tmp_path / "token.json"
    fake_creds = MagicMock()
    fake_creds.to_json.return_value = '{"token": "new"}'

    secrets_path = tmp_path / "client_secrets.json"
    secrets_path.touch()
    with patch("insta_loader.youtube_uploader.TOKEN_PATH", token_path), \
         patch("insta_loader.youtube_uploader.Credentials") as mock_creds_cls, \
         patch("insta_loader.youtube_uploader.InstalledAppFlow") as mock_flow_cls:
        mock_creds_cls.from_authorized_user_file.side_effect = FileNotFoundError
        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = fake_creds
        mock_flow_cls.from_client_secrets_file.return_value = mock_flow

        result = _get_credentials(secrets_path)

        mock_flow.run_local_server.assert_called_once_with(port=0)
        assert token_path.exists()
        assert result is fake_creds


def test_get_or_create_playlist_returns_existing_id():
    youtube = MagicMock()
    youtube.playlists().list().execute.return_value = {
        "items": [{"id": "PL123", "snippet": {"title": "Story Highlights"}}],
        "nextPageToken": None,
    }
    youtube.playlists().list_next.return_value = None

    result = _get_or_create_playlist(youtube, "Story Highlights")
    assert result == "PL123"


def test_get_or_create_playlist_case_insensitive():
    youtube = MagicMock()
    youtube.playlists().list().execute.return_value = {
        "items": [{"id": "PL123", "snippet": {"title": "story highlights"}}],
        "nextPageToken": None,
    }
    youtube.playlists().list_next.return_value = None

    result = _get_or_create_playlist(youtube, "Story Highlights")
    assert result == "PL123"


def test_get_or_create_playlist_creates_new_when_not_found():
    youtube = MagicMock()
    youtube.playlists().list().execute.return_value = {"items": [], "nextPageToken": None}
    youtube.playlists().list_next.return_value = None
    youtube.playlists().insert().execute.return_value = {"id": "PL_NEW"}

    result = _get_or_create_playlist(youtube, "Story Highlights")
    assert result == "PL_NEW"
    youtube.playlists().insert.assert_called()


def test_upload_video_returns_video_id():
    youtube = MagicMock()
    mock_request = MagicMock()
    mock_request.next_chunk.side_effect = [(None, None), (None, {"id": "vid_abc"})]
    youtube.videos().insert.return_value = mock_request

    meta = {
        "youtube": {
            "title": "Test Video",
            "description": "desc",
            "tags": ["a", "b"],
            "category_id": "19",
            "privacy_status": "private",
        }
    }

    with patch("insta_loader.youtube_uploader.MediaFileUpload"):
        result = _upload_video(youtube, meta, Path("/fake/video.mp4"))

    assert result == "vid_abc"


def test_add_to_playlist_calls_insert():
    youtube = MagicMock()
    _add_to_playlist(youtube, "PL123", "vid_abc")
    youtube.playlistItems().insert.assert_called_once()
    call_kwargs = youtube.playlistItems().insert.call_args[1]
    body = call_kwargs["body"]
    assert body["snippet"]["playlistId"] == "PL123"
    assert body["snippet"]["resourceId"]["videoId"] == "vid_abc"


def test_mark_uploaded_updates_json(tmp_path):
    meta_path = tmp_path / "Test.json"
    meta_path.write_text(json.dumps({
        "highlight_folder": "Test",
        "uploaded": False,
        "youtube_id": None,
        "youtube_url": None,
    }))

    _mark_uploaded(meta_path, "vid_xyz")

    updated = json.loads(meta_path.read_text())
    assert updated["uploaded"] is True
    assert updated["youtube_id"] == "vid_xyz"
    assert updated["youtube_url"] == "https://www.youtube.com/watch?v=vid_xyz"

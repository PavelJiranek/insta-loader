import json
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
    _check_missing_metadata,
    _delete_outdated,
    run as run_upload,
)
from insta_loader.cli import YoutubeConfig


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
            "privacy_status": "unlisted",
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


def _make_meta_file(youtube_dir, folder_name, uploaded=False,
                    youtube_id=None, video_path=None):
    youtube_dir.mkdir(parents=True, exist_ok=True)
    if video_path is None:
        video_path = f"output/test/videos/{folder_name}.mp4"
    data = {
        "highlight_folder": folder_name,
        "video_path": video_path,
        "youtube": {
            "title": folder_name,
            "description": "desc",
            "tags": ["tag"],
            "category_id": "19",
            "privacy_status": "unlisted",
        },
        "uploaded": uploaded,
        "youtube_id": youtube_id,
    }
    (youtube_dir / f"{folder_name}.json").write_text(json.dumps(data))


def test_run_skips_already_uploaded(tmp_path, capsys):
    youtube_dir = tmp_path / "youtube"
    _make_meta_file(youtube_dir, "Travel", uploaded=True, youtube_id="existing")
    secrets = tmp_path / "secrets.json"
    secrets.touch()

    with patch("insta_loader.youtube_uploader._get_credentials"), \
         patch("insta_loader.youtube_uploader.build"):
        run_upload(YoutubeConfig(
            username="test",
            output_dir=str(tmp_path),
            client_secrets=str(secrets),
        ))

    out = capsys.readouterr().out
    assert "already uploaded" in out.lower()


def test_run_skips_missing_video(tmp_path, capsys):
    youtube_dir = tmp_path / "youtube"
    # Use a path inside the output dir that simply doesn't exist on disk
    missing_video = str(tmp_path / "videos" / "Travel.mp4")
    _make_meta_file(youtube_dir, "Travel", video_path=missing_video)
    secrets = tmp_path / "secrets.json"
    secrets.touch()

    with patch("insta_loader.youtube_uploader._get_credentials"), \
         patch("insta_loader.youtube_uploader.build"):
        run_upload(YoutubeConfig(
            username="test",
            output_dir=str(tmp_path),
            client_secrets=str(secrets),
        ))

    out = capsys.readouterr().out
    assert "not found" in out.lower()


def test_run_marks_uploaded_on_success(tmp_path):
    youtube_dir = tmp_path / "youtube"
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "Travel.mp4").touch()
    _make_meta_file(youtube_dir, "Travel",
                    video_path=str(videos_dir / "Travel.mp4"))
    secrets = tmp_path / "secrets.json"
    secrets.touch()

    with patch("insta_loader.youtube_uploader._get_credentials"), \
         patch("insta_loader.youtube_uploader.build"), \
         patch("insta_loader.youtube_uploader._get_or_create_playlist", return_value="PL1"), \
         patch("insta_loader.youtube_uploader._upload_video", return_value="vid_new"), \
         patch("insta_loader.youtube_uploader._add_to_playlist"):
        run_upload(YoutubeConfig(
            username="test",
            output_dir=str(tmp_path),
            client_secrets=str(secrets),
        ))

    updated = json.loads((youtube_dir / "Travel.json").read_text())
    assert updated["uploaded"] is True
    assert updated["youtube_id"] == "vid_new"


def test_run_handles_api_error_and_continues(tmp_path, capsys):
    youtube_dir = tmp_path / "youtube"
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "Travel.mp4").touch()
    (videos_dir / "Summer.mp4").touch()
    _make_meta_file(youtube_dir, "Travel",
                    video_path=str(videos_dir / "Travel.mp4"))
    _make_meta_file(youtube_dir, "Summer",
                    video_path=str(videos_dir / "Summer.mp4"))
    secrets = tmp_path / "secrets.json"
    secrets.touch()

    with patch("insta_loader.youtube_uploader._get_credentials"), \
         patch("insta_loader.youtube_uploader.build"), \
         patch("insta_loader.youtube_uploader._get_or_create_playlist", return_value="PL1"), \
         patch("insta_loader.youtube_uploader._upload_video",
               side_effect=[Exception("quota exceeded"), "vid_summer"]), \
         patch("insta_loader.youtube_uploader._add_to_playlist"):
        run_upload(YoutubeConfig(
            username="test",
            output_dir=str(tmp_path),
            client_secrets=str(secrets),
        ))

    out = capsys.readouterr().out
    assert "quota exceeded" in out.lower() or "failed" in out.lower()
    summer = json.loads((youtube_dir / "Summer.json").read_text())
    assert summer["uploaded"] is True


def test_run_filters_by_highlight_name(tmp_path):
    youtube_dir = tmp_path / "youtube"
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "Travel.mp4").touch()
    (videos_dir / "Summer.mp4").touch()
    _make_meta_file(youtube_dir, "Travel",
                    video_path=str(videos_dir / "Travel.mp4"))
    _make_meta_file(youtube_dir, "Summer",
                    video_path=str(videos_dir / "Summer.mp4"))
    secrets = tmp_path / "secrets.json"
    secrets.touch()

    with patch("insta_loader.youtube_uploader._get_credentials"), \
         patch("insta_loader.youtube_uploader.build"), \
         patch("insta_loader.youtube_uploader._get_or_create_playlist", return_value="PL1"), \
         patch("insta_loader.youtube_uploader._upload_video", return_value="vid_t"), \
         patch("insta_loader.youtube_uploader._add_to_playlist"):
        run_upload(YoutubeConfig(
            username="test",
            output_dir=str(tmp_path),
            client_secrets=str(secrets),
            highlight="travel",
        ))

    travel = json.loads((youtube_dir / "Travel.json").read_text())
    summer = json.loads((youtube_dir / "Summer.json").read_text())
    assert travel["uploaded"] is True
    assert summer["uploaded"] is False


def test_run_exits_when_no_metadata(tmp_path):
    secrets = tmp_path / "secrets.json"
    secrets.touch()

    with pytest.raises(SystemExit) as exc:
        run_upload(YoutubeConfig(
            username="test",
            output_dir=str(tmp_path),
            client_secrets=str(secrets),
        ))
    assert exc.value.code == 1


def test_check_missing_metadata_returns_videos_without_json(tmp_path):
    youtube_dir = tmp_path / "youtube"
    youtube_dir.mkdir()
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "Travel.mp4").touch()
    (videos_dir / "Summer.mp4").touch()
    (youtube_dir / "Travel.json").write_text("{}")

    missing = _check_missing_metadata(tmp_path, youtube_dir)
    assert missing == ["Summer"]


def test_check_missing_metadata_empty_when_all_present(tmp_path):
    youtube_dir = tmp_path / "youtube"
    youtube_dir.mkdir()
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "Travel.mp4").touch()
    (youtube_dir / "Travel.json").write_text("{}")

    assert _check_missing_metadata(tmp_path, youtube_dir) == []


def test_check_missing_metadata_no_videos_dir(tmp_path):
    youtube_dir = tmp_path / "youtube"
    assert _check_missing_metadata(tmp_path, youtube_dir) == []


def test_delete_outdated_skips_when_none(tmp_path, capsys):
    youtube = MagicMock()
    youtube_dir = tmp_path / "youtube"
    youtube_dir.mkdir()
    meta_path = youtube_dir / "Travel.json"
    meta_path.write_text(json.dumps({
        "highlight_folder": "Travel",
        "uploaded": True,
        "outdated": False,
        "youtube_id": "vid1",
        "youtube": {"title": "Travel"},
    }))

    _delete_outdated(youtube, [meta_path])
    youtube.videos().delete.assert_not_called()
    assert "no outdated" in capsys.readouterr().out.lower()


def test_delete_outdated_resets_flags_on_confirmation(tmp_path, monkeypatch):
    youtube = MagicMock()
    youtube.videos().delete().execute.return_value = {}
    youtube_dir = tmp_path / "youtube"
    youtube_dir.mkdir()
    meta_path = youtube_dir / "Travel.json"
    meta_path.write_text(json.dumps({
        "highlight_folder": "Travel",
        "uploaded": True,
        "outdated": True,
        "youtube_id": "vid1",
        "youtube_url": "https://www.youtube.com/watch?v=vid1",
        "youtube": {"title": "Travel"},
    }))

    monkeypatch.setattr("builtins.input", lambda _: "y")
    _delete_outdated(youtube, [meta_path])

    updated = json.loads(meta_path.read_text())
    assert updated["uploaded"] is False
    assert updated["youtube_id"] is None
    assert updated["outdated"] is False


def test_run_update_resets_outdated_then_uploads(tmp_path):
    youtube_dir = tmp_path / "youtube"
    youtube_dir.mkdir()
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "Travel.mp4").touch()
    meta_path = youtube_dir / "Travel.json"
    meta_path.write_text(json.dumps({
        "highlight_folder": "Travel",
        "video_path": str(videos_dir / "Travel.mp4"),
        "youtube": {
            "title": "Travel",
            "description": "d",
            "tags": [],
            "category_id": "19",
            "privacy_status": "unlisted",
        },
        "uploaded": True,
        "outdated": True,
        "youtube_id": "old_id",
        "youtube_url": "https://www.youtube.com/watch?v=old_id",
    }))
    secrets = tmp_path / "secrets.json"
    secrets.touch()

    with patch("insta_loader.youtube_uploader._get_credentials"), \
         patch("insta_loader.youtube_uploader.build") as mock_build, \
         patch("builtins.input", return_value="y"), \
         patch("insta_loader.youtube_uploader._get_or_create_playlist", return_value="PL1"), \
         patch("insta_loader.youtube_uploader._upload_video", return_value="new_id"), \
         patch("insta_loader.youtube_uploader._add_to_playlist"):
        mock_yt = MagicMock()
        mock_yt.videos().delete().execute.return_value = {}
        mock_build.return_value = mock_yt
        run_upload(YoutubeConfig(
            username="test",
            output_dir=str(tmp_path),
            client_secrets=str(secrets),
            update=True,
        ))

    updated = json.loads(meta_path.read_text())
    assert updated["uploaded"] is True
    assert updated["youtube_id"] == "new_id"


def test_run_landscape_reads_from_youtube_landscape_dir(tmp_path, capsys):
    youtube_dir = tmp_path / "youtube_landscape"
    youtube_dir.mkdir()
    video_path = str(tmp_path / "videos_landscape" / "Travel.mp4")
    (tmp_path / "videos_landscape").mkdir()
    Path(video_path).touch()
    _make_meta_file(youtube_dir, "Travel", video_path=video_path)
    secrets = tmp_path / "secrets.json"
    secrets.touch()

    mock_playlist = MagicMock(return_value="pl1")
    with patch("insta_loader.youtube_uploader._get_credentials"), \
         patch("insta_loader.youtube_uploader.build"), \
         patch("insta_loader.youtube_uploader._get_or_create_playlist", mock_playlist), \
         patch("insta_loader.youtube_uploader._upload_video", return_value="vid1"), \
         patch("insta_loader.youtube_uploader._add_to_playlist"), \
         patch("insta_loader.youtube_uploader._mark_uploaded"):
        run_upload(YoutubeConfig(
            username="testuser",
            output_dir=str(tmp_path),
            client_secrets=str(secrets),
            landscape=True,
        ))

    out = capsys.readouterr().out
    assert "no metadata found" not in out.lower()
    playlist_name_used = mock_playlist.call_args[0][1]
    assert "16:9" in playlist_name_used


def test_run_landscape_exits_when_no_landscape_dir(tmp_path):
    youtube_dir = tmp_path / "youtube"
    youtube_dir.mkdir()
    _make_meta_file(youtube_dir, "Travel")
    secrets = tmp_path / "secrets.json"
    secrets.touch()

    with patch("insta_loader.youtube_uploader._get_credentials"), \
         patch("insta_loader.youtube_uploader.build"), \
         pytest.raises(SystemExit):
        run_upload(YoutubeConfig(
            username="testuser",
            output_dir=str(tmp_path),
            client_secrets=str(secrets),
            landscape=True,
        ))

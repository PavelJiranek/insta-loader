import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from insta_loader.youtube_uploader import _get_credentials, _resolve_secrets_path


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

    with patch("insta_loader.youtube_uploader.TOKEN_PATH", token_path), \
         patch("insta_loader.youtube_uploader.Credentials") as mock_creds_cls:
        token_path.write_text('{"token": "fake"}')
        mock_creds_cls.from_authorized_user_file.return_value = fake_creds

        result = _get_credentials(tmp_path / "client_secrets.json")

        mock_creds_cls.from_authorized_user_file.assert_called_once()
        assert result is fake_creds


def test_get_credentials_triggers_browser_flow_when_no_token(tmp_path):
    token_path = tmp_path / "token.json"
    fake_creds = MagicMock()
    fake_creds.to_json.return_value = '{"token": "new"}'

    with patch("insta_loader.youtube_uploader.TOKEN_PATH", token_path), \
         patch("insta_loader.youtube_uploader.Credentials") as mock_creds_cls, \
         patch("insta_loader.youtube_uploader.InstalledAppFlow") as mock_flow_cls:
        mock_creds_cls.from_authorized_user_file.side_effect = FileNotFoundError
        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = fake_creds
        mock_flow_cls.from_client_secrets_file.return_value = mock_flow

        result = _get_credentials(tmp_path / "client_secrets.json")

        mock_flow.run_local_server.assert_called_once_with(port=0)
        assert token_path.exists()
        assert result is fake_creds

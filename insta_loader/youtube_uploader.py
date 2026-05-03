import json
import os
import sys
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from rich import print as rprint

from insta_loader.cli import YoutubeConfig

SCOPES = ["https://www.googleapis.com/auth/youtube"]
TOKEN_PATH = Path.home() / ".config" / "instaloader" / "youtube_token.json"


def _resolve_secrets_path(client_secrets: Optional[str]) -> Path:
    if client_secrets:
        return Path(client_secrets)
    env = os.environ.get("YOUTUBE_CLIENT_SECRETS")
    if env:
        return Path(env)
    return Path.home() / ".config" / "instaloader" / "youtube_client_secrets.json"


def _print_setup_instructions(secrets_path: Path) -> None:
    print(f"✗  YouTube client secrets not found at {secrets_path}.")
    print("   To set up:")
    print("   1. Go to https://console.cloud.google.com/")
    print("   2. Create a project → Enable YouTube Data API v3")
    print("   3. Create OAuth 2.0 credentials (Desktop app)")
    print(f"   4. Download and save as {secrets_path}")


def _get_credentials(client_secrets_path: Path) -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())

    return creds

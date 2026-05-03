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
    if not client_secrets_path.exists():
        _print_setup_instructions(client_secrets_path)
        sys.exit(1)

    creds = None
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception:
            TOKEN_PATH.unlink(missing_ok=True)
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


def _get_or_create_playlist(youtube, name: str) -> str:
    request = youtube.playlists().list(part="snippet", mine=True, maxResults=50)
    while request is not None:
        response = request.execute()
        for item in response.get("items", []):
            if item["snippet"]["title"].lower() == name.lower():
                return item["id"]
        request = youtube.playlists().list_next(request, response)

    response = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": name, "description": ""},
            "status": {"privacyStatus": "private"},
        },
    ).execute()
    return response["id"]


def _upload_video(youtube, meta: dict, video_path: Path) -> str:
    body = {
        "snippet": {
            "title": meta["youtube"]["title"],
            "description": meta["youtube"]["description"],
            "tags": meta["youtube"]["tags"],
            "categoryId": meta["youtube"]["category_id"],
        },
        "status": {"privacyStatus": meta["youtube"]["privacy_status"]},
    }
    media = MediaFileUpload(str(video_path), chunksize=10 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]


def _add_to_playlist(youtube, playlist_id: str, video_id: str) -> None:
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        },
    ).execute()


def _mark_uploaded(meta_path: Path, youtube_id: str) -> None:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["uploaded"] = True
    meta["youtube_id"] = youtube_id
    meta["youtube_url"] = f"https://www.youtube.com/watch?v={youtube_id}"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

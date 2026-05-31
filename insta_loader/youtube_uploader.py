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
    print("   2. Create a project → APIs & Services → Enable APIs → YouTube Data API v3")
    print("   3. APIs & Services → Credentials → Create Credentials → OAuth client ID")
    print("      → 'Which API?' select YouTube Data API v3 → choose 'User data' (not Public data)")
    print("      → App name: anything → your email as support/developer contact")
    print("      → Scopes: skip (Next) → OAuth client type: Desktop app → Create")
    print("      → OAuth consent screen → Test users → Add users → add your Google account email")
    print("   4. Download the JSON and save as:")
    print(f"      {secrets_path}")


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
            try:
                creds.refresh(Request())
            except Exception:
                print("⚠  Token refresh failed — re-authenticating...")
                TOKEN_PATH.unlink(missing_ok=True)
                creds = None
        if not creds or not creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secrets_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
        TOKEN_PATH.chmod(0o600)

    return creds


def _get_or_create_playlist(youtube, name: str, privacy: str = "unlisted") -> str:
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
            "status": {"privacyStatus": privacy},
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
    recording_details = {}
    if meta.get("recording_date"):
        recording_details["recordingDate"] = meta["recording_date"] + "T00:00:00.000Z"
    if meta.get("location"):
        recording_details["location"] = meta["location"]
    if recording_details:
        body["recordingDetails"] = recording_details
    part = "snippet,status,recordingDetails" if recording_details else "snippet,status"
    media = MediaFileUpload(str(video_path), chunksize=10 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part=part, body=body, media_body=media)
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


def _check_missing_metadata(base: Path, youtube_dir: Path) -> list:
    """Return folder names that have a video but no YouTube metadata JSON."""
    videos_dir = base / "videos"
    if not videos_dir.exists():
        return []
    return sorted(
        v.stem for v in videos_dir.glob("*.mp4")
        if not (youtube_dir / f"{v.stem}.json").exists()
    )


def _delete_outdated(youtube, meta_files: list) -> None:
    """Find uploaded+outdated metadata, confirm with user, delete from YouTube, reset flags."""
    outdated = [
        (mp, json.loads(mp.read_text(encoding="utf-8")))
        for mp in meta_files
        if json.loads(mp.read_text(encoding="utf-8")).get("uploaded")
        and json.loads(mp.read_text(encoding="utf-8")).get("outdated")
    ]
    if not outdated:
        rprint("[dim]–  No outdated uploads found.[/dim]")
        return

    rprint(f"[yellow]ℹ  {len(outdated)} uploaded video(s) are outdated:[/yellow]")
    for mp, meta in outdated:
        rprint(f"   [dim]• {meta['youtube']['title']}  {meta.get('youtube_url', '')}[/dim]")

    answer = input("Delete from YouTube and re-upload? [y/N]: ").strip().lower()
    if answer != "y":
        return

    for mp, meta in outdated:
        title = meta["youtube"]["title"]
        try:
            youtube.videos().delete(id=meta["youtube_id"]).execute()
            current = json.loads(mp.read_text(encoding="utf-8"))
            current["uploaded"] = False
            current["youtube_id"] = None
            current["youtube_url"] = None
            current["outdated"] = False
            mp.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
            rprint(f"[green]✓[/green]  Deleted '{title}' from YouTube")
        except Exception as e:
            rprint(f"[red]✗  Failed to delete '{title}': {e}[/red]")


def run(config: YoutubeConfig) -> None:
    base = Path(config.output_dir) if config.output_dir else Path("output") / config.username
    youtube_dir = base / "youtube"

    # Offer to auto-generate metadata for videos that have none yet
    missing = _check_missing_metadata(base, youtube_dir)
    if missing:
        rprint(f"[yellow]ℹ  {len(missing)} video(s) have no YouTube metadata:[/yellow]")
        for name in missing:
            rprint(f"   [dim]• {name}[/dim]")
        answer = input("Run youtube-meta now? [y/N]: ").strip().lower()
        if answer == "y":
            from insta_loader.youtube_meta import run as run_meta
            run_meta(config)

    if not youtube_dir.exists():
        print(f"✗  No metadata found at {youtube_dir}. Run youtube-meta first.")
        sys.exit(1)

    all_meta_files = list(youtube_dir.glob("*.json"))
    if not all_meta_files:
        print(f"✗  No metadata files found in {youtube_dir}.")
        sys.exit(1)

    secrets_path = _resolve_secrets_path(config.client_secrets)
    creds = _get_credentials(secrets_path)
    youtube = build("youtube", "v3", credentials=creds)

    # Handle --update: delete outdated uploads first, then reload
    if config.update:
        _delete_outdated(youtube, all_meta_files)
        all_meta_files = list(youtube_dir.glob("*.json"))

    # Apply highlight filter
    meta_files = all_meta_files
    if config.highlight:
        q = config.highlight.lower()
        meta_files = [f for f in meta_files if q in f.stem.lower()]
        if not meta_files:
            print(f"✗  No highlight matching '{config.highlight}'")
            sys.exit(1)

    playlist_id: Optional[str] = None
    total = len(meta_files)
    done = 0

    for meta_path in meta_files:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        title = meta["youtube"]["title"]
        done += 1
        prefix = f"[{done}/{total}]"

        if meta.get("uploaded"):
            rprint(f"[green]✓[/green]  {prefix} {title} — already uploaded")
            continue

        video_path = Path(meta["video_path"]).resolve()
        if not str(video_path).startswith(str(base.resolve())):
            rprint(f"[red]✗  {prefix} {title} — video_path escapes output directory, skipping[/red]")
            continue
        if not video_path.exists():
            rprint(f"[yellow]✗  {prefix} {title} — video not found at {video_path}[/yellow]")
            continue

        if playlist_id is None:
            playlist_id = _get_or_create_playlist(youtube, config.playlist, config.privacy)

        rprint(f"[cyan]↑  {prefix} {title} — uploading…[/cyan]")
        try:
            video_id = _upload_video(youtube, meta, video_path)
            _add_to_playlist(youtube, playlist_id, video_id)
            _mark_uploaded(meta_path, video_id)
            rprint(f"[green]✓[/green]  {prefix} {title} → youtube.com/watch?v={video_id} ({config.privacy})")
        except Exception as e:
            err = str(e)
            current = json.loads(meta_path.read_text(encoding="utf-8"))
            current["upload_error"] = err
            meta_path.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
            rprint(f"[red]✗  {prefix} {title} — upload failed: {err}[/red]")

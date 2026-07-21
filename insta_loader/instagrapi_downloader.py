"""Alternative highlights-download backend built on instagrapi.

instagrapi emulates the Instagram mobile app more completely than instaloader
(persistent device fingerprint, consistent UUIDs, full header seeding), so it
gets through the `highlights_tray` endpoint in cases where instaloader receives
a generic ``"fail"`` response. Selected with ``--backend instagrapi``.

Output is byte-compatible with the instaloader backend: slides are written as
``<stem>_<YYYYMMDD_HHMMSS>.<ext>`` and the same ``metadata.json`` is produced,
so the downstream ``videos`` / ``youtube-*`` commands are unaffected.
"""
import getpass
import json
import random
import sys
import time
from pathlib import Path

import requests

from insta_loader import organizer
from insta_loader import progress as prog
from insta_loader import summarizer
from insta_loader.cli import Config
from insta_loader.downloader import _SLEEP, _SLEEP_JITTER


def _settings_path(username: str) -> Path:
    path = Path.home() / ".config" / "instaloader"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"instagrapi-settings-{username}.json"


def _authenticate(login_user: str):
    """Return a logged-in instagrapi Client, reusing a saved session when possible."""
    from instagrapi import Client
    from instagrapi.exceptions import TwoFactorRequired

    cl = Client()
    settings = _settings_path(login_user)

    if settings.exists():
        try:
            cl.load_settings(settings)
        except Exception:
            pass
        try:
            cl.get_timeline_feed()  # cheap authenticated call to validate the session
            return cl
        except Exception:
            print("⚠  Saved instagrapi session invalid — logging in.")

    password = getpass.getpass(f"Instagram password for {login_user}: ")
    try:
        cl.login(login_user, password)
    except TwoFactorRequired:
        code = input("2FA code: ").strip()
        cl.login(login_user, password, verification_code=code)
    settings.parent.mkdir(parents=True, exist_ok=True)
    cl.dump_settings(settings)
    print(f"✓  Logged in and saved session to {settings}")
    return cl


def _base_tray_params(cl) -> dict:
    from instagrapi import config as ig_config

    return {
        "supported_capabilities_new": json.dumps(ig_config.SUPPORTED_CAPABILITIES),
        "phone_id": cl.phone_id,
        "battery_level": random.randint(25, 100),
        "panavision_mode": "",
        "is_charging": random.randint(0, 1),
        "is_dark_mode": random.randint(0, 1),
        "will_sound_on": random.randint(0, 1),
    }


def _fetch_all_highlights(cl, user_id: int) -> list:
    """Return all highlight tray entries, following the cursor past the 100-item page cap.

    Each entry is a dict with 'pk' and 'title'. instagrapi's built-in
    user_highlights() makes a single tray request and stops at 100; this
    paginates like the instaloader backend so no highlights are silently lost.
    """
    entries: list = []
    seen: set = set()
    cursor = None
    while True:
        params = _base_tray_params(cl)
        if cursor:
            params["cursor"] = cursor
        result = cl.private_request(f"highlights/{user_id}/highlights_tray/", params=params)
        for item in result.get("tray", []):
            raw_id = item.get("id", "")
            pk = raw_id.replace("highlight:", "") if isinstance(raw_id, str) else str(raw_id)
            if pk in seen:
                continue
            seen.add(pk)
            entries.append({"pk": pk, "title": item.get("title", "")})
        cursor = result.get("cursor") or None
        if not cursor:
            break
    return entries


def _get_items(cl, pk: str) -> list:
    """Return a highlight's media items sorted oldest-first (slide 01 = oldest)."""
    info = cl.highlight_info(pk)
    return sorted(info.items, key=lambda m: m.taken_at)


def _download_item(item, folder: Path, stem: str) -> None:
    """Download one media item to <folder>/<stem>_<YYYYMMDD_HHMMSS>.<ext>."""
    ts = item.taken_at.strftime("%Y%m%d_%H%M%S")
    if int(item.media_type) == 2:
        url = str(item.video_url)
        ext = "mp4"
    else:
        url = str(item.thumbnail_url)
        ext = "jpg"
    out = folder / f"{stem}_{ts}.{ext}"
    tmp = folder / f"{stem}_{ts}.{ext}.temp"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    tmp.write_bytes(resp.content)
    tmp.rename(out)


def run(config: Config) -> None:
    if not config.login_user:
        print("✗  The instagrapi backend requires authentication. "
              "Set INSTA_LOGIN_USER in .env or pass --login-user.")
        sys.exit(1)

    cl = _authenticate(config.login_user)

    try:
        user_id = int(cl.user_id_from_username(config.username))
    except Exception as e:
        print(f"✗  Could not resolve @{config.username}: {e}")
        sys.exit(1)

    try:
        entries = _fetch_all_highlights(cl, user_id)
    except Exception as e:
        print(f"✗  Instagram returned an error fetching highlights: {e}")
        print("   This is usually a temporary server-side block. Wait a few minutes and try again.")
        sys.exit(1)

    if config.highlight:
        q = config.highlight.lower()
        matched = [e for e in entries if e["title"].lower() == q]
        if not matched:
            matched = [e for e in entries if q in e["title"].lower()]
        if not matched:
            available = ", ".join(e["title"] for e in entries)
            print(f"✗  No highlight matching '{config.highlight}' found.")
            print(f"   Available: {available}")
            sys.exit(1)
        entries = matched

    base_dir = config.output_dir or f"output/{config.username}"
    print(f"✓  @{config.username} — {len(entries)} highlight(s) to download\n")

    with prog.create_progress() as progress:
        for entry in entries:
            title = entry["title"]
            items = None

            if config.retry_failed:
                folder_path = Path(base_dir) / "instagram" / organizer.sanitize_name(title)
                meta_path = folder_path / "metadata.json"
                if not meta_path.exists():
                    prog.log_video_skip(f"{title} — no metadata, skipping")
                    continue
                existing = json.loads(meta_path.read_text())
                failed = [s for s in existing.get("slides", []) if s.get("status") == "failed"]
                if not failed:
                    prog.log_video_skip(f"{title} — no failed slides, skipping")
                    continue

            elif config.update:
                folder_path = Path(base_dir) / "instagram" / organizer.sanitize_name(title)
                meta_path = folder_path / "metadata.json"
                if meta_path.exists():
                    existing = json.loads(meta_path.read_text())
                    if existing.get("status") == "complete":
                        items = _get_items(cl, entry["pk"])
                        if len(items) == existing.get("total_items", 0):
                            prog.log_video_skip(f"{title} — complete, skipping")
                            continue
                        prog.log_video_skip(
                            f"{title} — {len(items)} slides on Instagram vs "
                            f"{existing.get('total_items', '?')} stored, re-downloading"
                        )

            if items is None:
                items = _get_items(cl, entry["pk"])
            task_id = prog.add_highlight_task(progress, title, len(items))
            folder = organizer.highlight_dir(base_dir, title)

            on_disk = 0
            newly_downloaded = 0
            skipped_count = 0
            failed_count = 0
            videos = 0
            images = 0
            slides = []

            for idx, item in enumerate(items, start=1):
                filename = organizer.slide_filename(title, idx)
                is_video = int(item.media_type) == 2
                slide = {
                    "index": idx,
                    "filename": filename,
                    "type": "video" if is_video else "image",
                    "date_utc": item.taken_at.isoformat(),
                    "mediaid": str(item.pk),
                }

                if organizer.slide_exists(folder, title, idx):
                    slide["status"] = "skipped"
                    prog.log_skip(filename)
                    prog.advance(progress, task_id)
                    on_disk += 1
                    skipped_count += 1
                    if is_video:
                        videos += 1
                    else:
                        images += 1
                    slides.append(slide)
                    prog.update_stats(progress, task_id, newly_downloaded, skipped_count, failed_count)
                    continue

                try:
                    _download_item(item, folder, filename)
                except Exception as e:
                    slide["status"] = "failed"
                    failed_count += 1
                    slides.append(slide)
                    prog.advance(progress, task_id)
                    prog.update_stats(progress, task_id, newly_downloaded, skipped_count, failed_count)
                    print(f"\n⚠  Skipping slide {idx} of '{title}': {e}\n")
                    continue

                slide["status"] = "downloaded"
                on_disk += 1
                newly_downloaded += 1
                if is_video:
                    videos += 1
                else:
                    images += 1
                slides.append(slide)
                prog.advance(progress, task_id, filename)
                prog.update_stats(progress, task_id, newly_downloaded, skipped_count, failed_count)
                if _SLEEP:
                    jitter = random.uniform(-_SLEEP * _SLEEP_JITTER, _SLEEP * _SLEEP_JITTER)
                    time.sleep(max(0.1, _SLEEP + jitter))

            organizer.write_metadata(folder, title, len(items), on_disk, videos, images, slides)

    summarizer.run(config.username, config.output_dir)

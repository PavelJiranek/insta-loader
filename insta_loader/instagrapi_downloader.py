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
from insta_loader import downloader as _dl
from insta_loader.cli import Config
from insta_loader.downloader import _SLEEP, _SLEEP_JITTER


def _settings_path(username: str) -> Path:
    path = Path.home() / ".config" / "instaloader"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"instagrapi-settings-{username}.json"


_APP_KEYS = ("app_version", "version_code", "bloks_versioning_id")


def _reset_session_keep_device(cl) -> None:
    """Drop a dead session so login() really logs in, as the same phone.

    A dead session loaded from disk still sets user_id, and instagrapi's login()
    returns True early whenever user_id is set, without sending the password.
    So the session state is cleared first. The device IDs and hardware are kept,
    so Instagram sees the same phone signing back in, not a brand-new device.

    The app version is the one thing that is deliberately not kept. Instagram
    rejects logins from app versions it considers out of date ("Your version of
    Instagram is out of date"), and set_device() would keep a saved version it
    still recognises. Moving to the library's current version reads as the same
    phone with the app updated, which is what a real phone does.
    """
    from instagrapi import config as ig_config

    old = cl.get_settings()
    cl.set_settings({})
    cl.set_uuids(old.get("uuids", {}))
    hardware = {k: v for k, v in (old.get("device_settings") or {}).items() if k not in _APP_KEYS}
    if hardware:
        cl.set_device(hardware)
    cl.set_app(ig_config.DEFAULT_APP_VERSION)
    cl.set_user_agent()


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
            print("⚠  Saved session is no longer valid (Instagram signed it out).")
            print("   If that happened in the last few hours, logging straight back in can")
            print("   get the account flagged again. Press Ctrl+C now and try later.")
            _reset_session_keep_device(cl)

    password = getpass.getpass(f"Instagram password for {login_user}: ")
    try:
        try:
            cl.login(login_user, password)
        except TwoFactorRequired:
            code = input("2FA code: ").strip()
            cl.login(login_user, password, verification_code=code)
    except _blocked_errors() as e:
        _report_block(e, {"checked": 0, "total": 0})
        sys.exit(1)
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
        _dl._api_pause()
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
    _dl._api_pause()  # one private-API call per highlight: the call Instagram throttles
    info = cl.highlight_info(pk)
    return sorted(info.items, key=lambda m: m.taken_at)


def _spec(item) -> tuple:
    """(timestamp, ext) that identifies this media's file on disk."""
    ts = item.taken_at.strftime("%Y%m%d_%H%M%S")
    return ts, ("mp4" if int(item.media_type) == 2 else "jpg")


def _download_item(item, folder: Path, stem: str) -> None:
    """Download one media item to <folder>/<stem>_<YYYYMMDD_HHMMSS>.<ext>."""
    ts, ext = _spec(item)
    url = str(item.video_url) if ext == "mp4" else str(item.thumbnail_url)
    out = folder / f"{stem}_{ts}.{ext}"
    tmp = folder / f"{stem}_{ts}.{ext}.temp"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    tmp.write_bytes(resp.content)
    tmp.rename(out)


def _blocked_errors() -> tuple:
    """instagrapi errors meaning Instagram is pushing back on this session.

    Continuing after one of these only digs the hole deeper, so the run stops.
    """
    from instagrapi import exceptions as E

    return (E.LoginRequired, E.ClientLoginRequired, E.ChallengeRequired,
            E.ClientForbiddenError, E.PleaseWaitFewMinutes, E.RateLimitError,
            E.ClientThrottledError, E.FeedbackRequired)


def _report_block(err: Exception, state: dict) -> None:
    from instagrapi import exceptions as E

    if isinstance(err, (E.LoginRequired, E.ClientLoginRequired)):
        what = "Instagram signed this session out (login_required)."
    elif isinstance(err, E.ChallengeRequired):
        what = ("Instagram wants this login confirmed (challenge_required). "
                "Open the Instagram app on your phone and approve it.")
    else:
        what = f"Instagram is rate-limiting requests ({type(err).__name__})."
    print(f"\n✗  {what}")
    if state["total"]:
        print("   Stopped here so it doesn't get worse. "
              f"{state['checked']}/{state['total']} highlight(s) checked this run; "
              "everything that finished is saved.")
        print("   Wait a few hours, then re-run with --update: finished highlights are skipped.")
    else:
        print("   Wait a few hours before trying again.")


def run(config: Config) -> None:
    if not config.login_user:
        print("✗  The instagrapi backend requires authentication. "
              "Set INSTA_LOGIN_USER in .env or pass --login-user.")
        sys.exit(1)

    cl = _authenticate(config.login_user)
    state = {"checked": 0, "total": 0}
    try:
        _run(cl, config, state)
    except _blocked_errors() as e:
        _report_block(e, state)
        summarizer.run(config.username, config.output_dir)
        sys.exit(1)


def _run(cl, config: Config, state: dict) -> None:
    try:
        _dl._api_pause()
        user_id = int(cl.user_id_from_username(config.username))
    except _blocked_errors():
        raise
    except Exception as e:
        print(f"✗  Could not resolve @{config.username}: {e}")
        sys.exit(1)

    try:
        entries = _fetch_all_highlights(cl, user_id)
    except _blocked_errors():
        raise
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
    state["total"] = len(entries)

    with prog.create_progress() as progress:
        for n, entry in enumerate(entries):
            state["checked"] = n
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
                    items = _get_items(cl, entry["pk"])
                    # Compare what's on disk with what's on Instagram slide by
                    # slide, not just the count: removals, additions and reorders
                    # all show up here even when the total is unchanged.
                    if existing.get("status") == "complete" and organizer.in_sync(
                        folder_path, title, [_spec(m) for m in items]
                    ):
                        prog.log_video_skip(f"{title} — up to date, skipping")
                        continue

            if items is None:
                items = _get_items(cl, entry["pk"])
            if not items:
                # An empty response is far more likely to be an API hiccup than a
                # highlight emptied on purpose. Syncing against it would move
                # every local slide to Trash, so leave the folder alone.
                prog.log_video_skip(f"{title} — Instagram returned no slides, leaving local copy untouched")
                continue
            task_id = prog.add_highlight_task(progress, title, len(items))
            folder = organizer.highlight_dir(base_dir, title)

            if not config.retry_failed:
                sync = organizer.sync_folder(folder, title, [_spec(m) for m in items])
                if sync.changed:
                    prog.log_resync(f"{title} — resynced with Instagram: {sync.summary()}")

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

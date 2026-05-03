import json
import os
import sys
import time
from pathlib import Path

import instaloader

from insta_loader import organizer
from insta_loader import progress as prog
from insta_loader import summarizer
from insta_loader.cli import Config

_SLEEP = float(os.environ.get("INSTA_SLEEP", "0"))


def _session_path(username: str) -> str:
    # Always use ~/.config/instaloader/ so the session persists across processes.
    path = Path.home() / ".config" / "instaloader"
    path.mkdir(parents=True, exist_ok=True)
    return str(path / f"session-{username}")


def _resolve_highlight(query: str, all_highlights: list) -> list:
    exact = [h for h in all_highlights if h.title.lower() == query.lower()]
    if exact:
        return exact

    partial = [h for h in all_highlights if query.lower() in h.title.lower()]
    if not partial:
        available = ", ".join(h.title for h in all_highlights)
        print(f"✗  No highlight matching '{query}' found.")
        print(f"   Available: {available}")
        sys.exit(1)

    if len(partial) == 1:
        print(f"→  Matched '{partial[0].title}'")
        return partial

    print(f"Multiple highlights match '{query}':")
    for i, h in enumerate(partial, start=1):
        print(f"  {i}. {h.title}")
    raw = input(f"Pick [1-{len(partial)}]: ").strip()
    if not raw.isdigit() or not (1 <= int(raw) <= len(partial)):
        print("✗  Invalid selection.")
        sys.exit(1)
    return [partial[int(raw) - 1]]


def _get_all_highlights(L: instaloader.Instaloader, profile) -> list:
    highlights = []
    cursor = None
    while True:
        params: dict = {}
        if cursor:
            params["cursor"] = cursor
        data = L.context.get_iphone_json(
            path=f"api/v1/highlights/{profile.userid}/highlights_tray/",
            params=params,
        )
        for item in data.get("tray", []):
            raw_id = item.get("id", "")
            node_id = raw_id.replace("highlight:", "") if isinstance(raw_id, str) else str(raw_id)
            node = {
                "id": node_id,
                "title": item.get("title", ""),
                "cover_media": item.get("cover_media", {}),
                "cover_media_cropped_thumbnail": item.get("cover_media_cropped_thumbnail", {}),
            }
            highlights.append(instaloader.Highlight(L.context, node, profile))
        cursor = data.get("cursor") or None
        if not cursor:
            break
    return highlights


def run(config: Config) -> None:
    L = instaloader.Instaloader(
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern="",
    )

    if config.login_user:
        session_file = _session_path(config.login_user)
        try:
            L.load_session_from_file(config.login_user, session_file)
        except FileNotFoundError:
            print(f"No saved session for @{config.login_user} — logging in...")
            try:
                L.interactive_login(config.login_user)
                L.save_session_to_file(session_file)
            except instaloader.exceptions.BadCredentialsException:
                print("✗  Wrong password.")
                sys.exit(1)

    try:
        profile = instaloader.Profile.from_username(L.context, config.username)
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"✗  @{config.username} not found.")
        sys.exit(1)

    if profile.is_private:
        print(
            f"✗  @{config.username} is a private account. "
            "Only public accounts are supported in V1."
        )
        sys.exit(1)

    all_highlights = _get_all_highlights(L, profile)

    if config.highlight:
        highlights = _resolve_highlight(config.highlight, all_highlights)
    else:
        highlights = all_highlights

    base_dir = config.output_dir or f"output/{config.username}"
    print(f"✓  @{config.username} is public — {len(highlights)} highlight(s) to download\n")

    with prog.create_progress() as progress:
        for highlight in highlights:
            if config.update:
                folder_path = Path(base_dir) / organizer.sanitize_name(highlight.title)
                meta_path = folder_path / "metadata.json"
                if meta_path.exists():
                    existing = json.loads(meta_path.read_text())
                    if existing.get("status") == "complete":
                        prog.log_video_skip(f"{highlight.title} — complete, skipping")
                        continue

            items = list(reversed(list(highlight.get_items())))
            task_id = prog.add_highlight_task(progress, highlight.title, len(items))
            folder = organizer.highlight_dir(base_dir, highlight.title)

            on_disk = 0
            newly_downloaded = 0
            skipped_count = 0
            failed_count = 0
            videos = 0
            images = 0
            slides = []

            for idx, item in enumerate(items, start=1):
                filename = organizer.slide_filename(highlight.title, idx)
                is_video = item.is_video
                slide = {
                    "index": idx,
                    "filename": filename,
                    "type": "video" if is_video else "image",
                    "date_utc": item.date_utc.isoformat(),
                    "mediaid": str(item.mediaid),
                }

                if organizer.slide_exists(folder, highlight.title, idx):
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

                L.dirname_pattern = str(folder)
                L.filename_pattern = filename + "_{date_utc:%Y%m%d_%H%M%S}"

                try:
                    L.download_storyitem(item, highlight.unique_id)
                except Exception as e:
                    slide["status"] = "failed"
                    failed_count += 1
                    slides.append(slide)
                    prog.advance(progress, task_id)
                    prog.update_stats(progress, task_id, newly_downloaded, skipped_count, failed_count)
                    print(f"\n⚠  Skipping slide {idx} of '{highlight.title}': {e}\n")
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
                    time.sleep(_SLEEP)

            organizer.write_metadata(folder, highlight.title, len(items), on_disk, videos, images, slides)

    summarizer.run(config.username, config.output_dir)

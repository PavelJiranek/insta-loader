import sys

import instaloader

from insta_loader import organizer
from insta_loader import progress as prog
from insta_loader.cli import Config


def run(config: Config) -> None:
    L = instaloader.Instaloader(
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern="",
    )

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

    all_highlights = list(L.get_highlights(profile))

    if config.highlight:
        highlights = [
            h for h in all_highlights if h.title.lower() == config.highlight.lower()
        ]
        if not highlights:
            available = ", ".join(h.title for h in all_highlights)
            print(f"✗  Highlight '{config.highlight}' not found.")
            print(f"   Available: {available}")
            sys.exit(1)
    else:
        highlights = all_highlights

    base_dir = config.output_dir or f"{config.username}/highlights"
    print(f"✓  @{config.username} is public — {len(highlights)} highlight(s) to download\n")

    with prog.create_progress() as progress:
        for highlight in highlights:
            items = list(highlight.get_items())
            task_id = prog.add_highlight_task(progress, highlight.title, len(items))
            folder = organizer.highlight_dir(base_dir, highlight.title)

            for idx, item in enumerate(items, start=1):
                filename = organizer.slide_filename(highlight.title, idx)

                if organizer.slide_exists(folder, highlight.title, idx):
                    prog.log_skip(filename)
                    prog.advance(progress, task_id)
                    continue

                L.dirname_pattern = str(folder)
                L.filename_pattern = filename + "_{date_utc:%Y%m%d_%H%M%S}"

                try:
                    L.download_storyitem(item, highlight.unique_id)
                except Exception as e:
                    print(f"\n✗  Error on slide {idx} of '{highlight.title}': {e}")
                    print("   Resume by running the same command again.")
                    sys.exit(1)

                prog.advance(progress, task_id, filename)

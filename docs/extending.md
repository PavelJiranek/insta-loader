# Extending the Tool

## Adding V2: Video Stitcher

V2 stitches downloaded slides into a single `.mp4` per highlight. It reads V1's output — do not modify V1 modules.

**New file:** `insta_loader/stitcher.py`

```python
from pathlib import Path


def stitch(highlight_dir: Path, output_path: Path) -> None:
    """Concatenate all slides in order into a single mp4 via ffmpeg."""
    ...
```

**New entry point:** `stitch.py` — mirrors `highlights.py`, wires `cli` → `stitcher`.
Keep separate entry points so V1 and V2 remain independently usable.

New dependency to add to `requirements.txt`: `moviepy` or shell out to `ffmpeg`.

## Adding a New CLI Flag

1. Add the argument to `parse_args()` in `insta_loader/cli.py`.
2. Add the field to the `Config` dataclass.
3. Consume the new field in `insta_loader/downloader.py`.
4. Add tests in `tests/test_cli.py` and `tests/test_downloader.py`.

## Swapping instaloader for Another Library

All instaloader calls are isolated in `insta_loader/downloader.py`. The four call sites to replace:

```python
instaloader.Instaloader(...)             # initialization
instaloader.Profile.from_username(...)   # profile + public check
L.get_highlights(profile)               # highlight list
L.download_storyitem(item, target)       # single slide download
```

`organizer`, `cli`, and `progress` have zero knowledge of instaloader.

## What Not to Touch

- **`organizer.py`** — stable interface; both the downloader and a future stitcher depend on it
- **`Config` dataclass fields** — removing fields breaks downloader
- **Filename format** — changing it breaks resume (existing files won't be detected by glob)

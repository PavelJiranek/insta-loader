# V1 — Instagram Highlight Downloader: Design Spec

**Date:** 2026-05-03  
**Scope:** V1 only — download + folder organizer. V2 (video stitcher) is a separate project.

---

## Overview

A Python CLI tool that accepts an Instagram username, verifies the account is public, and downloads all story highlight reels into an organized local folder structure. Downloads are idempotent — re-running skips already-downloaded slides and picks up new highlights.

---

## CLI Interface

```
python highlights.py <username> [--output-dir DIR] [--highlight NAME]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `username` | yes | — | Instagram username (without @) |
| `--output-dir` | no | `<username>/highlights/` | Where to save downloaded files |
| `--highlight` | no | all highlights | Download only the named highlight reel |

**Confirmation prompt:** When `--highlight` is omitted, the tool prints a warning and asks `Continue? [y/N]` before starting. Default is No.

---

## Project Structure

```
insta-loader/
├── highlights.py              # Entry point
├── requirements.txt           # instaloader, rich
├── README.md
├── .gitignore                 # Includes default <username>/highlights/ pattern; custom --output-dir paths are user's responsibility
├── insta_loader/
│   ├── __init__.py
│   ├── cli.py                 # Argument parsing, confirmation prompt
│   ├── downloader.py          # instaloader wrapper, resume logic, error handling
│   ├── organizer.py           # Folder creation, file naming
│   └── progress.py            # Rich progress bar helpers
└── docs/
    ├── how-it-works.md        # Architecture overview (agent-agnostic)
    ├── extending.md           # How to add V2 stitcher and other extensions
    └── superpowers/specs/     # Design specs
```

---

## Output Folder Structure

Default output path: `<username>/highlights/` relative to CWD. Override with `--output-dir`.

```
<output-dir>/
  Travel/
    Travel_01_20230415_143200.mp4
    Travel_02_20230415_143500.jpg
    Travel_03_20230415_144100.mp4
  Summer_2024/
    Summer_2024_01_20240701_090000.mp4
    Summer_2024_02_20240701_090300.mp4
```

**Filename format:** `<HighlightName>_<idx:02d>_<date_utc:%Y%m%d_%H%M%S>.<ext>`

- Highlight name is sanitized: spaces → `_`, `/` → `-`
- `idx` is 1-based, zero-padded to 2 digits
- Extension (`.mp4` / `.jpg`) is assigned by instaloader from media type
- Files are self-describing even when moved out of their folder

---

## Module Responsibilities

### `highlights.py`
Entry point. Calls `cli.parse_args()`, then `downloader.run()`. No logic of its own.

### `insta_loader/cli.py`
- Parses arguments with `argparse`
- If `--highlight` is omitted, prints confirmation prompt and exits on `n`/empty input
- Returns a typed config object consumed by `downloader.py`

### `insta_loader/organizer.py`
- `sanitize_name(title) -> str` — replaces `/` with `-`, spaces with `_`
- `highlight_dir(base_dir, highlight_title) -> Path` — returns and creates the folder
- `slide_filename(highlight_title, idx, date) -> str` — returns the filename stem (no extension)
- `slide_exists(highlight_dir, highlight_title, idx) -> bool` — globs for `<Name>_<idx:02d>_*` to detect already-downloaded slides

### `insta_loader/progress.py`
- Wraps `rich.progress.Progress` with a consistent style
- Exposes: `create_progress()`, `add_highlight_task(progress, title, total)`, `advance(progress, task_id)`
- Prints skip messages via `rich.print` in muted style

### `insta_loader/downloader.py`
Core orchestration:
1. Initialize `instaloader.Instaloader` with metadata/comments/geotags disabled
2. Fetch profile via `Profile.from_username()` — exit with error if private
3. Fetch highlights via `L.get_highlights(profile)` — if `--highlight` given, filter by case-insensitive exact match on title; exit with error listing available names if no match found
4. For each highlight, for each slide:
   - Call `organizer.slide_exists()` — skip if true
   - Set `L.dirname_pattern` and `L.filename_pattern` via `organizer`
   - Call `L.download_storyitem(item, target)`
   - Advance progress bar
5. On `QueryReturnedNotFoundException`, network error, or keyboard interrupt: print clean error message and exit with code 1. Best-effort cleanup of any partial file for the interrupted slide.

---

## Resume Behaviour

The filesystem is the state. On each slide, `organizer.slide_exists()` globs for `<HighlightName>_<idx:02d>_*` in the highlight folder. If a match exists the slide is skipped and logged. This means:

- Re-running after a failure resumes from the first missing slide
- Re-running on a fully downloaded account is a no-op (fast)
- New highlights added since the last run are picked up automatically

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Private account | Print error, exit 1 |
| Account not found | Print error, exit 1 |
| Rate limited / network error | Print message with resume instructions, exit 1 |
| Highlight name not found (--highlight) | Print available highlight names, exit 1 |
| Keyboard interrupt (Ctrl+C) | Clean exit, partial slide file deleted |

---

## Dependencies

```
instaloader>=4.10
rich>=13.0
```

Python 3.9+. No virtual env tooling for V1 — plain `pip install -r requirements.txt`.

---

## Agent-Agnostic Documentation

Two markdown files in `docs/` describe the system for any developer or AI agent:

- **`how-it-works.md`** — architecture overview, module responsibilities, data flow, file naming conventions
- **`extending.md`** — how to add V2 stitcher, swap instaloader, add CLI flags; which files to touch and which to leave alone

These docs are written without assuming any specific AI tool or workflow.

---

## Out of Scope (V1)

- Authenticated / private account downloads
- Video stitching (V2)
- Web or iOS interface (V3)
- Rate-limit auto-retry with backoff
- Metadata/caption saving

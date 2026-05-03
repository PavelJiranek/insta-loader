# How It Works

## Architecture

The tool is split into four focused modules inside `insta_loader/`:

| Module | Responsibility |
|---|---|
| `cli.py` | Parse CLI arguments; run confirmation prompt when no `--highlight`; return `Config` |
| `organizer.py` | Sanitize names; create folders; build filename stems; check if a slide already exists |
| `progress.py` | Wrap Rich for progress bars and skip messages |
| `downloader.py` | Orchestrate: fetch profile, iterate highlights and slides, delegate to other modules |

`highlights.py` is the entry point — it calls `parse_args()` then `run(config)` and contains no logic of its own.

## Data Flow

```
highlights.py
  └─ cli.parse_args()  →  Config(username, output_dir, highlight)
  └─ downloader.run(config)
       ├─ instaloader.Profile.from_username()     # verify account is public
       ├─ instaloader.get_highlights(profile)     # list all highlight reels
       └─ for each highlight, for each slide:
            ├─ organizer.slide_exists()           # resume check via glob
            ├─ [skip and log if already present]
            ├─ organizer.slide_filename()         # build filename stem
            ├─ L.download_storyitem()             # download via instaloader
            └─ progress.advance()                 # update progress bar
```

## File Naming

Format: `<HighlightName>_<idx:02d>_<date_utc:%Y%m%d_%H%M%S>.<ext>`

- `HighlightName`: title sanitized — spaces → `_`, `/` → `-`
- `idx`: 1-based slide index, zero-padded to 2 digits (e.g. `01`, `12`)
- `date`: UTC timestamp from the story item, set by instaloader's template engine
- `ext`: `.mp4` for video, `.jpg` for images (assigned by instaloader)

## Resume Logic

Before downloading each slide, `organizer.slide_exists()` runs `glob("<Name>_<idx:02d>_*")` in the highlight folder. If any file matches, the slide is skipped. The filesystem is the state — no database or lock files needed.

## Error Handling

All errors print a human-readable message and call `sys.exit(1)`. There are no automatic retries. Re-running after any error resumes from the first missing slide.

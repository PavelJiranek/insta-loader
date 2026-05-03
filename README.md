# insta-loader

Download Instagram story highlight reels to organized local folders.

## Requirements

- Python 3.9+

```bash
pip install -r requirements.txt
```

## Setup

Copy `.env.template` to `.env` and fill in your Instagram username:

```bash
cp .env.template .env
```

On first run you will be prompted for your Instagram password. The session is saved to `~/.config/instaloader/` and reused automatically on subsequent runs.

## Commands

All commands are available through the unified `insta.py` entry point. Run `python insta.py --help` for a full list or `python insta.py <command> --help` for per-command help.

The legacy `highlights.py` and `summary.py` entry points still work unchanged.

---

### `insta.py highlights` — download highlights

```
python insta.py highlights <username> [options]
```

| Option | Description |
|---|---|
| `--highlight NAME` | Download only this highlight (partial name match, case-insensitive). Omit to download all (asks for confirmation). |
| `--output-dir DIR` | Save to this directory instead of `output/<username>/`. |
| `--login-user USER` | Instagram account to authenticate as. Defaults to `INSTA_LOGIN_USER` from `.env`. |

```bash
# Download all highlights (asks for confirmation)
python insta.py highlights natgeo

# Partial name match — picks from a list if multiple match
python insta.py highlights natgeo --highlight "travel"

# Specific highlight, custom output dir, explicit login user
python insta.py highlights natgeo --highlight "Travel" --output-dir ~/Desktop/insta --login-user myaccount
```

After each run a `summary.json` is written automatically to `output/<username>/`.

---

### `insta.py videos` — create highlight videos

Assembles downloaded slides for a user into one MP4 per highlight. Images are shown for 15 seconds; videos play at full duration with audio.

```
python insta.py videos <username> [options]
```

| Option | Description |
|---|---|
| `--highlight NAME` | Create video only for this highlight (partial name match, case-insensitive). Omit to process all. |
| `--output-dir DIR` | Base directory (default: `output/<username>/`). |

```bash
# Create videos for all downloaded highlights
python insta.py videos natgeo

# Create video for one highlight
python insta.py videos natgeo --highlight "travel"
```

Videos are saved to `output/<username>/videos/<HighlightName>.mp4`. If a video already exists you will be prompted to overwrite, skip, or save as a new file.

Requires `ffmpeg` on your PATH. Install from [ffmpeg.org](https://ffmpeg.org/download.html).

---

### `insta.py summary` — regenerate summary

Reads all `metadata.json` files on disk and writes `output/<username>/summary.json`. Useful if you want to refresh the summary without re-downloading.

```
python insta.py summary <username> [options]
```

| Option | Description |
|---|---|
| `--output-dir DIR` | Read from this directory instead of `output/<username>/`. |

```bash
python insta.py summary natgeo
```

---

## Output

Files are saved to `output/<username>/` by default (gitignored):

```
output/natgeo/
  summary.json
  Travel/
    metadata.json
    Travel_01_20230415_143200.mp4
    Travel_02_20230415_143500.jpg
  Summer_2024/
    metadata.json
    Summer_2024_01_20240701_090000.mp4
    Summer_2024_02_20240701_090300.mp4
```

Filename format: `<HighlightName>_<index>_<date>.<ext>` — newest slide is `_01`.

## Resume

Downloads are **idempotent** — re-running the same command skips already-downloaded slides and picks up any new or failed ones automatically.

## Notes

- Only public Instagram accounts are supported.
- If rate-limited, add `INSTA_SLEEP=2` to `.env` to pause 2 seconds between slides.
- Slides that fail to download are skipped and marked `"failed"` in `metadata.json` — other slides in the highlight are unaffected.

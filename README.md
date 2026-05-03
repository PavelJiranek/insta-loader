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

### `highlights.py` — download highlights

```
python highlights.py <username> [options]
```

| Option | Description |
|---|---|
| `--highlight NAME` | Download only this highlight (partial name match, case-insensitive). Omit to download all (asks for confirmation). |
| `--output-dir DIR` | Save to this directory instead of `output/<username>/`. |
| `--login-user USER` | Instagram account to authenticate as. Defaults to `INSTA_LOGIN_USER` from `.env`. |

```bash
# Download all highlights (asks for confirmation)
python highlights.py natgeo

# Partial name match — picks from a list if multiple match
python highlights.py natgeo --highlight "travel"

# Specific highlight, custom output dir, explicit login user
python highlights.py natgeo --highlight "Travel" --output-dir ~/Desktop/insta --login-user myaccount
```

After each run a `summary.json` is written automatically to `output/<username>/`.

---

### `summary.py` — regenerate summary

Reads all `metadata.json` files on disk and writes `output/<username>/summary.json`. Useful if you want to refresh the summary without re-downloading.

```
python summary.py <username> [options]
```

| Option | Description |
|---|---|
| `--output-dir DIR` | Read from this directory instead of `output/<username>/`. |

```bash
python summary.py natgeo
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

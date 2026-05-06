# insta-loader

A command-line tool to back up your own story highlights from Instagram, assemble them into MP4 videos, and optionally upload them to YouTube.

> ☕ If this saves you time, consider supporting the project — Buy Me a Coffee link coming soon.

---

## What it does

- **Downloads** story highlights from public Instagram accounts, with resume support
- **Assembles** downloaded slides (images + videos) into a single MP4 per highlight using bundled ffmpeg
- **Uploads** assembled videos to YouTube with auto-generated titles, descriptions, tags, recording date, and location
- Keeps everything in a clean local folder structure you own

---

## Requirements

- Python 3.9+
- No system ffmpeg required — bundled via `imageio-ffmpeg`

```bash
pip install -r requirements.txt
```

---

## Setup

Create a `.env` file in the project root:

```
INSTA_LOGIN_USER=your_instagram_username
```

On first run you will be prompted for your password. The session is saved to `~/.config/instaloader/` and reused on subsequent runs.

---

## Output structure

```
output/<username>/
  instagram/          <- downloaded highlight folders
    Travel/
      metadata.json
      Travel_01_20230415_143200.mp4
      Travel_02_20230415_143500.jpg
    summary.json
  videos/             <- assembled MP4s
    Travel.mp4
  youtube/            <- YouTube metadata per highlight
    Travel.json
```

---

## Commands

Run `python3 insta.py --help` or `python3 insta.py <command> --help` for the full reference.

---

### `highlights` — download story highlights

```bash
python3 insta.py highlights <username> [options]
```

| Option | Description |
|---|---|
| `--highlight NAME` | Download only this highlight (partial name, case-insensitive) |
| `--update` | Skip highlights already marked complete; re-download if the source has new slides |
| `--retry-failed` | Only retry highlights that have failed slides |
| `--login-user USER` | Account to authenticate as (or set `INSTA_LOGIN_USER` in `.env`) |
| `--output-dir DIR` | Override default output path |

```bash
# Download all (asks for confirmation)
python3 insta.py highlights natgeo

# Only new or incomplete highlights
python3 insta.py highlights natgeo --update

# Re-try previously failed slides only
python3 insta.py highlights natgeo --retry-failed

# Single highlight by partial name
python3 insta.py highlights natgeo --highlight "travel"
```

---

### `videos` — assemble highlights into MP4s

```bash
python3 insta.py videos <username> [options]
```

| Option | Description |
|---|---|
| `--highlight NAME` | Process only this highlight |
| `--update` | Re-encode only highlights newer than their existing video |
| `--image-duration N` | Seconds each image slide is shown (default: 10) |
| `--output-dir DIR` | Override base directory |

```bash
python3 insta.py videos natgeo
python3 insta.py videos natgeo --update
```

Videos are saved to `output/<username>/videos/`. Failed encodes are moved to Trash, not permanently deleted.

---

### `youtube-meta` — generate YouTube metadata

Generates a JSON file per highlight with title, description, tags, recording date, and location.

```bash
python3 insta.py youtube-meta <username> [options]
```

| Option | Description |
|---|---|
| `--highlight NAME` | Process only this highlight |
| `--privacy STATUS` | `unlisted` (default), `private`, or `public` |

Titles and tags are auto-generated from folder names — flag emoji detection, camelCase splitting, part numbers, date ranges, country/continent tags.

---

### `youtube-upload` — upload to YouTube

```bash
python3 insta.py youtube-upload <username> [options]
```

| Option | Description |
|---|---|
| `--highlight NAME` | Upload only this highlight |
| `--update` | Delete outdated uploads (after confirmation) and re-upload |
| `--playlist NAME` | Playlist to add videos to (default: `Story Highlights`) |
| `--privacy STATUS` | `unlisted` (default), `private`, or `public` |
| `--client-secrets PATH` | Path to OAuth secrets JSON |

**First-time YouTube setup:**

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project → APIs & Services → Enable **YouTube Data API v3**
3. Credentials → Create OAuth client ID → **User data** (not Public data) → Desktop app
4. OAuth consent screen → Test users → add your Google account email
5. Download the JSON and save to `~/.config/instaloader/youtube_client_secrets.json`

Token is cached at `~/.config/instaloader/youtube_token.json` after first login.

---

### `summary` — regenerate summary

```bash
python3 insta.py summary <username>
```

Reads all `metadata.json` files on disk and rewrites `summary.json`. Useful after manual fixes.

---

## Typical workflow

```bash
# 1. Download new/updated highlights
python3 insta.py highlights natgeo --update

# 2. Retry any failed slides
python3 insta.py highlights natgeo --retry-failed

# 3. Assemble videos (re-encode changed ones only)
python3 insta.py videos natgeo --update

# 4. Generate YouTube metadata
python3 insta.py youtube-meta natgeo

# 5. Upload to YouTube
python3 insta.py youtube-upload natgeo --update
```

---

## Notes

- Only **public** accounts are supported without login. Private accounts require `--login-user`.
- YouTube free quota: ~6 uploads/day unverified, ~100/day after phone verification.
- Add `INSTA_SLEEP=2` to `.env` to pause 2 seconds between slide downloads if rate-limited.
- Partial downloads resume automatically — already-downloaded slides are never re-fetched.
- Interrupted downloads leave `.temp` files which are ignored and safely re-downloaded.

---

## License

[GNU General Public License v3.0](LICENSE)

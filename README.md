# insta-loader

A command-line tool to back up your own story highlights from Instagram, assemble them into MP4 videos, and optionally upload them to YouTube.

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-support-yellow?logo=buy-me-a-coffee)](https://buymeacoffee.com/pauliejr)

---

## What it does

- **Downloads** story highlights from public Instagram accounts, with resume support
- **Assembles** downloaded slides (images + videos) into a single MP4 per highlight using bundled ffmpeg
- **Uploads** assembled videos to YouTube with auto-generated titles, descriptions, tags, recording date, and location
- Keeps everything in a clean local folder structure you own

![insta-loader terminal](docs/screenshot.png)

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
# Optional — set the default download backend (instaloader | instagrapi).
# instagrapi requires login but survives the highlights-API soft blocks that
# periodically hit instaloader. Overridable per-run with --backend.
#INSTA_BACKEND=instagrapi
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
| `--backend {instaloader,instagrapi}` | Download backend (default: `instaloader`). Switch to `instagrapi` if Instagram soft-blocks the highlights API |
| `--output-dir DIR` | Override default output path |

```bash
# Download all (asks for confirmation)
python3 insta.py highlights natgeo

# Only new or incomplete highlights
python3 insta.py highlights natgeo --update

# Re-try previously failed slides only
python3 insta.py highlights natgeo --retry-failed

# Use the instagrapi backend when instaloader gets a "fail" response on highlights
python3 insta.py highlights natgeo --update --backend instagrapi

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
| `--landscape` | Create 16:9 landscape videos with blurred+darkened background (saved to `videos_landscape/`) |
| `--both-formats` | Create both portrait and landscape videos in one run |
| `--no-sleep` | Prevent macOS from sleeping during encoding (uses `caffeinate`) |
| `--output-dir DIR` | Override base directory |

```bash
python3 insta.py videos natgeo
python3 insta.py videos natgeo --update

# Portrait + landscape in one pass, keeping the Mac awake
python3 insta.py videos natgeo --both-formats --update --no-sleep
```

Videos are saved to `output/<username>/videos/` (portrait) and `output/<username>/videos_landscape/` (landscape). Failed or interrupted encodes are moved to Trash, not permanently deleted.

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
| `--landscape` | Generate metadata for landscape videos (reads `videos_landscape/`, writes `youtube_landscape/`) |
| `--both-formats` | Generate metadata for both portrait and landscape videos in one run |

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
| `--landscape` | Upload landscape videos (reads `youtube_landscape/` metadata, uploads to a separate `· 16:9` playlist) |
| `--both-formats` | Upload both portrait and landscape videos in one run |
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

### Landscape (16:9) workflow

```bash
# 1. Assemble landscape versions
python3 insta.py videos <username> --landscape --update

# 2. Generate YouTube metadata (titles get · 16:9 suffix)
python3 insta.py youtube-meta <username> --landscape

# 3. Upload to YouTube (separate playlist suffixed with · 16:9)
python3 insta.py youtube-upload <username> --landscape
```

### Both formats at once

`--both-formats` processes portrait and landscape in a single command:

```bash
python3 insta.py videos <username> --both-formats --update --no-sleep
python3 insta.py youtube-meta <username> --both-formats
python3 insta.py youtube-upload <username> --both-formats --update
```

---

## Notes

- Only **public** accounts are supported without login. Private accounts require `--login-user`.
- YouTube free quota: ~6 uploads/day unverified, ~100/day after phone verification.
- Add `INSTA_SLEEP=3` to `.env` to pause ~3 seconds between slide downloads if rate-limited. The delay is randomised by ±50% by default to avoid fixed-interval detection patterns. Override the jitter with `INSTA_SLEEP_JITTER=0.3` (0 = no jitter, 1 = ±100%).
- Partial downloads resume automatically — already-downloaded slides are never re-fetched.
- Interrupted downloads leave `.temp` files which are ignored and safely re-downloaded.

---

## Architecture

```mermaid
flowchart TD
    CLI["insta.py\n(CLI entry point)"]

    CLI -->|highlights| DL["downloader.py\nFetch slides from Instagram API\nResume / retry-failed / update"]
    CLI -->|videos| VC["video_creator.py\nAssemble slides into MP4\nvia bundled ffmpeg"]
    CLI -->|youtube-meta| YM["youtube_meta.py\nGenerate title, description,\ntags, date, location JSON"]
    CLI -->|youtube-upload| YU["youtube_uploader.py\nOAuth2 upload to YouTube\nPlaylist management"]
    CLI -->|summary| SU["summarizer.py\nRebuild summary.json\nfrom metadata on disk"]

    DL -->|writes| FS["output/&lt;user&gt;/instagram/\n&lt;Highlight&gt;/\n  metadata.json\n  slide_01.mp4 / .jpg"]
    DL --> OR["organizer.py\nFolder layout &amp; naming\nSlide dedup / .temp guard"]
    DL --> SU

    VC -->|reads| FS
    VC -->|writes| VD["output/&lt;user&gt;/videos/\n&lt;Highlight&gt;.mp4"]

    YM -->|reads| FS
    YM -->|writes| YD["output/&lt;user&gt;/youtube/\n&lt;Highlight&gt;.json"]

    YU -->|reads| VD
    YU -->|reads/updates| YD

    subgraph Shared
        CL["cli.py\nConfig / VideoConfig /\nYoutubeConfig dataclasses"]
        PR["progress.py\nRich progress bar helpers"]
    end

    DL --- CL
    VC --- CL
    YM --- CL
    YU --- CL
    DL --- PR
    VC --- PR
```

---

## License

[GNU General Public License v3.0](LICENSE)

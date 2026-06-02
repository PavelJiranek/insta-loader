# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added
- `--landscape` flag for `videos`, `youtube-meta`, and `youtube-upload` commands — produces 16:9 MP4s with blurred+darkened portrait background (`sigma=25`, 40% brightness), stored in `videos_landscape/` and `youtube_landscape/`, uploaded to a separate playlist suffixed with `· 16:9`; landscape filenames get a `_landscape` suffix (e.g. `Travel_landscape.mp4`)
- `--retry-failed` flag on `highlights` — scans local metadata for slides with `"status": "failed"` and retries only those, without fetching the full highlight list from the API
- `INSTA_SLEEP_JITTER` env var — randomises the sleep interval by ±50% by default to avoid fixed-interval request patterns; configurable (0 = no jitter, 1 = ±100%)
- `highlights --update` now re-downloads highlights previously marked `complete` when Instagram has added new slides since the last run
- `--privacy` flag on `youtube-meta` and `youtube-upload` (choices: `unlisted`, `private`, `public`; default: `unlisted`)
- `youtube-upload --update` — finds uploaded videos marked `outdated: true`, shows the list, asks for confirmation, deletes from YouTube, and re-uploads re-encoded versions
- `youtube-upload` auto-prompts to run `youtube-meta` when videos have no metadata JSON yet
- `youtube-meta` and `youtube-upload` record `recording_date` and GPS `location` in YouTube metadata, derived from the first slide date and a city/country lookup table
- Overall `[N/M]` progress counter on `youtube-upload` output lines
- Overall progress task row in the `videos` Rich progress bar showing N/M highlights done
- Architecture diagram (Mermaid) in README
- Buy Me a Coffee badge and terminal screenshot in README

### Changed
- `videos --update`: skipped highlights now print `✓ <title> — up to date` in green
- `INSTA_SLEEP` default example raised from 2 s to 3 s in docs (jitter makes effective range 1.5–4.5 s)
- Output folder restructured: all downloaded content now lives under `output/<user>/instagram/`, assembled videos under `output/<user>/videos/`, YouTube metadata under `output/<user>/youtube/`
- Elapsed time shown in completed video task rows instead of the misleading `0:00:00` remaining time

### Fixed
- **Landscape SAR mismatch in concat**: `setsar=1:1` added to `_VF_LANDSCAPE` so all landscape clips normalise before concatenation
- **Landscape missing-metadata check always scanned `videos/`**: `_check_missing_metadata` now receives the resolved `videos_dir` so `--landscape` correctly scans `videos_landscape/`
- **Playlist suffix inconsistency**: landscape playlist was `<name> 16:9` (space) while title used `· 16:9`; both now consistently use `· 16:9`
- **YouTube token refresh crashing on invalid/changed scope**: token is now auto-deleted and re-auth triggered instead of crashing
- **`is_private` check crashing when downloading own account**: skipped when `--login-user` matches the target username; also catches API rejections gracefully
- **ffmpeg SAR mismatch on ICC-profiled images**: `setsar=1:1` added to portrait `_VF` filter
- **Partial output file left after ffmpeg failure**: failed encodes are moved to Trash rather than leaving a corrupt file
- **`youtube-upload` confirmation prompt skipped when `--retry-failed` set**: all three non-interactive flags (`--update`, `--retry-failed`, `--highlight`) now suppress the bulk-download prompt
- **`.temp` files counted as valid slides**: glob patterns now exclude `*.temp` files in slide existence checks

### Security
- Username validated against Instagram's allowed character set (`[a-zA-Z0-9._]{1,30}`) at CLI entry to prevent path traversal
- Highlight folder names sanitised: leading dots stripped, control characters removed, empty result replaced with `unnamed`
- `slide['filename']` directory components stripped before glob to prevent metadata-tampering escapes
- Symlinks skipped when iterating highlight directories
- `video_path` from YouTube JSON bounds-checked against output dir before upload
- `youtube_token.json` written with `chmod 600` (owner-only)
- `youtube_token.json` and `client_secrets*.json` added to `.gitignore`
- `pytest` moved to `requirements-dev.txt`

---

## [0.3.0] — Landscape & hardening

Initial landscape video mode and security hardening pass. See `[Unreleased]` above for details.

---

## [0.2.0] — YouTube pipeline

### Added
- `youtube-meta` command: generates per-highlight YouTube metadata JSON with title, description, tags, category, privacy, recording date, and location
- `youtube-upload` command: OAuth2 upload to YouTube; creates/reuses playlist; marks videos as uploaded; handles re-upload with `--update`
- Title generation from folder names: strips sequence numbers, splits camelCase, detects part numbers (Arabic and Roman), appends date range
- Tag enrichment: country name, continent, EU membership, US state — derived from flag emojis or city name lookup
- `CITY_TO_LATLON` and `COUNTRY_TO_LATLON` lookup tables for GPS location metadata
- `videos` command: assembles downloaded slides into a single MP4 per highlight using bundled ffmpeg (`imageio-ffmpeg` — no system install required)
- `--image-duration` option (default 10 s) for controlling how long each image slide is displayed
- `--update` flag on `videos`: re-encodes only highlights newer than their existing video
- Per-highlight download stats in the progress bar: `✓N –N ✗N` (new / on-disk / failed) updated live
- `send2trash` used for all file deletions — nothing permanently removed without going to Trash first

### Fixed
- **QuickTime incompatibility**: JPEG inputs caused `yuvj420p(pc)` full-range colour to propagate; fixed with `scale=out_range=tv` and explicit colour flags
- **Audio sync drift**: concat demuxer with `-c copy` accumulated AAC rounding (~8 ms/clip); switched to concat filter with re-encode
- **Missing audio in assembled videos**: image slides had no audio stream; fixed by injecting `anullsrc` silent track into every image clip
- **Video/audio length mismatch on image clips**: `-t` was an output option; moved to input option with `-shortest`
- **Rich progress bar eating `[o]`/`[s]`/`[n]` brackets**: conflict-resolution `input()` calls moved to a pre-pass before the progress context

---

## [0.1.0] — Highlight downloader

### Added
- `highlights` command: downloads all story highlights for an Instagram account with resume support
- `--highlight` flag: case-insensitive partial name matching with interactive picker for multiple matches
- `--login-user` / `INSTA_LOGIN_USER` env var for authenticated sessions (required for private accounts)
- Per-slide `metadata.json` written after each highlight with slide list, statuses, and timestamps
- `summary` command: regenerates `summary.json` from all highlight folders on disk
- Paginated highlight fetching via the Instagram mobile API
- `INSTA_SLEEP` env var for rate-limit throttling between slide downloads
- Session persisted at `~/.config/instaloader/session-<user>` for reuse across runs

# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

- `--privacy` flag on `youtube-meta` and `youtube-upload` (choices: `unlisted`, `private`, `public`; default: `unlisted`)
- `youtube-upload --update` flag: finds uploaded videos marked `outdated: true`, shows the list, asks for confirmation, deletes them from YouTube, and re-uploads the re-encoded versions
- `youtube-upload` now detects videos with no metadata and prompts to run `youtube-meta` automatically before uploading
- Overall progress counter `[N/M]` prefix on each `youtube-upload` line so it's clear how many videos remain
- Overall `[cyan]Progress` task row added to the `videos` command Rich progress bar showing N/M highlights done
- Elapsed time baked into each video task row description when it completes (e.g. `Video: Travel (2m35s)`) — fixes the misleading `0:00:00` that Rich shows for completed tasks

### Fixed

- **ffmpeg error on video clips with no audio track**: the concat filtergraph referenced `[N:a:0]` for every clip, causing an `Invalid argument` error when a video slide had no audio stream; `_normalize_slide` now probes each video for an audio stream first and adds a silent `anullsrc` track when none is found

### Changed

- `videos --update`: skipped (up-to-date) highlights now print `✓  <title> — up to date` in green instead of dim grey



#### V3 — YouTube (implementation in progress)
- Design spec and implementation plan for `youtube-meta` and `youtube-upload` commands
- CLI wiring for `youtube-meta` and `youtube-upload` subcommands in `insta.py`; `youtube-upload` uses lazy import to avoid ImportError when `youtube_uploader.py` doesn't exist yet
- `youtube-meta` command generates per-highlight YouTube metadata JSON (title, description, tags, category, privacy)
- `youtube-upload` command uploads assembled MP4s as private YouTube videos and adds them to a "Story Highlights" playlist
- Metadata builder: `_build_youtube_meta()` with full title/description/tags generation
- Title generation from folder names: strips sequence numbers, splits camelCase, detects part numbers, appends date range
- Tag enrichment: country name, continent, EU membership, US state — derived from flag emojis or city name lookup
- Americas dual-tag: both `Americas` and `North America` / `South America`
- Flag-as-hint fallback: city-name lookup when flag emoji absent from highlight title
- Geo data maps: `COUNTRY_TO_CONTINENT`, `CITY_TO_COUNTRY`, `CITY_TO_STATE` for tag/location enrichment
- Date range helper: `_date_range()` extracts month-year span from slides, skips failed slides
- Metadata write: `_write_meta()` creates JSON files, skips overwriting already-uploaded content
- Highlight filtering: `_filter_highlights()` via partial name matching (case-insensitive)
- Metadata orchestrator: `run()` discovers highlights, filters by name if requested, skips highlights with no MP4, builds and writes metadata JSON
- OAuth 2.0 via `google-auth-oauthlib`; token cached at `~/.config/instaloader/youtube_token.json`
- `--playlist` flag (default `"Story Highlights"`) — creates playlist if not found, reuses if it exists
- `youtube_url` field stored in metadata after successful upload
- `outdated` field set to `true` when a re-encoded video has already been uploaded
- YouTube upload orchestrator: `youtube_uploader.run()` discovers metadata, filters by highlight name if requested, skips already-uploaded and missing videos, handles API errors gracefully, marks videos as uploaded, and adds them to playlists

#### V2.x — Video creator improvements
- `--update` flag on `videos` command: re-encodes only highlights whose downloaded files are newer than the existing video, and encodes highlights with no video yet; marks YouTube metadata as `outdated: true` after re-encode
- `--update` flag on `highlights` command: skips highlights already marked `"status": "complete"` in `metadata.json`; processes partial and new highlights without prompting
- Per-highlight download stats in the progress bar: `✓N –N ✗N` (newly downloaded / already on disk / failed) updated live as each slide is processed

#### V2 — Video creator
- `videos` command: assembles downloaded slides into a single MP4 per highlight using ffmpeg
- `--image-duration` option (default 10 s) controls how long each image slide is held
- `--highlight` flag for partial name matching — same behaviour as the `highlights` command
- Conflict resolution prompt before encoding starts (`[o]verwrite / [s]kip / [n]ew file`) so Rich progress bar never garbles the input
- `imageio-ffmpeg` bundled binary — no system ffmpeg install required

#### V1 — Highlight downloader
- `highlights` command: downloads all story highlights for an Instagram account with resume support
- `--highlight` flag for case-insensitive partial name matching with interactive picker for multiple matches
- Per-slide `metadata.json` written after each highlight with slide list, status, and timestamps
- `summary` command: regenerates `summary.json` from all highlight folders on disk
- Paginated highlight fetching via the Instagram mobile API (handles accounts with many highlights)
- `INSTA_SLEEP` env var for rate-limit throttling between slide downloads
- `.env` / `--login-user` support for authenticated sessions (required for private accounts and rate-limit bypass)
- Session persisted at `~/.config/instaloader/session-<user>` for reuse across runs

### Changed

- Progress bar column switched from **time remaining** to **time elapsed** — remaining time showed `0:00:00` for all completed rows, elapsed time shows how long each highlight actually took

### Fixed

- **QuickTime incompatibility**: JPEG inputs caused `yuvj420p(pc)` full-range color flag to propagate into the output; fixed with `scale=out_range=tv` filter and explicit `-color_range tv -colorspace bt709 -color_primaries bt709 -color_trc bt709` output flags
- **Audio sync drift**: using the concat demuxer with `-c copy` accumulated AAC frame-boundary rounding (~8 ms/clip, ~500 ms over 65 slides); switched to concat filter which re-encodes into a single continuous timeline
- **Missing audio in assembled videos**: image slides had no audio stream, causing the concat filter to drop audio from video slides too; fixed by adding a `anullsrc` silent stereo track to every image clip
- **Video/audio length mismatch on image clips**: `-t` was placed as an output option, causing a subtle gap at clip boundaries; moved to input option (`-loop 1 -t N -i img.jpg`) and added `-shortest`
- **Rich progress bar eating `[o]`/`[s]`/`[n]` brackets** in the conflict resolution prompt: moved all `input()` calls to a pre-pass before the `with progress:` context
- **`_resolve_conflict` silently skipping on invalid input**: added explicit error message and consistent `None` return for unrecognised choices

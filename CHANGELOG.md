# Changelog

All notable changes to this project are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

#### V3 — YouTube (design complete, implementation planned)
- Design spec and implementation plan for `youtube-meta` and `youtube-upload` commands
- `youtube-meta` will generate per-highlight YouTube metadata JSON (title, description, tags, category, privacy)
- `youtube-upload` will upload assembled MP4s as private YouTube videos and add them to a "Story Highlights" playlist
- Title generation from folder names: strips sequence numbers, splits camelCase, detects part numbers, appends date range
- Tag enrichment: country name, continent, EU membership, US state — derived from flag emojis or city name lookup
- Americas dual-tag: both `Americas` and `North America` / `South America`
- Flag-as-hint fallback: city-name lookup when flag emoji absent from highlight title
- OAuth 2.0 via `google-auth-oauthlib`; token cached at `~/.config/instaloader/youtube_token.json`
- `--playlist` flag (default `"Story Highlights"`) — creates playlist if not found, reuses if it exists
- `youtube_url` field stored in metadata after successful upload
- `outdated` field set to `true` when a re-encoded video has already been uploaded

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

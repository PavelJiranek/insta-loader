# Contributing

## Project overview

`insta-loader` is a Python 3.9+ CLI tool that:
1. Downloads Instagram story highlights via the instaloader library
2. Assembles slides (images + video clips) into MP4s using bundled ffmpeg
3. Uploads assembled videos to YouTube via OAuth2

Entry point: `insta.py` — all subcommands (`highlights`, `videos`, `youtube-meta`, `youtube-upload`, `summary`) are wired here.

## Module map

| File | Responsibility |
|---|---|
| `insta.py` | CLI entry point — argparse subcommands, config construction |
| `insta_loader/cli.py` | `Config`, `VideoConfig`, `YoutubeConfig` dataclasses |
| `insta_loader/downloader.py` | Instagram API calls (instaloader backend), slide download, resume logic |
| `insta_loader/instagrapi_downloader.py` | Alternative download backend (instagrapi), selected with `--backend instagrapi` |
| `insta_loader/organizer.py` | Folder layout, filename sanitisation, slide existence checks |
| `insta_loader/summarizer.py` | Rebuilds `summary.json` from metadata on disk |
| `insta_loader/video_creator.py` | ffmpeg pipeline — normalise slides, concat, landscape mode |
| `insta_loader/youtube_meta.py` | Build YouTube metadata JSON (title, tags, location, date) |
| `insta_loader/youtube_uploader.py` | OAuth2 token management, upload, playlist management |
| `insta_loader/progress.py` | Rich progress bar helpers shared across commands |

## Output structure

```
output/<username>/
  instagram/              ← downloaded slides + metadata.json per highlight
  videos/                 ← portrait MP4s
  videos_landscape/       ← landscape MP4s (--landscape flag)
  youtube/                ← YouTube metadata JSONs (portrait)
  youtube_landscape/      ← YouTube metadata JSONs (landscape)
```

## Dev setup

```bash
git clone https://github.com/PavelJiranek/insta-loader.git
cd insta-loader
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
```

Create `.env` for local runs:
```
INSTA_LOGIN_USER=your_instagram_username
```

Run tests:
```bash
python -m pytest -q
```

**Important:** always run tests via the venv Python — the project uses Python 3.9, and the system Python may be a different version.

## Test conventions

- Tests live in `tests/` and mirror the module they test (`test_video_creator.py` → `video_creator.py`)
- Use `tmp_path` (pytest fixture) for all file I/O — never write to real output directories
- Mock `subprocess.run` for ffmpeg calls; mock `instaloader` for API calls
- `tests/conftest.py` has an autouse fixture that mocks the summarizer in downloader tests
- Use `pytest.raises(SystemExit)` to test `sys.exit()` paths

## Commits

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>
```

Common types: `feat`, `fix`, `docs`, `refactor`, `chore`, `test`

Examples:
```
feat(downloader): add --retry-failed flag
fix(video): add setsar=1:1 to landscape filter
chore: move pytest to requirements-dev.txt
```

## Changelog

Update `CHANGELOG.md` after every commit (or logical batch) that has a user-visible effect. Add entries under `## [Unreleased]`, grouped as `### Added`, `### Changed`, `### Fixed`, `### Security`. Skip docs-only, test-only, and pure-refactor commits.

## Key design decisions

**Why `output/<user>/instagram/` subfolder?**
Keeps the three top-level output dirs clean: `instagram/`, `videos/`, `youtube/`. All downloaded content is isolated from assembled/uploaded artefacts.

**Why `send2trash` instead of `os.remove`?**
Deleted files (invalid encodes, outdated videos) go to the system Trash rather than being permanently removed. Safer for a tool that modifies personal media.

**Why `imageio-ffmpeg` instead of system ffmpeg?**
Bundles a known-good ffmpeg binary so the tool works out of the box without requiring a system install.

**Why `filter_complex` for landscape instead of `-vf`?**
The landscape pipeline needs two independent video streams from the same input (blurred background + sharp foreground overlay), which requires `filter_complex`. Portrait uses `-vf` because it only needs one stream.

**Why `setsar=1:1` in both portrait and landscape filters?**
Slides from ICC-profiled photos can have non-square sample aspect ratios (e.g. `47120:47029`). Without normalisation, the concat filter rejects clips with mismatched SARs.

**Why two download backends (instaloader + instagrapi)?**
instaloader is the default and needs no login for public accounts. When Instagram soft-blocks its `highlights_tray` requests (a generic `200 OK "fail"` response), instagrapi's fuller mobile-app emulation often still works. The backend is selected at the top of `downloader.run()`; `instagrapi_downloader.run()` reuses `organizer`, `progress`, and `summarizer` so both backends produce identical on-disk output. The instaloader path is intentionally left untouched by the instagrapi branch to avoid regressions.

**Why split `youtube/` and `youtube_landscape/`?**
Keeps portrait and landscape upload states completely independent. Either can be uploaded, re-uploaded, or deleted without touching the other.

## Credentials (never commit these)

| File | Location | Purpose |
|---|---|---|
| Instagram session | `~/.config/instaloader/session-<user>` | Reusable login cookie |
| YouTube client secrets | `~/.config/instaloader/youtube_client_secrets.json` | OAuth app credentials |
| YouTube token | `~/.config/instaloader/youtube_token.json` | OAuth access/refresh token |

All three are outside the repo or covered by `.gitignore`. Token files are written with `chmod 600`.

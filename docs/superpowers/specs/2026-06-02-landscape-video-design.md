# Landscape Video Mode Design

## Goal

Add a `--landscape` flag to the `videos`, `youtube-meta`, and `youtube-upload` commands that produces 16:9 landscape MP4s with a blurred, darkened portrait background — without touching the existing portrait pipeline.

## Architecture

Two completely parallel pipelines sharing the same source slides and highlight metadata. Portrait is the default and unchanged. Landscape is opt-in via `--landscape`.

## Output Structure

```
output/<username>/
  videos/              ← portrait MP4s (unchanged)
  videos_landscape/    ← landscape MP4s (new)
  youtube/             ← portrait YouTube metadata (unchanged)
  youtube_landscape/   ← landscape YouTube metadata (new)
```

## Components

### `insta_loader/cli.py`

Add `landscape: bool = False` to both `VideoConfig` and `YoutubeConfig`.

### `insta_loader/video_creator.py`

Add a landscape filter constant:

```python
_VF_LANDSCAPE = (
    "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
    "crop=1920:1080,gblur=sigma=25,"
    "colorchannelmixer=rr=0.4:gg=0.4:bb=0.4[bg];"
    "[0:v]scale=-1:1080[fg];"
    "[bg][fg]overlay=(W-w)/2:(H-h)/2[out]"
)
```

The filtergraph:
1. Scales and crops the portrait video to fill 1920×1080 (background layer)
2. Applies gaussian blur (sigma=25) and darkens to 40% brightness
3. Scales the original portrait to 1080px tall (foreground layer)
4. Overlays foreground centred on background

When `config.landscape` is True:
- Output folder: `base / "videos_landscape"` instead of `base / "videos"`
- `_normalize_slide` uses `_VF_LANDSCAPE` filtergraph instead of `_VF`
- `_mark_youtube_outdated` targets `youtube_landscape/` instead of `youtube/`

`_concat_clips` is unchanged — clips are already encoded to the target resolution before concatenation.

`_needs_update` receives the resolved `output_path` (already pointing at `videos_landscape/`) so update detection is independent per mode.

### `insta_loader/youtube_meta.py`

When `config.landscape` is True:
- Look for videos in `base / "videos_landscape"` instead of `base / "videos"`
- Write metadata to `base / "youtube_landscape"` instead of `base / "youtube"`
- `video_path` field in JSON: `output/<username>/videos_landscape/<name>.mp4`
- Append `· 16:9` to the generated YouTube title, e.g. `🇮🇹 Milano · May 2026 · 16:9`

### `insta_loader/youtube_uploader.py`

When `config.landscape` is True:
- Read metadata from `base / "youtube_landscape"` instead of `base / "youtube"`
- `video_path` bounds check uses `base` as before (both `videos/` and `videos_landscape/` are under `base`)
- Playlist name gets `" 16:9"` appended: e.g. `"Story Highlights"` → `"Story Highlights 16:9"`

### `insta.py`

Add `--landscape` flag to three subcommands:

```bash
python3 insta.py videos <username> --landscape [--update] [--highlight NAME]
python3 insta.py youtube-meta <username> --landscape [--highlight NAME]
python3 insta.py youtube-upload <username> --landscape [--update] [--highlight NAME]
```

`highlights`, `summary`, and `videos` without `--landscape` are completely unaffected.

## Data Flow

```
highlights/               (unchanged source)
    ↓
videos --landscape        → videos_landscape/<name>.mp4
    ↓
youtube-meta --landscape  → youtube_landscape/<name>.json
    ↓
youtube-upload --landscape → YouTube (separate uploads from portrait)
```

## Error Handling

- `videos --landscape` with no downloaded highlights: same error as portrait mode
- `youtube-meta --landscape` with no landscape videos: prints "no video" skip per highlight (same as portrait)
- `youtube-upload --landscape` with no `youtube_landscape/` dir: exits with same message as portrait mode

## Testing

- `VideoConfig` and `YoutubeConfig` default `landscape=False`
- `_normalize_slide` with `landscape=True` produces a filtergraph containing `overlay` and `gblur`
- `run(VideoConfig(..., landscape=True))` writes to `videos_landscape/`
- `_mark_youtube_outdated` with landscape=True writes `outdated=True` to `youtube_landscape/<name>.json`
- `youtube-meta --landscape` reads from `videos_landscape/` and writes to `youtube_landscape/`
- All existing portrait tests pass unchanged

## Tech Stack

- ffmpeg (bundled via `imageio-ffmpeg`) — `filter_complex` with overlay
- Python 3.9+, `Optional[str]` (not `str | None`)
- Existing `VideoConfig` / `YoutubeConfig` dataclasses in `cli.py`

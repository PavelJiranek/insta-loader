# V2 Create Videos Design Spec

## Goal

Add a `videos` command that assembles downloaded highlight slides into one MP4 per highlight, and unify all commands under a single `insta.py` entry point.

## Architecture

Two new files: `insta.py` (unified CLI entry point) and `insta_loader/video_creator.py` (all video assembly logic). `insta_loader/cli.py` gains a `VideoConfig` dataclass. The existing `highlights.py` and `summary.py` are kept as thin backward-compatible shims.

Video assembly uses ffmpeg via subprocess in a two-pass approach: normalize each slide to a temp clip (uniform codec, resolution, audio track), then concat all clips into the final MP4 using ffmpeg's concat demuxer.

## CLI

Single entry point `insta.py` with argparse subparsers:

```
python insta.py highlights <username> [--highlight NAME] [--output-dir DIR] [--login-user USER]
python insta.py videos     <username> [--highlight NAME] [--output-dir DIR]
python insta.py summary    <username> [--output-dir DIR]
python insta.py            # prints help listing all three commands
```

Each subcommand supports `--help`. The existing `highlights.py` and `summary.py` scripts are kept as shims so existing usage is not broken.

## `video_creator.py` module

Public interface: `run(config: VideoConfig) -> None`

Internal functions:

| Function | Responsibility |
|---|---|
| `_collect_slides(highlight_dir)` | Read `metadata.json`, return slides sorted by index, skipping `"failed"` ones |
| `_resolve_conflict(output_path)` | If file exists, prompt user: `[o]verwrite / [s]kip / [n]ew` (new appends `_1`, `_2`, etc.) |
| `_normalize_slide(slide_path, index, tmp_dir, is_video)` | Convert one slide to a normalized temp `.mp4` via ffmpeg |
| `_concat_clips(clip_paths, output_path)` | Write a concat list file and run ffmpeg concat demuxer |

## Video assembly rules

**Images** (`jpg`): rendered as a 15-second silent video clip.
```
ffmpeg -loop 1 -t 15 -i slide.jpg -vf scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2 -r 30 -c:v libx264 -pix_fmt yuv420p -an temp_N.mp4
```

**Videos** (`mp4`): re-encoded to h264/aac at 1080×1920, full duration with audio preserved.
```
ffmpeg -i slide.mp4 -vf scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2 -c:v libx264 -pix_fmt yuv420p -c:a aac temp_N.mp4
```

**Concat**: write a `list.txt` with `file 'temp_N.mp4'` entries, then:
```
ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4
```

Temp files are written to a `tempfile.mkdtemp()` directory and deleted after each highlight (success or failure).

## Output

Files saved to `output/<username>/videos/<HighlightName>.mp4`.

If the videos directory does not exist it is created automatically.

## Conflict resolution

If the output file already exists, prompt:
```
'Travel.mp4' already exists. [o]verwrite / [s]kip / [n]ew file (Travel_1.mp4)?
```
- `o` — delete existing file and write new one
- `s` — skip this highlight entirely
- `n` — write to `<name>_1.mp4`, incrementing suffix until a free name is found

## Progress output

Uses Rich (same as the downloader). Per highlight:
- A progress bar showing `Normalizing slide 3/8 — Travel_03_20250310.jpg`
- A completion line: `✓  Travel.mp4 — 8 slides, 2m 14s`
- On skip: `–  Travel.mp4 skipped`
- On failure: `✗  Travel — ffmpeg error on slide 3 (see above)`

## Error handling

- **ffmpeg not on PATH**: print `✗  ffmpeg not found. Install it: https://ffmpeg.org/download.html` and exit 1 before any work begins.
- **No highlights found**: print `✗  No downloaded highlights found at <path>` and exit 1.
- **Highlight has no non-failed slides**: skip it with a warning, continue to next.
- **ffmpeg error on a slide**: mark the highlight as failed, print the ffmpeg stderr, clean up temp dir, continue to next highlight.

## `VideoConfig` dataclass

Added to `insta_loader/cli.py`:

```python
@dataclass
class VideoConfig:
    username: str
    highlight: Optional[str] = None
    output_dir: Optional[str] = None
```

## Files

| File | Change |
|---|---|
| `insta.py` | Create — unified CLI entry point with subparsers |
| `insta_loader/video_creator.py` | Create — video assembly logic |
| `insta_loader/cli.py` | Modify — add `VideoConfig` dataclass |
| `highlights.py` | Modify — become shim calling existing `downloader.run()` |
| `summary.py` | Modify — become shim calling existing `summarizer.run()` |
| `requirements.txt` | No change — ffmpeg is a system dependency, not a Python package |
| `README.md` | Update — replace per-script commands section with unified `insta.py` reference |

## Testing

- `tests/test_video_creator.py` — unit tests for each internal function, mocking subprocess calls
- `_collect_slides`: returns slides sorted by index, excludes failed
- `_resolve_conflict`: overwrite/skip/new-suffix prompts
- `_normalize_slide`: correct ffmpeg args for image vs video
- `_concat_clips`: correct list file content and concat command
- `run`: ffmpeg-not-found exit, no-highlights exit, skips highlight with zero valid slides

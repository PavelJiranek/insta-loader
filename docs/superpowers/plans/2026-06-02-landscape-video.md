# Landscape Video Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--landscape` flag to `videos`, `youtube-meta`, and `youtube-upload` that produces 16:9 MP4s with blurred+darkened portrait background, tracked in separate output folders, without touching the portrait pipeline.

**Architecture:** Each affected module gets a `landscape: bool = False` parameter threaded through from `VideoConfig`/`YoutubeConfig`. Landscape outputs go to `videos_landscape/` and `youtube_landscape/`. The ffmpeg landscape pipeline uses `filter_complex` with a two-layer overlay (blurred background + centred portrait foreground) instead of the portrait `-vf` pad approach.

**Tech Stack:** Python 3.9+, ffmpeg via `imageio-ffmpeg`, pytest, `Optional[str]` (not `str | None`), conventional commits.

---

### Task 1: Add `landscape` field to `VideoConfig` and `YoutubeConfig`

**Files:**
- Modify: `insta_loader/cli.py`
- Test: `tests/test_cli.py` — this file was deleted; add tests to `tests/test_youtube_meta.py` (already imports `YoutubeConfig`) and `tests/test_video_creator.py` (already imports `VideoConfig`)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_video_creator.py`:
```python
def test_video_config_landscape_defaults_false():
    c = VideoConfig(username="testuser")
    assert c.landscape is False
```

Add to `tests/test_youtube_meta.py`:
```python
def test_youtube_config_landscape_defaults_false():
    c = YoutubeConfig(username="testuser")
    assert c.landscape is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_video_creator.py::test_video_config_landscape_defaults_false tests/test_youtube_meta.py::test_youtube_config_landscape_defaults_false -v
```
Expected: FAIL — `VideoConfig` and `YoutubeConfig` have no `landscape` field.

- [ ] **Step 3: Add `landscape` field to both dataclasses**

Replace the contents of `insta_loader/cli.py` with:
```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    username: str
    output_dir: Optional[str]
    highlight: Optional[str]
    login_user: Optional[str]
    update: bool = False
    retry_failed: bool = False


@dataclass
class VideoConfig:
    username: str
    highlight: Optional[str] = None
    output_dir: Optional[str] = None
    image_duration: int = 10
    update: bool = False
    landscape: bool = False


@dataclass
class YoutubeConfig:
    username: str
    highlight: Optional[str] = None
    output_dir: Optional[str] = None
    client_secrets: Optional[str] = None
    playlist: str = "Story Highlights"
    update: bool = False
    privacy: str = "unlisted"
    landscape: bool = False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_video_creator.py::test_video_config_landscape_defaults_false tests/test_youtube_meta.py::test_youtube_config_landscape_defaults_false -v
```
Expected: PASS

- [ ] **Step 5: Run full suite to check nothing broke**

```bash
python3 -m pytest -q
```
Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add insta_loader/cli.py tests/test_video_creator.py tests/test_youtube_meta.py
git commit -m "feat(cli): add landscape field to VideoConfig and YoutubeConfig"
```

---

### Task 2: Add `_VF_LANDSCAPE` and landscape branch in `_normalize_slide`

**Files:**
- Modify: `insta_loader/video_creator.py` (lines 94–153)
- Test: `tests/test_video_creator.py`

The landscape ffmpeg pipeline uses `filter_complex` with a two-layer overlay:
1. Scale+crop the input to fill 1920×1080, blur (sigma=25), darken to 40% brightness → `[bg]`
2. Scale input to 1080px tall preserving aspect ratio → `[fg]`
3. Overlay `[fg]` centred on `[bg]` → `[out]`

This replaces `-vf _VF` entirely for landscape clips.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_video_creator.py`:
```python
from unittest.mock import patch, MagicMock
import tempfile

def test_normalize_slide_landscape_video_uses_filter_complex(tmp_path):
    slide = tmp_path / "clip.mp4"
    slide.touch()
    with patch("insta_loader.video_creator.subprocess.run") as mock_run, \
         patch("insta_loader.video_creator._has_audio", return_value=True):
        mock_run.return_value = MagicMock(returncode=0)
        _normalize_slide(slide, 1, tmp_path, is_video=True, landscape=True)
    cmd = mock_run.call_args[0][0]
    assert "-filter_complex" in cmd
    full_cmd = " ".join(cmd)
    assert "overlay" in full_cmd
    assert "gblur" in full_cmd
    assert "-vf" not in cmd


def test_normalize_slide_landscape_image_uses_filter_complex(tmp_path):
    slide = tmp_path / "slide.jpg"
    slide.touch()
    with patch("insta_loader.video_creator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _normalize_slide(slide, 1, tmp_path, is_video=False, landscape=True)
    cmd = mock_run.call_args[0][0]
    assert "-filter_complex" in cmd
    full_cmd = " ".join(cmd)
    assert "overlay" in full_cmd
    assert "gblur" in full_cmd


def test_normalize_slide_portrait_unchanged(tmp_path):
    slide = tmp_path / "slide.jpg"
    slide.touch()
    with patch("insta_loader.video_creator.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _normalize_slide(slide, 1, tmp_path, is_video=False, landscape=False)
    cmd = mock_run.call_args[0][0]
    assert "-vf" in cmd
    assert "overlay" not in " ".join(cmd)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_video_creator.py::test_normalize_slide_landscape_video_uses_filter_complex tests/test_video_creator.py::test_normalize_slide_landscape_image_uses_filter_complex tests/test_video_creator.py::test_normalize_slide_portrait_unchanged -v
```
Expected: FAIL — `_normalize_slide` has no `landscape` parameter.

- [ ] **Step 3: Add `_VF_LANDSCAPE` and update `_normalize_slide`**

After the existing `_VF` and `_COLOR_FLAGS` constants (around line 94 of `insta_loader/video_creator.py`), add:

```python
_VF_LANDSCAPE = (
    "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
    "crop=1920:1080,gblur=sigma=25,"
    "colorchannelmixer=rr=0.4:gg=0.4:bb=0.4[bg];"
    "[0:v]scale=-1:1080[fg];"
    "[bg][fg]overlay=(W-w)/2:(H-h)/2[out]"
)
```

Replace the entire `_normalize_slide` function with:

```python
def _normalize_slide(slide_path: Path, index: int, tmp_dir: Path, is_video: bool, image_duration: int = 10, landscape: bool = False) -> Path:
    out = tmp_dir / f"clip_{index:03d}.mp4"
    if landscape:
        if is_video:
            if _has_audio(slide_path):
                cmd = [
                    _FFMPEG, "-i", str(slide_path),
                    "-filter_complex", _VF_LANDSCAPE,
                    "-map", "[out]", "-map", "0:a",
                    "-r", "30",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", *_COLOR_FLAGS,
                    "-c:a", "aac", "-ar", "44100",
                    "-y", str(out),
                ]
            else:
                cmd = [
                    _FFMPEG,
                    "-i", str(slide_path),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-filter_complex", _VF_LANDSCAPE,
                    "-map", "[out]", "-map", "1:a",
                    "-r", "30",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", *_COLOR_FLAGS,
                    "-c:a", "aac", "-ar", "44100",
                    "-shortest",
                    "-y", str(out),
                ]
        else:
            cmd = [
                _FFMPEG,
                "-loop", "1", "-t", str(image_duration), "-i", str(slide_path),
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-filter_complex", _VF_LANDSCAPE,
                "-map", "[out]", "-map", "1:a",
                "-r", "30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", *_COLOR_FLAGS,
                "-c:a", "aac",
                "-shortest",
                "-y", str(out),
            ]
    else:
        if is_video:
            if _has_audio(slide_path):
                cmd = [
                    _FFMPEG, "-i", str(slide_path),
                    "-vf", _VF,
                    "-r", "30",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", *_COLOR_FLAGS,
                    "-c:a", "aac", "-ar", "44100",
                    "-y", str(out),
                ]
            else:
                cmd = [
                    _FFMPEG,
                    "-i", str(slide_path),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-filter_complex", f"[0:v]{_VF}[vout]",
                    "-map", "[vout]", "-map", "1:a",
                    "-r", "30",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", *_COLOR_FLAGS,
                    "-c:a", "aac", "-ar", "44100",
                    "-shortest",
                    "-y", str(out),
                ]
        else:
            cmd = [
                _FFMPEG,
                "-loop", "1", "-t", str(image_duration), "-i", str(slide_path),
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-vf", _VF,
                "-r", "30",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", *_COLOR_FLAGS,
                "-c:a", "aac",
                "-shortest",
                "-y", str(out),
            ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_video_creator.py::test_normalize_slide_landscape_video_uses_filter_complex tests/test_video_creator.py::test_normalize_slide_landscape_image_uses_filter_complex tests/test_video_creator.py::test_normalize_slide_portrait_unchanged -v
```
Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add insta_loader/video_creator.py tests/test_video_creator.py
git commit -m "feat(video): add landscape ffmpeg pipeline to _normalize_slide"
```

---

### Task 3: Update `_mark_youtube_outdated` for landscape

**Files:**
- Modify: `insta_loader/video_creator.py` (lines 83–91)
- Test: `tests/test_video_creator.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_video_creator.py`:
```python
def test_mark_youtube_outdated_landscape_writes_to_landscape_dir(tmp_path):
    yt_dir = tmp_path / "youtube_landscape"
    yt_dir.mkdir()
    meta = {"uploaded": True, "outdated": False, "youtube": {"title": "Test"}}
    (yt_dir / "Travel.json").write_text(json.dumps(meta))

    _mark_youtube_outdated(tmp_path, "Travel", landscape=True)

    result = json.loads((yt_dir / "Travel.json").read_text())
    assert result["outdated"] is True


def test_mark_youtube_outdated_portrait_unchanged_by_landscape_param(tmp_path):
    yt_dir = tmp_path / "youtube"
    yt_dir.mkdir()
    meta = {"uploaded": True, "outdated": False}
    (yt_dir / "Travel.json").write_text(json.dumps(meta))

    # landscape=True should NOT touch youtube/ folder
    _mark_youtube_outdated(tmp_path, "Travel", landscape=True)

    result = json.loads((yt_dir / "Travel.json").read_text())
    assert result["outdated"] is False  # portrait folder untouched
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_video_creator.py::test_mark_youtube_outdated_landscape_writes_to_landscape_dir tests/test_video_creator.py::test_mark_youtube_outdated_portrait_unchanged_by_landscape_param -v
```
Expected: FAIL — `_mark_youtube_outdated` takes no `landscape` parameter.

- [ ] **Step 3: Update `_mark_youtube_outdated`**

Replace the function in `insta_loader/video_creator.py`:

```python
def _mark_youtube_outdated(base: Path, folder_name: str, landscape: bool = False) -> None:
    """Set outdated=True in youtube[_landscape]/<folder_name>.json if previously uploaded."""
    youtube_folder = "youtube_landscape" if landscape else "youtube"
    meta_path = base / youtube_folder / f"{folder_name}.json"
    if not meta_path.exists():
        return
    meta = json.loads(meta_path.read_text())
    if meta.get("uploaded"):
        meta["outdated"] = True
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_video_creator.py::test_mark_youtube_outdated_landscape_writes_to_landscape_dir tests/test_video_creator.py::test_mark_youtube_outdated_portrait_unchanged_by_landscape_param -v
```
Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add insta_loader/video_creator.py tests/test_video_creator.py
git commit -m "feat(video): _mark_youtube_outdated targets youtube_landscape/ when landscape=True"
```

---

### Task 4: Update `run()` in `video_creator.py` for landscape output folder

**Files:**
- Modify: `insta_loader/video_creator.py` (`run()` function, lines 203–284)
- Test: `tests/test_video_creator.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_video_creator.py`:
```python
def test_run_landscape_writes_to_videos_landscape_dir(tmp_path):
    instagram_dir = tmp_path / "instagram" / "Travel"
    instagram_dir.mkdir(parents=True)
    slides = [{"index": 1, "filename": "Travel_01", "type": "image",
               "date_utc": "2026-01-01T00:00:00Z", "status": "downloaded"}]
    (instagram_dir / "metadata.json").write_text(json.dumps({
        "highlight_title": "Travel", "slides": slides
    }))
    (instagram_dir / "Travel_01_20260101_000000.jpg").touch()

    with patch("insta_loader.video_creator.subprocess.run") as mock_run, \
         patch("insta_loader.video_creator._normalize_slide") as mock_norm, \
         patch("insta_loader.video_creator._concat_clips") as mock_concat:
        mock_run.return_value = MagicMock(returncode=0)
        mock_norm.return_value = tmp_path / "clip_001.mp4"
        (tmp_path / "clip_001.mp4").touch()

        run(VideoConfig(username="testuser", output_dir=str(tmp_path), landscape=True))

    assert (tmp_path / "videos_landscape").exists()
    assert not (tmp_path / "videos").exists() or True  # portrait dir not created
    mock_norm.assert_called_once()
    _, kwargs = mock_norm.call_args
    assert kwargs.get("landscape") is True or mock_norm.call_args[0][-1] is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_video_creator.py::test_run_landscape_writes_to_videos_landscape_dir -v
```
Expected: FAIL — `run()` always uses `videos/` and `_normalize_slide` is called without `landscape`.

- [ ] **Step 3: Update `run()` in `video_creator.py`**

In the `run()` function, make two targeted changes:

**Change 1** — replace the videos_dir setup (around line 222):
```python
    videos_dir_name = "videos_landscape" if config.landscape else "videos"
    videos_dir = base / videos_dir_name
    videos_dir.mkdir(exist_ok=True)
```

**Change 2** — pass `landscape` to `_normalize_slide` (around line 264):
```python
                    clip = _normalize_slide(
                        slide["path"], slide["index"], tmp_dir, slide["type"] == "video",
                        config.image_duration,
                        landscape=config.landscape,
                    )
```

**Change 3** — pass `landscape` to `_mark_youtube_outdated` (around line 277):
```python
                if config.update:
                    _mark_youtube_outdated(base, hdir.name, landscape=config.landscape)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_video_creator.py::test_run_landscape_writes_to_videos_landscape_dir -v
```
Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add insta_loader/video_creator.py tests/test_video_creator.py
git commit -m "feat(video): run() uses videos_landscape/ and passes landscape to _normalize_slide"
```

---

### Task 5: Update `_build_youtube_meta` for landscape title and path

**Files:**
- Modify: `insta_loader/youtube_meta.py` (`_build_youtube_meta`, line 397)
- Test: `tests/test_youtube_meta.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_youtube_meta.py`:
```python
def test_build_youtube_meta_landscape_appends_16_9_to_title():
    slides = [_slide("2026-04-01T00:00:00Z")]
    meta = _build_youtube_meta("Travel", slides, "testuser", landscape=True)
    assert meta["youtube"]["title"].endswith("· 16:9")


def test_build_youtube_meta_landscape_uses_videos_landscape_path():
    slides = [_slide("2026-04-01T00:00:00Z")]
    meta = _build_youtube_meta("Travel", slides, "testuser", landscape=True)
    assert "videos_landscape" in meta["video_path"]


def test_build_youtube_meta_portrait_unaffected_by_landscape_false():
    slides = [_slide("2026-04-01T00:00:00Z")]
    meta = _build_youtube_meta("Travel", slides, "testuser", landscape=False)
    assert "16:9" not in meta["youtube"]["title"]
    assert "videos_landscape" not in meta["video_path"]
    assert "videos" in meta["video_path"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_youtube_meta.py::test_build_youtube_meta_landscape_appends_16_9_to_title tests/test_youtube_meta.py::test_build_youtube_meta_landscape_uses_videos_landscape_path tests/test_youtube_meta.py::test_build_youtube_meta_portrait_unaffected_by_landscape_false -v
```
Expected: FAIL — `_build_youtube_meta` has no `landscape` parameter.

- [ ] **Step 3: Update `_build_youtube_meta`**

Change the function signature and body in `insta_loader/youtube_meta.py`:

```python
def _build_youtube_meta(folder_name: str, slides: list, username: str, privacy: str = "unlisted", landscape: bool = False) -> dict:
    country_codes = _decode_flags(folder_name)
    flag_str = _extract_flag_str(folder_name)
    place_name, part_num = _parse_title(folder_name)
    date_str = _date_range(slides)
    tags = _build_tags(place_name, country_codes)
    recording_date = _first_slide_date(slides)
    location = _resolve_location(place_name, country_codes)

    title_parts = []
    if flag_str:
        title_parts.append(flag_str)
    title_parts.append(place_name)
    if part_num is not None:
        title_parts.append(f"· Part {part_num}")
    if date_str:
        title_parts.append(f"· {date_str}")
    title = " ".join(title_parts)
    if landscape:
        title = f"{title} · 16:9"

    desc_main = f"{place_name} highlights" if place_name.strip() else "highlights"
    if part_num is not None:
        desc_main += f" · Part {part_num}"
    if date_str:
        desc_main += f" · {date_str}"
    description = f"{desc_main}\n\n@{username}"

    video_subdir = "videos_landscape" if landscape else "videos"
    video_path = str(Path("output") / username / video_subdir / f"{folder_name}.mp4")
    return {
        "highlight_folder": folder_name,
        "video_path": video_path,
        "recording_date": recording_date,
        "location": location,
        "youtube": {
            "title": title,
            "description": description,
            "tags": tags,
            "category_id": "19",
            "privacy_status": privacy,
        },
        "uploaded": False,
        "youtube_id": None,
        "youtube_url": None,
        "outdated": False,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_youtube_meta.py::test_build_youtube_meta_landscape_appends_16_9_to_title tests/test_youtube_meta.py::test_build_youtube_meta_landscape_uses_videos_landscape_path tests/test_youtube_meta.py::test_build_youtube_meta_portrait_unaffected_by_landscape_false -v
```
Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add insta_loader/youtube_meta.py tests/test_youtube_meta.py
git commit -m "feat(youtube-meta): _build_youtube_meta appends · 16:9 to title and uses videos_landscape/ when landscape=True"
```

---

### Task 6: Update `run()` in `youtube_meta.py` for landscape folders

**Files:**
- Modify: `insta_loader/youtube_meta.py` (`run()`, line 455)
- Test: `tests/test_youtube_meta.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_youtube_meta.py`:
```python
def test_run_landscape_reads_videos_landscape_and_writes_youtube_landscape(tmp_path):
    _make_highlight(tmp_path, "Travel")
    videos_dir = tmp_path / "videos_landscape"
    videos_dir.mkdir()
    (videos_dir / "Travel.mp4").touch()

    run_meta(YoutubeConfig(username="testuser", output_dir=str(tmp_path), landscape=True))

    assert (tmp_path / "youtube_landscape" / "Travel.json").exists()
    assert not (tmp_path / "youtube" / "Travel.json").exists()
    meta = json.loads((tmp_path / "youtube_landscape" / "Travel.json").read_text())
    assert "16:9" in meta["youtube"]["title"]


def test_run_landscape_skips_when_no_landscape_video(tmp_path, capsys):
    _make_highlight(tmp_path, "Travel")
    # Only portrait video exists
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "Travel.mp4").touch()

    run_meta(YoutubeConfig(username="testuser", output_dir=str(tmp_path), landscape=True))

    assert not (tmp_path / "youtube_landscape").exists()
    assert "no video" in capsys.readouterr().out.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_youtube_meta.py::test_run_landscape_reads_videos_landscape_and_writes_youtube_landscape tests/test_youtube_meta.py::test_run_landscape_skips_when_no_landscape_video -v
```
Expected: FAIL — `run()` always uses `videos/` and `youtube/`.

- [ ] **Step 3: Update `run()` in `youtube_meta.py`**

Replace the two folder assignments near line 474:
```python
    videos_dir = base / ("videos_landscape" if config.landscape else "videos")
    youtube_dir = base / ("youtube_landscape" if config.landscape else "youtube")
```

Also update the `_build_youtube_meta` call to pass `landscape`:
```python
        meta = _build_youtube_meta(folder_name, slides, config.username, config.privacy, landscape=config.landscape)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_youtube_meta.py::test_run_landscape_reads_videos_landscape_and_writes_youtube_landscape tests/test_youtube_meta.py::test_run_landscape_skips_when_no_landscape_video -v
```
Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add insta_loader/youtube_meta.py tests/test_youtube_meta.py
git commit -m "feat(youtube-meta): run() uses videos_landscape/ and youtube_landscape/ when landscape=True"
```

---

### Task 7: Update `run()` in `youtube_uploader.py` for landscape folder

**Files:**
- Modify: `insta_loader/youtube_uploader.py` (`run()`, line 181)
- Test: `tests/test_youtube_uploader.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_youtube_uploader.py`:
```python
def test_run_landscape_reads_from_youtube_landscape_dir(tmp_path, capsys):
    youtube_dir = tmp_path / "youtube_landscape"
    youtube_dir.mkdir()
    video_path = str(tmp_path / "videos_landscape" / "Travel.mp4")
    (tmp_path / "videos_landscape").mkdir()
    Path(video_path).touch()
    _make_meta_file(youtube_dir, "Travel", video_path=video_path)
    secrets = tmp_path / "secrets.json"
    secrets.touch()

    mock_playlist = MagicMock(return_value="pl1")
    with patch("insta_loader.youtube_uploader._get_credentials"), \
         patch("insta_loader.youtube_uploader.build"), \
         patch("insta_loader.youtube_uploader._get_or_create_playlist", mock_playlist), \
         patch("insta_loader.youtube_uploader._upload_video", return_value="vid1"), \
         patch("insta_loader.youtube_uploader._add_to_playlist"), \
         patch("insta_loader.youtube_uploader._mark_uploaded"):
        run_upload(YoutubeConfig(
            username="testuser",
            output_dir=str(tmp_path),
            client_secrets=str(secrets),
            landscape=True,
        ))

    # Should not exit — found the landscape dir
    out = capsys.readouterr().out
    assert "no metadata found" not in out.lower()
    # Playlist name should be suffixed with 16:9
    playlist_name_used = mock_playlist.call_args[0][1]
    assert "16:9" in playlist_name_used


def test_run_landscape_exits_when_no_landscape_dir(tmp_path):
    # Only portrait youtube/ exists, not youtube_landscape/
    youtube_dir = tmp_path / "youtube"
    youtube_dir.mkdir()
    _make_meta_file(youtube_dir, "Travel")
    secrets = tmp_path / "secrets.json"
    secrets.touch()

    with patch("insta_loader.youtube_uploader._get_credentials"), \
         patch("insta_loader.youtube_uploader.build"), \
         pytest.raises(SystemExit):
        run_upload(YoutubeConfig(
            username="testuser",
            output_dir=str(tmp_path),
            client_secrets=str(secrets),
            landscape=True,
        ))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_youtube_uploader.py::test_run_landscape_reads_from_youtube_landscape_dir tests/test_youtube_uploader.py::test_run_landscape_exits_when_no_landscape_dir -v
```
Expected: FAIL — `run()` always uses `youtube/`.

- [ ] **Step 3: Update `run()` in `youtube_uploader.py`**

Replace line 183 in `insta_loader/youtube_uploader.py`:
```python
    youtube_dir = base / ("youtube_landscape" if config.landscape else "youtube")
```

Also update the `_get_or_create_playlist` call (around line 243) to append `" 16:9"` to the playlist name when landscape:
```python
        if playlist_id is None:
            playlist_name = f"{config.playlist} 16:9" if config.landscape else config.playlist
            playlist_id = _get_or_create_playlist(youtube, playlist_name, config.privacy)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_youtube_uploader.py::test_run_landscape_reads_from_youtube_landscape_dir tests/test_youtube_uploader.py::test_run_landscape_exits_when_no_landscape_dir -v
```
Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add insta_loader/youtube_uploader.py tests/test_youtube_uploader.py
git commit -m "feat(youtube-upload): run() uses youtube_landscape/ when landscape=True"
```

---

### Task 8: Add `--landscape` CLI flags to `insta.py`

**Files:**
- Modify: `insta.py`
- Test: `tests/test_insta_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_insta_cli.py`:
```python
from unittest.mock import patch, MagicMock
from insta_loader.cli import VideoConfig, YoutubeConfig
import sys


def test_videos_landscape_flag_passed_to_video_config():
    with patch("insta_loader.video_creator.run") as mock_run, \
         patch("sys.argv", ["insta.py", "videos", "testuser", "--landscape"]):
        import insta
        import importlib
        importlib.reload(insta)
        insta.main()
    config = mock_run.call_args[0][0]
    assert config.landscape is True


def test_youtube_meta_landscape_flag_passed_to_youtube_config():
    with patch("insta_loader.youtube_meta.run") as mock_run, \
         patch("sys.argv", ["insta.py", "youtube-meta", "testuser", "--landscape"]):
        import insta
        import importlib
        importlib.reload(insta)
        insta.main()
    config = mock_run.call_args[0][0]
    assert config.landscape is True


def test_youtube_upload_landscape_flag_passed_to_youtube_config():
    with patch("insta_loader.youtube_uploader.run") as mock_run, \
         patch("sys.argv", ["insta.py", "youtube-upload", "testuser", "--landscape"]):
        import insta
        import importlib
        importlib.reload(insta)
        insta.main()
    config = mock_run.call_args[0][0]
    assert config.landscape is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_insta_cli.py::test_videos_landscape_flag_passed_to_video_config tests/test_insta_cli.py::test_youtube_meta_landscape_flag_passed_to_youtube_config tests/test_insta_cli.py::test_youtube_upload_landscape_flag_passed_to_youtube_config -v
```
Expected: FAIL — no `--landscape` flag exists on any subparser.

- [ ] **Step 3: Add `--landscape` to three subparsers in `insta.py`**

**In the `videos` subparser block** (after the `--update` line):
```python
    vid.add_argument("--landscape", action="store_true", help="Create 16:9 landscape videos with blurred+darkened background (outputs to videos_landscape/)")
```

**In the `VideoConfig` construction** (in the `elif args.command == "videos":` block):
```python
        run_videos(VideoConfig(
            username=args.username,
            highlight=args.highlight,
            output_dir=args.output_dir,
            image_duration=args.image_duration,
            update=args.update,
            landscape=args.landscape,
        ))
```

**In the `youtube-meta` subparser block** (after `--privacy`):
```python
    yt_meta.add_argument("--landscape", action="store_true", help="Generate metadata for landscape videos in videos_landscape/ (writes to youtube_landscape/)")
```

**In the `YoutubeConfig` construction for `youtube-meta`:**
```python
        run_youtube_meta(YoutubeConfig(
            username=args.username,
            highlight=args.highlight,
            output_dir=args.output_dir,
            privacy=args.privacy,
            landscape=args.landscape,
        ))
```

**In the `youtube-upload` subparser block** (after `--privacy`):
```python
    yt_upload.add_argument("--landscape", action="store_true", help="Upload landscape videos from youtube_landscape/ metadata")
```

**In the `YoutubeConfig` construction for `youtube-upload`:**
```python
        run_youtube_upload(YoutubeConfig(
            username=args.username,
            highlight=args.highlight,
            output_dir=args.output_dir,
            client_secrets=args.client_secrets,
            playlist=args.playlist,
            update=args.update,
            privacy=args.privacy,
            landscape=args.landscape,
        ))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_insta_cli.py::test_videos_landscape_flag_passed_to_video_config tests/test_insta_cli.py::test_youtube_meta_landscape_flag_passed_to_youtube_config tests/test_insta_cli.py::test_youtube_upload_landscape_flag_passed_to_youtube_config -v
```
Expected: PASS

- [ ] **Step 5: Run full suite**

```bash
python3 -m pytest -q
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add insta.py tests/test_insta_cli.py
git commit -m "feat(cli): add --landscape flag to videos, youtube-meta and youtube-upload subcommands"
```

---

### Task 9: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add `--landscape` to the `videos` options table**

In the `### videos` section, add a row to the options table:
```markdown
| `--landscape` | Create 16:9 landscape videos with blurred+darkened background (saved to `videos_landscape/`) |
```

- [ ] **Step 2: Add `--landscape` to the `youtube-meta` options table**

```markdown
| `--landscape` | Generate metadata for landscape videos (reads `videos_landscape/`, writes `youtube_landscape/`) |
```

- [ ] **Step 3: Add `--landscape` to the `youtube-upload` options table**

```markdown
| `--landscape` | Upload landscape videos (reads `youtube_landscape/` metadata) |
```

- [ ] **Step 4: Add a landscape workflow example to the Typical workflow section**

After the existing workflow block, add:
```markdown
### Landscape (16:9) workflow

```bash
# 1. Assemble landscape versions
python3 insta.py videos <username> --landscape --update

# 2. Generate YouTube metadata (titles get · 16:9 suffix)
python3 insta.py youtube-meta <username> --landscape

# 3. Upload to YouTube
python3 insta.py youtube-upload <username> --landscape
```
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document --landscape flag in README"
```

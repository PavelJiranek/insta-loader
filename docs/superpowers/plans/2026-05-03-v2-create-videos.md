# V2 Create Videos Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `videos` command that assembles downloaded highlight slides into one MP4 per highlight, and unify all commands under a single `insta.py` entry point.

**Architecture:** A new `insta_loader/video_creator.py` module handles all video assembly logic using ffmpeg via subprocess in a two-pass approach: normalize each slide to a temp clip at 1080×1920 h264/aac, then concat with ffmpeg's concat demuxer. A new `insta.py` entry point wraps all three commands (`highlights`, `videos`, `summary`) as argparse subcommands. The existing `highlights.py` and `summary.py` are already thin shims and require no changes.

**Tech Stack:** Python 3.9+, ffmpeg (system dependency), Rich (progress), pytest, conventional commits. All type hints use `Optional[str]` not `str | None`.

---

## File map

| File | Action |
|---|---|
| `insta_loader/cli.py` | Modify — add `VideoConfig` dataclass |
| `insta_loader/video_creator.py` | Create — all video assembly logic |
| `insta_loader/progress.py` | Modify — add `add_video_task` |
| `insta.py` | Create — unified CLI entry point |
| `tests/test_video_creator.py` | Create — unit tests |
| `tests/test_insta_cli.py` | Create — CLI routing tests |
| `README.md` | Modify — replace per-script section with unified CLI |

`highlights.py` and `summary.py` are already thin shims — no changes needed.

---

### Task 1: `VideoConfig` dataclass

**Files:**
- Modify: `insta_loader/cli.py`
- Test: `tests/test_video_creator.py` (created here, first test)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_video_creator.py
from insta_loader.cli import VideoConfig

def test_video_config_defaults():
    c = VideoConfig(username="natgeo")
    assert c.highlight is None
    assert c.output_dir is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/test_video_creator.py::test_video_config_defaults -v
```

Expected: `ImportError: cannot import name 'VideoConfig'`

- [ ] **Step 3: Add `VideoConfig` to `insta_loader/cli.py`**

Add after the existing `Config` dataclass (around line 14):

```python
@dataclass
class VideoConfig:
    username: str
    highlight: Optional[str] = None
    output_dir: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/test_video_creator.py::test_video_config_defaults -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add insta_loader/cli.py tests/test_video_creator.py
git commit -m "feat(cli): add VideoConfig dataclass"
```

---

### Task 2: `_collect_slides`

**Files:**
- Create: `insta_loader/video_creator.py`
- Modify: `tests/test_video_creator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_video_creator.py  (add to existing file)
import json
from pathlib import Path
from insta_loader.video_creator import _collect_slides

def _write_meta(folder: Path, slides: list) -> None:
    (folder / "metadata.json").write_text(json.dumps({"highlight_title": folder.name, "slides": slides}))


def test_collect_slides_returns_sorted_by_index(tmp_path):
    _write_meta(tmp_path, [
        {"index": 2, "filename": "Test_02", "type": "image", "status": "downloaded"},
        {"index": 1, "filename": "Test_01", "type": "video", "status": "downloaded"},
    ])
    (tmp_path / "Test_01_20250101_000000.mp4").touch()
    (tmp_path / "Test_02_20250101_000001.jpg").touch()

    result = _collect_slides(tmp_path)

    assert [s["index"] for s in result] == [1, 2]


def test_collect_slides_excludes_failed(tmp_path):
    _write_meta(tmp_path, [
        {"index": 1, "filename": "Test_01", "type": "video", "status": "downloaded"},
        {"index": 2, "filename": "Test_02", "type": "image", "status": "failed"},
        {"index": 3, "filename": "Test_03", "type": "image", "status": "downloaded"},
    ])
    (tmp_path / "Test_01_20250101_000000.mp4").touch()
    (tmp_path / "Test_03_20250101_000001.jpg").touch()

    result = _collect_slides(tmp_path)

    assert len(result) == 2
    assert all(s["index"] != 2 for s in result)


def test_collect_slides_returns_correct_type_and_path(tmp_path):
    _write_meta(tmp_path, [
        {"index": 1, "filename": "Test_01", "type": "video", "status": "downloaded"},
    ])
    actual_file = tmp_path / "Test_01_20250101_000000.mp4"
    actual_file.touch()

    result = _collect_slides(tmp_path)

    assert result[0]["type"] == "video"
    assert result[0]["path"] == actual_file


def test_collect_slides_skips_missing_file(tmp_path):
    _write_meta(tmp_path, [
        {"index": 1, "filename": "Test_01", "type": "video", "status": "downloaded"},
        {"index": 2, "filename": "Test_02", "type": "image", "status": "downloaded"},
    ])
    # only create file for index 2
    (tmp_path / "Test_02_20250101_000000.jpg").touch()

    result = _collect_slides(tmp_path)

    assert len(result) == 1
    assert result[0]["index"] == 2


def test_collect_slides_returns_empty_when_no_metadata(tmp_path):
    result = _collect_slides(tmp_path)
    assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_video_creator.py -k "collect" -v
```

Expected: `ModuleNotFoundError: No module named 'insta_loader.video_creator'`

- [ ] **Step 3: Create `insta_loader/video_creator.py` with `_collect_slides`**

```python
import glob as _glob
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from insta_loader import progress as prog
from insta_loader.cli import VideoConfig


def _collect_slides(highlight_dir: Path) -> list:
    meta_file = highlight_dir / "metadata.json"
    if not meta_file.exists():
        return []
    meta = json.loads(meta_file.read_text())
    result = []
    for slide in meta.get("slides", []):
        if slide.get("status") == "failed":
            continue
        matches = _glob.glob(str(highlight_dir / f"{slide['filename']}_*"))
        if not matches:
            continue
        result.append({
            "index": slide["index"],
            "type": slide.get("type", "image"),
            "path": Path(matches[0]),
        })
    result.sort(key=lambda s: s["index"])
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_video_creator.py -k "collect" -v
```

Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add insta_loader/video_creator.py tests/test_video_creator.py
git commit -m "feat(video): add _collect_slides"
```

---

### Task 3: `_resolve_conflict`

**Files:**
- Modify: `insta_loader/video_creator.py`
- Modify: `tests/test_video_creator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_video_creator.py  (add to existing file)
from insta_loader.video_creator import _resolve_conflict


def test_resolve_conflict_returns_path_when_no_conflict(tmp_path):
    output = tmp_path / "Travel.mp4"
    assert _resolve_conflict(output) == output


def test_resolve_conflict_overwrite_returns_same_path(tmp_path, monkeypatch):
    output = tmp_path / "Travel.mp4"
    output.touch()
    monkeypatch.setattr("builtins.input", lambda _: "o")

    result = _resolve_conflict(output)

    assert result == output
    assert not output.exists()  # deleted so ffmpeg can write fresh


def test_resolve_conflict_skip_returns_none(tmp_path, monkeypatch):
    output = tmp_path / "Travel.mp4"
    output.touch()
    monkeypatch.setattr("builtins.input", lambda _: "s")

    assert _resolve_conflict(output) is None


def test_resolve_conflict_new_returns_suffixed_path(tmp_path, monkeypatch):
    output = tmp_path / "Travel.mp4"
    output.touch()
    monkeypatch.setattr("builtins.input", lambda _: "n")

    result = _resolve_conflict(output)

    assert result == tmp_path / "Travel_1.mp4"


def test_resolve_conflict_new_increments_suffix_past_existing(tmp_path, monkeypatch):
    (tmp_path / "Travel.mp4").touch()
    (tmp_path / "Travel_1.mp4").touch()
    monkeypatch.setattr("builtins.input", lambda _: "n")

    result = _resolve_conflict(tmp_path / "Travel.mp4")

    assert result == tmp_path / "Travel_2.mp4"


def test_resolve_conflict_invalid_input_returns_none(tmp_path, monkeypatch):
    output = tmp_path / "Travel.mp4"
    output.touch()
    monkeypatch.setattr("builtins.input", lambda _: "x")

    assert _resolve_conflict(output) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_video_creator.py -k "conflict" -v
```

Expected: `ImportError: cannot import name '_resolve_conflict'`

- [ ] **Step 3: Add `_resolve_conflict` to `insta_loader/video_creator.py`**

Add after `_collect_slides`:

```python
def _resolve_conflict(output_path: Path) -> Optional[Path]:
    if not output_path.exists():
        return output_path

    suffix = 1
    while True:
        candidate = output_path.parent / f"{output_path.stem}_{suffix}.mp4"
        if not candidate.exists():
            break
        suffix += 1

    answer = input(
        f"'{output_path.name}' already exists. [o]verwrite / [s]kip / [n]ew file ({candidate.name})? "
    ).strip().lower()

    if answer == "o":
        output_path.unlink()
        return output_path
    elif answer == "n":
        return candidate
    else:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_video_creator.py -k "conflict" -v
```

Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add insta_loader/video_creator.py tests/test_video_creator.py
git commit -m "feat(video): add _resolve_conflict"
```

---

### Task 4: `_normalize_slide`

**Files:**
- Modify: `insta_loader/video_creator.py`
- Modify: `tests/test_video_creator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_video_creator.py  (add to existing file)
from unittest.mock import patch
from insta_loader.video_creator import _normalize_slide


@patch("insta_loader.video_creator.subprocess.run")
def test_normalize_slide_image_uses_loop_and_no_audio(mock_run, tmp_path):
    img = tmp_path / "slide.jpg"
    img.touch()

    out = _normalize_slide(img, 1, tmp_path, is_video=False)

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "-loop" in cmd
    assert "15" in cmd
    assert "-an" in cmd
    assert "-c:a" not in cmd
    assert out == tmp_path / "clip_001.mp4"


@patch("insta_loader.video_creator.subprocess.run")
def test_normalize_slide_video_preserves_audio(mock_run, tmp_path):
    vid = tmp_path / "slide.mp4"
    vid.touch()

    out = _normalize_slide(vid, 2, tmp_path, is_video=True)

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "-loop" not in cmd
    assert "-c:a" in cmd and "aac" in cmd
    assert "-an" not in cmd
    assert out == tmp_path / "clip_002.mp4"


@patch("insta_loader.video_creator.subprocess.run")
def test_normalize_slide_both_use_scale_filter(mock_run, tmp_path):
    img = tmp_path / "slide.jpg"
    img.touch()
    _normalize_slide(img, 1, tmp_path, is_video=False)

    cmd = mock_run.call_args[0][0]
    vf_index = cmd.index("-vf")
    assert "1080" in cmd[vf_index + 1]
    assert "1920" in cmd[vf_index + 1]


@patch("insta_loader.video_creator.subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg"))
def test_normalize_slide_raises_on_ffmpeg_error(mock_run, tmp_path):
    img = tmp_path / "slide.jpg"
    img.touch()

    with pytest.raises(subprocess.CalledProcessError):
        _normalize_slide(img, 1, tmp_path, is_video=False)
```

Note: add `import subprocess` and `import pytest` to the test file imports.

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_video_creator.py -k "normalize" -v
```

Expected: `ImportError: cannot import name '_normalize_slide'`

- [ ] **Step 3: Add `_normalize_slide` to `insta_loader/video_creator.py`**

Add after `_resolve_conflict`:

```python
_VF = (
    "scale=1080:1920:force_original_aspect_ratio=decrease,"
    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
)


def _normalize_slide(slide_path: Path, index: int, tmp_dir: Path, is_video: bool) -> Path:
    out = tmp_dir / f"clip_{index:03d}.mp4"
    if is_video:
        cmd = [
            "ffmpeg", "-i", str(slide_path),
            "-vf", _VF,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-y", str(out),
        ]
    else:
        cmd = [
            "ffmpeg",
            "-loop", "1", "-t", "15", "-i", str(slide_path),
            "-vf", _VF,
            "-r", "30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-an",
            "-y", str(out),
        ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out
```

- [ ] **Step 4: Update test file imports** — add these at the top of `tests/test_video_creator.py` if not already present:

```python
import subprocess
import pytest
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_video_creator.py -k "normalize" -v
```

Expected: 4 PASS

- [ ] **Step 6: Commit**

```bash
git add insta_loader/video_creator.py tests/test_video_creator.py
git commit -m "feat(video): add _normalize_slide with ffmpeg two-pass encoding"
```

---

### Task 5: `_concat_clips`

**Files:**
- Modify: `insta_loader/video_creator.py`
- Modify: `tests/test_video_creator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_video_creator.py  (add to existing file)
from insta_loader.video_creator import _concat_clips


@patch("insta_loader.video_creator.subprocess.run")
def test_concat_clips_runs_ffmpeg_concat(mock_run, tmp_path):
    clips = [tmp_path / "clip_001.mp4", tmp_path / "clip_002.mp4"]
    output = tmp_path / "out.mp4"

    _concat_clips(clips, output)

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "-f" in cmd
    assert "concat" in cmd
    assert str(output) in cmd


@patch("insta_loader.video_creator.subprocess.run")
def test_concat_clips_list_file_contains_all_clips(mock_run, tmp_path):
    clips = [tmp_path / "clip_001.mp4", tmp_path / "clip_002.mp4"]
    clips[0].touch()
    clips[1].touch()
    output = tmp_path / "out.mp4"

    _concat_clips(clips, output)

    # find the list file arg (-i <list_file>)
    cmd = mock_run.call_args[0][0]
    i_index = cmd.index("-i")
    list_file = Path(cmd[i_index + 1])
    content = list_file.read_text()
    assert str(clips[0].resolve()) in content
    assert str(clips[1].resolve()) in content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_video_creator.py -k "concat" -v
```

Expected: `ImportError: cannot import name '_concat_clips'`

- [ ] **Step 3: Add `_concat_clips` to `insta_loader/video_creator.py`**

Add after `_normalize_slide`:

```python
def _concat_clips(clip_paths: list, output_path: Path) -> None:
    list_file = clip_paths[0].parent / "concat_list.txt"
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in clip_paths))
    cmd = [
        "ffmpeg", "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        "-y", str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_video_creator.py -k "concat" -v
```

Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add insta_loader/video_creator.py tests/test_video_creator.py
git commit -m "feat(video): add _concat_clips"
```

---

### Task 6: `_filter_highlights`

**Files:**
- Modify: `insta_loader/video_creator.py`
- Modify: `tests/test_video_creator.py`

`_filter_highlights` works like `_resolve_highlight` in `downloader.py` but operates on `Path` objects using `.name` instead of Highlight objects with `.title`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_video_creator.py  (add to existing file)
from insta_loader.video_creator import _filter_highlights


def make_dirs(names: list, base: Path) -> list:
    dirs = []
    for name in names:
        d = base / name
        d.mkdir()
        dirs.append(d)
    return dirs


def test_filter_highlights_exact_match(tmp_path):
    dirs = make_dirs(["Travel", "Summer"], tmp_path)
    result = _filter_highlights("Travel", dirs)
    assert len(result) == 1
    assert result[0].name == "Travel"


def test_filter_highlights_case_insensitive(tmp_path):
    dirs = make_dirs(["Travel", "Summer"], tmp_path)
    result = _filter_highlights("travel", dirs)
    assert result[0].name == "Travel"


def test_filter_highlights_single_partial_match(tmp_path, capsys):
    dirs = make_dirs(["Czech_Republic", "Summer"], tmp_path)
    result = _filter_highlights("czech", dirs)
    assert result[0].name == "Czech_Republic"
    assert "Matched" in capsys.readouterr().out


def test_filter_highlights_no_match_exits_1(tmp_path):
    dirs = make_dirs(["Travel", "Summer"], tmp_path)
    with pytest.raises(SystemExit) as exc:
        _filter_highlights("xyz", dirs)
    assert exc.value.code == 1


def test_filter_highlights_multiple_partial_prompts(tmp_path, monkeypatch):
    dirs = make_dirs(["Czech_Republic", "Czech_Brno", "Summer"], tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "2")
    result = _filter_highlights("czech", dirs)
    assert result[0].name == "Czech_Brno"


def test_filter_highlights_invalid_selection_exits_1(tmp_path, monkeypatch):
    dirs = make_dirs(["Czech_Republic", "Czech_Brno"], tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "99")
    with pytest.raises(SystemExit) as exc:
        _filter_highlights("czech", dirs)
    assert exc.value.code == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_video_creator.py -k "filter" -v
```

Expected: `ImportError: cannot import name '_filter_highlights'`

- [ ] **Step 3: Add `_filter_highlights` to `insta_loader/video_creator.py`**

Add after `_concat_clips`:

```python
def _filter_highlights(query: str, dirs: list) -> list:
    exact = [d for d in dirs if d.name.lower() == query.lower()]
    if exact:
        return exact

    partial = [d for d in dirs if query.lower() in d.name.lower()]
    if not partial:
        available = ", ".join(d.name for d in dirs)
        print(f"✗  No highlight matching '{query}' found.")
        print(f"   Available: {available}")
        sys.exit(1)

    if len(partial) == 1:
        print(f"→  Matched '{partial[0].name}'")
        return partial

    print(f"Multiple highlights match '{query}':")
    for i, d in enumerate(partial, start=1):
        print(f"  {i}. {d.name}")
    raw = input(f"Pick [1-{len(partial)}]: ").strip()
    if not raw.isdigit() or not (1 <= int(raw) <= len(partial)):
        print("✗  Invalid selection.")
        sys.exit(1)
    return [partial[int(raw) - 1]]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_video_creator.py -k "filter" -v
```

Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add insta_loader/video_creator.py tests/test_video_creator.py
git commit -m "feat(video): add _filter_highlights"
```

---

### Task 7: `add_video_task` + `run()`

**Files:**
- Modify: `insta_loader/progress.py`
- Modify: `insta_loader/video_creator.py`
- Modify: `tests/test_video_creator.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_video_creator.py  (add to existing file)
from unittest.mock import MagicMock, patch, call
from insta_loader.video_creator import run
from insta_loader.cli import VideoConfig


@patch("insta_loader.video_creator.shutil.which", return_value=None)
def test_run_exits_when_ffmpeg_missing(mock_which):
    with pytest.raises(SystemExit) as exc:
        run(VideoConfig(username="test"))
    assert exc.value.code == 1


@patch("insta_loader.video_creator.shutil.which", return_value="/usr/bin/ffmpeg")
def test_run_exits_when_base_dir_missing(mock_which, tmp_path):
    with pytest.raises(SystemExit) as exc:
        run(VideoConfig(username="test", output_dir=str(tmp_path / "nonexistent")))
    assert exc.value.code == 1


@patch("insta_loader.video_creator.shutil.which", return_value="/usr/bin/ffmpeg")
def test_run_exits_when_no_highlight_dirs_with_metadata(mock_which, tmp_path):
    (tmp_path / "some_dir").mkdir()  # has no metadata.json
    with pytest.raises(SystemExit) as exc:
        run(VideoConfig(username="test", output_dir=str(tmp_path)))
    assert exc.value.code == 1


@patch("insta_loader.video_creator._concat_clips")
@patch("insta_loader.video_creator._normalize_slide")
@patch("insta_loader.video_creator._collect_slides", return_value=[])
@patch("insta_loader.video_creator.prog")
@patch("insta_loader.video_creator.shutil.which", return_value="/usr/bin/ffmpeg")
def test_run_skips_highlight_with_no_valid_slides(
    mock_which, mock_prog, mock_collect, mock_norm, mock_concat, tmp_path
):
    mock_prog.create_progress.return_value = MagicMock()
    hdir = tmp_path / "Travel"
    hdir.mkdir()
    (hdir / "metadata.json").write_text('{"highlight_title": "Travel", "slides": []}')

    run(VideoConfig(username="test", output_dir=str(tmp_path)))

    mock_norm.assert_not_called()
    mock_concat.assert_not_called()


@patch("insta_loader.video_creator._concat_clips")
@patch("insta_loader.video_creator._normalize_slide")
@patch("insta_loader.video_creator._resolve_conflict")
@patch("insta_loader.video_creator._collect_slides")
@patch("insta_loader.video_creator.prog")
@patch("insta_loader.video_creator.shutil.which", return_value="/usr/bin/ffmpeg")
def test_run_skips_highlight_when_resolve_returns_none(
    mock_which, mock_prog, mock_collect, mock_conflict, mock_norm, mock_concat, tmp_path
):
    mock_prog.create_progress.return_value = MagicMock()
    mock_collect.return_value = [{"index": 1, "type": "image", "path": tmp_path / "f.jpg"}]
    mock_conflict.return_value = None

    hdir = tmp_path / "Travel"
    hdir.mkdir()
    (hdir / "metadata.json").write_text('{"highlight_title": "Travel", "slides": []}')

    run(VideoConfig(username="test", output_dir=str(tmp_path)))

    mock_norm.assert_not_called()
    mock_concat.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_video_creator.py -k "run_" -v
```

Expected: `ImportError` or `AttributeError` since `run` is not defined yet.

- [ ] **Step 3: Add `add_video_task` to `insta_loader/progress.py`**

Add after `add_highlight_task`:

```python
def add_video_task(progress: Progress, title: str, total: int) -> TaskID:
    return progress.add_task(f"Video: {title}", total=total, current_file="")
```

Also add `"add_video_task"` to `__all__`.

The full updated `__all__` line:
```python
__all__ = ["create_progress", "add_highlight_task", "add_video_task", "advance", "log_skip"]
```

- [ ] **Step 4: Add `run()` to `insta_loader/video_creator.py`**

Add at the bottom of the file:

```python
def run(config: VideoConfig) -> None:
    if shutil.which("ffmpeg") is None:
        print("✗  ffmpeg not found. Install it: https://ffmpeg.org/download.html")
        sys.exit(1)

    base = Path(config.output_dir) if config.output_dir else Path("output") / config.username
    if not base.exists():
        print(f"✗  No downloaded highlights found at {base}")
        sys.exit(1)

    highlight_dirs = sorted(
        d for d in base.iterdir() if d.is_dir() and (d / "metadata.json").exists()
    )
    if not highlight_dirs:
        print(f"✗  No downloaded highlights found at {base}")
        sys.exit(1)

    if config.highlight:
        highlight_dirs = _filter_highlights(config.highlight, highlight_dirs)

    videos_dir = base / "videos"
    videos_dir.mkdir(exist_ok=True)
    print(f"✓  {len(highlight_dirs)} highlight(s) to process\n")

    with prog.create_progress() as progress:
        for hdir in highlight_dirs:
            meta = json.loads((hdir / "metadata.json").read_text())
            title = meta.get("highlight_title", hdir.name)
            slides = _collect_slides(hdir)

            if not slides:
                prog.log_skip(f"{title} — no valid slides, skipping")
                continue

            output_path = videos_dir / f"{hdir.name}.mp4"
            resolved = _resolve_conflict(output_path)
            if resolved is None:
                prog.log_skip(f"{title}.mp4 skipped")
                continue
            output_path = resolved

            task_id = prog.add_video_task(progress, title, len(slides))
            tmp_dir = Path(tempfile.mkdtemp())
            start = time.time()
            try:
                clips = []
                for slide in slides:
                    clip = _normalize_slide(
                        slide["path"], slide["index"], tmp_dir, slide["type"] == "video"
                    )
                    clips.append(clip)
                    prog.advance(progress, task_id, slide["path"].name)
                _concat_clips(clips, output_path)
                elapsed = time.time() - start
                m, s = divmod(int(elapsed), 60)
                print(f"✓  {output_path.name} — {len(slides)} slides, {m}m {s:02d}s")
            except subprocess.CalledProcessError as e:
                stderr = e.stderr.decode(errors="replace") if e.stderr else ""
                print(f"✗  {title} — ffmpeg error\n{stderr}")
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
```

- [ ] **Step 5: Run all tests to verify they pass**

```bash
python3 -m pytest tests/test_video_creator.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add insta_loader/progress.py insta_loader/video_creator.py tests/test_video_creator.py
git commit -m "feat(video): add run() orchestration and add_video_task progress helper"
```

---

### Task 8: `insta.py` unified CLI

**Files:**
- Create: `insta.py`
- Create: `tests/test_insta_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_insta_cli.py
import sys
import pytest
from unittest.mock import patch, MagicMock


def run_insta(args):
    """Helper: run insta.py main() with given argv."""
    import importlib, types
    with patch("sys.argv", ["insta.py"] + args):
        import insta
        importlib.reload(insta)
        return insta


@patch("insta_loader.downloader.run")
def test_highlights_subcommand_calls_downloader(mock_run):
    with patch("sys.argv", ["insta.py", "highlights", "natgeo", "--highlight", "Travel"]):
        import insta
        import importlib
        importlib.reload(insta)
        insta.main()
    mock_run.assert_called_once()
    config = mock_run.call_args[0][0]
    assert config.username == "natgeo"
    assert config.highlight == "Travel"


@patch("insta_loader.video_creator.run")
def test_videos_subcommand_calls_video_creator(mock_run):
    with patch("sys.argv", ["insta.py", "videos", "natgeo", "--highlight", "Travel"]):
        import insta
        import importlib
        importlib.reload(insta)
        insta.main()
    mock_run.assert_called_once()
    config = mock_run.call_args[0][0]
    assert config.username == "natgeo"
    assert config.highlight == "Travel"


@patch("insta_loader.summarizer.run")
def test_summary_subcommand_calls_summarizer(mock_run):
    with patch("sys.argv", ["insta.py", "summary", "natgeo"]):
        import insta
        import importlib
        importlib.reload(insta)
        insta.main()
    mock_run.assert_called_once_with("natgeo", None)


def test_no_subcommand_exits_0(capsys):
    with patch("sys.argv", ["insta.py"]):
        import insta
        import importlib
        importlib.reload(insta)
        with pytest.raises(SystemExit) as exc:
            insta.main()
    assert exc.value.code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/test_insta_cli.py -v
```

Expected: `ModuleNotFoundError: No module named 'insta'`

- [ ] **Step 3: Create `insta.py`**

```python
import argparse
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from insta_loader.cli import Config, VideoConfig
from insta_loader.downloader import run as run_highlights
from insta_loader.summarizer import run as run_summary
from insta_loader.video_creator import run as run_videos


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="insta",
        description="Instagram highlights downloader and video creator.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    hl = subparsers.add_parser("highlights", help="Download story highlights from Instagram.")
    hl.add_argument("username", help="Instagram username (without @)")
    hl.add_argument("--highlight", help="Partial name match — download only this highlight")
    hl.add_argument("--output-dir", dest="output_dir", help="Save to this directory instead of output/<username>/")
    hl.add_argument(
        "--login-user",
        dest="login_user",
        default=os.environ.get("INSTA_LOGIN_USER"),
        help="Instagram account to authenticate as (defaults to INSTA_LOGIN_USER from .env)",
    )

    vid = subparsers.add_parser("videos", help="Assemble downloaded slides into MP4s.")
    vid.add_argument("username", help="Instagram username (without @)")
    vid.add_argument("--highlight", help="Partial name match — create video only for this highlight")
    vid.add_argument("--output-dir", dest="output_dir", help="Base directory (default: output/<username>/)")

    summ = subparsers.add_parser("summary", help="Regenerate summary.json from downloaded slides on disk.")
    summ.add_argument("username", help="Instagram username (without @)")
    summ.add_argument("--output-dir", dest="output_dir", help="Base directory (default: output/<username>/)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "highlights":
        if not args.highlight:
            print(f"⚠  This will download all highlights for @{args.username}.")
            answer = input("Continue? [y/N]: ").strip().lower()
            if answer != "y":
                print("Aborted.")
                sys.exit(0)
        run_highlights(Config(
            username=args.username,
            output_dir=args.output_dir,
            highlight=args.highlight,
            login_user=args.login_user,
        ))

    elif args.command == "videos":
        run_videos(VideoConfig(
            username=args.username,
            highlight=args.highlight,
            output_dir=args.output_dir,
        ))

    elif args.command == "summary":
        run_summary(args.username, args.output_dir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n✗  Interrupted.")
        sys.exit(1)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/test_insta_cli.py -v
```

Expected: 4 PASS

- [ ] **Step 5: Run the full test suite to check nothing is broken**

```bash
python3 -m pytest -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add insta.py tests/test_insta_cli.py
git commit -m "feat: add insta.py unified CLI entry point"
```

---

### Task 9: README update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the Commands section in `README.md`**

Replace the entire `## Commands` section (everything from `## Commands` down to just before `## Output`) with:

```markdown
## Commands

All commands are available through the unified `insta.py` entry point. Run `python insta.py --help` for a full list or `python insta.py <command> --help` for per-command help.

The legacy `highlights.py` and `summary.py` entry points still work unchanged.

---

### `insta.py highlights` — download highlights

```
python insta.py highlights <username> [options]
```

| Option | Description |
|---|---|
| `--highlight NAME` | Download only this highlight (partial name match, case-insensitive). Omit to download all (asks for confirmation). |
| `--output-dir DIR` | Save to this directory instead of `output/<username>/`. |
| `--login-user USER` | Instagram account to authenticate as. Defaults to `INSTA_LOGIN_USER` from `.env`. |

```bash
# Download all highlights (asks for confirmation)
python insta.py highlights natgeo

# Partial name match — picks from a list if multiple match
python insta.py highlights natgeo --highlight "travel"

# Specific highlight, custom output dir, explicit login user
python insta.py highlights natgeo --highlight "Travel" --output-dir ~/Desktop/insta --login-user myaccount
```

After each run a `summary.json` is written automatically to `output/<username>/`.

---

### `insta.py videos` — create highlight videos

Assembles downloaded slides for a user into one MP4 per highlight. Images are shown for 15 seconds; videos play at full duration with audio.

```
python insta.py videos <username> [options]
```

| Option | Description |
|---|---|
| `--highlight NAME` | Create video only for this highlight (partial name match, case-insensitive). Omit to process all. |
| `--output-dir DIR` | Base directory (default: `output/<username>/`). |

```bash
# Create videos for all downloaded highlights
python insta.py videos natgeo

# Create video for one highlight
python insta.py videos natgeo --highlight "travel"
```

Videos are saved to `output/<username>/videos/<HighlightName>.mp4`. If a video already exists you will be prompted to overwrite, skip, or save as a new file.

Requires `ffmpeg` on your PATH. Install from [ffmpeg.org](https://ffmpeg.org/download.html).

---

### `insta.py summary` — regenerate summary

Reads all `metadata.json` files on disk and writes `output/<username>/summary.json`. Useful if you want to refresh the summary without re-downloading.

```
python insta.py summary <username> [options]
```

| Option | Description |
|---|---|
| `--output-dir DIR` | Read from this directory instead of `output/<username>/`. |

```bash
python insta.py summary natgeo
```
```

- [ ] **Step 2: Run the full test suite one final time**

```bash
python3 -m pytest -v
```

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README for unified insta.py CLI and videos command"
```

---

## Self-review

**Spec coverage:**
- ✅ `insta.py` unified CLI with subparsers — Task 8
- ✅ `insta.py videos` subcommand — Tasks 2–7
- ✅ `--highlight` partial-match picker for videos — Task 6
- ✅ Output to `output/<username>/videos/<HighlightName>.mp4` — Task 7
- ✅ Images: 15-second silent clip — Task 4
- ✅ Videos: full duration with audio — Task 4
- ✅ 1080×1920 scale+pad — Task 4
- ✅ ffmpeg two-pass normalize → concat — Tasks 4–5
- ✅ Conflict resolution: overwrite/skip/new suffix — Task 3
- ✅ Rich progress bar per highlight — Task 7
- ✅ ffmpeg not on PATH → exit 1 — Task 7
- ✅ No highlights found → exit 1 — Task 7
- ✅ Skip highlight with zero valid slides — Task 7
- ✅ ffmpeg error on slide → log and continue — Task 7
- ✅ Temp dir cleanup in finally block — Task 7
- ✅ `highlights.py` and `summary.py` remain as shims (no changes needed) — noted in file map
- ✅ README updated — Task 9
- ✅ `VideoConfig` dataclass — Task 1

**Type consistency:** `VideoConfig` defined in Task 1, used in Tasks 7 and 8. `_collect_slides` returns `list[dict]` with keys `index`, `type`, `path` — consumed consistently in Task 7's `run()`. `_filter_highlights` takes `list[Path]` and returns `list[Path]` — matches Task 7's `highlight_dirs` type.

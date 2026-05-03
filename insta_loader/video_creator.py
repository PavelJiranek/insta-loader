import glob as _glob
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import imageio_ffmpeg

from insta_loader import progress as prog
from insta_loader.cli import VideoConfig

_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def _collect_slides(highlight_dir: Path, meta: Optional[dict] = None) -> list:
    if meta is None:
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


def _resolve_conflict(output_path: Path) -> Optional[Path]:
    if not output_path.exists():
        return output_path

    suffix = 1
    while True:
        candidate = output_path.parent / f"{output_path.stem}_{suffix}{output_path.suffix}"
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
    elif answer == "s":
        return None
    else:
        print(f"✗  Invalid choice '{answer}' — skipping {output_path.name}")
        return None


_VF = (
    "scale=1080:1920:force_original_aspect_ratio=decrease,"
    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
)


def _normalize_slide(slide_path: Path, index: int, tmp_dir: Path, is_video: bool, image_duration: int = 10) -> Path:
    out = tmp_dir / f"clip_{index:03d}.mp4"
    if is_video:
        cmd = [
            _FFMPEG, "-i", str(slide_path),
            "-vf", _VF,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-y", str(out),
        ]
    else:
        cmd = [
            _FFMPEG,
            "-loop", "1", "-t", str(image_duration), "-i", str(slide_path),
            "-vf", _VF,
            "-r", "30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-an",
            "-y", str(out),
        ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def _concat_clips(clip_paths: list, output_path: Path) -> None:
    list_file = clip_paths[0].parent / "concat_list.txt"
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in clip_paths))
    cmd = [
        _FFMPEG, "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        "-y", str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


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


def run(config: VideoConfig) -> None:

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
            slides = _collect_slides(hdir, meta)

            if not slides:
                prog.log_video_skip(f"{title} — no valid slides, skipping")
                continue

            output_path = videos_dir / f"{hdir.name}.mp4"
            resolved = _resolve_conflict(output_path)
            if resolved is None:
                prog.log_video_skip(f"{title}.mp4 skipped")
                continue
            output_path = resolved

            task_id = prog.add_video_task(progress, title, len(slides))
            tmp_dir = Path(tempfile.mkdtemp())
            start = time.time()
            try:
                clips = []
                for slide in slides:
                    clip = _normalize_slide(
                        slide["path"], slide["index"], tmp_dir, slide["type"] == "video",
                        config.image_duration,
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

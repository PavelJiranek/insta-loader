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
    else:
        return None


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

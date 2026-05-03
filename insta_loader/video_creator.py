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

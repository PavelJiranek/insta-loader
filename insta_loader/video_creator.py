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

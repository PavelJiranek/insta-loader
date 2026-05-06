import glob
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Union


def sanitize_name(title: str) -> str:
    result = title.replace("/", "-")
    # Strip control characters (including null bytes)
    result = re.sub(r"[\x00-\x1f\x7f]", "", result)
    # Strip shell-problematic chars; keep letters, digits, emoji, accents, hyphens, dots.
    result = re.sub(r"""['"\\:*?<>|!@#$%^&()+={}\[\];,`~]""", "", result)
    result = result.replace(" ", "_")
    result = re.sub(r"_+", "_", result)  # collapse consecutive underscores
    result = result.lstrip(".")          # prevent . and .. path traversal
    result = result.strip("_-")
    return result or "unnamed"


def highlight_dir(base_dir: Union[str, Path], highlight_title: str) -> Path:
    folder = Path(base_dir) / "instagram" / sanitize_name(highlight_title)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def slide_filename(highlight_title: str, idx: int) -> str:
    # Returns the date-free stem; downloader appends _{date_utc} via instaloader's template engine.
    return f"{sanitize_name(highlight_title)}_{idx:02d}"


def slide_exists(folder: Path, highlight_title: str, idx: int) -> bool:
    stem = slide_filename(highlight_title, idx)
    return any(
        not f.endswith(".temp")
        for f in glob.glob(str(folder / f"{stem}_*"))
    )


def write_metadata(
    folder: Path,
    title: str,
    total: int,
    downloaded: int,
    videos: int,
    images: int,
    slides: list = None,
) -> None:
    data = {
        "highlight_title": title,
        "total_items": total,
        "downloaded": downloaded,
        "videos": videos,
        "images": images,
        "status": "complete" if downloaded == total else "partial",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "slides": slides or [],
    }
    (folder / "metadata.json").write_text(json.dumps(data, indent=2))

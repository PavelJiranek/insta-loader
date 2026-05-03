import glob
from pathlib import Path
from typing import Union


def sanitize_name(title: str) -> str:
    # Intentionally minimal: only replaces characters common in Instagram titles.
    # Extend if broader filesystem compatibility is needed.
    return title.replace("/", "-").replace(" ", "_")


def highlight_dir(base_dir: Union[str, Path], highlight_title: str) -> Path:
    folder = Path(base_dir) / sanitize_name(highlight_title)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def slide_filename(highlight_title: str, idx: int) -> str:
    return f"{sanitize_name(highlight_title)}_{idx:02d}"


def slide_exists(folder: Path, highlight_title: str, idx: int) -> bool:
    stem = slide_filename(highlight_title, idx)
    return len(glob.glob(str(folder / f"{stem}_*"))) > 0

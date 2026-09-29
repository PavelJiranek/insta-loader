import glob
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Union

from send2trash import send2trash

# A slide file ends with _<YYYYMMDD_HHMMSS>.<ext>, the media's own taken-at time
# in UTC. That pair identifies which Instagram media a file holds, whatever its
# index. It is written from the media at download time, so unlike the metadata
# index/mediaid it can't drift when a highlight is reordered or edited.
_SLIDE_KEY_RE = re.compile(r"_(\d{8}_\d{6})\.([A-Za-z0-9]+)$")

# A slide spec is (timestamp, extension) for one position in a highlight.
SlideSpec = Tuple[str, str]


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


def expected_name(highlight_title: str, idx: int, spec: SlideSpec) -> str:
    ts, ext = spec
    return f"{slide_filename(highlight_title, idx)}_{ts}.{ext}"


def _slide_files(folder: Path) -> list:
    """(path, key) for every slide file in folder; key is (timestamp, ext)."""
    out = []
    for p in folder.iterdir():
        if not p.is_file() or p.name == "metadata.json" or p.name.endswith(".temp"):
            continue
        m = _SLIDE_KEY_RE.search(p.name)
        if m:
            out.append((p, (m.group(1), m.group(2).lower())))
    return out


def in_sync(folder: Path, highlight_title: str, specs: List[SlideSpec]) -> bool:
    """True if the folder holds exactly the expected slides, in order, nothing extra."""
    if not folder.exists():
        return False
    expected = {expected_name(highlight_title, i, s) for i, s in enumerate(specs, start=1)}
    actual = {p.name for p, _ in _slide_files(folder)}
    return expected == actual


@dataclass
class SyncResult:
    kept: int = 0      # already at the right position
    moved: int = 0     # reused, renamed to a new position
    removed: int = 0   # no longer on Instagram, moved to Trash
    missing: int = 0   # not on disk yet, left for the caller to download

    @property
    def changed(self) -> bool:
        return bool(self.moved or self.removed)

    def summary(self) -> str:
        parts = []
        if self.removed:
            parts.append(f"{self.removed} removed")
        if self.moved:
            parts.append(f"{self.moved} reordered")
        if self.missing:
            parts.append(f"{self.missing} to download")
        return ", ".join(parts)


def sync_folder(folder: Path, highlight_title: str, specs: List[SlideSpec]) -> SyncResult:
    """Rearrange a highlight folder to match the slide order on Instagram.

    Files are matched to positions by their (timestamp, ext) key, not by index,
    so removals, additions and reorders are all handled. Existing files are
    renamed into place rather than re-downloaded. Files whose media is gone
    are moved to Trash. Positions with no matching file are counted as missing
    and left for the caller to download.
    """
    result = SyncResult()
    pool: dict = {}
    for p, key in _slide_files(folder):
        pool.setdefault(key, []).append(p)
    for paths in pool.values():
        paths.sort(key=lambda p: p.name)

    targets = [folder / expected_name(highlight_title, i, s) for i, s in enumerate(specs, start=1)]
    assigned: list = [None] * len(specs)

    # Pass 1: files already sitting at their exact target name stay put.
    for i, (spec, target) in enumerate(zip(specs, targets)):
        candidates = pool.get((spec[0], spec[1].lower()), [])
        if target in candidates:
            candidates.remove(target)
            assigned[i] = target
            result.kept += 1

    # Pass 2: remaining positions reuse any other file holding the same media.
    moves = []
    for i, (spec, target) in enumerate(zip(specs, targets)):
        if assigned[i] is not None:
            continue
        candidates = pool.get((spec[0], spec[1].lower()), [])
        if candidates:
            src = candidates.pop(0)
            moves.append((src, target))
            assigned[i] = target
            result.moved += 1
        else:
            result.missing += 1

    for paths in pool.values():
        for p in paths:
            send2trash(str(p))
            result.removed += 1

    # Two-phase rename so a permutation (A->B, B->A) can't overwrite a file.
    # The staging name deliberately doesn't start with the slide stem, so a
    # crash mid-sync leaves nothing that slide_exists() would count; the next
    # sync still recognises these files by their key.
    staged = []
    for n, (src, target) in enumerate(moves):
        tmp = folder / f".sync-{n}-{target.name}"
        src.rename(tmp)
        staged.append((tmp, target))
    for tmp, target in staged:
        tmp.rename(target)

    return result


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

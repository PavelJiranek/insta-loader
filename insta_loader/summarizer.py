import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union


def run(username: str, output_dir: Optional[str] = None) -> None:
    base = Path(output_dir) if output_dir else Path("output") / username

    instagram_dir = base / "instagram"
    if not instagram_dir.exists():
        print(f"✗  No downloads found at {instagram_dir}")
        sys.exit(1)

    highlights = []
    for folder in sorted(instagram_dir.iterdir()):
        if not folder.is_dir():
            continue
        meta_file = folder / "metadata.json"
        if not meta_file.exists():
            highlights.append({
                "title": folder.name,
                "folder": folder.name,
                "status": "no_metadata",
            })
            continue

        meta = json.loads(meta_file.read_text())
        slides = meta.get("slides", [])
        failed = sum(1 for s in slides if s.get("status") == "failed")

        highlights.append({
            "title": meta.get("highlight_title", folder.name),
            "folder": folder.name,
            "status": meta.get("status", "unknown"),
            "total_items": meta.get("total_items", 0),
            "downloaded": meta.get("downloaded", 0),
            "failed": failed,
            "videos": meta.get("videos", 0),
            "images": meta.get("images", 0),
            "last_updated": meta.get("last_updated"),
        })

    total_slides = sum(h.get("total_items", 0) for h in highlights)
    total_downloaded = sum(h.get("downloaded", 0) for h in highlights)
    total_failed = sum(h.get("failed", 0) for h in highlights)
    total_videos = sum(h.get("videos", 0) for h in highlights)
    total_images = sum(h.get("images", 0) for h in highlights)

    summary = {
        "username": username,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(instagram_dir),
        "total_highlights": len(highlights),
        "highlights_complete": sum(1 for h in highlights if h.get("status") == "complete"),
        "highlights_partial": sum(1 for h in highlights if h.get("status") == "partial"),
        "highlights_with_failures": sum(1 for h in highlights if h.get("failed", 0) > 0),
        "total_slides": total_slides,
        "total_downloaded": total_downloaded,
        "total_failed": total_failed,
        "total_videos": total_videos,
        "total_images": total_images,
        "highlights": highlights,
    }

    out_file = instagram_dir / "summary.json"
    out_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"✓  Summary written to {out_file}")
    print(f"   {len(highlights)} highlights · {total_downloaded}/{total_slides} slides · {total_failed} failed")

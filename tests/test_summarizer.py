import json
import pytest
from pathlib import Path
from insta_loader.summarizer import run


def write_meta(folder: Path, **kwargs):
    defaults = {
        "highlight_title": folder.name,
        "total_items": 5,
        "downloaded": 5,
        "videos": 3,
        "images": 2,
        "status": "complete",
        "last_updated": "2026-05-03T10:00:00+00:00",
        "slides": [],
    }
    defaults.update(kwargs)
    (folder / "metadata.json").write_text(json.dumps(defaults))


def insta_dir(base: Path) -> Path:
    d = base / "instagram"
    d.mkdir(exist_ok=True)
    return d


def read_summary(base: Path) -> dict:
    return json.loads((base / "instagram" / "summary.json").read_text())


def test_summary_written_to_output_dir(tmp_path):
    folder = insta_dir(tmp_path) / "Travel"
    folder.mkdir()
    write_meta(folder)

    run("testuser", str(tmp_path))

    assert (tmp_path / "instagram" / "summary.json").exists()


def test_summary_counts_highlights(tmp_path):
    for name in ["Travel", "Summer", "Winter"]:
        f = insta_dir(tmp_path) / name
        f.mkdir()
        write_meta(f)

    run("testuser", str(tmp_path))

    data = read_summary(tmp_path)
    assert data["total_highlights"] == 3


def test_summary_totals_slides(tmp_path):
    for name, total, downloaded in [("A", 10, 10), ("B", 5, 4)]:
        f = insta_dir(tmp_path) / name
        f.mkdir()
        write_meta(f, total_items=total, downloaded=downloaded,
                   status="complete" if total == downloaded else "partial")

    run("testuser", str(tmp_path))

    data = read_summary(tmp_path)
    assert data["total_slides"] == 15
    assert data["total_downloaded"] == 14


def test_summary_counts_complete_and_partial(tmp_path):
    ig = insta_dir(tmp_path)
    (ig / "A").mkdir()
    write_meta(ig / "A", status="complete")
    (ig / "B").mkdir()
    write_meta(ig / "B", status="partial")
    (ig / "C").mkdir()
    write_meta(ig / "C", status="complete")

    run("testuser", str(tmp_path))

    data = read_summary(tmp_path)
    assert data["highlights_complete"] == 2
    assert data["highlights_partial"] == 1


def test_summary_counts_failed_slides(tmp_path):
    folder = insta_dir(tmp_path) / "Travel"
    folder.mkdir()
    slides = [
        {"index": 1, "status": "downloaded"},
        {"index": 2, "status": "failed"},
        {"index": 3, "status": "downloaded"},
    ]
    write_meta(folder, slides=slides, downloaded=2, total_items=3)

    run("testuser", str(tmp_path))

    data = read_summary(tmp_path)
    assert data["total_failed"] == 1
    assert data["highlights_with_failures"] == 1
    assert data["highlights"][0]["failed"] == 1


def test_summary_handles_missing_metadata(tmp_path):
    folder = insta_dir(tmp_path) / "NoMeta"
    folder.mkdir()
    # no metadata.json

    run("testuser", str(tmp_path))

    data = read_summary(tmp_path)
    assert data["highlights"][0]["status"] == "no_metadata"


def test_summary_exits_1_when_dir_not_found(tmp_path):
    with pytest.raises(SystemExit) as exc:
        run("ghost", str(tmp_path / "nonexistent"))
    assert exc.value.code == 1


def test_summary_includes_username_and_generated_at(tmp_path):
    folder = insta_dir(tmp_path) / "Travel"
    folder.mkdir()
    write_meta(folder)

    run("testuser", str(tmp_path))

    data = read_summary(tmp_path)
    assert data["username"] == "testuser"
    assert "generated_at" in data


def test_summary_uses_default_output_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    user_dir = tmp_path / "output" / "testuser"
    ig_dir = user_dir / "instagram"
    ig_dir.mkdir(parents=True)
    (ig_dir / "Travel").mkdir()
    write_meta(ig_dir / "Travel")

    run("testuser")

    assert (ig_dir / "summary.json").exists()

"""Resync of a highlight folder against the slide order on Instagram.

These run against a real temp filesystem (no organizer mocks) because the
correctness of sync_folder is entirely about which bytes end up at which name.
"""
from unittest.mock import patch

import pytest

from insta_loader import organizer
from insta_loader.organizer import in_sync, sync_folder

TITLE = "Trip"


@pytest.fixture(autouse=True)
def fake_trash(tmp_path):
    """Replace send2trash so tests don't fill the real macOS Trash."""
    trashed = []

    def _trash(path):
        trashed.append(path)
        from pathlib import Path
        Path(path).unlink()

    with patch.object(organizer, "send2trash", side_effect=_trash):
        yield trashed


def put(folder, idx, ts, ext="jpg", content=None):
    """Write a slide file the way the downloader names it."""
    p = folder / f"{TITLE}_{idx:02d}_{ts}.{ext}"
    p.write_bytes((content or ts).encode())
    return p


def names(folder):
    return sorted(p.name for p in folder.iterdir() if p.name != "metadata.json")


def content_at(folder, idx, ts, ext="jpg"):
    return (folder / f"{TITLE}_{idx:02d}_{ts}.{ext}").read_bytes().decode()


A, B, C, D = "20260101_100000", "20260102_100000", "20260103_100000", "20260104_100000"


# ── in_sync ───────────────────────────────────────────────────────────────────

def test_in_sync_true_when_folder_matches(tmp_path):
    put(tmp_path, 1, A), put(tmp_path, 2, B, "mp4")
    assert in_sync(tmp_path, TITLE, [(A, "jpg"), (B, "mp4")])


def test_in_sync_false_when_slide_removed_on_instagram(tmp_path):
    put(tmp_path, 1, A), put(tmp_path, 2, B), put(tmp_path, 3, C)
    assert not in_sync(tmp_path, TITLE, [(A, "jpg"), (C, "jpg")])


def test_in_sync_false_when_slide_added_on_instagram(tmp_path):
    put(tmp_path, 1, A)
    assert not in_sync(tmp_path, TITLE, [(A, "jpg"), (B, "jpg")])


def test_in_sync_false_when_reordered_with_same_count(tmp_path):
    put(tmp_path, 1, A), put(tmp_path, 2, B)
    assert not in_sync(tmp_path, TITLE, [(B, "jpg"), (A, "jpg")])


def test_in_sync_false_when_removed_and_added_same_count(tmp_path):
    # the case the old count-only check reported as "complete"
    put(tmp_path, 1, A), put(tmp_path, 2, B)
    assert not in_sync(tmp_path, TITLE, [(A, "jpg"), (C, "jpg")])


def test_in_sync_ignores_metadata_and_temp_files(tmp_path):
    put(tmp_path, 1, A)
    (tmp_path / "metadata.json").write_text("{}")
    (tmp_path / f"{TITLE}_02_{B}.jpg.temp").write_text("partial")
    assert in_sync(tmp_path, TITLE, [(A, "jpg")])


def test_in_sync_false_for_missing_folder(tmp_path):
    assert not in_sync(tmp_path / "nope", TITLE, [(A, "jpg")])


# ── sync_folder ───────────────────────────────────────────────────────────────

def test_sync_noop_when_already_in_sync(tmp_path, fake_trash):
    put(tmp_path, 1, A), put(tmp_path, 2, B)
    r = sync_folder(tmp_path, TITLE, [(A, "jpg"), (B, "jpg")])
    assert (r.kept, r.moved, r.removed, r.missing) == (2, 0, 0, 0)
    assert not r.changed
    assert fake_trash == []


def test_sync_removal_from_middle_shifts_later_slides_down(tmp_path, fake_trash):
    put(tmp_path, 1, A), put(tmp_path, 2, B), put(tmp_path, 3, C)
    r = sync_folder(tmp_path, TITLE, [(A, "jpg"), (C, "jpg")])  # B deleted on Instagram

    assert names(tmp_path) == [f"{TITLE}_01_{A}.jpg", f"{TITLE}_02_{C}.jpg"]
    assert content_at(tmp_path, 2, C) == C  # C's bytes, now at position 2
    assert (r.kept, r.moved, r.removed, r.missing) == (1, 1, 1, 0)
    assert len(fake_trash) == 1 and B in fake_trash[0]


def test_sync_addition_reports_missing_and_keeps_existing(tmp_path, fake_trash):
    put(tmp_path, 1, A), put(tmp_path, 2, C)
    r = sync_folder(tmp_path, TITLE, [(A, "jpg"), (B, "jpg"), (C, "jpg")])  # B inserted

    assert names(tmp_path) == [f"{TITLE}_01_{A}.jpg", f"{TITLE}_03_{C}.jpg"]
    assert (r.kept, r.moved, r.removed, r.missing) == (1, 1, 0, 1)
    assert fake_trash == []
    # the gap at position 2 is what the downloader will fill
    assert not organizer.slide_exists(tmp_path, TITLE, 2)
    assert organizer.slide_exists(tmp_path, TITLE, 3)


def test_sync_swap_moves_bytes_without_clobbering(tmp_path, fake_trash):
    # permutation A<->B: a naive single-phase rename would overwrite one of them
    put(tmp_path, 1, A), put(tmp_path, 2, B)
    r = sync_folder(tmp_path, TITLE, [(B, "jpg"), (A, "jpg")])

    assert content_at(tmp_path, 1, B) == B
    assert content_at(tmp_path, 2, A) == A
    assert (r.moved, r.removed) == (2, 0)
    assert not list(tmp_path.glob(".sync-*"))


def test_sync_full_reversal(tmp_path, fake_trash):
    for i, ts in enumerate([A, B, C, D], start=1):
        put(tmp_path, i, ts)
    sync_folder(tmp_path, TITLE, [(D, "jpg"), (C, "jpg"), (B, "jpg"), (A, "jpg")])
    for i, ts in enumerate([D, C, B, A], start=1):
        assert content_at(tmp_path, i, ts) == ts


def test_sync_matches_on_extension_too(tmp_path, fake_trash):
    # same timestamp but it's now a video: the old image is not the same media
    put(tmp_path, 1, A, "jpg")
    r = sync_folder(tmp_path, TITLE, [(A, "mp4")])
    assert (r.removed, r.missing) == (1, 1)
    assert names(tmp_path) == []


def test_sync_handles_duplicate_timestamps(tmp_path, fake_trash):
    put(tmp_path, 1, A, content="first"), put(tmp_path, 2, A, content="second")
    r = sync_folder(tmp_path, TITLE, [(A, "jpg"), (A, "jpg")])
    assert (r.kept, r.removed, r.missing) == (2, 0, 0)


def test_sync_recovers_files_left_staged_by_a_crash(tmp_path, fake_trash):
    # a previous sync died between its two rename phases
    staged = tmp_path / f".sync-0-{TITLE}_02_{B}.jpg"
    staged.write_bytes(B.encode())
    put(tmp_path, 1, A)

    r = sync_folder(tmp_path, TITLE, [(A, "jpg"), (B, "jpg")])

    assert names(tmp_path) == [f"{TITLE}_01_{A}.jpg", f"{TITLE}_02_{B}.jpg"]
    assert content_at(tmp_path, 2, B) == B
    assert r.missing == 0


def test_staged_file_is_not_counted_as_an_existing_slide(tmp_path):
    # so a crash mid-sync can't make the downloader think a slot is filled
    (tmp_path / f".sync-0-{TITLE}_02_{B}.jpg").write_bytes(b"x")
    assert not organizer.slide_exists(tmp_path, TITLE, 2)


def test_sync_leaves_unrecognised_files_alone(tmp_path, fake_trash):
    put(tmp_path, 1, A)
    (tmp_path / ".DS_Store").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("mine")
    sync_folder(tmp_path, TITLE, [(A, "jpg")])
    assert (tmp_path / ".DS_Store").exists() and (tmp_path / "notes.txt").exists()
    assert fake_trash == []


def test_summary_text():
    r = organizer.SyncResult(kept=40, moved=12, removed=3, missing=4)
    assert r.summary() == "3 removed, 12 reordered, 4 to download"

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from insta_loader.cli import Config
from insta_loader import instagrapi_downloader as igd


def make_config(username="paveljjiranek", output_dir=None, highlight=None,
                login_user="paveljjiranek", update=False, retry_failed=False):
    return Config(username=username, output_dir=output_dir, highlight=highlight,
                  login_user=login_user, update=update, retry_failed=retry_failed,
                  backend="instagrapi")


def make_media(pk="1", media_type=1, year=2025, month=1, day=1):
    m = MagicMock()
    m.pk = pk
    m.media_type = media_type
    m.taken_at = datetime(year, month, day, 12, 0, 0, tzinfo=timezone.utc)
    m.thumbnail_url = f"https://cdn.example/{pk}.jpg"
    m.video_url = f"https://cdn.example/{pk}.mp4"
    return m


# ── run() guard ───────────────────────────────────────────────────────────────

def test_requires_login_user_exits_1():
    with pytest.raises(SystemExit) as exc:
        igd.run(make_config(login_user=None))
    assert exc.value.code == 1


# ── _fetch_all_highlights pagination ───────────────────────────────────────────

def test_fetch_all_highlights_follows_cursor():
    cl = MagicMock()
    cl.phone_id = "phone"
    page1 = {"tray": [{"id": f"highlight:{i}", "title": f"H{i}"} for i in range(100)], "cursor": "next"}
    page2 = {"tray": [{"id": f"highlight:{i}", "title": f"H{i}"} for i in range(100, 140)], "cursor": None}
    cl.private_request.side_effect = [page1, page2]

    with patch.object(igd, "_base_tray_params", return_value={}):
        entries = igd._fetch_all_highlights(cl, 999)

    assert len(entries) == 140
    assert entries[0] == {"pk": "0", "title": "H0"}
    assert entries[-1] == {"pk": "139", "title": "H139"}
    assert cl.private_request.call_count == 2


def test_fetch_all_highlights_dedupes_repeated_ids():
    cl = MagicMock()
    page1 = {"tray": [{"id": "highlight:1", "title": "A"}], "cursor": "next"}
    page2 = {"tray": [{"id": "highlight:1", "title": "A"}], "cursor": None}
    cl.private_request.side_effect = [page1, page2]

    with patch.object(igd, "_base_tray_params", return_value={}):
        entries = igd._fetch_all_highlights(cl, 999)

    assert len(entries) == 1


# ── _get_items ordering ─────────────────────────────────────────────────────────

def test_get_items_sorted_oldest_first():
    cl = MagicMock()
    info = MagicMock()
    info.items = [make_media("new", day=3), make_media("old", day=1), make_media("mid", day=2)]
    cl.highlight_info.return_value = info

    items = igd._get_items(cl, "pk")

    assert [m.pk for m in items] == ["old", "mid", "new"]


# ── _download_item naming ────────────────────────────────────────────────────────

def test_download_item_image_named_with_timestamp(tmp_path):
    item = make_media("1", media_type=1)
    resp = MagicMock()
    resp.content = b"jpgbytes"
    with patch.object(igd.requests, "get", return_value=resp) as mock_get:
        igd._download_item(item, tmp_path, "Travel_01")

    out = tmp_path / "Travel_01_20250101_120000.jpg"
    assert out.exists()
    assert out.read_bytes() == b"jpgbytes"
    mock_get.assert_called_once_with("https://cdn.example/1.jpg", timeout=60)
    # no leftover .temp file
    assert not list(tmp_path.glob("*.temp"))


def test_download_item_video_uses_mp4_and_video_url(tmp_path):
    item = make_media("2", media_type=2)
    resp = MagicMock()
    resp.content = b"mp4bytes"
    with patch.object(igd.requests, "get", return_value=resp) as mock_get:
        igd._download_item(item, tmp_path, "Travel_02")

    assert (tmp_path / "Travel_02_20250101_120000.mp4").exists()
    mock_get.assert_called_once_with("https://cdn.example/2.mp4", timeout=60)


# ── run() download loop ──────────────────────────────────────────────────────────

@patch("insta_loader.instagrapi_downloader.summarizer")
@patch("insta_loader.instagrapi_downloader.prog")
@patch("insta_loader.instagrapi_downloader.organizer")
@patch("insta_loader.instagrapi_downloader._download_item")
@patch("insta_loader.instagrapi_downloader._get_items")
@patch("insta_loader.instagrapi_downloader._fetch_all_highlights")
@patch("insta_loader.instagrapi_downloader._authenticate")
def test_downloads_missing_slides(mock_auth, mock_fetch, mock_items, mock_dl,
                                  mock_org, mock_prog, mock_summ, tmp_path):
    mock_auth.return_value = MagicMock()
    mock_fetch.return_value = [{"pk": "1", "title": "Travel"}]
    mock_items.return_value = [make_media("1", media_type=1)]
    mock_org.highlight_dir.return_value = tmp_path
    mock_org.slide_filename.return_value = "Travel_01"
    mock_org.slide_exists.return_value = False

    igd.run(make_config(highlight="Travel", output_dir=str(tmp_path)))

    mock_dl.assert_called_once()


@patch("insta_loader.instagrapi_downloader.summarizer")
@patch("insta_loader.instagrapi_downloader.prog")
@patch("insta_loader.instagrapi_downloader.organizer")
@patch("insta_loader.instagrapi_downloader._download_item")
@patch("insta_loader.instagrapi_downloader._get_items")
@patch("insta_loader.instagrapi_downloader._fetch_all_highlights")
@patch("insta_loader.instagrapi_downloader._authenticate")
def test_skips_existing_slides(mock_auth, mock_fetch, mock_items, mock_dl,
                               mock_org, mock_prog, mock_summ, tmp_path):
    mock_auth.return_value = MagicMock()
    mock_fetch.return_value = [{"pk": "1", "title": "Travel"}]
    mock_items.return_value = [make_media("1", media_type=1)]
    mock_org.highlight_dir.return_value = tmp_path
    mock_org.slide_filename.return_value = "Travel_01"
    mock_org.slide_exists.return_value = True  # already on disk

    igd.run(make_config(highlight="Travel", output_dir=str(tmp_path)))

    mock_dl.assert_not_called()


@patch("insta_loader.instagrapi_downloader.summarizer")
@patch("insta_loader.instagrapi_downloader.prog")
@patch("insta_loader.instagrapi_downloader.organizer")
@patch("insta_loader.instagrapi_downloader._get_items")
@patch("insta_loader.instagrapi_downloader._fetch_all_highlights")
@patch("insta_loader.instagrapi_downloader._authenticate")
def test_highlight_not_found_exits_1(mock_auth, mock_fetch, mock_items,
                                     mock_org, mock_prog, mock_summ, tmp_path):
    mock_auth.return_value = MagicMock()
    mock_fetch.return_value = [{"pk": "1", "title": "Summer"}]

    with pytest.raises(SystemExit) as exc:
        igd.run(make_config(highlight="Travel", output_dir=str(tmp_path)))
    assert exc.value.code == 1


@patch("insta_loader.instagrapi_downloader.summarizer")
@patch("insta_loader.instagrapi_downloader.prog")
@patch("insta_loader.instagrapi_downloader.organizer")
@patch("insta_loader.instagrapi_downloader._download_item")
@patch("insta_loader.instagrapi_downloader._get_items")
@patch("insta_loader.instagrapi_downloader._fetch_all_highlights")
@patch("insta_loader.instagrapi_downloader._authenticate")
def test_update_skips_complete_highlight(mock_auth, mock_fetch, mock_items, mock_dl,
                                         mock_org, mock_prog, mock_summ, tmp_path):
    mock_auth.return_value = MagicMock()
    mock_fetch.return_value = [{"pk": "1", "title": "Travel"}]
    mock_items.return_value = [make_media("1"), make_media("2")]

    # Pre-seed a complete metadata.json with matching total_items
    folder = tmp_path / "instagram" / "Travel"
    folder.mkdir(parents=True)
    (folder / "metadata.json").write_text(json.dumps({"status": "complete", "total_items": 2}))
    mock_org.sanitize_name.return_value = "Travel"

    igd.run(make_config(output_dir=str(tmp_path), update=True))

    mock_dl.assert_not_called()

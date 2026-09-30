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
@patch("insta_loader.instagrapi_downloader._download_item")
@patch("insta_loader.instagrapi_downloader._get_items")
@patch("insta_loader.instagrapi_downloader._fetch_all_highlights")
@patch("insta_loader.instagrapi_downloader._authenticate")
def test_update_resyncs_after_slide_removed_on_instagram(
        mock_auth, mock_fetch, mock_items, mock_dl, mock_prog, mock_summ, tmp_path):
    """Real organizer: 3 slides on disk, the middle one deleted on Instagram."""
    from insta_loader import organizer
    mock_auth.return_value = MagicMock()
    mock_fetch.return_value = [{"pk": "1", "title": "Travel"}]
    a, b, c = make_media("a", day=1), make_media("b", day=2), make_media("c", day=3)
    mock_items.return_value = [a, c]  # b removed

    folder = tmp_path / "instagram" / "Travel"
    folder.mkdir(parents=True)
    for idx, day in ((1, 1), (2, 2), (3, 3)):
        (folder / f"Travel_{idx:02d}_202501{day:02d}_120000.jpg").write_bytes(str(day).encode())
    (folder / "metadata.json").write_text(json.dumps({"status": "complete", "total_items": 3}))

    trashed = []
    with patch.object(organizer, "send2trash",
                      side_effect=lambda p: (trashed.append(p), __import__("os").remove(p))):
        igd.run(make_config(output_dir=str(tmp_path), update=True))

    files = sorted(p.name for p in folder.iterdir() if p.suffix == ".jpg")
    assert files == ["Travel_01_20250101_120000.jpg", "Travel_02_20250103_120000.jpg"]
    assert (folder / "Travel_02_20250103_120000.jpg").read_bytes() == b"3"
    assert len(trashed) == 1 and "20250102" in trashed[0]
    mock_dl.assert_not_called()  # nothing new: everything reused by rename
    meta = json.loads((folder / "metadata.json").read_text())
    assert meta["total_items"] == 2 and meta["status"] == "complete"
    mock_prog.log_resync.assert_called_once()


@patch("insta_loader.instagrapi_downloader.summarizer")
@patch("insta_loader.instagrapi_downloader.prog")
@patch("insta_loader.instagrapi_downloader.organizer")
@patch("insta_loader.instagrapi_downloader._download_item")
@patch("insta_loader.instagrapi_downloader._get_items")
@patch("insta_loader.instagrapi_downloader._fetch_all_highlights")
@patch("insta_loader.instagrapi_downloader._authenticate")
def test_empty_response_leaves_local_copy_untouched(
        mock_auth, mock_fetch, mock_items, mock_dl, mock_org, mock_prog, mock_summ, tmp_path):
    mock_auth.return_value = MagicMock()
    mock_fetch.return_value = [{"pk": "1", "title": "Travel"}]
    mock_items.return_value = []  # API hiccup

    igd.run(make_config(output_dir=str(tmp_path)))

    mock_org.sync_folder.assert_not_called()
    mock_org.write_metadata.assert_not_called()
    mock_dl.assert_not_called()


@patch("insta_loader.instagrapi_downloader.summarizer")
@patch("insta_loader.instagrapi_downloader.prog")
@patch("insta_loader.instagrapi_downloader.organizer")
@patch("insta_loader.instagrapi_downloader._download_item")
@patch("insta_loader.instagrapi_downloader._get_items")
@patch("insta_loader.instagrapi_downloader._fetch_all_highlights")
@patch("insta_loader.instagrapi_downloader._authenticate")
def test_retry_failed_does_not_resync(
        mock_auth, mock_fetch, mock_items, mock_dl, mock_org, mock_prog, mock_summ, tmp_path):
    mock_auth.return_value = MagicMock()
    mock_fetch.return_value = [{"pk": "1", "title": "Travel"}]
    mock_items.return_value = [make_media("1")]
    folder = tmp_path / "instagram" / "Travel"
    folder.mkdir(parents=True)
    (folder / "metadata.json").write_text(json.dumps({"slides": [{"status": "failed"}]}))
    mock_org.sanitize_name.return_value = "Travel"
    mock_org.slide_exists.return_value = False

    igd.run(make_config(output_dir=str(tmp_path), retry_failed=True))

    mock_org.sync_folder.assert_not_called()


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


# ── throttling of private-API calls ────────────────────────────────────────────

def test_api_delay_is_jittered_around_api_sleep():
    from insta_loader import downloader
    with patch.object(downloader, "_API_SLEEP", 5.0), patch.object(downloader, "_SLEEP_JITTER", 0.6):
        delays = [downloader._api_delay() for _ in range(200)]
    assert all(2.0 <= d <= 8.0 for d in delays)
    assert max(delays) - min(delays) > 1.0  # actually varies, not a fixed interval


def test_api_delay_zero_when_disabled():
    from insta_loader import downloader
    with patch.object(downloader, "_API_SLEEP", 0.0):
        assert downloader._api_delay() == 0.0


def test_get_items_pauses_before_the_api_call(no_api_pause):
    cl = MagicMock()
    order = []
    no_api_pause.side_effect = lambda: order.append("pause")
    cl.highlight_info.side_effect = lambda pk: order.append("call") or MagicMock(items=[])
    igd._get_items(cl, "pk")
    assert order == ["pause", "call"]


def test_fetch_all_highlights_pauses_before_every_page(no_api_pause):
    cl = MagicMock()
    cl.private_request.side_effect = [{"tray": [], "cursor": "next"}, {"tray": [], "cursor": None}]
    with patch.object(igd, "_base_tray_params", return_value={}):
        igd._fetch_all_highlights(cl, 1)
    assert no_api_pause.call_count == 2


# ── stopping cleanly when Instagram pushes back ────────────────────────────────

def _blocked_run(err, tmp_path, capsys):
    """Two highlights; listing the 2nd one's slides raises `err`."""
    calls = {"n": 0}

    def items(cl, pk):
        calls["n"] += 1
        if calls["n"] == 2:
            raise err
        return [make_media("1")]

    with patch.object(igd, "_authenticate", return_value=MagicMock()), \
         patch.object(igd, "_fetch_all_highlights",
                      return_value=[{"pk": "1", "title": "One"}, {"pk": "2", "title": "Two"}]), \
         patch.object(igd, "_get_items", side_effect=items), \
         patch.object(igd, "_download_item"), \
         patch.object(igd, "summarizer") as summ, \
         patch.object(igd, "prog"):
        with pytest.raises(SystemExit) as exc:
            igd.run(make_config(output_dir=str(tmp_path)))
    return exc.value.code, summ, capsys.readouterr().out


def test_forbidden_mid_run_stops_cleanly_and_keeps_progress(tmp_path, capsys):
    from instagrapi import exceptions as E
    code, summ, out = _blocked_run(E.ClientForbiddenError("forbidden"), tmp_path, capsys)

    assert code == 1
    assert "rate-limiting" in out and "ClientForbiddenError" in out
    assert "1/2 highlight(s) checked" in out
    assert (tmp_path / "instagram" / "One" / "metadata.json").exists()  # finished one saved
    assert not (tmp_path / "instagram" / "Two").exists()                # stopped before it
    summ.run.assert_called_once()                                       # summary.json refreshed


def test_login_required_mid_run_says_signed_out(tmp_path, capsys):
    from instagrapi import exceptions as E
    code, _, out = _blocked_run(E.LoginRequired("login_required"), tmp_path, capsys)
    assert code == 1
    assert "signed this session out" in out


def test_unrelated_errors_are_not_treated_as_blocks(tmp_path, capsys):
    with pytest.raises(ValueError):
        _blocked_run(ValueError("a real bug"), tmp_path, capsys)


def test_challenge_at_login_exits_cleanly(tmp_path, capsys):
    from instagrapi import exceptions as E
    fake = MagicMock()
    fake.login.side_effect = E.ChallengeRequired("challenge_required")
    with patch("instagrapi.Client", return_value=fake), \
         patch.object(igd, "_settings_path", return_value=tmp_path / "none.json"), \
         patch.object(igd.getpass, "getpass", return_value="pw"):
        with pytest.raises(SystemExit) as exc:
            igd._authenticate("someone")
    assert exc.value.code == 1
    assert "approve it" in capsys.readouterr().out


# ── re-login after a revoked session ───────────────────────────────────────────

def test_revoked_session_does_a_real_login_keeping_device(tmp_path):
    """Regression: a dead session left user_id set, so instagrapi's login()
    returned early without sending the password and the tool reported success."""
    settings = tmp_path / "s.json"
    settings.write_text("{}")
    fake = MagicMock()
    fake.get_timeline_feed.side_effect = Exception("login_required")
    fake.get_settings.return_value = {
        "uuids": {"uuid": "U", "phone_id": "P"},
        "device_settings": {"model": "M", "app_version": "428.0.0.47.67",
                            "version_code": "961145276", "bloks_versioning_id": "old"},
        "authorization_data": {"ds_user_id": "1"},
    }
    with patch("instagrapi.Client", return_value=fake), \
         patch.object(igd, "_settings_path", return_value=settings), \
         patch.object(igd.getpass, "getpass", return_value="pw"):
        igd._authenticate("me")

    from instagrapi import config as ig_config
    order = [c[0] for c in fake.method_calls]
    assert order.index("set_settings") < order.index("login")  # cleared first
    fake.set_settings.assert_called_once_with({})
    fake.set_uuids.assert_called_once_with({"uuid": "U", "phone_id": "P"})  # same device
    fake.set_device.assert_called_once_with({"model": "M"})  # hardware only, stale app dropped
    fake.set_app.assert_called_once_with(ig_config.DEFAULT_APP_VERSION)  # app "updated"
    assert order.index("set_app") < order.index("set_user_agent") < order.index("login")
    fake.login.assert_called_once_with("me", "pw")


def test_valid_saved_session_is_reused_without_login(tmp_path):
    settings = tmp_path / "s.json"
    settings.write_text("{}")
    fake = MagicMock()
    with patch("instagrapi.Client", return_value=fake), \
         patch.object(igd, "_settings_path", return_value=settings):
        assert igd._authenticate("me") is fake
    fake.login.assert_not_called()
    fake.set_settings.assert_not_called()

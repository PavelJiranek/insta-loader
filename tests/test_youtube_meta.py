from insta_loader.cli import YoutubeConfig
from insta_loader.youtube_meta import _decode_flags, _parse_title, _first_slide_date, _resolve_location


def test_first_slide_date_returns_first_non_failed():
    slides = [
        {"status": "failed", "date_utc": "2019-01-01T00:00:00Z"},
        {"status": "downloaded", "date_utc": "2019-02-15T10:30:00Z"},
        {"status": "downloaded", "date_utc": "2019-02-20T00:00:00Z"},
    ]
    assert _first_slide_date(slides) == "2019-02-15"


def test_first_slide_date_returns_none_when_all_failed():
    slides = [{"status": "failed", "date_utc": "2019-01-01T00:00:00Z"}]
    assert _first_slide_date(slides) is None


def test_first_slide_date_returns_none_for_empty():
    assert _first_slide_date([]) is None


def test_resolve_location_city_lookup():
    result = _resolve_location("Prague", [])
    assert result is not None
    assert abs(result["latitude"] - 50.08) < 0.1
    assert abs(result["longitude"] - 14.44) < 0.1


def test_resolve_location_country_fallback():
    result = _resolve_location("Bohemia", ["CZ"])
    assert result is not None
    assert abs(result["latitude"] - 49.82) < 0.5


def test_resolve_location_returns_none_when_unknown():
    result = _resolve_location("SomeUnknownPlace", [])
    assert result is None


def test_resolve_location_city_takes_priority_over_country():
    # Berlin is in CITY_TO_LATLON; should use city coords, not DE centroid
    city = _resolve_location("Berlin", ["DE"])
    country = _resolve_location("", ["DE"])
    assert city != country


def test_youtube_config_defaults():
    c = YoutubeConfig(username="natgeo")
    assert c.highlight is None
    assert c.output_dir is None
    assert c.client_secrets is None
    assert c.playlist == "Story Highlights"


def test_decode_flags_single():
    assert _decode_flags("🇿🇦9.CapeTown") == ["ZA"]


def test_decode_flags_none():
    assert _decode_flags("CapeTown") == []


def test_decode_flags_multiple():
    # 🇬🇧🇫🇷 = GB + FR
    s = "\U0001F1EC\U0001F1E7\U0001F1EB\U0001F1F7London"
    assert _decode_flags(s) == ["GB", "FR"]


def test_parse_title_camel_case():
    place, part = _parse_title("CapeTown")
    assert place == "Cape Town"
    assert part is None


def test_parse_title_strips_sequence_number_with_dot():
    place, part = _parse_title("\U0001F1FF\U0001F1E69.CapeTown")
    assert place == "Cape Town"
    assert part is None


def test_parse_title_detects_pt_suffix():
    place, part = _parse_title("\U0001F1FF\U0001F1E69.CapeTown_Pt2")
    assert place == "Cape Town"
    assert part == 2


def test_parse_title_digit_before_flag():
    # 8🇿🇦CapePeninsula
    s = "8\U0001F1FF\U0001F1E6CapePeninsula"
    place, part = _parse_title(s)
    assert place == "Cape Peninsula"
    assert part is None


def test_parse_title_underscore_separated():
    # 🇦🇷_Buenos_Aires
    s = "\U0001F1E6\U0001F1F7_Buenos_Aires"
    place, part = _parse_title(s)
    assert place == "Buenos Aires"
    assert part is None


def test_parse_title_roman_numeral_part():
    place, part = _parse_title("Cape_Part_II")
    assert place == "Cape"
    assert part == 2


def test_parse_title_no_flags_no_sequence():
    place, part = _parse_title("LosAngeles")
    assert place == "Los Angeles"
    assert part is None


from insta_loader.youtube_meta import _build_tags


def test_build_tags_africa():
    assert _build_tags("Cape Town", ["ZA"]) == ["Cape Town", "South Africa", "Africa"]


def test_build_tags_europe_eu():
    assert _build_tags("Zillertal", ["AT"]) == ["Zillertal", "Austria", "Europe", "EU"]


def test_build_tags_north_america_with_state():
    tags = _build_tags("Los Angeles", ["US"])
    assert tags == ["Los Angeles", "California", "United States", "North America", "Americas"]


def test_build_tags_south_america():
    tags = _build_tags("São Paulo", ["BR"])
    assert tags == ["São Paulo", "Brazil", "South America", "Americas"]


def test_build_tags_no_flag_city_lookup():
    tags = _build_tags("Cape Town", [])
    assert "South Africa" in tags
    assert "Africa" in tags


def test_build_tags_no_flag_us_city_lookup():
    tags = _build_tags("Los Angeles", [])
    assert "California" in tags
    assert "United States" in tags
    assert "Americas" in tags


def test_build_tags_no_flag_unknown_city():
    assert _build_tags("SomeRandomPlace", []) == ["SomeRandomPlace"]


def test_build_tags_europe_non_eu():
    tags = _build_tags("London", ["GB"])
    assert tags == ["London", "United Kingdom", "Europe"]
    assert "EU" not in tags


from insta_loader.youtube_meta import _date_range


def _slide(date_utc, status="downloaded"):
    return {"date_utc": date_utc, "status": status}


def test_date_range_same_month():
    slides = [_slide("2025-11-01T00:00:00Z"), _slide("2025-11-15T00:00:00Z")]
    assert _date_range(slides) == "Nov 2025"


def test_date_range_adjacent_months_same_year():
    slides = [_slide("2026-04-10T00:00:00Z"), _slide("2026-05-20T00:00:00Z")]
    assert _date_range(slides) == "Apr–May 2026"


def test_date_range_cross_year():
    slides = [_slide("2025-12-20T00:00:00Z"), _slide("2026-01-05T00:00:00Z")]
    assert _date_range(slides) == "Dec 2025–Jan 2026"


def test_date_range_skips_failed_slides():
    slides = [
        _slide("2025-11-01T00:00:00Z"),
        _slide("2026-05-01T00:00:00Z", status="failed"),
    ]
    assert _date_range(slides) == "Nov 2025"


def test_date_range_empty_slides():
    assert _date_range([]) == ""


def test_date_range_all_failed():
    assert _date_range([_slide("2025-11-01T00:00:00Z", status="failed")]) == ""


import json
from insta_loader.youtube_meta import _build_youtube_meta, _write_meta


def test_build_youtube_meta_title_and_description():
    slides = [
        _slide("2026-04-10T00:00:00Z"),
        _slide("2026-05-20T00:00:00Z"),
    ]
    # 🇿🇦 = \U0001F1FF\U0001F1E6
    folder = "\U0001F1FF\U0001F1E69.CapeTown_Pt2"
    meta = _build_youtube_meta(folder, slides, "testuser")
    assert meta["youtube"]["title"] == "\U0001F1FF\U0001F1E6 Cape Town · Part 2 · Apr–May 2026"
    assert "Cape Town" in meta["youtube"]["description"]
    assert "Part 2" in meta["youtube"]["description"]
    assert "@testuser" in meta["youtube"]["description"]


def test_build_youtube_meta_structure():
    slides = [_slide("2026-04-01T00:00:00Z")]
    meta = _build_youtube_meta("Travel", slides, "user")
    assert meta["highlight_folder"] == "Travel"
    assert meta["video_path"] == "output/user/videos/Travel.mp4"
    assert meta["youtube"]["category_id"] == "19"
    assert meta["youtube"]["privacy_status"] == "unlisted"
    assert meta["uploaded"] is False
    assert meta["youtube_id"] is None
    assert meta["youtube_url"] is None


def test_build_youtube_meta_tags_populated():
    slides = [_slide("2026-04-01T00:00:00Z")]
    folder = "\U0001F1FF\U0001F1E6Travel"  # 🇿🇦Travel
    meta = _build_youtube_meta(folder, slides, "user")
    assert "Travel" in meta["youtube"]["tags"]
    assert "South Africa" in meta["youtube"]["tags"]


def test_write_meta_creates_file(tmp_path):
    meta = {"highlight_folder": "Test", "uploaded": False, "youtube_id": None}
    result = _write_meta(tmp_path, "Test", meta)
    assert result is True
    written = json.loads((tmp_path / "Test.json").read_text())
    assert written["highlight_folder"] == "Test"


def test_write_meta_skips_if_already_uploaded(tmp_path):
    existing = {"highlight_folder": "Test", "uploaded": True, "youtube_id": "abc123"}
    (tmp_path / "Test.json").write_text(json.dumps(existing))
    result = _write_meta(tmp_path, "Test", {"highlight_folder": "Test", "uploaded": False})
    assert result is False
    assert json.loads((tmp_path / "Test.json").read_text())["youtube_id"] == "abc123"


def test_write_meta_overwrites_if_not_uploaded(tmp_path):
    old = {"highlight_folder": "Test", "uploaded": False, "youtube_id": None}
    (tmp_path / "Test.json").write_text(json.dumps(old))
    new_meta = {"highlight_folder": "Test", "uploaded": False,
                "youtube": {"title": "Updated Title"}}
    result = _write_meta(tmp_path, "Test", new_meta)
    assert result is True
    assert json.loads((tmp_path / "Test.json").read_text())["youtube"]["title"] == "Updated Title"


def test_write_meta_creates_youtube_dir(tmp_path):
    subdir = tmp_path / "youtube"
    meta = {"highlight_folder": "Test", "uploaded": False}
    _write_meta(subdir, "Test", meta)
    assert subdir.exists()
    assert (subdir / "Test.json").exists()


from unittest.mock import patch
from insta_loader.youtube_meta import run as run_meta


def _make_highlight(base, name, slides=None):
    hdir = base / "instagram" / name
    hdir.mkdir(parents=True)
    if slides is None:
        slides = [{"date_utc": "2026-04-01T00:00:00Z", "status": "downloaded"}]
    (hdir / "metadata.json").write_text(json.dumps({
        "highlight_title": name,
        "slides": slides,
    }))
    return hdir


def test_run_skips_highlight_with_no_video(tmp_path, capsys):
    _make_highlight(tmp_path, "Travel")
    run_meta(YoutubeConfig(username="test", output_dir=str(tmp_path)))
    assert not (tmp_path / "youtube").exists()
    assert "no video" in capsys.readouterr().out.lower()


def test_run_creates_json_for_highlight_with_video(tmp_path):
    _make_highlight(tmp_path, "Travel")
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "Travel.mp4").touch()

    run_meta(YoutubeConfig(username="test", output_dir=str(tmp_path)))

    assert (tmp_path / "youtube" / "Travel.json").exists()


def test_run_skips_already_uploaded(tmp_path, capsys):
    _make_highlight(tmp_path, "Travel")
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "Travel.mp4").touch()
    youtube_dir = tmp_path / "youtube"
    youtube_dir.mkdir()
    existing = {"highlight_folder": "Travel", "uploaded": True, "youtube_id": "abc"}
    (youtube_dir / "Travel.json").write_text(json.dumps(existing))

    run_meta(YoutubeConfig(username="test", output_dir=str(tmp_path)))

    out = capsys.readouterr().out
    assert "skipped" in out.lower()
    assert json.loads((youtube_dir / "Travel.json").read_text())["youtube_id"] == "abc"


def test_run_filters_by_highlight_name(tmp_path):
    _make_highlight(tmp_path, "Travel")
    _make_highlight(tmp_path, "Summer")
    videos_dir = tmp_path / "videos"
    videos_dir.mkdir()
    (videos_dir / "Travel.mp4").touch()
    (videos_dir / "Summer.mp4").touch()

    run_meta(YoutubeConfig(username="test", output_dir=str(tmp_path), highlight="travel"))

    assert (tmp_path / "youtube" / "Travel.json").exists()
    assert not (tmp_path / "youtube" / "Summer.json").exists()

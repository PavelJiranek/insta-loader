from insta_loader.cli import YoutubeConfig
from insta_loader.youtube_meta import _decode_flags, _parse_title


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

from insta_loader.variants import Variant, resolve


# ── naming ────────────────────────────────────────────────────────────────────

def test_portrait_full_has_no_suffix():
    v = Variant()
    assert v.suffix == ""
    assert v.videos_dir == "videos"
    assert v.youtube_dir == "youtube"
    assert v.stem("Travel") == "Travel"
    assert v.title_suffix == ""


def test_landscape_full_matches_existing_convention():
    v = Variant(landscape=True)
    assert v.videos_dir == "videos_landscape"
    assert v.youtube_dir == "youtube_landscape"
    assert v.stem("Travel") == "Travel_landscape"
    assert v.title_suffix == " · 16:9"


def test_portrait_short():
    v = Variant(short=True)
    assert v.videos_dir == "videos_short"
    assert v.youtube_dir == "youtube_short"
    assert v.stem("Travel") == "Travel_short"
    assert v.title_suffix == " · Short"


def test_landscape_short():
    v = Variant(landscape=True, short=True)
    assert v.videos_dir == "videos_landscape_short"
    assert v.youtube_dir == "youtube_landscape_short"
    assert v.stem("Travel") == "Travel_landscape_short"
    assert v.title_suffix == " · 16:9 · Short"


def test_labels_are_distinct():
    labels = {v.label for v in resolve(all_variants=True)}
    assert len(labels) == 4


# ── resolve() ─────────────────────────────────────────────────────────────────

def test_resolve_default_is_portrait_full():
    assert resolve() == [Variant(False, False)]


def test_resolve_landscape_only():
    assert resolve(landscape=True) == [Variant(True, False)]


def test_resolve_short_only():
    assert resolve(short=True) == [Variant(False, True)]


def test_resolve_both_formats_keeps_length():
    assert resolve(both_formats=True) == [Variant(False, False), Variant(True, False)]


def test_resolve_both_formats_with_short():
    assert resolve(both_formats=True, short=True) == [Variant(False, True), Variant(True, True)]


def test_resolve_all_variants_returns_four_unique():
    got = resolve(all_variants=True)
    assert len(got) == 4
    assert len(set(got)) == 4
    assert got[0] == Variant(False, False)  # portrait full first


def test_resolve_all_variants_overrides_other_flags():
    got = resolve(landscape=True, short=True, both_formats=True, all_variants=True)
    assert got == [
        Variant(False, False), Variant(False, True),
        Variant(True, False), Variant(True, True),
    ]

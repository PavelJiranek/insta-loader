import json
import re
import sys
from pathlib import Path
from typing import Optional

import pycountry

from insta_loader.cli import YoutubeConfig
from insta_loader.video_creator import _filter_highlights


# ── Geo data ─────────────────────────────────────────────────────────────────

EU_COUNTRIES = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
    "NL", "PL", "PT", "RO", "SE", "SI", "SK",
}

COUNTRY_TO_CONTINENT = {
    # Africa
    "ZA": "Africa", "NG": "Africa", "KE": "Africa", "ET": "Africa",
    "EG": "Africa", "GH": "Africa", "TZ": "Africa", "MA": "Africa",
    "DZ": "Africa", "MZ": "Africa", "CI": "Africa", "CM": "Africa",
    "SN": "Africa", "ZM": "Africa", "ZW": "Africa", "TN": "Africa",
    # North America
    "US": "North America", "CA": "North America", "MX": "North America",
    "GT": "North America", "HN": "North America", "SV": "North America",
    "NI": "North America", "CR": "North America", "PA": "North America",
    "CU": "North America", "JM": "North America", "HT": "North America",
    "DO": "North America", "TT": "North America", "BB": "North America",
    # South America
    "BR": "South America", "AR": "South America", "CO": "South America",
    "VE": "South America", "CL": "South America", "PE": "South America",
    "EC": "South America", "BO": "South America", "PY": "South America",
    "UY": "South America", "GY": "South America", "SR": "South America",
    # Asia
    "CN": "Asia", "JP": "Asia", "IN": "Asia", "KR": "Asia", "TH": "Asia",
    "VN": "Asia", "ID": "Asia", "MY": "Asia", "SG": "Asia", "PH": "Asia",
    "AE": "Asia", "SA": "Asia", "IL": "Asia", "TR": "Asia", "PK": "Asia",
    "BD": "Asia", "KH": "Asia", "MM": "Asia", "NP": "Asia", "LK": "Asia",
    "KZ": "Asia", "UZ": "Asia", "GE": "Asia", "AM": "Asia", "AZ": "Asia",
    "JO": "Asia", "LB": "Asia", "OM": "Asia", "QA": "Asia", "KW": "Asia",
    "BH": "Asia", "IQ": "Asia", "IR": "Asia", "TW": "Asia", "HK": "Asia",
    # Europe
    "GB": "Europe", "FR": "Europe", "DE": "Europe", "IT": "Europe",
    "ES": "Europe", "PT": "Europe", "NL": "Europe", "BE": "Europe",
    "CH": "Europe", "AT": "Europe", "SE": "Europe", "NO": "Europe",
    "DK": "Europe", "FI": "Europe", "PL": "Europe", "CZ": "Europe",
    "SK": "Europe", "HU": "Europe", "RO": "Europe", "BG": "Europe",
    "GR": "Europe", "HR": "Europe", "SI": "Europe", "RS": "Europe",
    "BA": "Europe", "ME": "Europe", "MK": "Europe", "AL": "Europe",
    "UA": "Europe", "BY": "Europe", "MD": "Europe", "LT": "Europe",
    "LV": "Europe", "EE": "Europe", "IS": "Europe", "IE": "Europe",
    "LU": "Europe", "MT": "Europe", "CY": "Europe", "LI": "Europe",
    "MC": "Europe", "SM": "Europe", "AD": "Europe",
    # Oceania
    "AU": "Oceania", "NZ": "Oceania", "FJ": "Oceania", "PG": "Oceania",
    "SB": "Oceania", "VU": "Oceania", "WS": "Oceania", "TO": "Oceania",
}

CITY_TO_COUNTRY = {
    "los angeles": "US", "new york": "US", "chicago": "US", "houston": "US",
    "san francisco": "US", "seattle": "US", "miami": "US", "boston": "US",
    "san diego": "US", "denver": "US", "las vegas": "US", "phoenix": "US",
    "portland": "US", "atlanta": "US", "nashville": "US", "new orleans": "US",
    "cape town": "ZA", "johannesburg": "ZA", "durban": "ZA",
    "buenos aires": "AR",
    "sao paulo": "BR", "são paulo": "BR", "rio de janeiro": "BR",
    "paris": "FR", "london": "GB", "berlin": "DE", "madrid": "ES",
    "rome": "IT", "amsterdam": "NL", "vienna": "AT", "prague": "CZ",
    "budapest": "HU", "warsaw": "PL", "lisbon": "PT", "athens": "GR",
    "brussels": "BE", "zurich": "CH", "stockholm": "SE", "oslo": "NO",
    "copenhagen": "DK", "helsinki": "FI", "dublin": "IE",
    "tokyo": "JP", "osaka": "JP", "kyoto": "JP",
    "sydney": "AU", "melbourne": "AU", "brisbane": "AU",
    "toronto": "CA", "vancouver": "CA", "montreal": "CA",
    "mexico city": "MX", "cancun": "MX", "guadalajara": "MX",
    "dubai": "AE", "singapore": "SG", "bangkok": "TH", "bali": "ID",
    "istanbul": "TR", "zillertal": "AT", "salzburg": "AT", "innsbruck": "AT",
    "barcelona": "ES", "seville": "ES", "valencia": "ES",
    "florence": "IT", "venice": "IT", "milan": "IT", "naples": "IT",
    "bogota": "CO", "medellin": "CO", "cartagena": "CO",
    "lima": "PE", "cusco": "PE",
    "santiago": "CL",
}

CITY_TO_STATE = {
    "los angeles": "California", "san francisco": "California",
    "san diego": "California", "sacramento": "California",
    "new york": "New York", "buffalo": "New York",
    "chicago": "Illinois",
    "houston": "Texas", "dallas": "Texas", "austin": "Texas",
    "san antonio": "Texas",
    "miami": "Florida", "orlando": "Florida", "tampa": "Florida",
    "jacksonville": "Florida",
    "seattle": "Washington",
    "boston": "Massachusetts",
    "denver": "Colorado",
    "las vegas": "Nevada",
    "phoenix": "Arizona",
    "portland": "Oregon",
    "atlanta": "Georgia",
    "nashville": "Tennessee",
    "new orleans": "Louisiana",
    "minneapolis": "Minnesota",
    "detroit": "Michigan",
    "philadelphia": "Pennsylvania",
    "pittsburgh": "Pennsylvania",
}


# ── Flag helpers ──────────────────────────────────────────────────────────────

def _decode_flags(folder_name: str) -> list:
    """Extract flag emoji pairs; return list of ISO-3166-1 alpha-2 codes."""
    codes = []
    chars = list(folder_name)
    i = 0
    while i < len(chars):
        cp = ord(chars[i])
        if 0x1F1E6 <= cp <= 0x1F1FF and i + 1 < len(chars):
            cp2 = ord(chars[i + 1])
            if 0x1F1E6 <= cp2 <= 0x1F1FF:
                codes.append(chr(cp - 0x1F1A5) + chr(cp2 - 0x1F1A5))
                i += 2
                continue
        i += 1
    return codes


def _extract_flag_str(folder_name: str) -> str:
    """Return raw flag emoji string (all flag pairs concatenated)."""
    result = []
    chars = list(folder_name)
    i = 0
    while i < len(chars):
        cp = ord(chars[i])
        if 0x1F1E6 <= cp <= 0x1F1FF and i + 1 < len(chars):
            cp2 = ord(chars[i + 1])
            if 0x1F1E6 <= cp2 <= 0x1F1FF:
                result.append(chars[i] + chars[i + 1])
                i += 2
                continue
        i += 1
    return "".join(result)


def _strip_flags(s: str) -> str:
    return "".join(c for c in s if not (0x1F1E6 <= ord(c) <= 0x1F1FF))


# ── Title parsing ─────────────────────────────────────────────────────────────

def _roman_to_int(s: str) -> int:
    roman = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    s = s.upper()
    total = 0
    for i, c in enumerate(s):
        if i + 1 < len(s) and roman.get(c, 0) < roman.get(s[i + 1], 0):
            total -= roman.get(c, 0)
        else:
            total += roman.get(c, 0)
    return total


_PART_PATTERNS = [
    (r"[_\s]?[Pp]t\.?\s*(\d+)\s*$", lambda m: int(m.group(1))),
    (r"[_\s]?[Pp]art\.?\s*_?\s*(\d+)\s*$", lambda m: int(m.group(1))),
    (
        r"[_\s]?[Pp]art\.?\s*_?\s*(II|III|IV|V|VI|VII|VIII|IX|X|XI|XII)\s*$",
        lambda m: _roman_to_int(m.group(1)),
    ),
]


def _parse_title(folder_name: str) -> tuple:
    """Return (place_name, part_number) — part_number is None if no part suffix found."""
    s = _strip_flags(folder_name)
    s = re.sub(r"^\d+\.?", "", s)
    s = s.strip("_. ")

    part_num = None
    for pattern, extractor in _PART_PATTERNS:
        m = re.search(pattern, s, re.IGNORECASE)
        if m:
            part_num = extractor(m)
            s = s[: m.start()]
            break

    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    s = s.replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip(" .")

    return s, part_num


def _build_tags(place_name: str, country_codes: list) -> list:
    """Enrich a place name with country/continent/EU/state tags."""
    if not country_codes:
        iso = CITY_TO_COUNTRY.get(place_name.lower())
        if iso:
            country_codes = [iso]

    tags = [place_name] if place_name.strip() else []

    for iso in country_codes:
        if iso == "US":
            state = CITY_TO_STATE.get(place_name.lower())
            if state:
                tags.append(state)

        country = pycountry.countries.get(alpha_2=iso)
        if country:
            tags.append(country.name)

        continent = COUNTRY_TO_CONTINENT.get(iso)
        if continent in ("North America", "South America"):
            tags.append(continent)
            tags.append("Americas")
        elif continent:
            tags.append(continent)

        if iso in EU_COUNTRIES:
            tags.append("EU")

    seen: set = set()
    result = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _date_range(slides: list) -> str:
    """Return formatted date range from first and last non-failed slides."""
    dates = []
    for s in slides:
        if s.get("status") == "failed":
            continue
        d = s.get("date_utc", "")
        m = re.match(r"(\d{4})-(\d{2})", d)
        if m:
            dates.append((int(m.group(1)), int(m.group(2))))

    if not dates:
        return ""

    first_y, first_m = min(dates)
    last_y, last_m = max(dates)

    if first_y == last_y and first_m == last_m:
        return f"{_MONTHS[first_m - 1]} {first_y}"
    elif first_y == last_y:
        return f"{_MONTHS[first_m - 1]}–{_MONTHS[last_m - 1]} {first_y}"
    else:
        return f"{_MONTHS[first_m - 1]} {first_y}–{_MONTHS[last_m - 1]} {last_y}"


def _build_youtube_meta(folder_name: str, slides: list, username: str) -> dict:
    country_codes = _decode_flags(folder_name)
    flag_str = _extract_flag_str(folder_name)
    place_name, part_num = _parse_title(folder_name)
    date_str = _date_range(slides)
    tags = _build_tags(place_name, country_codes)

    title_parts = []
    if flag_str:
        title_parts.append(flag_str)
    title_parts.append(place_name)
    if part_num is not None:
        title_parts.append(f"· Part {part_num}")
    if date_str:
        title_parts.append(f"· {date_str}")
    title = " ".join(title_parts)

    desc_main = place_name
    if part_num is not None:
        desc_main += f" · Part {part_num}"
    if date_str:
        desc_main += f" · {date_str}"
    description = f"{desc_main}\n\n@{username}"

    video_path = str(Path("output") / username / "videos" / f"{folder_name}.mp4")
    return {
        "highlight_folder": folder_name,
        "video_path": video_path,
        "youtube": {
            "title": title,
            "description": description,
            "tags": tags,
            "category_id": "19",
            "privacy_status": "private",
        },
        "uploaded": False,
        "youtube_id": None,
        "youtube_url": None,
        "outdated": False,
    }


def _write_meta(youtube_dir: Path, folder_name: str, meta: dict) -> bool:
    """Write JSON file. Returns False (skipped) if already uploaded, True otherwise."""
    youtube_dir.mkdir(parents=True, exist_ok=True)
    meta_path = youtube_dir / f"{folder_name}.json"
    if meta_path.exists():
        existing = json.loads(meta_path.read_text(encoding="utf-8"))
        if existing.get("uploaded"):
            return False
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def run(config: YoutubeConfig) -> None:
    from rich import print as rprint

    base = Path(config.output_dir) if config.output_dir else Path("output") / config.username
    if not base.exists():
        print(f"✗  No downloaded highlights found at {base}")
        sys.exit(1)

    highlight_dirs = sorted(
        d for d in base.iterdir() if d.is_dir() and (d / "metadata.json").exists()
    )
    if not highlight_dirs:
        print(f"✗  No downloaded highlights found at {base}")
        sys.exit(1)

    if config.highlight:
        highlight_dirs = _filter_highlights(config.highlight, highlight_dirs)

    videos_dir = base / "videos"
    youtube_dir = base / "youtube"

    for hdir in highlight_dirs:
        folder_name = hdir.name
        video_path = videos_dir / f"{folder_name}.mp4"

        if not video_path.exists():
            print(f"✗  {folder_name} — no video at {video_path}, skipping")
            continue

        meta_obj = json.loads((hdir / "metadata.json").read_text(encoding="utf-8"))
        slides = meta_obj.get("slides", [])
        meta = _build_youtube_meta(folder_name, slides, config.username)
        written = _write_meta(youtube_dir, folder_name, meta)

        title = meta["youtube"]["title"]
        if written:
            meta_path = youtube_dir / f"{folder_name}.json"
            rprint(f"[green]✓[/green]  {title} → {meta_path}")
        else:
            rprint(f"[dim]–  {title} skipped (already uploaded, not regenerating)[/dim]")

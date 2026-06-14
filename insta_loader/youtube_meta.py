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

CITY_TO_LATLON = {
    # North America
    "los angeles": (34.05, -118.24), "new york": (40.71, -74.01),
    "chicago": (41.88, -87.63), "houston": (29.76, -95.37),
    "san francisco": (37.77, -122.42), "seattle": (47.61, -122.33),
    "miami": (25.77, -80.19), "boston": (42.36, -71.06),
    "san diego": (32.72, -117.16), "denver": (39.74, -104.98),
    "las vegas": (36.17, -115.14), "phoenix": (33.45, -112.07),
    "portland": (45.52, -122.68), "atlanta": (33.75, -84.39),
    "nashville": (36.17, -86.78), "new orleans": (29.95, -90.07),
    "toronto": (43.65, -79.38), "vancouver": (49.25, -123.12),
    "montreal": (45.50, -73.57), "mexico city": (19.43, -99.13),
    "cancun": (21.16, -86.85), "guadalajara": (20.66, -103.35),
    # South America
    "buenos aires": (-34.60, -58.38), "sao paulo": (-23.55, -46.63),
    "são paulo": (-23.55, -46.63), "rio de janeiro": (-22.91, -43.17),
    "bogota": (4.71, -74.07), "medellin": (6.25, -75.56),
    "cartagena": (10.39, -75.48), "lima": (-12.05, -77.04),
    "cusco": (-13.53, -71.97), "santiago": (-33.45, -70.67),
    "montevideo": (-34.90, -56.19),
    # Europe — West
    "london": (51.51, -0.13), "paris": (48.85, 2.35),
    "berlin": (52.52, 13.40), "madrid": (40.42, -3.70),
    "rome": (41.90, 12.50), "amsterdam": (52.37, 4.90),
    "vienna": (48.21, 16.37), "zurich": (47.38, 8.54),
    "brussels": (50.85, 4.35), "lisbon": (38.72, -9.14),
    "barcelona": (41.39, 2.15), "seville": (37.39, -5.99),
    "valencia": (39.47, -0.38), "florence": (43.77, 11.26),
    "venice": (45.44, 12.32), "milan": (45.46, 9.19),
    "naples": (40.85, 14.27), "dublin": (53.33, -6.25),
    "edinburgh": (55.95, -3.19), "luxembourg": (49.61, 6.13),
    # Europe — North
    "stockholm": (59.33, 18.07), "oslo": (59.91, 10.75),
    "copenhagen": (55.68, 12.57), "helsinki": (60.17, 24.94),
    "reykjavik": (64.13, -21.95), "malmö": (55.61, 13.00),
    # Europe — Central & East
    "prague": (50.08, 14.44), "budapest": (47.50, 19.04),
    "warsaw": (52.23, 21.01), "athens": (37.98, 23.73),
    "bucharest": (44.43, 26.10), "sofia": (42.70, 23.32),
    "zagreb": (45.81, 15.98), "ljubljana": (46.06, 14.51),
    "bratislava": (48.15, 17.11), "vilnius": (54.69, 25.28),
    "riga": (56.95, 24.11), "tallinn": (59.44, 24.75),
    "dubrovnik": (42.65, 18.09), "kotor": (42.42, 18.77),
    "shkodër": (42.07, 19.51), "shkoder": (42.07, 19.51),
    "bled": (46.37, 14.11),
    # Alps
    "zillertal": (47.27, 11.88), "salzburg": (47.80, 13.04),
    "innsbruck": (47.27, 11.40), "stubai": (47.10, 11.32),
    "hallstatt": (47.56, 13.65), "gmunden": (47.92, 13.80),
    "linz": (48.31, 14.29), "solden": (46.96, 11.00),
    "kitzbühel": (47.45, 12.39), "klínovec": (50.40, 12.97),
    "neuschwanstein": (47.56, 10.75), "nuremberg": (49.45, 11.08),
    "frankfurt": (50.11, 8.68), "hamburg": (53.55, 10.00),
    "münchen": (48.14, 11.58), "munich": (48.14, 11.58),
    "leipzig": (51.34, 12.37), "dresden": (51.05, 13.74),
    "köln": (50.94, 6.96), "regensburg": (49.01, 12.10),
    "gorlitz": (51.15, 14.99),
    # Mediterranean & Islands
    "athens": (37.98, 23.73), "corfu": (39.62, 19.92),
    "kos": (36.89, 27.29), "zakynthos": (37.79, 20.90),
    "cyprus": (35.13, 33.43), "nicosia": (35.17, 33.37),
    "valletta": (35.90, 14.51), "gran canaria": (27.93, -15.39),
    "mallorca": (39.70, 2.99),
    # Middle East & Asia
    "istanbul": (41.01, 28.95), "dubai": (25.20, 55.27),
    "tel aviv": (32.08, 34.78), "jerusalem": (31.77, 35.22),
    "singapore": (1.35, 103.82), "bangkok": (13.75, 100.52),
    "bali": (-8.34, 115.09), "jakarta": (-6.21, 106.85),
    "tokyo": (35.69, 139.69), "osaka": (34.69, 135.50),
    "kyoto": (35.01, 135.77), "hong kong": (22.32, 114.17),
    "macao": (22.20, 113.55), "taipei": (25.03, 121.57),
    "seoul": (37.57, 126.98), "kuala lumpur": (3.14, 101.69),
    # Oceania
    "sydney": (-33.87, 151.21), "melbourne": (-37.81, 144.96),
    "brisbane": (-27.47, 153.03), "auckland": (-36.85, 174.76),
    # Africa
    "cape town": (-33.92, 18.42), "johannesburg": (-26.20, 28.04),
    "durban": (-29.86, 31.02), "agadir": (30.43, -9.60),
    "casablanca": (33.59, -7.62), "nairobi": (-1.29, 36.82),
}

COUNTRY_TO_LATLON = {
    "US": (37.09, -95.71), "CA": (56.13, -106.35), "MX": (23.63, -102.55),
    "BR": (-14.24, -51.93), "AR": (-38.42, -63.62), "CO": (4.57, -74.30),
    "CL": (-35.68, -71.54), "PE": (-9.19, -75.02), "UY": (-32.52, -55.77),
    "GB": (55.38, -3.44), "FR": (46.23, 2.21), "DE": (51.17, 10.45),
    "IT": (41.87, 12.57), "ES": (40.46, -3.75), "PT": (39.40, -8.22),
    "NL": (52.13, 5.29), "BE": (50.50, 4.47), "CH": (46.82, 8.23),
    "AT": (47.52, 14.55), "SE": (60.13, 18.64), "NO": (60.47, 8.47),
    "DK": (56.26, 9.50), "FI": (61.92, 25.75), "IE": (53.41, -8.24),
    "PL": (51.92, 19.15), "CZ": (49.82, 15.47), "SK": (48.67, 19.70),
    "HU": (47.16, 19.50), "RO": (45.94, 24.97), "BG": (42.73, 25.49),
    "GR": (39.07, 21.82), "HR": (45.10, 15.20), "SI": (46.15, 14.99),
    "RS": (44.02, 21.01), "BA": (43.92, 17.68), "ME": (42.71, 19.37),
    "MK": (41.61, 21.75), "AL": (41.15, 20.17), "LU": (49.82, 6.13),
    "MT": (35.94, 14.38), "CY": (35.13, 33.43), "IS": (64.96, -19.02),
    "EE": (58.60, 25.01), "LV": (56.88, 24.60), "LT": (55.17, 23.88),
    "UA": (48.38, 31.17), "BY": (53.71, 27.95),
    "AU": (-25.27, 133.78), "NZ": (-40.90, 174.89),
    "JP": (36.20, 138.25), "CN": (35.86, 104.20), "KR": (35.91, 127.77),
    "TH": (15.87, 100.99), "VN": (14.06, 108.28), "ID": (-0.79, 113.92),
    "MY": (4.21, 101.98), "SG": (1.35, 103.82), "PH": (12.88, 121.77),
    "TW": (23.70, 120.96), "HK": (22.32, 114.17), "MO": (22.20, 113.55),
    "AE": (23.42, 53.85), "SA": (23.89, 45.08), "TR": (38.96, 35.24),
    "IL": (31.05, 34.85), "JO": (30.59, 36.24), "LB": (33.85, 35.86),
    "ZA": (-30.56, 22.94), "NG": (9.08, 8.68), "KE": (-0.02, 37.91),
    "MA": (31.79, -7.09), "TZ": (-6.37, 34.89), "ET": (9.15, 40.49),
    "GH": (7.95, -1.02), "SZ": (-26.52, 31.47),
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


def _first_slide_date(slides: list) -> Optional[str]:
    """Return YYYY-MM-DD of the first non-failed slide, or None."""
    for s in slides:
        if s.get("status") == "failed":
            continue
        m = re.match(r"(\d{4}-\d{2}-\d{2})", s.get("date_utc", ""))
        if m:
            return m.group(1)
    return None


def _resolve_location(place_name: str, country_codes: list) -> Optional[dict]:
    """Return {latitude, longitude} from city lookup, falling back to country centroid."""
    latlon = CITY_TO_LATLON.get(place_name.lower())
    if latlon is None and country_codes:
        latlon = COUNTRY_TO_LATLON.get(country_codes[0])
    if latlon is None:
        return None
    return {"latitude": latlon[0], "longitude": latlon[1]}


def _build_youtube_meta(folder_name: str, slides: list, username: str, privacy: str = "unlisted", landscape: bool = False) -> dict:
    country_codes = _decode_flags(folder_name)
    flag_str = _extract_flag_str(folder_name)
    place_name, part_num = _parse_title(folder_name)
    date_str = _date_range(slides)
    tags = _build_tags(place_name, country_codes)
    recording_date = _first_slide_date(slides)
    location = _resolve_location(place_name, country_codes)

    title_parts = []
    if flag_str:
        title_parts.append(flag_str)
    title_parts.append(place_name)
    if part_num is not None:
        title_parts.append(f"· Part {part_num}")
    if date_str:
        title_parts.append(f"· {date_str}")
    title = " ".join(title_parts)
    if landscape:
        title = f"{title} · 16:9"

    desc_main = f"{place_name} highlights" if place_name.strip() else "highlights"
    if part_num is not None:
        desc_main += f" · Part {part_num}"
    if date_str:
        desc_main += f" · {date_str}"
    description = f"{desc_main}\n\n@{username}"

    video_subdir = "videos_landscape" if landscape else "videos"
    video_stem = f"{folder_name}_landscape" if landscape else folder_name
    video_path = str(Path("output") / username / video_subdir / f"{video_stem}.mp4")
    return {
        "highlight_folder": folder_name,
        "video_path": video_path,
        "recording_date": recording_date,
        "location": location,
        "youtube": {
            "title": title,
            "description": description,
            "tags": tags,
            "category_id": "19",
            "privacy_status": privacy,
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
    instagram_dir = base / "instagram"
    if not instagram_dir.exists():
        print(f"✗  No downloaded highlights found at {instagram_dir}")
        sys.exit(1)

    highlight_dirs = sorted(
        d for d in instagram_dir.iterdir() if d.is_dir() and (d / "metadata.json").exists()
    )
    if not highlight_dirs:
        print(f"✗  No downloaded highlights found at {instagram_dir}")
        sys.exit(1)

    if config.highlight:
        highlight_dirs = _filter_highlights(config.highlight, highlight_dirs)

    videos_dir = base / ("videos_landscape" if config.landscape else "videos")
    youtube_dir = base / ("youtube_landscape" if config.landscape else "youtube")

    for hdir in highlight_dirs:
        folder_name = hdir.name
        stem = f"{folder_name}_landscape" if config.landscape else folder_name
        video_path = videos_dir / f"{stem}.mp4"

        if not video_path.exists():
            print(f"✗  {folder_name} — no video at {video_path}, skipping")
            continue

        meta_obj = json.loads((hdir / "metadata.json").read_text(encoding="utf-8"))
        slides = meta_obj.get("slides", [])
        meta = _build_youtube_meta(folder_name, slides, config.username, config.privacy, landscape=config.landscape)
        written = _write_meta(youtube_dir, folder_name, meta)

        title = meta["youtube"]["title"]
        if written:
            meta_path = youtube_dir / f"{folder_name}.json"
            rprint(f"[green]✓[/green]  {title} → {meta_path}")
        else:
            rprint(f"[dim]–  {title} skipped (already uploaded, not regenerating)[/dim]")

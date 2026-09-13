"""Output variants: orientation (portrait / landscape) x length (full / short).

Naming extends the existing ``_landscape`` convention, so portrait-full and
landscape-full keep the exact directory and file names they already had:

    portrait  full   videos/                 Travel.mp4
    portrait  short  videos_short/           Travel_short.mp4
    landscape full   videos_landscape/       Travel_landscape.mp4
    landscape short  videos_landscape_short/ Travel_landscape_short.mp4
"""
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Variant:
    landscape: bool = False
    short: bool = False

    @property
    def suffix(self) -> str:
        """Filename/directory suffix, e.g. '_landscape_short' (empty for portrait full)."""
        out = ""
        if self.landscape:
            out += "_landscape"
        if self.short:
            out += "_short"
        return out

    @property
    def videos_dir(self) -> str:
        return "videos" + self.suffix

    @property
    def youtube_dir(self) -> str:
        return "youtube" + self.suffix

    @property
    def title_suffix(self) -> str:
        """Appended to YouTube titles and playlist names."""
        out = ""
        if self.landscape:
            out += " · 16:9"
        if self.short:
            out += " · Short"
        return out

    @property
    def label(self) -> str:
        """Human-readable heading shown between phases of a multi-variant run."""
        out = "Landscape (16:9)" if self.landscape else "Portrait"
        return f"{out} · Short" if self.short else out

    def stem(self, base: str) -> str:
        return base + self.suffix


def resolve(landscape: bool = False, short: bool = False,
            both_formats: bool = False, all_variants: bool = False) -> List[Variant]:
    """Return the variants a run should produce, in a stable order."""
    if all_variants:
        return [Variant(l, s) for l in (False, True) for s in (False, True)]
    orientations = (False, True) if both_formats else (landscape,)
    return [Variant(l, short) for l in orientations]

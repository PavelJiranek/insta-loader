import argparse
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    username: str
    output_dir: Optional[str]
    highlight: Optional[str]


def parse_args(argv=None) -> Config:
    parser = argparse.ArgumentParser(
        description="Download Instagram story highlights to local folders."
    )
    parser.add_argument("username", help="Instagram username (without @)")
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        help="Where to save downloads (default: <username>/highlights/)",
    )
    parser.add_argument(
        "--highlight",
        help="Download only this highlight reel (case-insensitive exact match)",
    )
    args = parser.parse_args(argv)

    if args.highlight is None:
        print(f"⚠  This will download all highlights for @{args.username}.")
        answer = input("Continue? [y/N]: ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    return Config(
        username=args.username,
        output_dir=args.output_dir,
        highlight=args.highlight,
    )

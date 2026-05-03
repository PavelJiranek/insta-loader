import argparse
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from insta_loader.cli import Config, VideoConfig
from insta_loader.downloader import run as run_highlights
from insta_loader.summarizer import run as run_summary
from insta_loader.video_creator import run as run_videos


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="insta",
        description="Instagram highlights downloader and video creator.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    hl = subparsers.add_parser("highlights", help="Download story highlights from Instagram.")
    hl.add_argument("username", help="Instagram username (without @)")
    hl.add_argument("--highlight", help="Partial name match — download only this highlight")
    hl.add_argument("--output-dir", dest="output_dir", help="Save to this directory instead of output/<username>/")
    hl.add_argument("--update", action="store_true", help="Skip highlights already marked complete — only download new or partial ones")
    hl.add_argument(
        "--login-user",
        dest="login_user",
        default=os.environ.get("INSTA_LOGIN_USER"),
        help="Instagram account to authenticate as (defaults to INSTA_LOGIN_USER from .env)",
    )

    vid = subparsers.add_parser("videos", help="Assemble downloaded slides into MP4s.")
    vid.add_argument("username", help="Instagram username (without @)")
    vid.add_argument("--highlight", help="Partial name match — create video only for this highlight")
    vid.add_argument("--output-dir", dest="output_dir", help="Base directory (default: output/<username>/)")
    vid.add_argument("--image-duration", dest="image_duration", type=int, default=10, metavar="SECONDS", help="Duration in seconds for image slides (default: 10)")
    vid.add_argument("--update", action="store_true", help="Re-encode only highlights that are newer than their existing video (and highlights with no video yet)")

    summ = subparsers.add_parser("summary", help="Regenerate summary.json from downloaded slides on disk.")
    summ.add_argument("username", help="Instagram username (without @)")
    summ.add_argument("--output-dir", dest="output_dir", help="Base directory (default: output/<username>/)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "highlights":
        if not args.highlight and not args.update:
            print(f"⚠  This will download all highlights for @{args.username}.")
            answer = input("Continue? [y/N]: ").strip().lower()
            if answer != "y":
                print("Aborted.")
                sys.exit(0)
        run_highlights(Config(
            username=args.username,
            output_dir=args.output_dir,
            highlight=args.highlight,
            login_user=args.login_user,
            update=args.update,
        ))

    elif args.command == "videos":
        run_videos(VideoConfig(
            username=args.username,
            highlight=args.highlight,
            output_dir=args.output_dir,
            image_duration=args.image_duration,
            update=args.update,
        ))

    elif args.command == "summary":
        run_summary(args.username, args.output_dir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n✗  Interrupted.")
        sys.exit(1)

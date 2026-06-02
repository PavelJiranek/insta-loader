import argparse
import os
import re
import sys

from dotenv import load_dotenv
load_dotenv()


def _validate_username(username: str) -> str:
    """Instagram usernames: letters, digits, dots, underscores, max 30 chars."""
    if not re.fullmatch(r"[a-zA-Z0-9._]{1,30}", username):
        print(f"✗  Invalid username '{username}'. Only letters, digits, dots and underscores allowed (max 30 chars).")
        sys.exit(1)
    return username

from insta_loader.cli import Config, VideoConfig, YoutubeConfig
from insta_loader.downloader import run as run_highlights
from insta_loader.summarizer import run as run_summary
from insta_loader.video_creator import run as run_videos
from insta_loader.youtube_meta import run as run_youtube_meta


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
    hl.add_argument("--retry-failed", dest="retry_failed", action="store_true", help="Only retry highlights that have failed slides — skips complete and partial-without-failures")
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
    vid.add_argument("--landscape", action="store_true", help="Create 16:9 landscape videos with blurred+darkened background (outputs to videos_landscape/)")

    summ = subparsers.add_parser("summary", help="Regenerate summary.json from downloaded slides on disk.")
    summ.add_argument("username", help="Instagram username (without @)")
    summ.add_argument("--output-dir", dest="output_dir", help="Base directory (default: output/<username>/)")

    yt_meta = subparsers.add_parser("youtube-meta", help="Generate YouTube metadata JSON for downloaded highlights.")
    yt_meta.add_argument("username", metavar="insta-username", help="Instagram username (folder name under output/)")
    yt_meta.add_argument("--highlight", help="Partial name match — process only this highlight")
    yt_meta.add_argument("--output-dir", dest="output_dir", help="Base directory (default: output/<insta-username>/)")
    yt_meta.add_argument("--privacy", default="unlisted", choices=["unlisted", "private", "public"], help="YouTube privacy status (default: unlisted)")
    yt_meta.add_argument("--landscape", action="store_true", help="Generate metadata for landscape videos in videos_landscape/ (writes to youtube_landscape/)")

    yt_upload = subparsers.add_parser("youtube-upload", help="Upload assembled MP4s as private YouTube videos.")
    yt_upload.add_argument("username", metavar="insta-username", help="Instagram username (folder name under output/)")
    yt_upload.add_argument("--highlight", help="Partial name match — upload only this highlight")
    yt_upload.add_argument("--output-dir", dest="output_dir", help="Base directory (default: output/<insta-username>/)")
    yt_upload.add_argument("--client-secrets", dest="client_secrets", default=os.environ.get("YOUTUBE_CLIENT_SECRETS"), help="Path to client_secrets.json (or set YOUTUBE_CLIENT_SECRETS)")
    yt_upload.add_argument("--playlist", default="Story Highlights", help="YouTube playlist name (default: Story Highlights)")
    yt_upload.add_argument("--update", action="store_true", help="Delete outdated uploaded videos (after confirmation) and re-upload the re-encoded versions")
    yt_upload.add_argument("--privacy", default="unlisted", choices=["unlisted", "private", "public"], help="YouTube privacy status for new uploads (default: unlisted)")
    yt_upload.add_argument("--landscape", action="store_true", help="Upload landscape videos from youtube_landscape/ metadata")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    _validate_username(args.username)

    if args.command == "highlights":
        if not args.highlight and not args.update and not args.retry_failed:
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
            retry_failed=args.retry_failed,
        ))

    elif args.command == "videos":
        run_videos(VideoConfig(
            username=args.username,
            highlight=args.highlight,
            output_dir=args.output_dir,
            image_duration=args.image_duration,
            update=args.update,
            landscape=args.landscape,
        ))

    elif args.command == "summary":
        run_summary(args.username, args.output_dir)

    elif args.command == "youtube-meta":
        run_youtube_meta(YoutubeConfig(
            username=args.username,
            highlight=args.highlight,
            output_dir=args.output_dir,
            privacy=args.privacy,
            landscape=args.landscape,
        ))

    elif args.command == "youtube-upload":
        from insta_loader.youtube_uploader import run as run_youtube_upload
        run_youtube_upload(YoutubeConfig(
            username=args.username,
            highlight=args.highlight,
            output_dir=args.output_dir,
            client_secrets=args.client_secrets,
            playlist=args.playlist,
            update=args.update,
            privacy=args.privacy,
            landscape=args.landscape,
        ))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n✗  Interrupted.")
        sys.exit(1)

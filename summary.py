import argparse
import sys

from dotenv import load_dotenv
load_dotenv()

from insta_loader.summarizer import run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Summarize downloaded highlights for a user."
    )
    parser.add_argument("username", help="Instagram username (without @)")
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        help="Base output directory (default: output/<username>)",
    )
    args = parser.parse_args()

    try:
        run(args.username, args.output_dir)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)

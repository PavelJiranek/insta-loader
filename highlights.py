import sys

from dotenv import load_dotenv
load_dotenv()

from insta_loader.cli import parse_args
from insta_loader.downloader import run


if __name__ == "__main__":
    try:
        config = parse_args()
        run(config)
    except KeyboardInterrupt:
        print("\n✗  Interrupted. Resume by running the same command again.")
        sys.exit(1)

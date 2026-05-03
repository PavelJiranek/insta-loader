# insta-loader

Download Instagram story highlight reels to organized local folders.

## Requirements

- Python 3.9+

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Download all highlights (asks for confirmation)
python highlights.py <username>

# Download a specific highlight reel
python highlights.py <username> --highlight "Travel"

# Custom output directory
python highlights.py <username> --output-dir ~/Desktop/insta

# Combine flags
python highlights.py <username> --highlight "Travel" --output-dir ~/Desktop/insta
```

## Output

Files are saved to `output/<username>/` by default (gitignored):

```
output/natgeo/
  Travel/
    Travel_01_20230415_143200.mp4
    Travel_02_20230415_143500.jpg
  Summer_2024/
    Summer_2024_01_20240701_090000.mp4
    Summer_2024_02_20240701_090300.mp4
```

Filename format: `<HighlightName>_<index>_<date>.<ext>`

## Resume

Downloads are **idempotent** — re-running the same command skips already-downloaded slides and picks up any new ones automatically.

## Notes

- Only public Instagram accounts are supported.
- If rate-limited mid-download, re-run the same command — completed slides are skipped automatically.

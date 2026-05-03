# V1 Instagram Highlight Downloader — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI tool that downloads Instagram story highlights into organized local folders, with idempotent resume support and Rich progress output.

**Architecture:** A `highlights.py` entry point wires together four focused modules in `insta_loader/`: `cli.py` parses arguments, `organizer.py` handles file naming and folder creation, `progress.py` wraps Rich, and `downloader.py` orchestrates the full flow via instaloader. Each run skips already-downloaded slides by globbing for existing files — the filesystem is the state.

**Tech Stack:** Python 3.9+, instaloader>=4.10, rich>=13.0, pytest>=7.0

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `requirements.txt` | Create | instaloader, rich, pytest |
| `.gitignore` | Create | Ignore default output dirs, venv, pycache |
| `insta_loader/__init__.py` | Create | Empty package marker |
| `insta_loader/organizer.py` | Create | sanitize_name, highlight_dir, slide_filename, slide_exists |
| `insta_loader/cli.py` | Create | Config dataclass, parse_args, confirmation prompt |
| `insta_loader/progress.py` | Create | create_progress, add_highlight_task, advance, log_skip |
| `insta_loader/downloader.py` | Create | Core orchestration: fetch profile, loop highlights/slides |
| `highlights.py` | Create | Entry point: parse_args → run |
| `tests/test_organizer.py` | Create | Unit tests for all organizer functions |
| `tests/test_cli.py` | Create | Unit tests for argument parsing and confirmation prompt |
| `tests/test_downloader.py` | Create | Unit tests for downloader with mocked instaloader |
| `README.md` | Create | Usage, installation, output examples |
| `docs/how-it-works.md` | Create | Architecture overview (agent-agnostic) |
| `docs/extending.md` | Create | How to add V2 and other extensions |

---

### Task 1: Project scaffold

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `insta_loader/__init__.py`

- [ ] **Step 1: Create `requirements.txt`**

```
instaloader>=4.10
rich>=13.0
pytest>=7.0
```

- [ ] **Step 2: Create `.gitignore`**

```
# Default output path (username/highlights/)
*/highlights/

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/
*.egg-info/

# OS / tools
.DS_Store
.superpowers/
```

- [ ] **Step 3: Create `insta_loader/__init__.py`**

Empty file — just marks the directory as a Python package:

```python
```

- [ ] **Step 4: Install dependencies and verify pytest**

```bash
pip install -r requirements.txt
pytest --version
```

Expected: `pytest 7.x.x` (or higher)

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .gitignore insta_loader/__init__.py
git commit -m "chore: scaffold project structure and dependencies"
```

---

### Task 2: `organizer.py` — file naming and folder logic

**Files:**
- Create: `insta_loader/organizer.py`
- Create: `tests/test_organizer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_organizer.py`:

```python
import pytest
from pathlib import Path
from insta_loader.organizer import sanitize_name, slide_filename, slide_exists, highlight_dir


def test_sanitize_name_replaces_spaces():
    assert sanitize_name("Summer 2024") == "Summer_2024"


def test_sanitize_name_replaces_slashes():
    assert sanitize_name("Travel/Europe") == "Travel-Europe"


def test_sanitize_name_plain_name_unchanged():
    assert sanitize_name("Travel") == "Travel"


def test_slide_filename_zero_pads_single_digit():
    assert slide_filename("Travel", 1) == "Travel_01"


def test_slide_filename_two_digit_index():
    assert slide_filename("Travel", 12) == "Travel_12"


def test_slide_filename_sanitizes_title():
    assert slide_filename("Summer 2024", 3) == "Summer_2024_03"


def test_slide_exists_false_when_folder_empty(tmp_path):
    assert slide_exists(tmp_path, "Travel", 1) is False


def test_slide_exists_true_when_file_present(tmp_path):
    (tmp_path / "Travel_01_20230415_143200.mp4").touch()
    assert slide_exists(tmp_path, "Travel", 1) is True


def test_slide_exists_false_for_different_index(tmp_path):
    (tmp_path / "Travel_01_20230415_143200.mp4").touch()
    assert slide_exists(tmp_path, "Travel", 2) is False


def test_slide_exists_false_for_different_name(tmp_path):
    (tmp_path / "Travel_01_20230415_143200.mp4").touch()
    assert slide_exists(tmp_path, "Summer", 1) is False


def test_highlight_dir_creates_folder(tmp_path):
    result = highlight_dir(tmp_path, "Travel")
    assert result.exists()
    assert result.name == "Travel"


def test_highlight_dir_sanitizes_name(tmp_path):
    result = highlight_dir(tmp_path, "Summer 2024")
    assert result.name == "Summer_2024"


def test_highlight_dir_is_idempotent(tmp_path):
    highlight_dir(tmp_path, "Travel")
    highlight_dir(tmp_path, "Travel")  # second call must not raise
    assert (tmp_path / "Travel").exists()
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_organizer.py -v
```

Expected: `ModuleNotFoundError: No module named 'insta_loader.organizer'`

- [ ] **Step 3: Implement `insta_loader/organizer.py`**

```python
import glob
from pathlib import Path


def sanitize_name(title: str) -> str:
    return title.replace("/", "-").replace(" ", "_")


def highlight_dir(base_dir: str | Path, highlight_title: str) -> Path:
    folder = Path(base_dir) / sanitize_name(highlight_title)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def slide_filename(highlight_title: str, idx: int) -> str:
    return f"{sanitize_name(highlight_title)}_{idx:02d}"


def slide_exists(folder: Path, highlight_title: str, idx: int) -> bool:
    stem = slide_filename(highlight_title, idx)
    return len(glob.glob(str(folder / f"{stem}_*"))) > 0
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
pytest tests/test_organizer.py -v
```

Expected: 13 passed

- [ ] **Step 5: Commit**

```bash
git add insta_loader/organizer.py tests/test_organizer.py
git commit -m "feat(organizer): add file naming and folder creation logic"
```

---

### Task 3: `cli.py` — argument parsing and confirmation prompt

**Files:**
- Create: `insta_loader/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_cli.py`:

```python
import pytest
from insta_loader.cli import parse_args, Config


def test_parse_args_username():
    config = parse_args(["natgeo", "--highlight", "Travel"])
    assert config.username == "natgeo"


def test_parse_args_highlight_flag():
    config = parse_args(["natgeo", "--highlight", "Travel"])
    assert config.highlight == "Travel"


def test_parse_args_output_dir_flag():
    config = parse_args(["natgeo", "--highlight", "Travel", "--output-dir", "/tmp/out"])
    assert config.output_dir == "/tmp/out"


def test_parse_args_output_dir_defaults_to_none():
    config = parse_args(["natgeo", "--highlight", "Travel"])
    assert config.output_dir is None


def test_parse_args_highlight_defaults_to_none_after_confirmation(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    config = parse_args(["natgeo"])
    assert config.highlight is None


def test_parse_args_no_highlight_y_continues(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "y")
    config = parse_args(["natgeo"])
    assert config.username == "natgeo"


def test_parse_args_no_highlight_n_exits_0(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "n")
    with pytest.raises(SystemExit) as exc:
        parse_args(["natgeo"])
    assert exc.value.code == 0


def test_parse_args_no_highlight_empty_input_exits_0(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "")
    with pytest.raises(SystemExit) as exc:
        parse_args(["natgeo"])
    assert exc.value.code == 0


def test_parse_args_returns_config_instance():
    config = parse_args(["natgeo", "--highlight", "Travel"])
    assert isinstance(config, Config)
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_cli.py -v
```

Expected: `ModuleNotFoundError: No module named 'insta_loader.cli'`

- [ ] **Step 3: Implement `insta_loader/cli.py`**

```python
import argparse
import sys
from dataclasses import dataclass


@dataclass
class Config:
    username: str
    output_dir: str | None
    highlight: str | None


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
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
pytest tests/test_cli.py -v
```

Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add insta_loader/cli.py tests/test_cli.py
git commit -m "feat(cli): add argument parsing and download confirmation prompt"
```

---

### Task 4: `progress.py` — Rich progress bar helpers

**Files:**
- Create: `insta_loader/progress.py`

Rich's live display can't be meaningfully unit-tested. Implement and verify with a smoke test.

- [ ] **Step 1: Implement `insta_loader/progress.py`**

```python
from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich import print as rprint


def create_progress() -> Progress:
    return Progress(
        TextColumn("[bold yellow]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[dim]{task.fields[current_file]}"),
        TimeRemainingColumn(),
    )


def add_highlight_task(progress: Progress, title: str, total: int) -> TaskID:
    return progress.add_task(f"Highlight: {title}", total=total, current_file="")


def advance(progress: Progress, task_id: TaskID, filename: str = "") -> None:
    progress.update(task_id, advance=1, current_file=filename)


def log_skip(filename: str) -> None:
    rprint(f"[dim]Skipping {filename} — already downloaded[/dim]")
```

- [ ] **Step 2: Smoke-test in terminal**

```bash
python -c "
import time
from insta_loader.progress import create_progress, add_highlight_task, advance

with create_progress() as p:
    task = add_highlight_task(p, 'Travel', 3)
    for i in range(1, 4):
        time.sleep(0.1)
        advance(p, task, f'Travel_{i:02d}')
print('smoke-test passed')
"
```

Expected: animated progress bar completes, then `smoke-test passed`

- [ ] **Step 3: Commit**

```bash
git add insta_loader/progress.py
git commit -m "feat(progress): add rich progress bar helpers"
```

---

### Task 5: `downloader.py` — core orchestration

**Files:**
- Create: `insta_loader/downloader.py`
- Create: `tests/test_downloader.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_downloader.py`:

```python
import pytest
import instaloader as _il
from unittest.mock import MagicMock, patch
from pathlib import Path

from insta_loader.cli import Config
from insta_loader.downloader import run


def make_config(username="natgeo", output_dir=None, highlight=None):
    return Config(username=username, output_dir=output_dir, highlight=highlight)


def make_mock_highlight(title, num_items=2):
    h = MagicMock()
    h.title = title
    h.unique_id = "hl_123"
    h.get_items.return_value = [MagicMock() for _ in range(num_items)]
    return h


@patch("insta_loader.downloader.instaloader")
def test_private_account_exits_1(mock_il):
    mock_il.Instaloader.return_value = MagicMock()
    mock_profile = MagicMock()
    mock_profile.is_private = True
    mock_il.Profile.from_username.return_value = mock_profile

    with pytest.raises(SystemExit) as exc:
        run(make_config())
    assert exc.value.code == 1


@patch("insta_loader.downloader.instaloader")
def test_account_not_found_exits_1(mock_il):
    mock_il.Instaloader.return_value = MagicMock()
    # Map the mock exception to the real one so the except clause catches it
    mock_il.exceptions.ProfileNotExistsException = _il.exceptions.ProfileNotExistsException
    mock_il.Profile.from_username.side_effect = _il.exceptions.ProfileNotExistsException("natgeo")

    with pytest.raises(SystemExit) as exc:
        run(make_config())
    assert exc.value.code == 1


@patch("insta_loader.downloader.instaloader")
def test_highlight_not_found_exits_1(mock_il):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_loader.get_highlights.return_value = [make_mock_highlight("Summer")]

    with pytest.raises(SystemExit) as exc:
        run(make_config(highlight="Travel"))
    assert exc.value.code == 1


@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_skips_already_downloaded_slides(mock_organizer, mock_il, mock_prog, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_loader.get_highlights.return_value = [make_mock_highlight("Travel", num_items=1)]

    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = True  # slide already on disk

    run(make_config(highlight="Travel", output_dir=str(tmp_path)))

    mock_loader.download_storyitem.assert_not_called()


@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_downloads_missing_slides(mock_organizer, mock_il, mock_prog, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    mock_loader.get_highlights.return_value = [make_mock_highlight("Travel", num_items=1)]

    mock_organizer.highlight_dir.return_value = tmp_path
    mock_organizer.slide_filename.return_value = "Travel_01"
    mock_organizer.slide_exists.return_value = False  # not yet downloaded

    run(make_config(highlight="Travel", output_dir=str(tmp_path)))

    mock_loader.download_storyitem.assert_called_once()


@patch("insta_loader.downloader.prog")
@patch("insta_loader.downloader.instaloader")
@patch("insta_loader.downloader.organizer")
def test_highlight_match_is_case_insensitive(mock_organizer, mock_il, mock_prog, tmp_path):
    mock_loader = MagicMock()
    mock_il.Instaloader.return_value = mock_loader
    mock_profile = MagicMock()
    mock_profile.is_private = False
    mock_il.Profile.from_username.return_value = mock_profile
    # Stored as "Travel", queried as "travel"
    mock_loader.get_highlights.return_value = [make_mock_highlight("Travel", num_items=0)]
    mock_organizer.highlight_dir.return_value = tmp_path

    # Should NOT exit — "travel" matches "Travel"
    run(make_config(highlight="travel", output_dir=str(tmp_path)))
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
pytest tests/test_downloader.py -v
```

Expected: `ModuleNotFoundError: No module named 'insta_loader.downloader'`

- [ ] **Step 3: Implement `insta_loader/downloader.py`**

```python
import sys
from pathlib import Path

import instaloader

from insta_loader import organizer
from insta_loader import progress as prog
from insta_loader.cli import Config


def run(config: Config) -> None:
    L = instaloader.Instaloader(
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern="",
    )

    try:
        profile = instaloader.Profile.from_username(L.context, config.username)
    except instaloader.exceptions.ProfileNotExistsException:
        print(f"✗  @{config.username} not found.")
        sys.exit(1)

    if profile.is_private:
        print(
            f"✗  @{config.username} is a private account. "
            "Only public accounts are supported in V1."
        )
        sys.exit(1)

    all_highlights = list(L.get_highlights(profile))

    if config.highlight:
        highlights = [
            h for h in all_highlights if h.title.lower() == config.highlight.lower()
        ]
        if not highlights:
            available = ", ".join(h.title for h in all_highlights)
            print(f"✗  Highlight '{config.highlight}' not found.")
            print(f"   Available: {available}")
            sys.exit(1)
    else:
        highlights = all_highlights

    base_dir = config.output_dir or f"{config.username}/highlights"
    print(f"✓  @{config.username} is public — {len(highlights)} highlight(s) to download\n")

    with prog.create_progress() as progress:
        for highlight in highlights:
            items = list(highlight.get_items())
            task_id = prog.add_highlight_task(progress, highlight.title, len(items))
            folder = organizer.highlight_dir(base_dir, highlight.title)

            for idx, item in enumerate(items, start=1):
                filename = organizer.slide_filename(highlight.title, idx)

                if organizer.slide_exists(folder, highlight.title, idx):
                    prog.log_skip(filename)
                    prog.advance(progress, task_id)
                    continue

                L.dirname_pattern = str(folder)
                L.filename_pattern = filename + "_{date_utc:%Y%m%d_%H%M%S}"

                try:
                    L.download_storyitem(item, highlight.unique_id)
                except Exception as e:
                    print(f"\n✗  Error on slide {idx} of '{highlight.title}': {e}")
                    print("   Resume by running the same command again.")
                    sys.exit(1)

                prog.advance(progress, task_id, filename)
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
pytest tests/test_downloader.py -v
```

Expected: 6 passed

- [ ] **Step 5: Run the full test suite**

```bash
pytest -v
```

Expected: all tests pass (organizer + cli + downloader)

- [ ] **Step 6: Commit**

```bash
git add insta_loader/downloader.py tests/test_downloader.py
git commit -m "feat(downloader): add core orchestration with resume and error handling"
```

---

### Task 6: Entry point

**Files:**
- Create: `highlights.py`

- [ ] **Step 1: Create `highlights.py`**

```python
import sys

from insta_loader.cli import parse_args
from insta_loader.downloader import run


if __name__ == "__main__":
    try:
        config = parse_args()
        run(config)
    except KeyboardInterrupt:
        print("\n✗  Interrupted. Resume by running the same command again.")
        sys.exit(1)
```

- [ ] **Step 2: Verify `--help` output**

```bash
python highlights.py --help
```

Expected output:
```
usage: highlights.py [-h] [--output-dir OUTPUT_DIR] [--highlight HIGHLIGHT] username

Download Instagram story highlights to local folders.

positional arguments:
  username              Instagram username (without @)

options:
  -h, --help            show this help message and exit
  --output-dir OUTPUT_DIR
                        Where to save downloads (default: <username>/highlights/)
  --highlight HIGHLIGHT
                        Download only this highlight reel (case-insensitive exact match)
```

- [ ] **Step 3: Commit**

```bash
git add highlights.py
git commit -m "feat: wire up entry point"
```

---

### Task 7: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

````markdown
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

Files are saved to `<username>/highlights/` by default (gitignored):

```
natgeo/highlights/
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
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with usage and output examples"
```

---

### Task 8: Agent-agnostic docs

**Files:**
- Create: `docs/how-it-works.md`
- Create: `docs/extending.md`

- [ ] **Step 1: Create `docs/how-it-works.md`**

````markdown
# How It Works

## Architecture

The tool is split into four focused modules inside `insta_loader/`:

| Module | Responsibility |
|---|---|
| `cli.py` | Parse CLI arguments; run confirmation prompt when no `--highlight`; return `Config` |
| `organizer.py` | Sanitize names; create folders; build filename stems; check if a slide already exists |
| `progress.py` | Wrap Rich for progress bars and skip messages |
| `downloader.py` | Orchestrate: fetch profile, iterate highlights and slides, delegate to other modules |

`highlights.py` is the entry point — it calls `parse_args()` then `run(config)` and contains no logic of its own.

## Data Flow

```
highlights.py
  └─ cli.parse_args()  →  Config(username, output_dir, highlight)
  └─ downloader.run(config)
       ├─ instaloader.Profile.from_username()     # verify account is public
       ├─ instaloader.get_highlights(profile)     # list all highlight reels
       └─ for each highlight, for each slide:
            ├─ organizer.slide_exists()           # resume check via glob
            ├─ [skip and log if already present]
            ├─ organizer.slide_filename()         # build filename stem
            ├─ L.download_storyitem()             # download via instaloader
            └─ progress.advance()                 # update progress bar
```

## File Naming

Format: `<HighlightName>_<idx:02d>_<date_utc:%Y%m%d_%H%M%S>.<ext>`

- `HighlightName`: title sanitized — spaces → `_`, `/` → `-`
- `idx`: 1-based slide index, zero-padded to 2 digits (e.g. `01`, `12`)
- `date`: UTC timestamp from the story item, set by instaloader's template engine
- `ext`: `.mp4` for video, `.jpg` for images (assigned by instaloader)

## Resume Logic

Before downloading each slide, `organizer.slide_exists()` runs `glob("<Name>_<idx:02d>_*")` in the highlight folder. If any file matches, the slide is skipped. The filesystem is the state — no database or lock files needed.

## Error Handling

All errors print a human-readable message and call `sys.exit(1)`. There are no automatic retries. Re-running after any error resumes from the first missing slide.
````

- [ ] **Step 2: Create `docs/extending.md`**

````markdown
# Extending the Tool

## Adding V2: Video Stitcher

V2 stitches downloaded slides into a single `.mp4` per highlight. It reads V1's output — do not modify V1 modules.

**New file:** `insta_loader/stitcher.py`

```python
from pathlib import Path


def stitch(highlight_dir: Path, output_path: Path) -> None:
    """Concatenate all slides in order into a single mp4 via ffmpeg."""
    ...
```

**New entry point:** `stitch.py` — mirrors `highlights.py`, wires `cli` → `stitcher`.
Keep separate entry points so V1 and V2 remain independently usable.

New dependency to add to `requirements.txt`: `moviepy` or shell out to `ffmpeg`.

## Adding a New CLI Flag

1. Add the argument to `parse_args()` in `insta_loader/cli.py`.
2. Add the field to the `Config` dataclass.
3. Consume the new field in `insta_loader/downloader.py`.
4. Add tests in `tests/test_cli.py` and `tests/test_downloader.py`.

## Swapping instaloader for Another Library

All instaloader calls are isolated in `insta_loader/downloader.py`. The four call sites to replace:

```python
instaloader.Instaloader(...)             # initialization
instaloader.Profile.from_username(...)   # profile + public check
L.get_highlights(profile)               # highlight list
L.download_storyitem(item, target)       # single slide download
```

`organizer`, `cli`, and `progress` have zero knowledge of instaloader.

## What Not to Touch

- **`organizer.py`** — stable interface; both the downloader and a future stitcher depend on it
- **`Config` dataclass fields** — removing fields breaks downloader
- **Filename format** — changing it breaks resume (existing files won't be detected by glob)
````

- [ ] **Step 3: Commit**

```bash
git add docs/how-it-works.md docs/extending.md
git commit -m "docs: add how-it-works and extending guides"
```

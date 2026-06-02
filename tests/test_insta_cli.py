import sys
import pytest
from unittest.mock import patch, MagicMock


@patch("insta_loader.downloader.run")
def test_highlights_subcommand_calls_downloader(mock_run):
    with patch("sys.argv", ["insta.py", "highlights", "natgeo", "--highlight", "Travel"]):
        import insta
        import importlib
        importlib.reload(insta)
        insta.main()
    mock_run.assert_called_once()
    config = mock_run.call_args[0][0]
    assert config.username == "natgeo"
    assert config.highlight == "Travel"


@patch("insta_loader.video_creator.run")
def test_videos_subcommand_calls_video_creator(mock_run):
    with patch("sys.argv", ["insta.py", "videos", "natgeo", "--highlight", "Travel"]):
        import insta
        import importlib
        importlib.reload(insta)
        insta.main()
    mock_run.assert_called_once()
    config = mock_run.call_args[0][0]
    assert config.username == "natgeo"
    assert config.highlight == "Travel"


@patch("insta_loader.summarizer.run")
def test_summary_subcommand_calls_summarizer(mock_run):
    with patch("sys.argv", ["insta.py", "summary", "natgeo"]):
        import insta
        import importlib
        importlib.reload(insta)
        insta.main()
    mock_run.assert_called_once_with("natgeo", None)


def test_no_subcommand_exits_0(capsys):
    with patch("sys.argv", ["insta.py"]):
        import insta
        import importlib
        importlib.reload(insta)
        with pytest.raises(SystemExit) as exc:
            insta.main()
    assert exc.value.code == 0


def test_youtube_meta_subparser_exists():
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "insta.py", "youtube-meta", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "insta-username" in result.stdout or "username" in result.stdout


def test_youtube_upload_subparser_exists():
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "insta.py", "youtube-upload", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "insta-username" in result.stdout or "username" in result.stdout


def test_videos_landscape_flag_passed_to_video_config():
    with patch("insta_loader.video_creator.run") as mock_run, \
         patch("sys.argv", ["insta.py", "videos", "testuser", "--landscape"]):
        import insta
        import importlib
        importlib.reload(insta)
        insta.main()
    config = mock_run.call_args[0][0]
    assert config.landscape is True


def test_youtube_meta_landscape_flag_passed_to_youtube_config():
    with patch("insta_loader.youtube_meta.run") as mock_run, \
         patch("sys.argv", ["insta.py", "youtube-meta", "testuser", "--landscape"]):
        import insta
        import importlib
        importlib.reload(insta)
        insta.main()
    config = mock_run.call_args[0][0]
    assert config.landscape is True


def test_youtube_upload_landscape_flag_passed_to_youtube_config():
    with patch("insta_loader.youtube_uploader.run") as mock_run, \
         patch("sys.argv", ["insta.py", "youtube-upload", "testuser", "--landscape"]):
        import insta
        import importlib
        importlib.reload(insta)
        insta.main()
    config = mock_run.call_args[0][0]
    assert config.landscape is True

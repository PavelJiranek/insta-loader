import json
import subprocess
from pathlib import Path
from unittest.mock import patch
import pytest
from insta_loader.cli import VideoConfig
from insta_loader.video_creator import _collect_slides, _resolve_conflict, _normalize_slide

def test_video_config_defaults():
    c = VideoConfig(username="natgeo")
    assert c.highlight is None
    assert c.output_dir is None


def _write_meta(folder: Path, slides: list) -> None:
    (folder / "metadata.json").write_text(json.dumps({"highlight_title": folder.name, "slides": slides}))


def test_collect_slides_returns_sorted_by_index(tmp_path):
    _write_meta(tmp_path, [
        {"index": 2, "filename": "Test_02", "type": "image", "status": "downloaded"},
        {"index": 1, "filename": "Test_01", "type": "video", "status": "downloaded"},
    ])
    (tmp_path / "Test_01_20250101_000000.mp4").touch()
    (tmp_path / "Test_02_20250101_000001.jpg").touch()

    result = _collect_slides(tmp_path)

    assert [s["index"] for s in result] == [1, 2]


def test_collect_slides_excludes_failed(tmp_path):
    _write_meta(tmp_path, [
        {"index": 1, "filename": "Test_01", "type": "video", "status": "downloaded"},
        {"index": 2, "filename": "Test_02", "type": "image", "status": "failed"},
        {"index": 3, "filename": "Test_03", "type": "image", "status": "downloaded"},
    ])
    (tmp_path / "Test_01_20250101_000000.mp4").touch()
    (tmp_path / "Test_03_20250101_000001.jpg").touch()

    result = _collect_slides(tmp_path)

    assert len(result) == 2
    assert all(s["index"] != 2 for s in result)


def test_collect_slides_returns_correct_type_and_path(tmp_path):
    _write_meta(tmp_path, [
        {"index": 1, "filename": "Test_01", "type": "video", "status": "downloaded"},
    ])
    actual_file = tmp_path / "Test_01_20250101_000000.mp4"
    actual_file.touch()

    result = _collect_slides(tmp_path)

    assert result[0]["type"] == "video"
    assert result[0]["path"] == actual_file


def test_collect_slides_skips_missing_file(tmp_path):
    _write_meta(tmp_path, [
        {"index": 1, "filename": "Test_01", "type": "video", "status": "downloaded"},
        {"index": 2, "filename": "Test_02", "type": "image", "status": "downloaded"},
    ])
    # only create file for index 2
    (tmp_path / "Test_02_20250101_000000.jpg").touch()

    result = _collect_slides(tmp_path)

    assert len(result) == 1
    assert result[0]["index"] == 2


def test_collect_slides_returns_empty_when_no_metadata(tmp_path):
    result = _collect_slides(tmp_path)
    assert result == []


def test_resolve_conflict_returns_path_when_no_conflict(tmp_path):
    output = tmp_path / "Travel.mp4"
    assert _resolve_conflict(output) == output


def test_resolve_conflict_overwrite_returns_same_path(tmp_path, monkeypatch):
    output = tmp_path / "Travel.mp4"
    output.touch()
    monkeypatch.setattr("builtins.input", lambda _: "o")

    result = _resolve_conflict(output)

    assert result == output
    assert not output.exists()  # deleted so ffmpeg can write fresh


def test_resolve_conflict_skip_returns_none(tmp_path, monkeypatch):
    output = tmp_path / "Travel.mp4"
    output.touch()
    monkeypatch.setattr("builtins.input", lambda _: "s")

    assert _resolve_conflict(output) is None


def test_resolve_conflict_new_returns_suffixed_path(tmp_path, monkeypatch):
    output = tmp_path / "Travel.mp4"
    output.touch()
    monkeypatch.setattr("builtins.input", lambda _: "n")

    result = _resolve_conflict(output)

    assert result == tmp_path / "Travel_1.mp4"


def test_resolve_conflict_new_increments_suffix_past_existing(tmp_path, monkeypatch):
    (tmp_path / "Travel.mp4").touch()
    (tmp_path / "Travel_1.mp4").touch()
    monkeypatch.setattr("builtins.input", lambda _: "n")

    result = _resolve_conflict(tmp_path / "Travel.mp4")

    assert result == tmp_path / "Travel_2.mp4"


def test_resolve_conflict_invalid_input_returns_none(tmp_path, monkeypatch):
    output = tmp_path / "Travel.mp4"
    output.touch()
    monkeypatch.setattr("builtins.input", lambda _: "x")

    assert _resolve_conflict(output) is None


@patch("insta_loader.video_creator.subprocess.run")
def test_normalize_slide_image_uses_loop_and_no_audio(mock_run, tmp_path):
    img = tmp_path / "slide.jpg"
    img.touch()

    out = _normalize_slide(img, 1, tmp_path, is_video=False)

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "-loop" in cmd
    assert "15" in cmd
    assert "-an" in cmd
    assert "-c:a" not in cmd
    assert out == tmp_path / "clip_001.mp4"


@patch("insta_loader.video_creator.subprocess.run")
def test_normalize_slide_video_preserves_audio(mock_run, tmp_path):
    vid = tmp_path / "slide.mp4"
    vid.touch()

    out = _normalize_slide(vid, 2, tmp_path, is_video=True)

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "-loop" not in cmd
    assert "-c:a" in cmd and "aac" in cmd
    assert "-an" not in cmd
    assert out == tmp_path / "clip_002.mp4"


@patch("insta_loader.video_creator.subprocess.run")
def test_normalize_slide_both_use_scale_filter(mock_run, tmp_path):
    img = tmp_path / "slide.jpg"
    img.touch()
    _normalize_slide(img, 1, tmp_path, is_video=False)

    cmd = mock_run.call_args[0][0]
    vf_index = cmd.index("-vf")
    assert "1080" in cmd[vf_index + 1]
    assert "1920" in cmd[vf_index + 1]


@patch("insta_loader.video_creator.subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffmpeg"))
def test_normalize_slide_raises_on_ffmpeg_error(mock_run, tmp_path):
    img = tmp_path / "slide.jpg"
    img.touch()

    with pytest.raises(subprocess.CalledProcessError):
        _normalize_slide(img, 1, tmp_path, is_video=False)


from insta_loader.video_creator import _concat_clips


@patch("insta_loader.video_creator.subprocess.run")
def test_concat_clips_runs_ffmpeg_concat(mock_run, tmp_path):
    clips = [tmp_path / "clip_001.mp4", tmp_path / "clip_002.mp4"]
    output = tmp_path / "out.mp4"

    _concat_clips(clips, output)

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert "-f" in cmd
    assert "concat" in cmd
    assert str(output) in cmd


@patch("insta_loader.video_creator.subprocess.run")
def test_concat_clips_list_file_contains_all_clips(mock_run, tmp_path):
    clips = [tmp_path / "clip_001.mp4", tmp_path / "clip_002.mp4"]
    clips[0].touch()
    clips[1].touch()
    output = tmp_path / "out.mp4"

    _concat_clips(clips, output)

    # find the list file arg (-i <list_file>)
    cmd = mock_run.call_args[0][0]
    i_index = cmd.index("-i")
    list_file = Path(cmd[i_index + 1])
    content = list_file.read_text()
    assert str(clips[0].resolve()) in content
    assert str(clips[1].resolve()) in content


from insta_loader.video_creator import _filter_highlights


def make_dirs(names: list, base: Path) -> list:
    dirs = []
    for name in names:
        d = base / name
        d.mkdir()
        dirs.append(d)
    return dirs


def test_filter_highlights_exact_match(tmp_path):
    dirs = make_dirs(["Travel", "Summer"], tmp_path)
    result = _filter_highlights("Travel", dirs)
    assert len(result) == 1
    assert result[0].name == "Travel"


def test_filter_highlights_case_insensitive(tmp_path):
    dirs = make_dirs(["Travel", "Summer"], tmp_path)
    result = _filter_highlights("travel", dirs)
    assert result[0].name == "Travel"


def test_filter_highlights_single_partial_match(tmp_path, capsys):
    dirs = make_dirs(["Czech_Republic", "Summer"], tmp_path)
    result = _filter_highlights("czech", dirs)
    assert result[0].name == "Czech_Republic"
    assert "Matched" in capsys.readouterr().out


def test_filter_highlights_no_match_exits_1(tmp_path):
    dirs = make_dirs(["Travel", "Summer"], tmp_path)
    with pytest.raises(SystemExit) as exc:
        _filter_highlights("xyz", dirs)
    assert exc.value.code == 1


def test_filter_highlights_multiple_partial_prompts(tmp_path, monkeypatch):
    dirs = make_dirs(["Czech_Republic", "Czech_Brno", "Summer"], tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "2")
    result = _filter_highlights("czech", dirs)
    assert result[0].name == "Czech_Brno"


def test_filter_highlights_invalid_selection_exits_1(tmp_path, monkeypatch):
    dirs = make_dirs(["Czech_Republic", "Czech_Brno"], tmp_path)
    monkeypatch.setattr("builtins.input", lambda _: "99")
    with pytest.raises(SystemExit) as exc:
        _filter_highlights("czech", dirs)
    assert exc.value.code == 1


from unittest.mock import MagicMock
from insta_loader.video_creator import run


@patch("insta_loader.video_creator.shutil.which", return_value=None)
def test_run_exits_when_ffmpeg_missing(mock_which):
    with pytest.raises(SystemExit) as exc:
        run(VideoConfig(username="test"))
    assert exc.value.code == 1


@patch("insta_loader.video_creator.shutil.which", return_value="/usr/bin/ffmpeg")
def test_run_exits_when_base_dir_missing(mock_which, tmp_path):
    with pytest.raises(SystemExit) as exc:
        run(VideoConfig(username="test", output_dir=str(tmp_path / "nonexistent")))
    assert exc.value.code == 1


@patch("insta_loader.video_creator.shutil.which", return_value="/usr/bin/ffmpeg")
def test_run_exits_when_no_highlight_dirs_with_metadata(mock_which, tmp_path):
    (tmp_path / "some_dir").mkdir()  # has no metadata.json
    with pytest.raises(SystemExit) as exc:
        run(VideoConfig(username="test", output_dir=str(tmp_path)))
    assert exc.value.code == 1


@patch("insta_loader.video_creator._concat_clips")
@patch("insta_loader.video_creator._normalize_slide")
@patch("insta_loader.video_creator._collect_slides", return_value=[])
@patch("insta_loader.video_creator.prog")
@patch("insta_loader.video_creator.shutil.which", return_value="/usr/bin/ffmpeg")
def test_run_skips_highlight_with_no_valid_slides(
    mock_which, mock_prog, mock_collect, mock_norm, mock_concat, tmp_path
):
    mock_prog.create_progress.return_value = MagicMock()
    hdir = tmp_path / "Travel"
    hdir.mkdir()
    (hdir / "metadata.json").write_text('{"highlight_title": "Travel", "slides": []}')

    run(VideoConfig(username="test", output_dir=str(tmp_path)))

    mock_norm.assert_not_called()
    mock_concat.assert_not_called()


@patch("insta_loader.video_creator._concat_clips")
@patch("insta_loader.video_creator._normalize_slide")
@patch("insta_loader.video_creator._resolve_conflict")
@patch("insta_loader.video_creator._collect_slides")
@patch("insta_loader.video_creator.prog")
@patch("insta_loader.video_creator.shutil.which", return_value="/usr/bin/ffmpeg")
def test_run_skips_highlight_when_resolve_returns_none(
    mock_which, mock_prog, mock_collect, mock_conflict, mock_norm, mock_concat, tmp_path
):
    mock_prog.create_progress.return_value = MagicMock()
    mock_collect.return_value = [{"index": 1, "type": "image", "path": tmp_path / "f.jpg"}]
    mock_conflict.return_value = None

    hdir = tmp_path / "Travel"
    hdir.mkdir()
    (hdir / "metadata.json").write_text('{"highlight_title": "Travel", "slides": []}')

    run(VideoConfig(username="test", output_dir=str(tmp_path)))

    mock_norm.assert_not_called()
    mock_concat.assert_not_called()

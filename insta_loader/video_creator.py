import glob as _glob
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import imageio_ffmpeg
from rich import print as rprint
from send2trash import send2trash

from insta_loader import progress as prog
from insta_loader.cli import VideoConfig

_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

_VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}


def _collect_slides(highlight_dir: Path, meta: Optional[dict] = None) -> list:
    if meta is None:
        meta_file = highlight_dir / "metadata.json"
        if not meta_file.exists():
            return []
        meta = json.loads(meta_file.read_text())
    result = []
    for slide in meta.get("slides", []):
        if slide.get("status") == "failed":
            continue
        safe_filename = Path(slide["filename"]).name  # strip any directory components
        matches = [m for m in _glob.glob(str(highlight_dir / f"{safe_filename}_*")) if not m.endswith(".temp")]
        if not matches:
            continue
        path = Path(matches[0])
        # Derive type from the file on disk, not the metadata field — the recorded
        # type can go stale if a highlight is reordered on Instagram (the media at an
        # index changes but the file is kept), and feeding a video through the image
        # (-loop) branch makes ffmpeg fail.
        slide_type = "video" if path.suffix.lower() in _VIDEO_EXTS else "image"
        result.append({
            "index": slide["index"],
            "type": slide_type,
            "path": path,
        })
    result.sort(key=lambda s: s["index"])
    return result


def _resolve_conflict(output_path: Path) -> Optional[Path]:
    if not output_path.exists():
        return output_path

    suffix = 1
    while True:
        candidate = output_path.parent / f"{output_path.stem}_{suffix}{output_path.suffix}"
        if not candidate.exists():
            break
        suffix += 1

    answer = input(
        f"'{output_path.name}' already exists. [o]verwrite / [s]kip / [n]ew file ({candidate.name})? "
    ).strip().lower()

    if answer == "o":
        send2trash(str(output_path))
        return output_path
    elif answer == "n":
        return candidate
    elif answer == "s":
        return None
    else:
        print(f"✗  Invalid choice '{answer}' — skipping {output_path.name}")
        return None


def _needs_update(highlight_dir: Path, video_path: Path) -> bool:
    """True if no video exists or any highlight file is newer than the video."""
    if not video_path.exists():
        return True
    video_mtime = video_path.stat().st_mtime
    return any(
        f.stat().st_mtime > video_mtime
        for f in highlight_dir.iterdir()
        if f.is_file()
    )


def _mark_youtube_outdated(base: Path, folder_name: str, landscape: bool = False) -> None:
    """Set outdated=True in youtube[_landscape]/<stem>.json if previously uploaded."""
    youtube_folder = "youtube_landscape" if landscape else "youtube"
    stem = f"{folder_name}_landscape" if landscape else folder_name
    meta_path = base / youtube_folder / f"{stem}.json"
    if not meta_path.exists():
        return
    meta = json.loads(meta_path.read_text())
    if meta.get("uploaded"):
        meta["outdated"] = True
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))


_VF = (
    "scale=1080:1920:force_original_aspect_ratio=decrease:out_range=tv,"
    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
    "format=yuv420p,"
    "setsar=1:1"
)

_COLOR_FLAGS = [
    "-color_range", "tv",
    "-colorspace", "bt709",
    "-color_primaries", "bt709",
    "-color_trc", "bt709",
]

_ENCODE_FLAGS = [
    "-r", "30",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", *_COLOR_FLAGS,
]

_VF_LANDSCAPE = (
    "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
    "crop=1920:1080,gblur=sigma=25,"
    "colorchannelmixer=rr=0.4:gg=0.4:bb=0.4[bg];"
    "[0:v]scale=-1:1080[fg];"
    "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1:1[out]"
)


def _has_audio(path: Path) -> bool:
    result = subprocess.run([_FFMPEG, "-i", str(path)], capture_output=True)
    return b"Audio:" in result.stderr


def _normalize_slide(slide_path: Path, index: int, tmp_dir: Path, is_video: bool, image_duration: int = 10, landscape: bool = False) -> Path:
    out = tmp_dir / f"clip_{index:03d}.mp4"
    if landscape:
        if is_video:
            if _has_audio(slide_path):
                cmd = [
                    _FFMPEG, "-i", str(slide_path),
                    "-filter_complex", _VF_LANDSCAPE,
                    "-map", "[out]", "-map", "0:a",
                    *_ENCODE_FLAGS,
                    "-c:a", "aac", "-ar", "44100",
                    "-y", str(out),
                ]
            else:
                cmd = [
                    _FFMPEG,
                    "-i", str(slide_path),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-filter_complex", _VF_LANDSCAPE,
                    "-map", "[out]", "-map", "1:a",
                    *_ENCODE_FLAGS,
                    "-c:a", "aac", "-ar", "44100",
                    "-shortest",
                    "-y", str(out),
                ]
        else:
            cmd = [
                _FFMPEG,
                "-loop", "1", "-t", str(image_duration), "-i", str(slide_path),
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-filter_complex", _VF_LANDSCAPE,
                "-map", "[out]", "-map", "1:a",
                *_ENCODE_FLAGS,
                "-c:a", "aac",
                "-shortest",
                "-y", str(out),
            ]
    else:
        if is_video:
            if _has_audio(slide_path):
                cmd = [
                    _FFMPEG, "-i", str(slide_path),
                    "-vf", _VF,
                    *_ENCODE_FLAGS,
                    "-c:a", "aac", "-ar", "44100",
                    "-y", str(out),
                ]
            else:
                cmd = [
                    _FFMPEG,
                    "-i", str(slide_path),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-filter_complex", f"[0:v]{_VF}[vout]",
                    "-map", "[vout]", "-map", "1:a",
                    *_ENCODE_FLAGS,
                    "-c:a", "aac", "-ar", "44100",
                    "-shortest",
                    "-y", str(out),
                ]
        else:
            cmd = [
                _FFMPEG,
                "-loop", "1", "-t", str(image_duration), "-i", str(slide_path),
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-vf", _VF,
                *_ENCODE_FLAGS,
                "-c:a", "aac",
                "-shortest",
                "-y", str(out),
            ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def _concat_clips(clip_paths: list, output_path: Path) -> None:
    n = len(clip_paths)
    inputs = []
    for p in clip_paths:
        inputs.extend(["-i", str(p)])
    filter_str = (
        "".join(f"[{i}:v:0][{i}:a:0]" for i in range(n))
        + f"concat=n={n}:v=1:a=1[outv][outa]"
    )
    cmd = [
        _FFMPEG,
        *inputs,
        "-filter_complex", filter_str,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", *_COLOR_FLAGS,
        "-c:a", "aac", "-ar", "44100",
        "-y", str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _filter_highlights(query: str, dirs: list) -> list:
    exact = [d for d in dirs if d.name.lower() == query.lower()]
    if exact:
        return exact

    partial = [d for d in dirs if query.lower() in d.name.lower()]
    if not partial:
        available = ", ".join(d.name for d in dirs)
        print(f"✗  No highlight matching '{query}' found.")
        print(f"   Available: {available}")
        sys.exit(1)

    if len(partial) == 1:
        print(f"→  Matched '{partial[0].name}'")
        return partial

    print(f"Multiple highlights match '{query}':")
    for i, d in enumerate(partial, start=1):
        print(f"  {i}. {d.name}")
    raw = input(f"Pick [1-{len(partial)}]: ").strip()
    if not raw.isdigit() or not (1 <= int(raw) <= len(partial)):
        print("✗  Invalid selection.")
        sys.exit(1)
    return [partial[int(raw) - 1]]


def run(config: VideoConfig) -> None:
    caffeinate = None
    if config.no_sleep:
        try:
            caffeinate = subprocess.Popen(["caffeinate", "-i"])
        except FileNotFoundError:
            print("⚠  caffeinate not found — --no-sleep has no effect on this platform")
    try:
        if config.both_formats:
            formats = [False, True]
        elif config.landscape:
            formats = [True]
        else:
            formats = [False]
        for landscape in formats:
            if config.both_formats:
                rprint(f"\n[bold]━━ {'Landscape (16:9)' if landscape else 'Portrait'} ━━[/bold]")
            _encode(config, landscape)
    finally:
        if caffeinate is not None:
            caffeinate.terminate()


def _encode(config: VideoConfig, landscape: bool) -> None:
    base = Path(config.output_dir) if config.output_dir else Path("output") / config.username
    instagram_dir = base / "instagram"
    if not instagram_dir.exists():
        print(f"✗  No downloaded highlights found at {instagram_dir}")
        sys.exit(1)

    highlight_dirs = sorted(
        d for d in instagram_dir.iterdir()
        if d.is_dir() and not d.is_symlink() and (d / "metadata.json").exists()
    )
    if not highlight_dirs:
        print(f"✗  No downloaded highlights found at {instagram_dir}")
        sys.exit(1)

    if config.highlight:
        highlight_dirs = _filter_highlights(config.highlight, highlight_dirs)

    videos_dir_name = "videos_landscape" if landscape else "videos"
    videos_dir = base / videos_dir_name
    videos_dir.mkdir(exist_ok=True)

    # Resolve all conflicts before starting the progress bar so that
    # input() prompts are not corrupted by Rich's live terminal rendering.
    queue = []
    for hdir in highlight_dirs:
        meta = json.loads((hdir / "metadata.json").read_text())
        title = meta.get("highlight_title", hdir.name)
        slides = _collect_slides(hdir, meta)
        if not slides:
            prog.log_video_skip(f"{title} — no valid slides, skipping")
            continue
        stem = f"{hdir.name}_landscape" if landscape else hdir.name
        output_path = videos_dir / f"{stem}.mp4"
        if config.update:
            if not _needs_update(hdir, output_path):
                rprint(f"[green]✓[/green]  {title} — up to date")
                continue
            if output_path.exists():
                send2trash(str(output_path))
            resolved = output_path
        else:
            resolved = _resolve_conflict(output_path)
            if resolved is None:
                prog.log_video_skip(f"{title}.mp4 skipped")
                continue
        queue.append((title, slides, resolved, hdir))

    if not queue:
        return

    print(f"\n✓  {len(queue)} highlight(s) to encode\n")

    with prog.create_progress() as progress:
        overall = prog.add_overall_task(progress, len(queue))
        for title, slides, output_path, hdir in queue:
            task_id = prog.add_video_task(progress, title, len(slides))
            tmp_dir = Path(tempfile.mkdtemp())
            start = time.time()
            completed = False
            try:
                clips = []
                for slide in slides:
                    clip = _normalize_slide(
                        slide["path"], slide["index"], tmp_dir, slide["type"] == "video",
                        config.image_duration,
                        landscape=landscape,
                    )
                    clips.append(clip)
                    prog.advance(progress, task_id, slide["path"].name)
                _concat_clips(clips, output_path)
                completed = True
                elapsed = time.time() - start
                m, s = divmod(int(elapsed), 60)
                prog.complete_video_task(progress, task_id, title, m, s)
                progress.advance(overall)
                print(f"✓  {output_path.name} — {len(slides)} slides, {m}m {s:02d}s")
                if config.update:
                    _mark_youtube_outdated(base, hdir.name, landscape=landscape)
            except subprocess.CalledProcessError as e:
                stderr = e.stderr.decode(errors="replace") if e.stderr else ""
                print(f"✗  {title} — ffmpeg error\n{stderr}")
            finally:
                if not completed and output_path.exists():
                    send2trash(str(output_path))
                shutil.rmtree(tmp_dir, ignore_errors=True)

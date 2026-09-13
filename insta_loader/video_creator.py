import glob as _glob
import hashlib
import json
import re
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
from insta_loader import variants
from insta_loader.cli import VideoConfig

_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

_VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}

_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)")
_FPS_RE = re.compile(r",\s*([\d.]+)\s*fps")

# Instagram exports a "photo + music" story as an mp4, usually at 1 fps. Those are
# padding in an assembled reel, so the short variant caps them. Real video is left
# alone. fps alone is only ~85% accurate (some 1 fps clips are genuine video), so it
# is used purely as a cheap pre-filter before a definitive frame-identity check.
_STATIC_FPS_THRESHOLD = 2.0

_static_cache: dict = {}


def _probe(path: Path) -> tuple:
    """Return (duration_seconds, fps); either may be None if unreadable."""
    out = subprocess.run([_FFMPEG, "-i", str(path)], capture_output=True).stderr.decode(
        "utf-8", errors="replace"
    )
    d, f = _DURATION_RE.search(out), _FPS_RE.search(out)
    duration = None
    if d:
        duration = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3))
    return duration, (float(f.group(1)) if f else None)


def _frame_hash(path: Path, ts: float) -> Optional[str]:
    """md5 of a single frame decoded at `ts`, downscaled to 64x64."""
    r = subprocess.run(
        [_FFMPEG, "-ss", f"{ts}", "-i", str(path), "-frames:v", "1",
         "-vf", "scale=64:64", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
    )
    return hashlib.md5(r.stdout).hexdigest() if r.stdout else None


def _is_static(path: Path, duration: Optional[float], fps: Optional[float]) -> bool:
    """True if the clip is a still image with audio (no visual motion)."""
    if duration is None or fps is None or fps > _STATIC_FPS_THRESHOLD:
        return False
    key = str(path)
    if key in _static_cache:
        return _static_cache[key]
    # Frames sit 1s apart at 1 fps, so keep >=1.5s margin from the end or the
    # seek lands past the final frame and nothing decodes.
    a = _frame_hash(path, 0.5)
    b = _frame_hash(path, max(0.6, duration - 1.5))
    mid = _frame_hash(path, duration / 2)
    result = bool(a and b and mid and a == b == mid)
    _static_cache[key] = result
    return result


def _trim_for(path: Path, cap: int) -> Optional[int]:
    """Return the cap to apply to this video slide, or None to leave it untouched."""
    duration, fps = _probe(path)
    if duration is None or duration <= cap:
        return None
    return cap if _is_static(path, duration, fps) else None


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


def _mark_youtube_outdated(base: Path, folder_name: str,
                           variant: "variants.Variant" = None) -> None:
    """Set outdated=True in the variant's youtube dir/<stem>.json if previously uploaded."""
    variant = variant or variants.Variant()
    meta_path = base / variant.youtube_dir / f"{variant.stem(folder_name)}.json"
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


def _normalize_slide(slide_path: Path, index: int, tmp_dir: Path, is_video: bool, image_duration: int = 10, landscape: bool = False, trim_to: Optional[int] = None) -> Path:
    out = tmp_dir / f"clip_{index:03d}.mp4"
    # Output-side -t truncates a video slide; image slides are already bounded by
    # their input-side -t image_duration, so the caller clamps that instead.
    trim = ["-t", str(trim_to)] if trim_to else []
    if landscape:
        if is_video:
            if _has_audio(slide_path):
                cmd = [
                    _FFMPEG, "-i", str(slide_path),
                    "-filter_complex", _VF_LANDSCAPE,
                    "-map", "[out]", "-map", "0:a",
                    *_ENCODE_FLAGS,
                    "-c:a", "aac", "-ar", "44100",
                    *trim,
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
                    *trim,
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
                    *trim,
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
                    *trim,
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
        wanted = variants.resolve(
            landscape=config.landscape,
            short=config.short,
            both_formats=config.both_formats,
            all_variants=config.all_variants,
        )
        for variant in wanted:
            if len(wanted) > 1:
                rprint(f"\n[bold]━━ {variant.label} ━━[/bold]")
            _encode(config, variant)
    finally:
        if caffeinate is not None:
            caffeinate.terminate()


def _encode(config: VideoConfig, variant: "variants.Variant") -> None:
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

    videos_dir = base / variant.videos_dir
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
        stem = variant.stem(hdir.name)
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
                cap = config.max_slide_duration
                for slide in slides:
                    is_video = slide["type"] == "video"
                    # In the short variant, cap static photo-with-music clips; real
                    # video keeps its full length. Images are bounded by their duration.
                    trim_to = _trim_for(slide["path"], cap) if (variant.short and is_video) else None
                    image_duration = min(config.image_duration, cap) if variant.short else config.image_duration
                    clip = _normalize_slide(
                        slide["path"], slide["index"], tmp_dir, is_video,
                        image_duration,
                        landscape=variant.landscape,
                        trim_to=trim_to,
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
                    _mark_youtube_outdated(base, hdir.name, variant)
            except subprocess.CalledProcessError as e:
                stderr = e.stderr.decode(errors="replace") if e.stderr else ""
                print(f"✗  {title} — ffmpeg error\n{stderr}")
            finally:
                if not completed and output_path.exists():
                    send2trash(str(output_path))
                shutil.rmtree(tmp_dir, ignore_errors=True)

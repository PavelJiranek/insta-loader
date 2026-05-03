from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich import print as rprint

__all__ = [
    "create_progress", "add_highlight_task", "add_video_task",
    "advance", "update_stats", "log_skip", "log_video_skip",
]


def create_progress() -> Progress:
    return Progress(
        TextColumn("[bold yellow]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[dim]{task.fields[current_file]}"),
        TimeElapsedColumn(),
        TextColumn("{task.fields[stats]}"),
    )


def add_highlight_task(progress: Progress, title: str, total: int) -> TaskID:
    return progress.add_task(f"Highlight: {title}", total=total, current_file="", stats="")


def add_video_task(progress: Progress, title: str, total: int) -> TaskID:
    return progress.add_task(f"Video: {title}", total=total, current_file="", stats="")


def advance(progress: Progress, task_id: TaskID, filename: str = "") -> None:
    progress.update(task_id, advance=1, current_file=filename)


def update_stats(
    progress: Progress, task_id: TaskID,
    downloaded: int, skipped: int, failed: int,
) -> None:
    parts = []
    if downloaded:
        parts.append(f"[green]✓{downloaded}[/green]")
    if skipped:
        parts.append(f"[dim]–{skipped}[/dim]")
    if failed:
        parts.append(f"[red]✗{failed}[/red]")
    progress.update(task_id, stats=" ".join(parts))


def log_skip(filename: str) -> None:
    rprint(f"[dim]Skipping {filename} — already downloaded[/dim]")


def log_video_skip(message: str) -> None:
    rprint(f"[dim]–  {message}[/dim]")

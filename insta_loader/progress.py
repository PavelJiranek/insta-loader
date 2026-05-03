from rich.progress import (
    BarColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich import print as rprint

__all__ = ["create_progress", "add_highlight_task", "add_video_task", "advance", "log_skip"]


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


def add_video_task(progress: Progress, title: str, total: int) -> TaskID:
    return progress.add_task(f"Video: {title}", total=total, current_file="")


def advance(progress: Progress, task_id: TaskID, filename: str = "") -> None:
    progress.update(task_id, advance=1, current_file=filename)


def log_skip(filename: str) -> None:
    rprint(f"[dim]Skipping {filename} — already downloaded[/dim]")

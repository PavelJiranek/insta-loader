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
    "create_progress", "add_overall_task", "add_highlight_task", "add_video_task",
    "advance", "complete_video_task", "update_stats", "log_skip", "log_video_skip",
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


def add_overall_task(progress: Progress, total: int) -> TaskID:
    return progress.add_task("[cyan]Overall", total=total, current_file="", stats="")


def add_highlight_task(progress: Progress, title: str, total: int) -> TaskID:
    return progress.add_task(f"Highlight: {title}", total=total, current_file="", stats="")


def add_video_task(progress: Progress, title: str, total: int) -> TaskID:
    return progress.add_task(f"Video: {title}", total=total, current_file="", stats="")


def complete_video_task(progress: Progress, task_id: TaskID, title: str, elapsed_m: int, elapsed_s: int) -> None:
    """Mark a video task complete and bake elapsed time into the description."""
    progress.update(
        task_id,
        description=f"[bold green]Video: {title}[/bold green] [dim]({elapsed_m}m{elapsed_s:02d}s)[/dim]",
    )


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

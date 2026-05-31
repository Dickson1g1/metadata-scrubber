"""
Terminal rendering using rich.
All print() calls are banned from other modules — UI lives here only.
"""

from pathlib import Path
from rich.console import Console
from rich.table   import Table
from rich.panel   import Panel
from rich.text    import Text
from rich         import box

console = Console()
err     = Console(stderr=True)


def print_before_after(path: Path, before: dict, after: dict) -> None:
    """
    Display a two-column before/after metadata comparison table.
    Fields present before but absent after = successfully scrubbed (shown green).
    Fields still present after = not removed (shown red — should not happen).
    """
    table = Table(
        box=box.SIMPLE,
        show_header=True,
        header_style="bold",
        title=f"[dim]{path.name}[/dim]",
    )
    table.add_column("Field",  style="dim",   min_width=24)
    table.add_column("Before", style="bold",  min_width=30, overflow="fold")
    table.add_column("After",  min_width=10)

    all_fields = set(before) | set(after)
    for field in sorted(all_fields):
        b_val = before.get(field, "—")
        a_val = after.get(field, "—")

        if field in before and field not in after:
            # Successfully removed — green tick
            after_cell = Text("✔ removed", style="bold green")
        elif field in after:
            # Still present after scrubbing — flag in red
            after_cell = Text(f"⚠ {a_val[:40]}", style="bold red")
        else:
            after_cell = Text("—", style="dim")

        table.add_row(field, str(b_val)[:60], after_cell)

    console.print(table)


def print_progress(path: Path, result: dict) -> None:
    """Print a single live-update line as each file completes."""
    name = path.name
    if result.get("skipped"):
        console.print(f"  [dim]─ {name}  (skipped — unsupported format)[/dim]")
    elif result.get("success"):
        n = len(result.get("fields_removed", []))
        console.print(
            f"  [green]✔[/green] [bold]{name}[/bold]"
            f"  [dim]{n} field(s) removed[/dim]"
        )
    else:
        console.print(
            f"  [red]✘[/red] [bold]{name}[/bold]"
            f"  [red]{result.get('error', 'unknown error')}[/red]"
        )


def print_summary(results: list[dict], dry_run: bool) -> None:
    """Print the final summary panel after all files are processed."""
    total    = len(results)
    success  = sum(1 for r in results if r.get("success") and not r.get("skipped"))
    skipped  = sum(1 for r in results if r.get("skipped"))
    failed   = total - success - skipped
    removed  = sum(len(r.get("fields_removed", [])) for r in results)

    verb = "would be scrubbed" if dry_run else "scrubbed"

    lines = Text()
    lines.append(f"  Files {verb}: ", style="dim")
    lines.append(f"{success}", style="bold green")
    lines.append(f"\n  Fields removed:  ", style="dim")
    lines.append(f"{removed}", style="bold cyan")
    if skipped:
        lines.append(f"\n  Skipped:         ", style="dim")
        lines.append(f"{skipped}", style="dim")
    if failed:
        lines.append(f"\n  Errors:          ", style="dim")
        lines.append(f"{failed}", style="bold red")

    border = "green" if not failed else "yellow"
    prefix = "[DRY RUN] " if dry_run else ""
    console.print(Panel(lines, title=f"[bold]{prefix}Summary[/bold]",
                         border_style=border))
    console.print()


def print_error(msg: str) -> None:
    err.print(f"[bold red]Error:[/bold red] {msg}")

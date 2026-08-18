"""Build canonical timelines for all investigation cases."""

from rich.console import Console
from rich.progress import track
from rich.table import Table

from clinical_investigation.config import settings
from clinical_investigation.investigation.timeline_reconstruction import (
    TimelineReconstructionError,
    build_canonical_timeline,
)

console = Console()


def main() -> int:
    """Build all canonical timelines."""

    root = settings.investigation_cases_dir

    if not root.exists():
        console.print(f"[red]Investigation case directory not found: {root}[/red]")
        return 1

    case_dirs = sorted(path for path in root.iterdir() if path.is_dir())

    if not case_dirs:
        console.print("[red]No investigation cases found.[/red]")
        return 1

    table = Table(title="Canonical timeline reconstruction")
    table.add_column("Case ID")
    table.add_column("Status")
    table.add_column("Output")

    failure_count = 0

    for case_dir in track(
        case_dirs,
        description="Reconstructing timelines...",
    ):
        try:
            output_dir = build_canonical_timeline(case_dir)

            table.add_row(
                case_dir.name,
                "[green]PASS[/green]",
                str(output_dir),
            )
        except TimelineReconstructionError as exc:
            failure_count += 1

            table.add_row(
                case_dir.name,
                "[red]FAIL[/red]",
                str(exc),
            )

    console.print(table)

    if failure_count:
        console.print(f"[red]{failure_count} cases failed timeline reconstruction.[/red]")
        return 1

    console.print(f"[green]Built canonical timelines for {len(case_dirs)} cases.[/green]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

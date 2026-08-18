"""Build structured investigation cases from clinical documents."""

from rich.console import Console
from rich.progress import track
from rich.table import Table

from clinical_investigation.config import settings
from clinical_investigation.investigation.evidence_extraction import (
    EvidenceExtractionError,
    build_investigation_case,
)

console = Console()


def main() -> int:
    """Build all investigation cases."""

    source_root = settings.encounter_documents_dir
    output_root = settings.investigation_cases_dir

    if not source_root.exists():
        console.print(f"[red]Generated clinical document directory not found: {source_root}[/red]")
        return 1

    case_dirs = sorted(path for path in source_root.iterdir() if path.is_dir())

    if not case_dirs:
        console.print("[red]No generated clinical document cases were found.[/red]")
        return 1

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    table = Table(title="Investigation case extraction")
    table.add_column("Case ID")
    table.add_column("Status")
    table.add_column("Output")

    failure_count = 0

    for case_dir in track(
        case_dirs,
        description="Extracting evidence and claims...",
    ):
        try:
            output_dir = build_investigation_case(
                document_dir=case_dir,
                output_root=output_root,
            )

            table.add_row(
                case_dir.name,
                "[green]PASS[/green]",
                str(output_dir),
            )
        except EvidenceExtractionError as exc:
            failure_count += 1

            table.add_row(
                case_dir.name,
                "[red]FAIL[/red]",
                str(exc),
            )

    console.print(table)

    if failure_count:
        console.print(f"[red]{failure_count} cases failed evidence extraction.[/red]")
        return 1

    console.print(f"[green]Built {len(case_dirs)} investigation cases.[/green]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

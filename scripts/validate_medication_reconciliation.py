"""Validate all medication reconciliation outputs."""

from rich.console import Console
from rich.table import Table

from clinical_investigation.config import settings
from clinical_investigation.investigation.medication_validation import (
    validate_medication_reconciliation,
)

console = Console()


def main() -> int:
    """Validate all medication reconciliation cases."""

    root = settings.investigation_cases_dir

    if not root.exists():
        console.print(f"[red]Investigation case directory not found: {root}[/red]")
        return 1

    case_dirs = sorted(path for path in root.iterdir() if path.is_dir())

    if not case_dirs:
        console.print("[red]No investigation cases found.[/red]")
        return 1

    table = Table(title="Medication reconciliation validation")
    table.add_column("Case ID")
    table.add_column("Status")
    table.add_column("Errors")

    failure_count = 0

    for case_dir in case_dirs:
        errors = validate_medication_reconciliation(case_dir)

        if errors:
            failure_count += 1

            table.add_row(
                case_dir.name,
                "[red]FAIL[/red]",
                "; ".join(errors),
            )
        else:
            table.add_row(
                case_dir.name,
                "[green]PASS[/green]",
                "",
            )

    console.print(table)

    if failure_count:
        console.print(
            f"[red]{failure_count} medication reconciliation cases failed validation.[/red]"
        )
        return 1

    console.print(
        f"[green]All {len(case_dirs)} medication reconciliation cases passed validation.[/green]"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

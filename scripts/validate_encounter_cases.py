"""Validate all encounter-centered evidence bundles."""

from rich.console import Console
from rich.table import Table

from clinical_investigation.config import settings
from clinical_investigation.evidence.encounter_validation import (
    validate_encounter_case,
)

console = Console()


def main() -> int:
    root = settings.encounter_cases_dir

    if not root.exists():
        console.print(f"[red]Encounter case directory not found: {root}[/red]")
        return 1

    case_dirs = sorted(path for path in root.iterdir() if path.is_dir())

    table = Table(title="Encounter case validation")
    table.add_column("Case ID")
    table.add_column("Status")
    table.add_column("Errors")

    failure_count = 0

    for case_dir in case_dirs:
        errors = validate_encounter_case(case_dir)

        if errors:
            failure_count += 1
            status = "[red]FAIL[/red]"
            error_text = "; ".join(errors)
        else:
            status = "[green]PASS[/green]"
            error_text = ""

        table.add_row(
            case_dir.name,
            status,
            error_text,
        )

    console.print(table)

    if failure_count:
        console.print(f"[red]{failure_count} encounter cases failed.[/red]")
        return 1

    console.print(f"[green]All {len(case_dirs)} encounter cases passed.[/green]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

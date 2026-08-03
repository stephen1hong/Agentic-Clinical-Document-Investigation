"""Validate generated clinical document sets."""

from rich.console import Console
from rich.table import Table

from clinical_investigation.config import settings
from clinical_investigation.reporting.document_validation import (
    validate_document_set,
)

console = Console()


def main() -> int:
    root = settings.encounter_documents_dir

    if not root.exists():
        console.print(f"[red]Generated document directory not found: {root}[/red]")
        return 1

    document_dirs = sorted(path for path in root.iterdir() if path.is_dir())

    if not document_dirs:
        console.print("[red]No generated document sets found.[/red]")
        return 1

    table = Table(title="Clinical document validation")
    table.add_column("Case ID")
    table.add_column("Status")
    table.add_column("Errors")

    failure_count = 0

    for document_dir in document_dirs:
        errors = validate_document_set(document_dir)

        if errors:
            failure_count += 1
            status = "[red]FAIL[/red]"
            error_text = "; ".join(errors)
        else:
            status = "[green]PASS[/green]"
            error_text = ""

        table.add_row(
            document_dir.name,
            status,
            error_text,
        )

    console.print(table)

    if failure_count:
        console.print(f"[red]{failure_count} document sets failed.[/red]")
        return 1

    console.print(f"[green]All {len(document_dirs)} document sets passed validation.[/green]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

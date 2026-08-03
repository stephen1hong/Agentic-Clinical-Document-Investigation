"""Validate all generated longitudinal patient evidence packages."""

from rich.console import Console
from rich.table import Table

from clinical_investigation.config import settings
from clinical_investigation.ingestion.package_validation import (
    validate_patient_package,
)

console = Console()


def main() -> int:
    packages_root = settings.patient_packages_dir

    if not packages_root.exists():
        console.print(f"[red]Patient package directory not found: {packages_root}[/red]")
        return 1

    patient_dirs = sorted(path for path in packages_root.iterdir() if path.is_dir())

    if not patient_dirs:
        console.print("[red]No patient packages were found.[/red]")
        return 1

    table = Table(title="Patient package validation")
    table.add_column("Patient ID")
    table.add_column("Status")
    table.add_column("Errors")

    failure_count = 0

    for patient_dir in patient_dirs:
        errors = validate_patient_package(patient_dir)

        if errors:
            failure_count += 1
            status = "[red]FAIL[/red]"
            error_text = "; ".join(errors)
        else:
            status = "[green]PASS[/green]"
            error_text = ""

        table.add_row(
            patient_dir.name,
            status,
            error_text,
        )

    console.print(table)

    if failure_count:
        console.print(f"[red]{failure_count} patient packages failed validation.[/red]")
        return 1

    console.print(f"[green]All {len(patient_dirs)} patient packages passed validation.[/green]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

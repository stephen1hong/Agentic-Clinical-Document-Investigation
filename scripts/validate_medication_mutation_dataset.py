"""Validate the medication mutation dataset."""

from rich.console import Console

from clinical_investigation.config import settings
from clinical_investigation.evaluation.medication_mutation_validation import (
    validate_mutation_dataset,
)

console = Console()


def main() -> int:
    """Validate mutation cases and gold labels."""

    errors = validate_mutation_dataset(
        mutation_cases_root=(settings.medication_mutation_cases_dir),
        mutation_records_path=(settings.medication_mutation_gold_dir / "mutation_records.json"),
        gold_discrepancies_path=(settings.medication_mutation_gold_dir / "gold_discrepancies.json"),
    )

    if errors:
        for error in errors:
            console.print(f"[red]FAIL: {error}[/red]")

        return 1

    console.print("[green]Medication mutation dataset passed validation.[/green]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

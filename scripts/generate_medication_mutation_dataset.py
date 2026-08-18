"""Generate a mutation-based medication evaluation dataset."""

from rich.console import Console

from clinical_investigation.config import settings
from clinical_investigation.evaluation.medication_mutations import (
    generate_mutation_dataset,
)

console = Console()


def main() -> int:
    """Generate medication mutation cases."""

    (
        mutation_records,
        gold_records,
    ) = generate_mutation_dataset(
        investigation_root=(settings.investigation_cases_dir),
        source_documents_root=(settings.encounter_documents_dir),
        output_cases_root=(settings.medication_mutation_cases_dir),
        gold_root=(settings.medication_mutation_gold_dir),
        mutations_per_case=1,
        random_seed=42,
    )

    console.print(
        f"[green]Generated "
        f"{len(mutation_records)} mutation cases "
        f"and {len(gold_records)} gold labels."
        "[/green]"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

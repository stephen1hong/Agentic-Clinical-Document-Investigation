"""Build medication discrepancy predictions for mutated cases."""

from rich.console import Console
from rich.progress import track

from clinical_investigation.config import settings
from clinical_investigation.investigation.evidence_extraction import (
    build_investigation_case_from_documents,
)
from clinical_investigation.investigation.medication_reconciliation import (
    build_medication_reconciliation,
)
from clinical_investigation.investigation.timeline_reconstruction import (
    build_canonical_timeline,
)

console = Console()


def main() -> int:
    """Run the investigation pipeline over mutation cases."""

    root = settings.medication_mutation_cases_dir

    case_dirs = sorted(path for path in root.iterdir() if path.is_dir())

    failure_count = 0

    for case_dir in track(
        case_dirs,
        description="Evaluating mutation cases...",
    ):
        documents_dir = case_dir / "documents"

        try:
            build_investigation_case_from_documents(
                case_id=case_dir.name,
                documents_dir=documents_dir,
                output_dir=case_dir,
            )

            build_canonical_timeline(case_dir)

            build_medication_reconciliation(case_dir)

        except Exception as exc:
            failure_count += 1

            console.print(f"[red]{case_dir.name}: {exc}[/red]")

    if failure_count:
        console.print(f"[red]{failure_count} mutation cases failed.[/red]")
        return 1

    console.print(f"[green]Built predictions for {len(case_dirs)} mutation cases.[/green]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

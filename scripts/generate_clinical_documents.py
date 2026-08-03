"""Generate clinical documents for all encounter cases."""

from rich.console import Console
from rich.progress import track
from rich.table import Table

from clinical_investigation.config import settings
from clinical_investigation.reporting.clinical_documents import (
    ClinicalDocumentError,
    DocumentGenerationResult,
    generate_encounter_documents,
)

console = Console()


def display_results(
    results: list[DocumentGenerationResult],
) -> None:
    """Display generated document statistics."""

    table = Table(title="Generated clinical document sets")
    table.add_column("Case ID")
    table.add_column("Documents", justify="right")
    table.add_column("Evidence citations", justify="right")
    table.add_column("Output directory")

    for result in results:
        citation_count = sum(document.evidence_count for document in result.documents)

        table.add_row(
            result.case_id,
            str(len(result.documents)),
            str(citation_count),
            str(result.output_dir),
        )

    console.print(table)


def main() -> int:
    encounter_root = settings.encounter_cases_dir

    if not encounter_root.exists():
        console.print(f"[red]Encounter case directory not found: {encounter_root}[/red]")
        return 1

    case_dirs = sorted(path for path in encounter_root.iterdir() if path.is_dir())

    if not case_dirs:
        console.print("[red]No encounter cases were found.[/red]")
        return 1

    output_root = settings.encounter_documents_dir
    output_root.mkdir(parents=True, exist_ok=True)

    results: list[DocumentGenerationResult] = []
    failures: list[tuple[str, str]] = []

    for case_dir in track(
        case_dirs,
        description="Generating clinical documents...",
    ):
        try:
            result = generate_encounter_documents(
                case_dir=case_dir,
                output_root=output_root,
            )
            results.append(result)
        except ClinicalDocumentError as exc:
            failures.append((case_dir.name, str(exc)))

    display_results(results)

    console.print(f"[green]Generated document sets for {len(results)} encounter cases.[/green]")

    if failures:
        console.print()

        for case_id, error in failures:
            console.print(f"[red]{case_id}: {error}[/red]")

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Build encounter-centered clinical evidence bundles."""

import json

from rich.console import Console
from rich.progress import track
from rich.table import Table

from clinical_investigation.config import settings
from clinical_investigation.evidence.encounter_case import (
    EncounterCandidate,
    EncounterCaseError,
    EncounterCaseResult,
    build_encounter_case_bundle,
)

console = Console()


def load_candidates() -> list[EncounterCandidate]:
    """Load selected encounter candidates."""

    path = settings.selected_encounters_dir / "selected_encounter_cases.json"

    if not path.exists():
        raise FileNotFoundError(f"Selected encounter file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))

    return [EncounterCandidate(**item) for item in payload["cases"]]


def display_results(
    results: list[EncounterCaseResult],
) -> None:
    """Display generated bundle results."""

    table = Table(title="Encounter evidence bundles")
    table.add_column("Case ID")
    table.add_column("Patient ID")
    table.add_column("Encounter ID")
    table.add_column("Timeline events", justify="right")

    for result in results:
        table.add_row(
            result.case_id,
            result.patient_id,
            result.encounter_id,
            str(result.timeline_event_count),
        )

    console.print(table)


def main() -> int:
    try:
        candidates = load_candidates()
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    output_root = settings.encounter_cases_dir
    output_root.mkdir(parents=True, exist_ok=True)

    results: list[EncounterCaseResult] = []
    failures: list[tuple[str, str]] = []

    for candidate in track(
        candidates,
        description="Building encounter cases...",
    ):
        try:
            result = build_encounter_case_bundle(
                candidate=candidate,
                patient_packages_root=(settings.patient_packages_dir),
                output_root=output_root,
            )
            results.append(result)
        except EncounterCaseError as exc:
            failures.append((candidate.case_id, str(exc)))

    display_results(results)

    console.print(f"[green]Built {len(results)} encounter bundles.[/green]")
    console.print(f"Output directory: {output_root}")

    if failures:
        for case_id, error in failures:
            console.print(f"[red]{case_id}: {error}[/red]")

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

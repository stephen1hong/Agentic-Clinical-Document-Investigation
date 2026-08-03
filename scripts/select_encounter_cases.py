"""Select encounter-centered investigation cases."""

import csv
import json
from dataclasses import asdict

from rich.console import Console
from rich.table import Table

from clinical_investigation.config import settings
from clinical_investigation.evidence.encounter_case import (
    discover_encounter_candidates,
    select_encounter_candidates,
)

console = Console()

TARGET_CASE_COUNT = 20
MAX_CASES_PER_PATIENT = 2


def write_csv(
    path,
    rows: list[dict[str, object]],
) -> None:
    """Write encounter selection CSV."""

    if not rows:
        return

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    patient_root = settings.patient_packages_dir

    if not patient_root.exists():
        console.print(f"[red]Patient packages not found: {patient_root}[/red]")
        return 1

    console.print(f"Discovering encounter candidates from [bold]{patient_root}[/bold]")

    candidates = discover_encounter_candidates(patient_root)

    if not candidates:
        console.print("[red]No encounter candidates found.[/red]")
        return 1

    selected = select_encounter_candidates(
        candidates=candidates,
        target_count=TARGET_CASE_COUNT,
        max_cases_per_patient=MAX_CASES_PER_PATIENT,
    )

    output_dir = settings.selected_encounters_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = [asdict(candidate) for candidate in selected]

    csv_path = output_dir / "selected_encounter_cases.csv"
    json_path = output_dir / "selected_encounter_cases.json"

    write_csv(csv_path, rows)

    json_path.write_text(
        json.dumps(
            {
                "case_count": len(rows),
                "target_case_count": TARGET_CASE_COUNT,
                "cases": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    table = Table(title="Selected encounter cases")
    table.add_column("Case ID")
    table.add_column("Class")
    table.add_column("Score", justify="right")
    table.add_column("Conditions", justify="right")
    table.add_column("Meds", justify="right")
    table.add_column("Observations", justify="right")
    table.add_column("Procedures", justify="right")
    table.add_column("Discharge", justify="right")

    for candidate in selected:
        table.add_row(
            candidate.case_id,
            candidate.encounter_class,
            f"{candidate.score:.1f}",
            str(candidate.condition_count),
            str(candidate.medication_count),
            str(candidate.observation_count),
            str(candidate.procedure_count),
            str(candidate.discharge_candidate_count),
        )

    console.print(table)
    console.print(f"[green]Selected {len(selected)} encounter cases.[/green]")
    console.print(f"Saved: {csv_path}")
    console.print(f"Saved: {json_path}")

    if len(selected) < 15:
        console.print("[yellow]Warning: fewer than 15 suitable encounters were selected.[/yellow]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

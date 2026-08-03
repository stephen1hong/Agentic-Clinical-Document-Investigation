"""Build longitudinal evidence packages for selected Synthea patients."""

import json
from pathlib import Path

from rich.console import Console
from rich.progress import track
from rich.table import Table

from clinical_investigation.config import settings
from clinical_investigation.ingestion.patient_package import (
    PatientPackageError,
    PatientPackageResult,
    build_patient_package,
)
from clinical_investigation.ingestion.synthea_csv import (
    load_synthea_csv,
)

console = Console()


def load_selected_patient_ids(path: Path) -> list[str]:
    """Load patient identifiers produced by cohort selection."""

    if not path.exists():
        raise FileNotFoundError(f"Selected-patient file does not exist: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))

    patient_ids = payload.get("patient_ids")

    if not isinstance(patient_ids, list):
        raise ValueError("selected_patient_ids.json must contain a patient_ids list")

    cleaned_ids = [str(patient_id).strip() for patient_id in patient_ids if str(patient_id).strip()]

    if not cleaned_ids:
        raise ValueError("No selected patient IDs were found")

    return cleaned_ids


def display_results(
    results: list[PatientPackageResult],
) -> None:
    """Display a summary of generated patient packages."""

    table = Table(title="Patient evidence packages")
    table.add_column("Patient ID")
    table.add_column("Encounters", justify="right")
    table.add_column("Conditions", justify="right")
    table.add_column("Medications", justify="right")
    table.add_column("Observations", justify="right")
    table.add_column("Procedures", justify="right")
    table.add_column("Timeline", justify="right")

    for result in results:
        counts = result.record_counts

        table.add_row(
            result.patient_id,
            str(counts["encounters"]),
            str(counts["conditions"]),
            str(counts["medications"]),
            str(counts["observations"]),
            str(counts["procedures"]),
            str(result.timeline_event_count),
        )

    console.print(table)


def main() -> int:
    selected_ids_path = settings.selected_patients_dir / "selected_patient_ids.json"

    console.print(f"Loading selected patient IDs from [bold]{selected_ids_path}[/bold]")

    try:
        patient_ids = load_selected_patient_ids(selected_ids_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    console.print(f"Loading Synthea CSV data from [bold]{settings.synthea_csv_dir}[/bold]")

    tables = load_synthea_csv(settings.synthea_csv_dir)

    output_root = settings.patient_packages_dir
    output_root.mkdir(parents=True, exist_ok=True)

    results: list[PatientPackageResult] = []
    failures: list[tuple[str, str]] = []

    for patient_id in track(
        patient_ids,
        description="Building patient packages...",
    ):
        try:
            result = build_patient_package(
                patient_id=patient_id,
                tables=tables,
                output_root=output_root,
            )
            results.append(result)
        except PatientPackageError as exc:
            failures.append((patient_id, str(exc)))

    display_results(results)

    console.print()
    console.print(f"[green]Generated {len(results)} patient packages.[/green]")
    console.print(f"Output directory: {output_root}")

    if failures:
        console.print()
        console.print(f"[red]{len(failures)} packages failed:[/red]")

        for patient_id, error in failures:
            console.print(f"- {patient_id}: {error}")

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

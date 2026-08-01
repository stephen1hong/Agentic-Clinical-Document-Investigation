
"""Validate Synthea CSV data integrity and display summary statistics."""

import pandas as pd
from rich.console import Console
from rich.table import Table

from clinical_investigation.config import settings
from clinical_investigation.ingestion.synthea_csv import (
    SyntheaDataError,
    load_synthea_csv,
)

#from pathlib import Path
#import sys

#PROJECT_ROOT = Path(__file__).resolve().parents[1]
#SRC_DIR = PROJECT_ROOT / "src"

#if str(SRC_DIR) not in sys.path:
#    sys.path.insert(0, str(SRC_DIR))



console = Console()


def patient_reference_column(table_name: str, frame: pd.DataFrame) -> str | None:
    """Find the patient reference column in a DataFrame.

    Args:
        table_name: Name of the table.
        frame: DataFrame to search.

    Returns:
        Column name if found, None otherwise.
    """
    candidates = {
        "patients": ["Id", "ID"],
        "encounters": ["PATIENT", "Patient"],
        "conditions": ["PATIENT", "Patient"],
        "medications": ["PATIENT", "Patient"],
        "observations": ["PATIENT", "Patient"],
        "procedures": ["PATIENT", "Patient"],
    }

    for candidate in candidates.get(table_name, []):
        if candidate in frame.columns:
            return candidate

    return None


def validate_tables(tables: dict[str, pd.DataFrame]) -> bool:
    """Validate Synthea tables for referential integrity.

    Args:
        tables: Dictionary of table names to DataFrames.

    Returns:
        True if validation passes, False otherwise.
    """
    patient_frame = tables["patients"]

    patient_id_column = (
        "Id" if "Id" in patient_frame.columns else "ID" if "ID" in patient_frame.columns else None
    )

    if patient_id_column is None:
        console.print("[red]patients.csv has no Id or ID column.[/red]")
        return False

    known_patient_ids = set(patient_frame[patient_id_column].dropna().astype(str))

    valid = True

    summary = Table(title="Synthea dataset summary")
    summary.add_column("Table")
    summary.add_column("Rows", justify="right")
    summary.add_column("Columns", justify="right")
    summary.add_column("Unique patients", justify="right")
    summary.add_column("Status")

    for table_name, frame in tables.items():
        patient_column = patient_reference_column(table_name, frame)

        if patient_column:
            unique_ids = set(frame[patient_column].dropna().astype(str))
            unique_patient_count = len(unique_ids)

            if table_name == "patients":
                unknown_ids: set[str] = set()
            else:
                unknown_ids = unique_ids - known_patient_ids
        else:
            unique_patient_count = 0
            unknown_ids = set()

        if unknown_ids:
            status = f"FAIL: {len(unknown_ids)} unknown patient IDs"
            valid = False
        elif frame.empty:
            status = "WARN: empty"
        else:
            status = "OK"

        summary.add_row(
            table_name,
            f"{len(frame):,}",
            str(len(frame.columns)),
            f"{unique_patient_count:,}",
            status,
        )

    console.print(summary)
    return valid


def main() -> int:
    """Main validation routine.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    console.print(f"Loading Synthea CSV data from: [bold]{settings.synthea_csv_dir}[/bold]")

    try:
        tables = load_synthea_csv(settings.synthea_csv_dir)
    except SyntheaDataError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    is_valid = validate_tables(tables)

    if not is_valid:
        console.print("[red]Dataset validation failed.[/red]")
        return 1

    console.print("[green]Dataset validation completed successfully.[/green]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

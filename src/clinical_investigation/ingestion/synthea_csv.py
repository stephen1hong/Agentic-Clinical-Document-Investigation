"""Load Synthea CSV data files."""

from pathlib import Path

import pandas as pd

REQUIRED_TABLES = {
    "patients": "patients.csv",
    "encounters": "encounters.csv",
    "conditions": "conditions.csv",
    "medications": "medications.csv",
    "observations": "observations.csv",
    "procedures": "procedures.csv",
}

OPTIONAL_TABLES = {
    "allergies": "allergies.csv",
    "careplans": "careplans.csv",
    "immunizations": "immunizations.csv",
    "devices": "devices.csv",
    "supplies": "supplies.csv",
}


class SyntheaDataError(RuntimeError):
    """Raised when Synthea input data is missing or invalid."""


def load_csv_table(path: Path) -> pd.DataFrame:
    """Load a single CSV table.

    Args:
        path: Path to the CSV file.

    Returns:
        DataFrame containing the CSV data.

    Raises:
        SyntheaDataError: If the file is missing or cannot be read.
    """
    if not path.exists():
        raise SyntheaDataError(f"File not found: {path}")

    try:
        return pd.read_csv(path, low_memory=False)
    except Exception as exc:
        raise SyntheaDataError(f"Unable to read {path}: {exc}") from exc


def load_synthea_csv(data_dir: Path) -> dict[str, pd.DataFrame]:
    """Load required and available optional Synthea CSV tables.

    Args:
        data_dir: Directory containing Synthea CSV files.

    Returns:
        Dictionary mapping table names to DataFrames.

    Raises:
        SyntheaDataError: If the directory doesn't exist or required files are missing.
    """
    if not data_dir.exists():
        raise SyntheaDataError(f"Synthea directory does not exist: {data_dir}")

    tables: dict[str, pd.DataFrame] = {}

    for table_name, filename in REQUIRED_TABLES.items():
        tables[table_name] = load_csv_table(data_dir / filename)

    for table_name, filename in OPTIONAL_TABLES.items():
        path = data_dir / filename
        if path.exists():
            tables[table_name] = load_csv_table(path)

    return tables

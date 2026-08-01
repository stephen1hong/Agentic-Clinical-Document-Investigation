from pathlib import Path

import pandas as pd
import pytest

from clinical_investigation.ingestion.synthea_csv import (
    SyntheaDataError,
    load_csv_table,
)


def test_load_csv_table(tmp_path: Path) -> None:
    csv_path = tmp_path / "patients.csv"

    pd.DataFrame(
        [
            {"Id": "patient-1", "FIRST": "Test", "LAST": "Patient"},
            {"Id": "patient-2", "FIRST": "Example", "LAST": "Patient"},
        ]
    ).to_csv(csv_path, index=False)

    result = load_csv_table(csv_path)

    assert len(result) == 2
    assert "Id" in result.columns


def test_missing_csv_raises_error(tmp_path: Path) -> None:
    with pytest.raises(SyntheaDataError):
        load_csv_table(tmp_path / "missing.csv")

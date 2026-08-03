"""Tests for patient package validation."""

from pathlib import Path

from clinical_investigation.ingestion.package_validation import (
    validate_patient_package,
)
from clinical_investigation.ingestion.patient_package import (
    build_patient_package,
)
from tests.unit.test_patient_package import create_test_tables


def test_generated_package_passes_validation(
    tmp_path: Path,
) -> None:
    build_patient_package(
        patient_id="patient-001",
        tables=create_test_tables(),
        output_root=tmp_path,
    )

    errors = validate_patient_package(tmp_path / "patient-001")

    assert errors == []

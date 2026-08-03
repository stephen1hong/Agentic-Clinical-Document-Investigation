"""Tests for longitudinal patient package generation."""

import json
from pathlib import Path

import pandas as pd

from clinical_investigation.ingestion.patient_package import (
    build_patient_package,
    create_timeline_event,
)


def create_test_tables() -> dict[str, pd.DataFrame]:
    """Create a minimal synthetic patient dataset."""

    patient_id = "patient-001"
    encounter_id = "encounter-001"

    return {
        "patients": pd.DataFrame(
            [
                {
                    "Id": patient_id,
                    "FIRST": "Test",
                    "LAST": "Patient",
                    "BIRTHDATE": "1980-01-01",
                }
            ]
        ),
        "encounters": pd.DataFrame(
            [
                {
                    "Id": encounter_id,
                    "START": "2026-01-01T10:00:00Z",
                    "STOP": "2026-01-02T10:00:00Z",
                    "PATIENT": patient_id,
                    "ENCOUNTERCLASS": "inpatient",
                    "CODE": "123",
                    "DESCRIPTION": "Inpatient encounter",
                }
            ]
        ),
        "conditions": pd.DataFrame(
            [
                {
                    "START": "2026-01-01",
                    "STOP": None,
                    "PATIENT": patient_id,
                    "ENCOUNTER": encounter_id,
                    "CODE": "C001",
                    "DESCRIPTION": "Example condition",
                }
            ]
        ),
        "medications": pd.DataFrame(
            [
                {
                    "START": "2026-01-01",
                    "STOP": "2026-01-05",
                    "PATIENT": patient_id,
                    "ENCOUNTER": encounter_id,
                    "CODE": "M001",
                    "DESCRIPTION": "Example medication",
                }
            ]
        ),
        "observations": pd.DataFrame(
            [
                {
                    "DATE": "2026-01-01T12:00:00Z",
                    "PATIENT": patient_id,
                    "ENCOUNTER": encounter_id,
                    "CODE": "O001",
                    "DESCRIPTION": "Example laboratory test",
                    "VALUE": 5.4,
                    "UNITS": "mg/dL",
                }
            ]
        ),
        "procedures": pd.DataFrame(
            [
                {
                    "DATE": "2026-01-01T14:00:00Z",
                    "STOP": None,
                    "PATIENT": patient_id,
                    "ENCOUNTER": encounter_id,
                    "CODE": "P001",
                    "DESCRIPTION": "Example procedure",
                }
            ]
        ),
    }


def test_create_timeline_event() -> None:
    record = {
        "_source_row": 4,
        "DATE": "2026-01-01T12:00:00+00:00",
        "PATIENT": "patient-001",
        "ENCOUNTER": "encounter-001",
        "CODE": "O001",
        "DESCRIPTION": "Example laboratory test",
    }

    event = create_timeline_event(
        "observations",
        record,
    )

    assert event is not None
    assert event["event_type"] == "observation"
    assert event["code"] == "O001"
    assert event["source_table"] == "observations"
    assert event["source_row"] == 4


def test_build_patient_package(tmp_path: Path) -> None:
    tables = create_test_tables()

    result = build_patient_package(
        patient_id="patient-001",
        tables=tables,
        output_root=tmp_path,
    )

    patient_dir = tmp_path / "patient-001"

    assert result.output_dir == patient_dir
    assert result.timeline_event_count == 5

    expected_files = {
        "patient.json",
        "encounters.json",
        "conditions.json",
        "medications.json",
        "observations.json",
        "procedures.json",
        "timeline.json",
        "summary.json",
        "manifest.json",
    }

    assert expected_files == {path.name for path in patient_dir.iterdir()}

    timeline = json.loads((patient_dir / "timeline.json").read_text(encoding="utf-8"))

    assert len(timeline) == 5

    timestamps = [event["timestamp"] for event in timeline]

    assert timestamps == sorted(timestamps)

    summary = json.loads((patient_dir / "summary.json").read_text(encoding="utf-8"))

    assert summary["patient_id"] == "patient-001"
    assert summary["record_counts"]["encounters"] == 1
    assert summary["record_counts"]["observations"] == 1

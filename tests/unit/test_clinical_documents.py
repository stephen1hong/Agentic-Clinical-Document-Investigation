"""Tests for deterministic clinical document generation."""

import json
from pathlib import Path

from clinical_investigation.reporting.clinical_documents import (
    explicit_abnormal_status,
    generate_encounter_documents,
    medication_status,
)


def write_json(
    path: Path,
    payload: object,
) -> None:
    """Write test JSON."""

    path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def create_case_fixture(
    root: Path,
) -> Path:
    """Create a minimal encounter case fixture."""

    case_dir = root / "patient-001__encounter-001"
    case_dir.mkdir(parents=True)

    write_json(
        case_dir / "case.json",
        {
            "case_id": "patient-001__encounter-001",
            "patient_id": "patient-001",
            "encounter_id": "encounter-001",
            "encounter_class": "inpatient",
        },
    )

    write_json(
        case_dir / "patient_context.json",
        {
            "patient_id": "patient-001",
            "patient": {
                "id": "patient-001",
                "first": "Test",
                "last": "Patient",
                "birthdate": "1980-01-01",
            },
            "longitudinal_summary": {},
        },
    )

    write_json(
        case_dir / "encounter.json",
        {
            "id": "encounter-001",
            "start": "2026-01-01T10:00:00+00:00",
            "stop": "2026-01-03T10:00:00+00:00",
            "encounterclass": "inpatient",
            "description": "Example inpatient encounter",
            "_source_row": 10,
        },
    )

    write_json(
        case_dir / "active_conditions.json",
        [
            {
                "_source_row": 20,
                "description": "Example condition",
                "start": "2026-01-01T10:00:00+00:00",
            }
        ],
    )

    write_json(
        case_dir / "medications.json",
        [
            {
                "_source_row": 30,
                "description": "Example medication",
                "start": "2026-01-01T12:00:00+00:00",
                "stop": "2026-01-03T08:00:00+00:00",
            }
        ],
    )

    write_json(
        case_dir / "observations.json",
        [
            {
                "_source_row": 40,
                "date": "2026-01-02T08:00:00+00:00",
                "description": "Potassium",
                "value": 5.8,
                "units": "mmol/L",
                "interpretation": "High",
            }
        ],
    )

    write_json(
        case_dir / "procedures.json",
        [
            {
                "_source_row": 50,
                "date": "2026-01-02T12:00:00+00:00",
                "description": "Example procedure",
            }
        ],
    )

    write_json(
        case_dir / "discharge_candidates.json",
        [
            {
                "candidate_type": "abnormal_observation",
                "timestamp": "2026-01-02T08:00:00+00:00",
                "display": "Potassium",
                "source_table": "observations",
                "source_row": 40,
            },
            {
                "candidate_type": "encounter_discharge",
                "timestamp": "2026-01-03T10:00:00+00:00",
                "display": "Encounter discharge",
                "source_table": "encounters",
                "source_row": 10,
            },
        ],
    )

    write_json(
        case_dir / "timeline.json",
        [],
    )

    write_json(
        case_dir / "summary.json",
        {
            "case_id": "patient-001__encounter-001",
        },
    )

    return case_dir


def test_explicit_abnormal_status() -> None:
    observation = {
        "interpretation": "High",
    }

    assert explicit_abnormal_status(observation) == "Explicitly flagged abnormal: High"


def test_medication_status() -> None:
    encounter = {
        "start": "2026-01-01T10:00:00+00:00",
        "stop": "2026-01-03T10:00:00+00:00",
    }

    medication = {
        "start": "2026-01-01T12:00:00+00:00",
        "stop": "2026-01-03T08:00:00+00:00",
    }

    assert (
        medication_status(
            medication,
            encounter,
        )
        == "Stopped during encounter"
    )


def test_generate_encounter_documents(
    tmp_path: Path,
) -> None:
    case_dir = create_case_fixture(tmp_path / "cases")

    output_root = tmp_path / "documents"

    result = generate_encounter_documents(
        case_dir=case_dir,
        output_root=output_root,
    )

    assert len(result.documents) == 6

    expected_files = {
        "admission_note.md",
        "progress_note.md",
        "lab_report.md",
        "medication_reconciliation.md",
        "discharge_summary.md",
        "follow_up_note.md",
        "document_index.json",
        "manifest.json",
    }

    assert expected_files == {path.name for path in result.output_dir.iterdir()}

    lab_report = (result.output_dir / "lab_report.md").read_text(encoding="utf-8")

    assert "Explicitly flagged abnormal: High" in lab_report
    assert "clinically abnormal" not in lab_report.lower()

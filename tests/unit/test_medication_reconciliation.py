"""Tests for medication reconciliation."""

import json
from pathlib import Path

from clinical_investigation.investigation.medication_models import (
    MedicationDiscrepancyType,
    MedicationStatus,
)
from clinical_investigation.investigation.medication_reconciliation import (
    build_medication_reconciliation,
    infer_medication_status,
    normalize_medication_name,
    reconcile_case_medications,
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


def create_medication_fixture(
    root: Path,
) -> Path:
    """Create a minimal medication reconciliation fixture."""

    case_dir = root / "patient-001__encounter-001"
    case_dir.mkdir(parents=True)

    evidence = [
        {
            "evidence_id": "e-admission-med",
            "case_id": case_dir.name,
            "document_type": "admission_note",
            "source_file": "admission_note.md",
            "source_line": 20,
            "section": ("Medications Present During Encounter"),
            "text_span": ("- Lisinopril 10 mg active [Source: medications:30]"),
            "normalized_fact": ("Lisinopril 10 mg active"),
            "source_table": "medications",
            "source_row": 30,
            "event_time": None,
            "extraction_confidence": 1.0,
            "extraction_method": ("deterministic_provenance"),
        },
        {
            "evidence_id": "e-stop-med",
            "case_id": case_dir.name,
            "document_type": ("medication_reconciliation"),
            "source_file": ("medication_reconciliation.md"),
            "source_line": 22,
            "section": "Medication Records",
            "text_span": ("Lisinopril 10 mg; stopped"),
            "normalized_fact": ("Lisinopril 10 mg; stopped"),
            "source_table": "medications",
            "source_row": 30,
            "event_time": ("2026-01-03T08:00:00Z"),
            "extraction_confidence": 1.0,
            "extraction_method": ("deterministic_table"),
        },
        {
            "evidence_id": "e-discharge-med",
            "case_id": case_dir.name,
            "document_type": "discharge_summary",
            "source_file": "discharge_summary.md",
            "source_line": 25,
            "section": ("Medication Status at Encounter End"),
            "text_span": ("- Lisinopril 20 mg active"),
            "normalized_fact": ("Lisinopril 20 mg active"),
            "source_table": "medications",
            "source_row": 30,
            "event_time": ("2026-01-03T10:00:00Z"),
            "extraction_confidence": 1.0,
            "extraction_method": ("deterministic_provenance"),
        },
    ]

    claims = [
        {
            "claim_id": "c-admission-med",
            "case_id": case_dir.name,
            "claim_type": "medication_status",
            "subject": "Lisinopril 10 mg",
            "predicate": ("documented_medication_fact"),
            "value": "active",
            "time_start": ("2026-01-01T10:00:00Z"),
            "time_end": None,
            "source_evidence_ids": ["e-admission-med"],
            "extraction_confidence": 1.0,
            "extraction_method": ("deterministic_provenance"),
        },
        {
            "claim_id": "c-stop-med",
            "case_id": case_dir.name,
            "claim_type": "medication_status",
            "subject": "Lisinopril 10 mg",
            "predicate": ("documented_medication_fact"),
            "value": "stopped",
            "time_start": ("2026-01-03T08:00:00Z"),
            "time_end": None,
            "source_evidence_ids": ["e-stop-med"],
            "extraction_confidence": 1.0,
            "extraction_method": ("deterministic_table"),
        },
        {
            "claim_id": "c-discharge-med",
            "case_id": case_dir.name,
            "claim_type": "medication_status",
            "subject": "Lisinopril 20 mg",
            "predicate": ("documented_medication_fact"),
            "value": "active at discharge",
            "time_start": ("2026-01-03T10:00:00Z"),
            "time_end": None,
            "source_evidence_ids": ["e-discharge-med"],
            "extraction_confidence": 1.0,
            "extraction_method": ("deterministic_provenance"),
        },
    ]

    timeline = [
        {
            "event_id": "t-start",
            "case_id": case_dir.name,
            "event_type": "medication_start",
            "subject": "Lisinopril 10 mg",
            "description": "Medication start",
            "normalized_time": ("2026-01-01T10:00:00Z"),
            "time_end": None,
            "time_precision": "datetime",
            "time_source": "claim_field",
            "source_claim_ids": ["c-admission-med"],
            "evidence_ids": ["e-admission-med"],
            "source_document_types": ["admission_note"],
            "source_tables": ["medications"],
            "source_rows": [30],
            "confidence": 1.0,
        },
        {
            "event_id": "t-stop",
            "case_id": case_dir.name,
            "event_type": "medication_stop",
            "subject": "Lisinopril 10 mg",
            "description": "Medication stop",
            "normalized_time": ("2026-01-03T08:00:00Z"),
            "time_end": None,
            "time_precision": "datetime",
            "time_source": "claim_field",
            "source_claim_ids": ["c-stop-med"],
            "evidence_ids": ["e-stop-med"],
            "source_document_types": ["medication_reconciliation"],
            "source_tables": ["medications"],
            "source_rows": [30],
            "confidence": 1.0,
        },
    ]

    write_json(
        case_dir / "evidence_items.json",
        evidence,
    )
    write_json(
        case_dir / "clinical_claims.json",
        claims,
    )
    write_json(
        case_dir / "canonical_timeline.json",
        timeline,
    )

    return case_dir


def create_status_sequence_fixture(
    root: Path,
    *,
    first_status: str,
    second_status: str,
) -> Path:
    """Create two explicit medication-status mentions at different times."""

    case_dir = root / (f"patient-status__{first_status}-{second_status}")
    case_dir.mkdir(parents=True)

    evidence = [
        {
            "evidence_id": "e-first-status",
            "case_id": case_dir.name,
            "document_type": "progress_note",
            "source_file": "progress_note.md",
            "source_line": 10,
            "section": "Medication Status",
            "text_span": (f"Lisinopril 10 mg; {first_status}"),
            "normalized_fact": (f"Lisinopril 10 mg; {first_status}"),
            "source_table": "medications",
            "source_row": 100,
            "event_time": "2026-01-01T08:00:00Z",
            "extraction_confidence": 1.0,
            "extraction_method": "deterministic_table",
        },
        {
            "evidence_id": "e-second-status",
            "case_id": case_dir.name,
            "document_type": "discharge_summary",
            "source_file": "discharge_summary.md",
            "source_line": 20,
            "section": "Medication Status at Encounter End",
            "text_span": (f"Lisinopril 10 mg; {second_status}"),
            "normalized_fact": (f"Lisinopril 10 mg; {second_status}"),
            "source_table": "medications",
            "source_row": 101,
            "event_time": "2026-01-03T10:00:00Z",
            "extraction_confidence": 1.0,
            "extraction_method": "deterministic_table",
        },
    ]

    claims = [
        {
            "claim_id": "c-first-status",
            "case_id": case_dir.name,
            "claim_type": "medication_status",
            "subject": "Lisinopril 10 mg",
            "predicate": "documented_medication_fact",
            "value": first_status,
            "time_start": "2026-01-01T08:00:00Z",
            "time_end": None,
            "source_evidence_ids": ["e-first-status"],
            "extraction_confidence": 1.0,
            "extraction_method": "deterministic_table",
        },
        {
            "claim_id": "c-second-status",
            "case_id": case_dir.name,
            "claim_type": "medication_status",
            "subject": "Lisinopril 10 mg",
            "predicate": "documented_medication_fact",
            "value": second_status,
            "time_start": "2026-01-03T10:00:00Z",
            "time_end": None,
            "source_evidence_ids": ["e-second-status"],
            "extraction_confidence": 1.0,
            "extraction_method": "deterministic_table",
        },
    ]

    write_json(
        case_dir / "evidence_items.json",
        evidence,
    )
    write_json(
        case_dir / "clinical_claims.json",
        claims,
    )
    write_json(
        case_dir / "canonical_timeline.json",
        [],
    )

    return case_dir


def test_temporal_start_stop_text_is_not_status() -> None:
    """Start/stop timestamps alone must not imply lifecycle status."""

    status = infer_medication_status("Lisinopril 10 mg; start=2026-01-01; stop=2026-01-03")

    assert status == MedicationStatus.UNKNOWN


def test_started_then_stopped_is_not_conflicting_status(
    tmp_path: Path,
) -> None:
    """A normal start-to-stop lifecycle is not a status contradiction."""

    case_dir = create_status_sequence_fixture(
        tmp_path,
        first_status="started",
        second_status="stopped",
    )

    _, _, discrepancies = reconcile_case_medications(case_dir)

    discrepancy_types = {discrepancy.discrepancy_type for discrepancy in discrepancies}

    assert MedicationDiscrepancyType.CONFLICTING_STATUS not in discrepancy_types


def test_normalize_medication_name() -> None:
    """Medication names should normalize conservatively."""

    name, key = normalize_medication_name("Lisinopril 10 mg oral tablet")

    assert name.lower() == "lisinopril"
    assert key == "lisinopril"


def test_detects_status_and_dose_conflicts(
    tmp_path: Path,
) -> None:
    """Conflicting status and dose should be detected."""

    case_dir = create_medication_fixture(tmp_path)

    (
        mentions,
        profiles,
        discrepancies,
    ) = reconcile_case_medications(case_dir)

    assert mentions
    assert len(profiles) == 1

    assert {discrepancy.discrepancy_type for discrepancy in discrepancies}.issuperset(
        {
            MedicationDiscrepancyType.CONFLICTING_STATUS,
            MedicationDiscrepancyType.DOSE_CONFLICT,
        }
    )

    profile = profiles[0]

    assert profile.inferred_status_at_discharge == MedicationStatus.ACTIVE


def test_writes_medication_outputs(
    tmp_path: Path,
) -> None:
    """Medication build should write all output files."""

    case_dir = create_medication_fixture(tmp_path)

    build_medication_reconciliation(case_dir)

    expected = {
        "medication_mentions.json",
        "medication_profiles.json",
        "medication_discrepancies.json",
        "medication_reconciliation_manifest.json",
    }

    assert expected.issubset({path.name for path in case_dir.iterdir()})


def test_active_and_discontinued_detects_conflicting_status(
    tmp_path: Path,
) -> None:
    """Explicit incompatible statuses should remain detectable."""

    case_dir = create_status_sequence_fixture(
        tmp_path,
        first_status="active",
        second_status="discontinued",
    )

    _, _, discrepancies = reconcile_case_medications(case_dir)

    discrepancy_types = {discrepancy.discrepancy_type for discrepancy in discrepancies}

    assert MedicationDiscrepancyType.CONFLICTING_STATUS in discrepancy_types


def test_stopped_then_later_continued_is_detected(
    tmp_path: Path,
) -> None:
    """A later continuation after an explicit stop is a discrepancy."""

    case_dir = create_status_sequence_fixture(
        tmp_path,
        first_status="stopped",
        second_status="continued",
    )

    _, _, discrepancies = reconcile_case_medications(case_dir)

    discrepancy_types = {discrepancy.discrepancy_type for discrepancy in discrepancies}

    assert MedicationDiscrepancyType.STOPPED_BUT_LATER_CONTINUED in discrepancy_types

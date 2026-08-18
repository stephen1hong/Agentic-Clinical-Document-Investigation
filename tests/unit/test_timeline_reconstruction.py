"""Tests for canonical timeline reconstruction."""

import json
from pathlib import Path

from clinical_investigation.investigation.timeline_models import (
    TimelineConflictType,
    TimelineEventType,
)
from clinical_investigation.investigation.timeline_reconstruction import (
    build_canonical_timeline,
    extract_time_from_text,
    reconstruct_case_timeline,
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


def create_timeline_fixture(
    root: Path,
) -> Path:
    """Create minimal Milestone 1 outputs."""

    case_dir = root / "patient-001__encounter-001"
    case_dir.mkdir(parents=True)

    evidence = [
        {
            "evidence_id": "e-start",
            "case_id": case_dir.name,
            "document_type": "admission_note",
            "source_file": "admission_note.md",
            "source_line": 7,
            "section": "Admission Note",
            "text_span": ("**Encounter Start:** January 01, 2026 at 10:00 UTC"),
            "normalized_fact": ("Encounter Start: January 01, 2026 at 10:00 UTC"),
            "source_table": None,
            "source_row": None,
            "event_time": None,
            "extraction_confidence": 0.95,
            "extraction_method": ("deterministic_markdown"),
        },
        {
            "evidence_id": "e-stop",
            "case_id": case_dir.name,
            "document_type": "discharge_summary",
            "source_file": "discharge_summary.md",
            "source_line": 8,
            "section": "Discharge Summary",
            "text_span": ("**Encounter Stop:** January 03, 2026 at 10:00 UTC"),
            "normalized_fact": ("Encounter Stop: January 03, 2026 at 10:00 UTC"),
            "source_table": None,
            "source_row": None,
            "event_time": None,
            "extraction_confidence": 0.95,
            "extraction_method": ("deterministic_markdown"),
        },
        {
            "evidence_id": "e-potassium",
            "case_id": case_dir.name,
            "document_type": "lab_report",
            "source_file": "lab_report.md",
            "source_line": 20,
            "section": "Results",
            "text_span": ("January 02, 2026 | Potassium | 5.8 mmol/L"),
            "normalized_fact": ("January 02, 2026 | Potassium | 5.8 mmol/L"),
            "source_table": "observations",
            "source_row": 40,
            "event_time": None,
            "extraction_confidence": 1.0,
            "extraction_method": ("deterministic_table"),
        },
    ]

    claims = [
        {
            "claim_id": "c-potassium",
            "case_id": case_dir.name,
            "claim_type": "observation_result",
            "subject": "Potassium",
            "predicate": "result",
            "value": ("January 02, 2026; 5.8 mmol/L; Explicitly flagged abnormal: High"),
            "time_start": None,
            "time_end": None,
            "source_evidence_ids": ["e-potassium"],
            "extraction_confidence": 1.0,
            "extraction_method": ("deterministic_table"),
        }
    ]

    write_json(
        case_dir / "evidence_items.json",
        evidence,
    )

    write_json(
        case_dir / "clinical_claims.json",
        claims,
    )

    return case_dir


def test_extracts_human_datetime() -> None:
    """Generated human-readable timestamps should parse."""

    result = extract_time_from_text("January 02, 2026 at 08:30 UTC")

    assert result.value is not None
    assert result.value.year == 2026
    assert result.value.hour == 8


def test_reconstructs_ordered_timeline(
    tmp_path: Path,
) -> None:
    """Timeline events should be chronological."""

    case_dir = create_timeline_fixture(tmp_path)

    events, conflicts, _ = reconstruct_case_timeline(case_dir)

    dated_times = [event.normalized_time for event in events if event.normalized_time is not None]

    assert dated_times == sorted(dated_times)

    event_types = {event.event_type for event in events}

    assert TimelineEventType.ENCOUNTER_START in event_types
    assert TimelineEventType.OBSERVATION_RESULT in event_types
    assert TimelineEventType.ENCOUNTER_STOP in event_types

    assert not any(
        conflict.conflict_type == TimelineConflictType.ENCOUNTER_STOP_BEFORE_START
        for conflict in conflicts
    )


def test_writes_timeline_files(
    tmp_path: Path,
) -> None:
    """Timeline build should write all outputs."""

    case_dir = create_timeline_fixture(tmp_path)

    build_canonical_timeline(case_dir)

    assert {
        "canonical_timeline.json",
        "timeline_conflicts.json",
        "timeline_manifest.json",
    }.issubset({path.name for path in case_dir.iterdir()})

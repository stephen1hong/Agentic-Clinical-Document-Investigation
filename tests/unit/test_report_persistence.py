from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.agents.report_persistence import (
    FINAL_REPORT_FILENAME,
    persist_final_report,
)


def build_test_report() -> dict:
    """Create a minimal persisted report payload."""

    return {
        "case_id": "case-001",
        "investigation_question": "What happened?",
        "executive_summary": (
            "Investigation identified 1 finding. 0 finding(s) require human review."
        ),
        "high_priority_findings": [],
        "other_findings": [
            {
                "finding_id": "finding-001",
                "finding_type": "other",
                "subtype": "test_subtype",
                "severity": "low",
                "title": "Test finding",
                "summary": "Test finding summary",
                "evidence_ids": ["evidence-001"],
                "claim_ids": ["claim-001"],
                "event_ids": ["event-001"],
                "confidence": 0.9,
                "requires_human_review": False,
            }
        ],
        "validation_errors": [],
        "review_status": "not_required",
        "review_reasons": [],
        "finding_count": 1,
        "review_finding_count": 0,
    }


def test_persist_final_report_writes_expected_file(
    tmp_path: Path,
) -> None:
    """Persisted report should use the canonical filename."""

    case_dir = tmp_path / "case-001"

    report = build_test_report()

    output_path = persist_final_report(
        case_dir=case_dir,
        report=report,
    )

    assert output_path == (case_dir / FINAL_REPORT_FILENAME)

    assert output_path.exists()


def test_persist_final_report_creates_parent_directory(
    tmp_path: Path,
) -> None:
    """Persistence should create a missing case directory."""

    case_dir = tmp_path / "nested" / "case-001"

    assert not case_dir.exists()

    persist_final_report(
        case_dir=case_dir,
        report=build_test_report(),
    )

    assert case_dir.exists()

    assert (case_dir / FINAL_REPORT_FILENAME).exists()


def test_persisted_report_can_be_read_back(
    tmp_path: Path,
) -> None:
    """Persisted JSON should round-trip without data loss."""

    case_dir = tmp_path / "case-001"

    report = build_test_report()

    output_path = persist_final_report(
        case_dir=case_dir,
        report=report,
    )

    persisted = json.loads(
        output_path.read_text(
            encoding="utf-8",
        )
    )

    assert persisted == report


def test_persist_final_report_overwrites_existing_report(
    tmp_path: Path,
) -> None:
    """Repeated persistence should replace stale report content."""

    case_dir = tmp_path / "case-001"

    first_report = build_test_report()

    persist_final_report(
        case_dir=case_dir,
        report=first_report,
    )

    updated_report = build_test_report()

    updated_report["review_status"] = "pending"
    updated_report["review_reasons"] = ["Human review required."]

    output_path = persist_final_report(
        case_dir=case_dir,
        report=updated_report,
    )

    persisted = json.loads(
        output_path.read_text(
            encoding="utf-8",
        )
    )

    assert persisted == updated_report


def test_persisted_json_ends_with_newline(
    tmp_path: Path,
) -> None:
    """Persisted report should follow project JSON formatting."""

    case_dir = tmp_path / "case-001"

    output_path = persist_final_report(
        case_dir=case_dir,
        report=build_test_report(),
    )

    raw_text = output_path.read_text(
        encoding="utf-8",
    )

    assert raw_text.endswith("\n")

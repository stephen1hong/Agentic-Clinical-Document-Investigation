from __future__ import annotations

import json
from pathlib import Path

import pytest

from clinical_investigation.review.models import (
    CaseReviewStatus,
    FindingReviewDecision,
)
from clinical_investigation.review.review_persistence import (
    load_human_review,
)
from clinical_investigation.review.service import (
    complete_case_review,
    record_finding_decision,
    start_case_review,
)


def write_final_report(
    case_dir: Path,
    *,
    review_status: str = "pending",
    required_finding_ids: list[str] | None = None,
) -> None:
    """Write a minimal final investigation report."""

    required_ids = required_finding_ids or []

    high_priority_findings = [
        {
            "finding_id": finding_id,
            "finding_type": "unsupported_claim",
            "subtype": "insufficient_evidence_support",
            "severity": "medium",
            "title": "Review-required finding",
            "summary": "Evidence support is insufficient.",
            "evidence_ids": [f"evidence-{finding_id}"],
            "claim_ids": [],
            "event_ids": [],
            "confidence": 0.9,
            "requires_human_review": True,
        }
        for finding_id in required_ids
    ]

    report = {
        "case_id": case_dir.name,
        "investigation_question": "What happened?",
        "executive_summary": "Test report.",
        "high_priority_findings": high_priority_findings,
        "other_findings": [],
        "validation_errors": [],
        "review_status": review_status,
        "review_reasons": [],
        "finding_count": len(high_priority_findings),
        "review_finding_count": len(high_priority_findings),
    }

    case_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    (case_dir / "final_investigation_report.json").write_text(
        json.dumps(
            report,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_start_pending_case_review(
    tmp_path: Path,
) -> None:
    """Pending machine case should enter human review."""

    case_dir = tmp_path / "case-001"

    write_final_report(
        case_dir,
        review_status="pending",
        required_finding_ids=["finding-001"],
    )

    review = start_case_review(
        case_dir=case_dir,
        reviewer="reviewer-a",
    )

    assert review.case_id == "case-001"
    assert review.status == CaseReviewStatus.IN_PROGRESS
    assert review.reviewer == "reviewer-a"
    assert review.started_at is not None

    persisted = load_human_review(case_dir)

    assert persisted is not None
    assert persisted.status == CaseReviewStatus.IN_PROGRESS


def test_start_not_required_case_review(
    tmp_path: Path,
) -> None:
    """No-review machine case should remain not required."""

    case_dir = tmp_path / "case-001"

    write_final_report(
        case_dir,
        review_status="not_required",
    )

    review = start_case_review(
        case_dir=case_dir,
        reviewer="reviewer-a",
    )

    assert review.status == CaseReviewStatus.NOT_REQUIRED


def test_record_valid_finding_decision(
    tmp_path: Path,
) -> None:
    """Valid finding decision should persist."""

    case_dir = tmp_path / "case-001"

    write_final_report(
        case_dir,
        required_finding_ids=["finding-001"],
    )

    review = record_finding_decision(
        case_dir=case_dir,
        finding_id="finding-001",
        decision=FindingReviewDecision.ACCEPTED,
        rationale="Supported after review.",
        reviewer="reviewer-a",
    )

    assert len(review.finding_reviews) == 1

    finding_review = review.finding_reviews[0]

    assert finding_review.finding_id == "finding-001"
    assert finding_review.decision == FindingReviewDecision.ACCEPTED
    assert finding_review.rationale == ("Supported after review.")


def test_unknown_finding_id_is_rejected(
    tmp_path: Path,
) -> None:
    """Unknown finding IDs must not be recorded."""

    case_dir = tmp_path / "case-001"

    write_final_report(
        case_dir,
        required_finding_ids=["finding-001"],
    )

    with pytest.raises(
        ValueError,
        match="Unknown finding_id",
    ):
        record_finding_decision(
            case_dir=case_dir,
            finding_id="missing-finding",
            decision=FindingReviewDecision.DISMISSED,
            rationale="Not applicable.",
            reviewer="reviewer-a",
        )


def test_updating_decision_does_not_duplicate_record(
    tmp_path: Path,
) -> None:
    """A second decision for one finding should replace the first."""

    case_dir = tmp_path / "case-001"

    write_final_report(
        case_dir,
        required_finding_ids=["finding-001"],
    )

    record_finding_decision(
        case_dir=case_dir,
        finding_id="finding-001",
        decision=FindingReviewDecision.ACCEPTED,
        rationale="Initial decision.",
        reviewer="reviewer-a",
    )

    review = record_finding_decision(
        case_dir=case_dir,
        finding_id="finding-001",
        decision=FindingReviewDecision.NEEDS_FOLLOW_UP,
        rationale="Additional review needed.",
        reviewer="reviewer-a",
    )

    assert len(review.finding_reviews) == 1

    assert review.finding_reviews[0].decision == FindingReviewDecision.NEEDS_FOLLOW_UP


def test_cannot_complete_with_missing_decisions(
    tmp_path: Path,
) -> None:
    """Every required finding needs a human decision."""

    case_dir = tmp_path / "case-001"

    write_final_report(
        case_dir,
        required_finding_ids=[
            "finding-001",
            "finding-002",
        ],
    )

    record_finding_decision(
        case_dir=case_dir,
        finding_id="finding-001",
        decision=FindingReviewDecision.ACCEPTED,
        rationale="Reviewed.",
        reviewer="reviewer-a",
    )

    with pytest.raises(
        ValueError,
        match="missing decisions",
    ):
        complete_case_review(
            case_dir=case_dir,
            reviewer="reviewer-a",
        )


def test_complete_case_review(
    tmp_path: Path,
) -> None:
    """Case review should complete after all required decisions."""

    case_dir = tmp_path / "case-001"

    write_final_report(
        case_dir,
        required_finding_ids=[
            "finding-001",
            "finding-002",
        ],
    )

    for finding_id in [
        "finding-001",
        "finding-002",
    ]:
        record_finding_decision(
            case_dir=case_dir,
            finding_id=finding_id,
            decision=FindingReviewDecision.ACCEPTED,
            rationale="Reviewed.",
            reviewer="reviewer-a",
        )

    review = complete_case_review(
        case_dir=case_dir,
        reviewer="reviewer-a",
        case_notes="Review complete.",
    )

    assert review.status == CaseReviewStatus.COMPLETED
    assert review.completed_at is not None
    assert review.case_notes == "Review complete."

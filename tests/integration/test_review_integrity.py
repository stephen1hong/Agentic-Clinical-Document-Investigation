from __future__ import annotations

import json
from pathlib import Path

import pytest

from clinical_investigation.investigation.evidence_extraction import (
    sha256_file,
)
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
)

IMMUTABLE_MACHINE_FILES = [
    "final_investigation_report.json",
    "reviewer_bundle.json",
    "reviewer_report.md",
    "evidence_items.json",
    "clinical_claims.json",
    "canonical_timeline.json",
]


def write_minimal_case(
    case_dir: Path,
) -> None:
    """Create a minimal reviewable case."""

    case_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_report = {
        "case_id": case_dir.name,
        "investigation_question": "What happened?",
        "executive_summary": "One finding requires review.",
        "high_priority_findings": [
            {
                "finding_id": "finding-001",
                "finding_type": "unsupported_claim",
                "subtype": "insufficient_evidence_support",
                "severity": "medium",
                "title": "Unsupported claim",
                "summary": "Evidence support is insufficient.",
                "evidence_ids": ["evidence-001"],
                "claim_ids": [],
                "event_ids": [],
                "confidence": 0.9,
                "requires_human_review": True,
            }
        ],
        "other_findings": [],
        "validation_errors": [],
        "review_status": "pending",
        "review_reasons": ["Finding requires human review."],
        "finding_count": 1,
        "review_finding_count": 1,
    }

    (case_dir / "final_investigation_report.json").write_text(
        json.dumps(
            final_report,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (case_dir / "reviewer_bundle.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    (case_dir / "reviewer_report.md").write_text(
        "# Review\n",
        encoding="utf-8",
    )

    (case_dir / "evidence_items.json").write_text(
        "[]\n",
        encoding="utf-8",
    )

    (case_dir / "clinical_claims.json").write_text(
        "[]\n",
        encoding="utf-8",
    )

    (case_dir / "canonical_timeline.json").write_text(
        "[]\n",
        encoding="utf-8",
    )


def test_human_review_does_not_modify_machine_artifacts(
    tmp_path: Path,
) -> None:
    """Human review should only mutate human_review.json."""

    case_dir = tmp_path / "case-001"

    write_minimal_case(case_dir)

    before_hashes = {
        filename: sha256_file(case_dir / filename) for filename in IMMUTABLE_MACHINE_FILES
    }

    record_finding_decision(
        case_dir=case_dir,
        finding_id="finding-001",
        decision=FindingReviewDecision.ACCEPTED,
        rationale="Reviewed and accepted.",
        reviewer="reviewer-a",
    )

    after_hashes = {
        filename: sha256_file(case_dir / filename) for filename in IMMUTABLE_MACHINE_FILES
    }

    assert before_hashes == after_hashes

    assert (case_dir / "human_review.json").exists()


def test_completed_review_is_internally_consistent(
    tmp_path: Path,
) -> None:
    """Completed review should contain one decision per required finding."""

    case_dir = tmp_path / "case-002"

    write_minimal_case(case_dir)

    # Add a second review-required finding.
    report_path = case_dir / "final_investigation_report.json"

    report = json.loads(
        report_path.read_text(
            encoding="utf-8",
        )
    )

    second_finding = {
        "finding_id": "finding-002",
        "finding_type": "medication_discrepancy",
        "subtype": "dose_conflict",
        "severity": "high",
        "title": "Medication dose conflict",
        "summary": "Two source documents contain conflicting doses.",
        "evidence_ids": [
            "evidence-002",
            "evidence-003",
        ],
        "claim_ids": [],
        "event_ids": [],
        "confidence": 0.95,
        "requires_human_review": True,
    }

    report["high_priority_findings"].append(second_finding)

    report["finding_count"] = 2
    report["review_finding_count"] = 2

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    record_finding_decision(
        case_dir=case_dir,
        finding_id="finding-001",
        decision=FindingReviewDecision.ACCEPTED,
        rationale="Evidence supports this finding.",
        reviewer="reviewer-a",
    )

    record_finding_decision(
        case_dir=case_dir,
        finding_id="finding-002",
        decision=FindingReviewDecision.NEEDS_FOLLOW_UP,
        rationale="Dose conflict requires clinical follow-up.",
        reviewer="reviewer-a",
    )

    completed = complete_case_review(
        case_dir=case_dir,
        reviewer="reviewer-a",
        case_notes="Both required findings reviewed.",
    )

    assert completed.status == CaseReviewStatus.COMPLETED
    assert completed.completed_at is not None
    assert completed.started_at is not None
    assert completed.reviewer == "reviewer-a"

    required_ids = {
        finding["finding_id"]
        for finding in report["high_priority_findings"]
        if finding["requires_human_review"]
    }

    reviewed_ids = {review.finding_id for review in completed.finding_reviews}

    assert reviewed_ids == required_ids

    assert len(completed.finding_reviews) == len(required_ids)

    assert len(reviewed_ids) == len(completed.finding_reviews)

    for finding_review in completed.finding_reviews:
        assert finding_review.reviewed_at
        assert finding_review.reviewer == "reviewer-a"
        assert finding_review.finding_id in required_ids
        assert finding_review.decision in {
            FindingReviewDecision.ACCEPTED,
            FindingReviewDecision.DISMISSED,
            FindingReviewDecision.NEEDS_FOLLOW_UP,
        }

    persisted = load_human_review(case_dir)

    assert persisted is not None
    assert persisted == completed


def test_incomplete_review_cannot_be_completed(
    tmp_path: Path,
) -> None:
    """Case review must not complete with missing required decisions."""

    case_dir = tmp_path / "case-003"

    write_minimal_case(case_dir)

    report_path = case_dir / "final_investigation_report.json"

    report = json.loads(
        report_path.read_text(
            encoding="utf-8",
        )
    )

    report["high_priority_findings"].append(
        {
            "finding_id": "finding-002",
            "finding_type": "medication_discrepancy",
            "subtype": "dose_conflict",
            "severity": "high",
            "title": "Medication dose conflict",
            "summary": "Conflicting medication doses detected.",
            "evidence_ids": [
                "evidence-002",
            ],
            "claim_ids": [],
            "event_ids": [],
            "confidence": 0.95,
            "requires_human_review": True,
        }
    )

    report["finding_count"] = 2
    report["review_finding_count"] = 2

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    record_finding_decision(
        case_dir=case_dir,
        finding_id="finding-001",
        decision=FindingReviewDecision.ACCEPTED,
        rationale="First finding reviewed.",
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

    review = load_human_review(case_dir)

    assert review is not None
    assert review.status == CaseReviewStatus.IN_PROGRESS
    assert review.completed_at is None
    assert len(review.finding_reviews) == 1

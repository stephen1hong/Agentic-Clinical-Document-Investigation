from __future__ import annotations

import json
from pathlib import Path

import pytest

from clinical_investigation.investigation.evidence_extraction import (
    sha256_file,
)
from clinical_investigation.review.generation import (
    generate_reviewer_artifacts,
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

MACHINE_ARTIFACT_FILENAMES = [
    "final_investigation_report.json",
    "reviewer_bundle.json",
    "reviewer_report.md",
    "evidence_items.json",
    "clinical_claims.json",
    "canonical_timeline.json",
]


def write_json(
    path: Path,
    payload: object,
) -> None:
    """Write deterministic JSON for an acceptance-test fixture."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def create_acceptance_case(
    case_dir: Path,
) -> None:
    """Create one complete Step-7 acceptance-test case."""

    case_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_report = {
        "case_id": case_dir.name,
        "investigation_question": ("Are there findings requiring human review?"),
        "executive_summary": ("Two findings require review and one is contextual."),
        "high_priority_findings": [
            {
                "finding_id": "finding-001",
                "finding_type": "unsupported_claim",
                "subtype": "insufficient_evidence_support",
                "severity": "medium",
                "title": "Unsupported discharge claim",
                "summary": ("The discharge claim has insufficient evidence support."),
                "evidence_ids": [
                    "evidence-001",
                ],
                "claim_ids": [
                    "claim-001",
                ],
                "event_ids": [],
                "confidence": 0.90,
                "requires_human_review": True,
            },
            {
                "finding_id": "finding-002",
                "finding_type": "medication_discrepancy",
                "subtype": "dose_conflict",
                "severity": "high",
                "title": "Medication dose conflict",
                "summary": ("Two documents contain conflicting medication doses."),
                "evidence_ids": [
                    "evidence-002",
                    "evidence-003",
                ],
                "claim_ids": [],
                "event_ids": [],
                "confidence": 0.95,
                "requires_human_review": True,
            },
        ],
        "other_findings": [
            {
                "finding_id": "finding-003",
                "finding_type": "temporal_uncertainty",
                "subtype": "missing_event_time",
                "severity": "low",
                "title": "Missing event time",
                "summary": ("An event does not have a precise timestamp."),
                "evidence_ids": [
                    "evidence-004",
                ],
                "claim_ids": [],
                "event_ids": [
                    "event-001",
                ],
                "confidence": 0.80,
                "requires_human_review": False,
            }
        ],
        "validation_errors": [],
        "review_status": "pending",
        "review_reasons": [
            "Review-required findings are present.",
        ],
        "finding_count": 3,
        "review_finding_count": 2,
    }

    write_json(
        case_dir / "final_investigation_report.json",
        final_report,
    )

    write_json(
        case_dir / "evidence_items.json",
        [],
    )

    write_json(
        case_dir / "clinical_claims.json",
        [],
    )

    write_json(
        case_dir / "canonical_timeline.json",
        [],
    )


def test_step7_reviewer_artifacts_preserve_review_scope(
    tmp_path: Path,
) -> None:
    """Reviewer artifacts should preserve machine review semantics."""

    case_dir = tmp_path / "acceptance-case"

    create_acceptance_case(case_dir)

    final_report_path = case_dir / "final_investigation_report.json"

    machine_hash_before = sha256_file(final_report_path)

    bundle_path, report_path = generate_reviewer_artifacts(case_dir)

    machine_hash_after = sha256_file(final_report_path)

    assert machine_hash_before == machine_hash_after

    assert bundle_path.exists()
    assert report_path.exists()

    bundle = json.loads(
        bundle_path.read_text(
            encoding="utf-8",
        )
    )

    required_ids = {finding["finding_id"] for finding in bundle["findings_requiring_review"]}

    contextual_ids = {finding["finding_id"] for finding in bundle["contextual_findings"]}

    assert required_ids == {
        "finding-001",
        "finding-002",
    }

    assert contextual_ids == {
        "finding-003",
    }

    assert bundle["finding_count"] == 3
    assert bundle["review_finding_count"] == 2

    markdown = report_path.read_text(
        encoding="utf-8",
    )

    assert "Unsupported discharge claim" in markdown

    assert "Medication dose conflict" in markdown

    assert "Missing event time" in markdown


def test_step7_incomplete_review_cannot_complete(
    tmp_path: Path,
) -> None:
    """Completion must be blocked while required decisions are missing."""

    case_dir = tmp_path / "acceptance-case"

    create_acceptance_case(case_dir)

    generate_reviewer_artifacts(case_dir)

    record_finding_decision(
        case_dir=case_dir,
        finding_id="finding-001",
        decision=FindingReviewDecision.ACCEPTED,
        rationale="Finding accepted after evidence review.",
        reviewer="acceptance-reviewer",
    )

    with pytest.raises(
        ValueError,
        match="missing decisions",
    ):
        complete_case_review(
            case_dir=case_dir,
            reviewer="acceptance-reviewer",
        )

    review = load_human_review(case_dir)

    assert review is not None

    assert review.status == CaseReviewStatus.IN_PROGRESS

    assert review.completed_at is None

    assert len(review.finding_reviews) == 1


def test_step7_complete_review_preserves_machine_artifacts(
    tmp_path: Path,
) -> None:
    """Full Step-7 review should persist human decisions only."""

    case_dir = tmp_path / "acceptance-case"

    create_acceptance_case(case_dir)

    generate_reviewer_artifacts(case_dir)

    before_hashes = {
        filename: sha256_file(case_dir / filename) for filename in MACHINE_ARTIFACT_FILENAMES
    }

    record_finding_decision(
        case_dir=case_dir,
        finding_id="finding-001",
        decision=FindingReviewDecision.ACCEPTED,
        rationale="Evidence reviewed and accepted.",
        reviewer="acceptance-reviewer",
    )

    record_finding_decision(
        case_dir=case_dir,
        finding_id="finding-002",
        decision=FindingReviewDecision.NEEDS_FOLLOW_UP,
        rationale=("Medication discrepancy requires additional clinical follow-up."),
        reviewer="acceptance-reviewer",
    )

    completed = complete_case_review(
        case_dir=case_dir,
        reviewer="acceptance-reviewer",
        case_notes="Acceptance review completed.",
    )

    after_hashes = {
        filename: sha256_file(case_dir / filename) for filename in MACHINE_ARTIFACT_FILENAMES
    }

    assert before_hashes == after_hashes

    assert completed.status == CaseReviewStatus.COMPLETED

    assert completed.started_at is not None
    assert completed.completed_at is not None

    assert completed.reviewer == "acceptance-reviewer"

    assert len(completed.finding_reviews) == 2

    reviewed_ids = {item.finding_id for item in completed.finding_reviews}

    assert reviewed_ids == {
        "finding-001",
        "finding-002",
    }

    assert "finding-003" not in reviewed_ids

    persisted = load_human_review(case_dir)

    assert persisted is not None
    assert persisted == completed

    human_review_path = case_dir / "human_review.json"

    assert human_review_path.exists()

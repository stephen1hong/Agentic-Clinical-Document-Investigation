from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clinical_investigation.review.models import (
    CaseReviewRecord,
    CaseReviewStatus,
    FindingReviewDecision,
    FindingReviewRecord,
)
from clinical_investigation.review.review_persistence import (
    load_human_review,
    persist_human_review,
)

FINAL_REPORT_FILENAME = "final_investigation_report.json"


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp."""

    return datetime.now(UTC).isoformat()


def load_final_report(
    case_dir: Path,
) -> dict[str, Any]:
    """Load the machine-generated final investigation report."""

    path = case_dir / FINAL_REPORT_FILENAME

    if not path.exists():
        raise FileNotFoundError(f"Final report not found: {path}")

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(payload, dict):
        raise ValueError("Final report must contain a JSON object.")

    return payload


def get_report_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all findings from the final report."""

    return list(
        report.get(
            "high_priority_findings",
            [],
        )
    ) + list(
        report.get(
            "other_findings",
            [],
        )
    )


def start_case_review(
    *,
    case_dir: Path,
    reviewer: str,
) -> CaseReviewRecord:
    """Start or resume human review for one case."""

    existing = load_human_review(case_dir)

    if existing is not None:
        return existing

    report = load_final_report(case_dir)

    machine_status = str(
        report.get(
            "review_status",
            "not_required",
        )
    )

    if machine_status == "not_required":
        status = CaseReviewStatus.NOT_REQUIRED
    else:
        status = CaseReviewStatus.IN_PROGRESS

    record = CaseReviewRecord(
        case_id=str(report["case_id"]),
        status=status,
        reviewer=reviewer,
        started_at=utc_now_iso(),
    )

    persist_human_review(
        case_dir=case_dir,
        review=record,
    )

    return record


def record_finding_decision(
    *,
    case_dir: Path,
    finding_id: str,
    decision: FindingReviewDecision,
    rationale: str,
    reviewer: str,
) -> CaseReviewRecord:
    """Record or update a human decision for one finding."""

    report = load_final_report(case_dir)

    findings = get_report_findings(report)

    matching = [
        finding
        for finding in findings
        if str(
            finding.get(
                "finding_id",
                "",
            )
        )
        == finding_id
    ]

    if not matching:
        raise ValueError(f"Unknown finding_id: {finding_id}")

    finding = matching[0]

    review = load_human_review(case_dir)

    if review is None:
        review = start_case_review(
            case_dir=case_dir,
            reviewer=reviewer,
        )

    new_record = FindingReviewRecord(
        finding_id=finding_id,
        decision=decision,
        rationale=rationale,
        reviewer=reviewer,
        reviewed_at=utc_now_iso(),
        evidence_ids=list(
            finding.get(
                "evidence_ids",
                [],
            )
        ),
    )

    existing_by_id = {item.finding_id: item for item in review.finding_reviews}

    existing_by_id[finding_id] = new_record

    review = review.model_copy(
        update={
            "status": CaseReviewStatus.IN_PROGRESS,
            "reviewer": reviewer,
            "finding_reviews": list(existing_by_id.values()),
        }
    )

    persist_human_review(
        case_dir=case_dir,
        review=review,
    )

    return review


def complete_case_review(
    *,
    case_dir: Path,
    reviewer: str,
    case_notes: str = "",
) -> CaseReviewRecord:
    """Complete review after all required findings have decisions."""

    report = load_final_report(case_dir)

    required_findings = [
        finding
        for finding in get_report_findings(report)
        if bool(
            finding.get(
                "requires_human_review",
                False,
            )
        )
    ]

    review = load_human_review(case_dir)

    if review is None:
        raise ValueError("Human review has not been started.")

    reviewed_ids = {item.finding_id for item in review.finding_reviews}

    required_ids = {str(finding["finding_id"]) for finding in required_findings}

    missing = sorted(required_ids - reviewed_ids)

    if missing:
        raise ValueError(f"Cannot complete review; missing decisions for: {missing}")

    completed = review.model_copy(
        update={
            "status": CaseReviewStatus.COMPLETED,
            "reviewer": reviewer,
            "completed_at": utc_now_iso(),
            "case_notes": case_notes,
        }
    )

    persist_human_review(
        case_dir=case_dir,
        review=completed,
    )

    return completed

from __future__ import annotations

from typing import Any

from clinical_investigation.review.models import (
    ReviewerBundle,
    ReviewerFinding,
)


def to_reviewer_finding(
    finding: dict[str, Any],
) -> ReviewerFinding:
    """Convert a report finding for reviewer presentation."""

    return ReviewerFinding(
        finding_id=str(finding["finding_id"]),
        finding_type=str(finding["finding_type"]),
        subtype=str(finding["subtype"]),
        severity=str(finding["severity"]),
        title=str(finding["title"]),
        summary=str(finding["summary"]),
        confidence=float(finding["confidence"]),
        requires_human_review=bool(finding["requires_human_review"]),
        evidence_ids=list(
            finding.get(
                "evidence_ids",
                [],
            )
        ),
        claim_ids=list(
            finding.get(
                "claim_ids",
                [],
            )
        ),
        event_ids=list(
            finding.get(
                "event_ids",
                [],
            )
        ),
    )


def build_reviewer_bundle(
    report: dict[str, Any],
) -> ReviewerBundle:
    """Build reviewer-facing case representation."""

    all_findings = report.get(
        "high_priority_findings",
        [],
    ) + report.get(
        "other_findings",
        [],
    )

    review_findings = [
        finding
        for finding in all_findings
        if finding.get(
            "requires_human_review",
            False,
        )
    ]

    contextual_findings = [
        finding
        for finding in all_findings
        if not finding.get(
            "requires_human_review",
            False,
        )
    ]

    return ReviewerBundle(
        case_id=report["case_id"],
        investigation_question=report.get(
            "investigation_question",
            "",
        ),
        executive_summary=report.get(
            "executive_summary",
            "",
        ),
        review_status=report.get(
            "review_status",
            "not_required",
        ),
        findings_requiring_review=[to_reviewer_finding(finding) for finding in review_findings],
        contextual_findings=[to_reviewer_finding(finding) for finding in contextual_findings],
        finding_count=len(all_findings),
        review_finding_count=len(review_findings),
    )

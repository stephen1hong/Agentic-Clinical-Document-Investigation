from __future__ import annotations

from clinical_investigation.agents.models import (
    FindingSeverity,
    InvestigationFinding,
)
from clinical_investigation.agents.report_models import (
    InvestigationReport,
    ReportFinding,
)
from clinical_investigation.agents.state import InvestigationState


def to_report_finding(
    finding: InvestigationFinding,
) -> ReportFinding:
    return ReportFinding(
        finding_id=finding.finding_id,
        finding_type=finding.finding_type.value,
        subtype=finding.subtype,
        severity=finding.severity.value,
        title=finding.title,
        summary=finding.summary,
        evidence_ids=list(finding.evidence_ids),
        claim_ids=list(finding.claim_ids),
        event_ids=list(finding.event_ids),
        confidence=finding.confidence,
        requires_human_review=(finding.requires_human_review),
    )


def generate_investigation_report(
    state: InvestigationState,
) -> InvestigationReport:
    """Generate a deterministic evidence-grounded report."""

    findings = state.get(
        "investigation_findings",
        [],
    )

    high_priority = [
        finding
        for finding in findings
        if (finding.requires_human_review or finding.severity == FindingSeverity.HIGH)
    ]

    other = [finding for finding in findings if finding not in high_priority]

    review_findings = [finding for finding in findings if finding.requires_human_review]

    executive_summary = (
        f"Investigation identified {len(findings)} findings. "
        f"{len(review_findings)} finding(s) require human review."
    )

    return InvestigationReport(
        case_id=state.get("case_id", ""),
        investigation_question=state.get(
            "investigation_question",
            "",
        ),
        executive_summary=executive_summary,
        high_priority_findings=[to_report_finding(finding) for finding in high_priority],
        other_findings=[to_report_finding(finding) for finding in other],
        validation_errors=list(
            state.get(
                "validation_errors",
                [],
            )
        ),
        review_status=state.get(
            "review_status",
            "not_required",
        ),
        review_reasons=list(
            state.get(
                "review_reasons",
                [],
            )
        ),
        finding_count=len(findings),
        review_finding_count=len(review_findings),
    )

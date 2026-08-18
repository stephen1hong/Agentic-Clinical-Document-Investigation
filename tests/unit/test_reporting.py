from __future__ import annotations

from clinical_investigation.agents.models import (
    FindingSeverity,
    FindingSource,
    FindingType,
    InvestigationFinding,
)
from clinical_investigation.agents.reporting import (
    generate_investigation_report,
)


def make_finding(
    *,
    finding_id: str,
    severity: FindingSeverity,
    requires_human_review: bool,
) -> InvestigationFinding:
    """Create a minimal investigation finding for report tests."""

    return InvestigationFinding(
        finding_id=finding_id,
        case_id="case-001",
        finding_type=FindingType.OTHER,
        subtype="test_subtype",
        severity=severity,
        title="Test finding",
        summary="Test finding summary",
        evidence_ids=["evidence-001"],
        claim_ids=["claim-001"],
        event_ids=["event-001"],
        medication_key=None,
        confidence=0.9,
        requires_human_review=requires_human_review,
        source=FindingSource.SYNTHESIS,
    )


def test_generates_report_without_review() -> None:
    """A non-review case should produce a valid report."""

    finding = make_finding(
        finding_id="finding-001",
        severity=FindingSeverity.LOW,
        requires_human_review=False,
    )

    report = generate_investigation_report(
        {
            "case_id": "case-001",
            "investigation_question": "What happened?",
            "investigation_findings": [finding],
            "validation_errors": [],
            "review_status": "not_required",
            "review_reasons": [],
        }
    )

    assert report.case_id == "case-001"
    assert report.investigation_question == "What happened?"

    assert report.finding_count == 1
    assert report.review_finding_count == 0

    assert report.review_status == "not_required"

    assert len(report.high_priority_findings) == 0
    assert len(report.other_findings) == 1


def test_review_required_finding_is_high_priority() -> None:
    """Review-trigger findings should be placed in high priority."""

    finding = make_finding(
        finding_id="finding-review",
        severity=FindingSeverity.MEDIUM,
        requires_human_review=True,
    )

    report = generate_investigation_report(
        {
            "case_id": "case-001",
            "investigation_question": "What happened?",
            "investigation_findings": [finding],
            "validation_errors": [],
            "review_status": "pending",
            "review_reasons": ["Finding requires human review."],
        }
    )

    assert report.finding_count == 1
    assert report.review_finding_count == 1

    assert report.review_status == "pending"

    assert len(report.high_priority_findings) == 1
    assert len(report.other_findings) == 0

    assert report.high_priority_findings[0].finding_id == "finding-review"


def test_high_severity_finding_is_high_priority_without_review() -> None:
    """High severity alone should place a finding in high priority."""

    finding = make_finding(
        finding_id="finding-high",
        severity=FindingSeverity.HIGH,
        requires_human_review=False,
    )

    report = generate_investigation_report(
        {
            "case_id": "case-001",
            "investigation_findings": [finding],
            "validation_errors": [],
            "review_status": "not_required",
            "review_reasons": [],
        }
    )

    assert len(report.high_priority_findings) == 1
    assert len(report.other_findings) == 0

    assert report.review_finding_count == 0


def test_report_counts_are_consistent() -> None:
    """Report counts should match the input findings."""

    findings = [
        make_finding(
            finding_id="finding-001",
            severity=FindingSeverity.INFO,
            requires_human_review=False,
        ),
        make_finding(
            finding_id="finding-002",
            severity=FindingSeverity.LOW,
            requires_human_review=False,
        ),
        make_finding(
            finding_id="finding-003",
            severity=FindingSeverity.MEDIUM,
            requires_human_review=True,
        ),
    ]

    report = generate_investigation_report(
        {
            "case_id": "case-001",
            "investigation_findings": findings,
            "validation_errors": [],
            "review_status": "pending",
            "review_reasons": ["Human review required."],
        }
    )

    assert report.finding_count == 3
    assert report.review_finding_count == 1

    assert len(report.high_priority_findings) + len(report.other_findings) == 3


def test_report_preserves_provenance_ids() -> None:
    """Report findings should preserve evidence provenance."""

    finding = make_finding(
        finding_id="finding-provenance",
        severity=FindingSeverity.LOW,
        requires_human_review=False,
    )

    report = generate_investigation_report(
        {
            "case_id": "case-001",
            "investigation_findings": [finding],
            "validation_errors": [],
            "review_status": "not_required",
            "review_reasons": [],
        }
    )

    report_finding = report.other_findings[0]

    assert report_finding.evidence_ids == ["evidence-001"]

    assert report_finding.claim_ids == ["claim-001"]

    assert report_finding.event_ids == ["event-001"]


def test_report_copies_validation_and_review_metadata() -> None:
    """Validation and review metadata should be preserved."""

    report = generate_investigation_report(
        {
            "case_id": "case-001",
            "investigation_findings": [],
            "validation_errors": ["Unresolved evidence reference."],
            "review_status": "pending",
            "review_reasons": ["Validation error requires review."],
        }
    )

    assert report.validation_errors == ["Unresolved evidence reference."]

    assert report.review_status == "pending"

    assert report.review_reasons == ["Validation error requires review."]

    assert report.finding_count == 0
    assert report.review_finding_count == 0

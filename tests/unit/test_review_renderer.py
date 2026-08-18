from __future__ import annotations

from clinical_investigation.review.models import (
    ReviewerBundle,
    ReviewerFinding,
)
from clinical_investigation.review.renderer import (
    render_finding_markdown,
    render_reviewer_report,
)


def make_reviewer_finding(
    *,
    finding_id: str = "finding-001",
    requires_human_review: bool = True,
    severity: str = "medium",
) -> ReviewerFinding:
    """Create a minimal reviewer finding for renderer tests."""

    return ReviewerFinding(
        finding_id=finding_id,
        finding_type="unsupported_claim",
        subtype="insufficient_evidence_support",
        severity=severity,
        title="Unsupported discharge statement",
        summary="The statement does not have sufficient evidence support.",
        confidence=0.9,
        requires_human_review=requires_human_review,
        evidence_ids=["evidence-001"],
        claim_ids=["claim-001"],
        event_ids=["event-001"],
    )


def make_reviewer_bundle(
    *,
    findings_requiring_review: list[ReviewerFinding] | None = None,
    contextual_findings: list[ReviewerFinding] | None = None,
) -> ReviewerBundle:
    """Create a reviewer bundle for renderer tests."""

    review_findings = findings_requiring_review or []
    context_findings = contextual_findings or []

    return ReviewerBundle(
        case_id="case-001",
        investigation_question=("Identify clinically relevant inconsistencies."),
        executive_summary=("Investigation identified findings requiring review."),
        review_status="pending",
        findings_requiring_review=review_findings,
        contextual_findings=context_findings,
        finding_count=(len(review_findings) + len(context_findings)),
        review_finding_count=len(review_findings),
    )


def test_render_finding_markdown_contains_core_fields() -> None:
    """Rendered finding should expose core reviewer information."""

    finding = make_reviewer_finding()

    markdown = render_finding_markdown(
        finding,
        index=1,
    )

    assert "### 1. Unsupported discharge statement" in markdown
    assert "`finding-001`" in markdown
    assert "`unsupported_claim`" in markdown
    assert "`insufficient_evidence_support`" in markdown
    assert "`medium`" in markdown
    assert "`evidence-001`" in markdown
    assert "`claim-001`" in markdown
    assert "`event-001`" in markdown


def test_render_finding_markdown_contains_review_controls() -> None:
    """Review-required finding should expose decision placeholders."""

    finding = make_reviewer_finding()

    markdown = render_finding_markdown(
        finding,
        index=1,
    )

    assert "- [ ] Accepted" in markdown
    assert "- [ ] Dismissed" in markdown
    assert "- [ ] Needs follow-up" in markdown
    assert "Reviewer rationale:" in markdown


def test_render_reviewer_report_contains_case_metadata() -> None:
    """Reviewer report should include case-level metadata."""

    bundle = make_reviewer_bundle(findings_requiring_review=[make_reviewer_finding()])

    markdown = render_reviewer_report(bundle)

    assert "# Clinical Investigation Review" in markdown
    assert "`case-001`" in markdown
    assert "`pending`" in markdown
    assert "## Investigation Question" in markdown
    assert "## Executive Summary" in markdown
    assert "**Findings requiring review:** 1" in markdown
    assert "**Total findings:** 1" in markdown


def test_review_findings_are_rendered_before_contextual_findings() -> None:
    """Review-required findings should appear before context findings."""

    review_finding = make_reviewer_finding(
        finding_id="review-finding",
        requires_human_review=True,
    )

    contextual_finding = ReviewerFinding(
        finding_id="context-finding",
        finding_type="temporal_uncertainty",
        subtype="missing_event_time",
        severity="info",
        title="Missing event time",
        summary="No normalized event time was available.",
        confidence=1.0,
        requires_human_review=False,
        evidence_ids=["evidence-002"],
        claim_ids=[],
        event_ids=["event-002"],
    )

    bundle = make_reviewer_bundle(
        findings_requiring_review=[review_finding],
        contextual_findings=[contextual_finding],
    )

    markdown = render_reviewer_report(bundle)

    review_position = markdown.index("Unsupported discharge statement")

    context_position = markdown.index("Missing event time")

    assert review_position < context_position


def test_report_handles_no_review_findings() -> None:
    """A no-review case should render an explicit message."""

    contextual_finding = ReviewerFinding(
        finding_id="context-001",
        finding_type="temporal_uncertainty",
        subtype="missing_event_time",
        severity="info",
        title="Missing event time",
        summary="No normalized timestamp was available.",
        confidence=1.0,
        requires_human_review=False,
        evidence_ids=[],
        claim_ids=[],
        event_ids=["event-001"],
    )

    bundle = make_reviewer_bundle(contextual_findings=[contextual_finding])

    markdown = render_reviewer_report(bundle)

    assert "No findings currently require human review." in markdown

    assert "Missing event time" in markdown


def test_report_handles_empty_bundle() -> None:
    """Empty reviewer bundle should still produce valid Markdown."""

    bundle = make_reviewer_bundle()

    markdown = render_reviewer_report(bundle)

    assert "# Clinical Investigation Review" in markdown
    assert "No findings currently require human review." in markdown
    assert "No contextual findings." in markdown


def test_rendered_report_ends_with_single_newline() -> None:
    """Rendered report should follow normalized text formatting."""

    bundle = make_reviewer_bundle(findings_requiring_review=[make_reviewer_finding()])

    markdown = render_reviewer_report(bundle)

    assert markdown.endswith("\n")
    assert not markdown.endswith("\n\n")

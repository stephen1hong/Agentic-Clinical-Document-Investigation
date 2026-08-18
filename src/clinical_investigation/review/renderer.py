from __future__ import annotations

from clinical_investigation.review.models import (
    ReviewerBundle,
    ReviewerFinding,
)


def render_finding_markdown(
    finding: ReviewerFinding,
    *,
    index: int,
) -> str:
    """Render one reviewer-facing finding as Markdown."""

    lines = [
        f"### {index}. {finding.title}",
        "",
        f"- Finding ID: `{finding.finding_id}`",
        f"- Type: `{finding.finding_type}`",
        f"- Subtype: `{finding.subtype}`",
        f"- Severity: `{finding.severity}`",
        f"- Confidence: `{finding.confidence:.2f}`",
        (f"- Requires human review: `{finding.requires_human_review}`"),
        "",
        "#### Summary",
        "",
        finding.summary or "No summary available.",
        "",
    ]

    if finding.evidence_ids:
        lines.extend(
            [
                "#### Evidence IDs",
                "",
            ]
        )

        lines.extend(f"- `{evidence_id}`" for evidence_id in finding.evidence_ids)

        lines.append("")

    if finding.claim_ids:
        lines.extend(
            [
                "#### Claim IDs",
                "",
            ]
        )

        lines.extend(f"- `{claim_id}`" for claim_id in finding.claim_ids)

        lines.append("")

    if finding.event_ids:
        lines.extend(
            [
                "#### Event IDs",
                "",
            ]
        )

        lines.extend(f"- `{event_id}`" for event_id in finding.event_ids)

        lines.append("")

    lines.extend(
        [
            "#### Reviewer Decision",
            "",
            "- [ ] Accepted",
            "- [ ] Dismissed",
            "- [ ] Needs follow-up",
            "",
            "Reviewer rationale:",
            "",
            "> ",
            "",
        ]
    )

    return "\n".join(lines)


def render_reviewer_report(
    bundle: ReviewerBundle,
) -> str:
    """Render a reviewer bundle as deterministic Markdown."""

    lines = [
        "# Clinical Investigation Review",
        "",
        f"**Case ID:** `{bundle.case_id}`",
        "",
        f"**Review status:** `{bundle.review_status}`",
        "",
        (f"**Findings requiring review:** {bundle.review_finding_count}"),
        "",
        f"**Total findings:** {bundle.finding_count}",
        "",
        "## Investigation Question",
        "",
        (bundle.investigation_question or "No investigation question provided."),
        "",
        "## Executive Summary",
        "",
        (bundle.executive_summary or "No executive summary available."),
        "",
        "## Findings Requiring Review",
        "",
    ]

    if bundle.findings_requiring_review:
        for index, finding in enumerate(
            bundle.findings_requiring_review,
            start=1,
        ):
            lines.append(
                render_finding_markdown(
                    finding,
                    index=index,
                )
            )
    else:
        lines.extend(
            [
                "No findings currently require human review.",
                "",
            ]
        )

    lines.extend(
        [
            "## Contextual Findings",
            "",
        ]
    )

    if bundle.contextual_findings:
        for index, finding in enumerate(
            bundle.contextual_findings,
            start=1,
        ):
            lines.extend(
                [
                    f"### {index}. {finding.title}",
                    "",
                    f"- Type: `{finding.finding_type}`",
                    f"- Subtype: `{finding.subtype}`",
                    f"- Severity: `{finding.severity}`",
                    f"- Confidence: `{finding.confidence:.2f}`",
                    "",
                    finding.summary or "No summary available.",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "No contextual findings.",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"

from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.review.models import (
    ReviewerBundle,
)
from clinical_investigation.review.persistence import (
    REVIEWER_BUNDLE_FILENAME,
    REVIEWER_REPORT_FILENAME,
    persist_reviewer_bundle,
    persist_reviewer_report,
)


def make_bundle() -> ReviewerBundle:
    """Create a minimal reviewer bundle."""

    return ReviewerBundle(
        case_id="case-001",
        investigation_question="What happened?",
        executive_summary="No critical findings.",
        review_status="not_required",
        findings_requiring_review=[],
        contextual_findings=[],
        finding_count=0,
        review_finding_count=0,
    )


def test_persist_reviewer_bundle(
    tmp_path: Path,
) -> None:
    """Reviewer bundle should persist as JSON."""

    bundle = make_bundle()

    output_path = persist_reviewer_bundle(
        case_dir=tmp_path,
        bundle=bundle,
    )

    assert output_path == (tmp_path / REVIEWER_BUNDLE_FILENAME)

    assert output_path.exists()

    persisted = json.loads(
        output_path.read_text(
            encoding="utf-8",
        )
    )

    assert persisted == bundle.model_dump(
        mode="json",
    )


def test_persist_reviewer_report(
    tmp_path: Path,
) -> None:
    """Reviewer report should persist as normalized Markdown."""

    markdown = "# Review\n\nTest report."

    output_path = persist_reviewer_report(
        case_dir=tmp_path,
        markdown=markdown,
    )

    assert output_path == (tmp_path / REVIEWER_REPORT_FILENAME)

    assert output_path.exists()

    persisted = output_path.read_text(
        encoding="utf-8",
    )

    assert persisted == ("# Review\n\nTest report.\n")

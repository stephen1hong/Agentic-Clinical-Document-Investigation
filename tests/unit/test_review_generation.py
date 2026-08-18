from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.review.generation import (
    generate_reviewer_artifacts,
)


def test_generate_reviewer_artifacts(
    tmp_path: Path,
) -> None:
    """Reviewer artifacts should be generated from final report."""

    final_report = {
        "case_id": "case-001",
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
                "claim_ids": ["claim-001"],
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

    report_path = tmp_path / "final_investigation_report.json"

    report_path.write_text(
        json.dumps(
            final_report,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    (
        bundle_path,
        reviewer_report_path,
    ) = generate_reviewer_artifacts(tmp_path)

    assert bundle_path.exists()
    assert reviewer_report_path.exists()

    bundle = json.loads(
        bundle_path.read_text(
            encoding="utf-8",
        )
    )

    assert bundle["case_id"] == "case-001"
    assert bundle["review_finding_count"] == 1

    markdown = reviewer_report_path.read_text(
        encoding="utf-8",
    )

    assert "# Clinical Investigation Review" in markdown
    assert "Unsupported claim" in markdown

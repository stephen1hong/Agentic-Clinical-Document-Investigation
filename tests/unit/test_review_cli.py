from __future__ import annotations

import pytest
from scripts.review_investigation_case import (
    get_required_findings,
    prompt_decision,
)

from clinical_investigation.review.models import (
    FindingReviewDecision,
)


def test_get_required_findings_filters_contextual_findings() -> None:
    """Only human-review findings should be presented."""

    report = {
        "high_priority_findings": [
            {
                "finding_id": "review-001",
                "requires_human_review": True,
            }
        ],
        "other_findings": [
            {
                "finding_id": "context-001",
                "requires_human_review": False,
            }
        ],
    }

    findings = get_required_findings(report)

    assert len(findings) == 1

    assert findings[0]["finding_id"] == "review-001"


@pytest.mark.parametrize(
    (
        "entered",
        "expected",
    ),
    [
        (
            "1",
            FindingReviewDecision.ACCEPTED,
        ),
        (
            "2",
            FindingReviewDecision.DISMISSED,
        ),
        (
            "3",
            FindingReviewDecision.NEEDS_FOLLOW_UP,
        ),
        (
            "accepted",
            FindingReviewDecision.ACCEPTED,
        ),
    ],
)
def test_prompt_decision_accepts_valid_input(
    monkeypatch: pytest.MonkeyPatch,
    entered: str,
    expected: FindingReviewDecision,
) -> None:
    """CLI should map valid input to review decisions."""

    monkeypatch.setattr(
        "builtins.input",
        lambda _: entered,
    )

    result = prompt_decision()

    assert result == expected

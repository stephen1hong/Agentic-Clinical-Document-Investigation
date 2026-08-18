from __future__ import annotations

import pytest
from scripts.annotate_gold_findings import (
    get_annotation_findings,
    prompt_disposition,
    prompt_evidence_support,
)

from clinical_investigation.evaluation.models import (
    EvidenceSupportLabel,
    GoldFindingDisposition,
)


def make_report() -> dict[str, object]:
    return {
        "high_priority_findings": [
            {
                "finding_id": "finding-001",
                "requires_human_review": True,
            }
        ],
        "other_findings": [
            {
                "finding_id": "finding-002",
                "requires_human_review": False,
            }
        ],
    }


def test_default_scope_selects_review_findings() -> None:
    findings = get_annotation_findings(
        report=make_report(),
        all_findings=False,
    )

    assert len(findings) == 1
    assert findings[0]["finding_id"] == "finding-001"


def test_all_findings_scope() -> None:
    findings = get_annotation_findings(
        report=make_report(),
        all_findings=True,
    )

    assert len(findings) == 2


@pytest.mark.parametrize(
    ("entered", "expected"),
    [
        ("1", GoldFindingDisposition.TRUE_POSITIVE),
        ("2", GoldFindingDisposition.FALSE_POSITIVE),
        ("3", GoldFindingDisposition.PARTIALLY_CORRECT),
        ("4", None),
    ],
)
def test_prompt_disposition(
    monkeypatch: pytest.MonkeyPatch,
    entered: str,
    expected: GoldFindingDisposition | None,
) -> None:
    monkeypatch.setattr(
        "builtins.input",
        lambda _: entered,
    )

    assert prompt_disposition() == expected


@pytest.mark.parametrize(
    ("entered", "expected"),
    [
        ("1", EvidenceSupportLabel.SUPPORTED),
        ("2", EvidenceSupportLabel.PARTIALLY_SUPPORTED),
        ("3", EvidenceSupportLabel.UNSUPPORTED),
        ("4", EvidenceSupportLabel.NOT_EVALUATED),
    ],
)
def test_prompt_evidence_support(
    monkeypatch: pytest.MonkeyPatch,
    entered: str,
    expected: EvidenceSupportLabel,
) -> None:
    monkeypatch.setattr(
        "builtins.input",
        lambda _: entered,
    )

    assert prompt_evidence_support() == expected

from __future__ import annotations

import pytest

from clinical_investigation.evaluation.finding_metrics import (
    FindingOutcome,
)
from clinical_investigation.evaluation.finding_scorer import (
    score_case_findings,
    summarize_scores,
)
from clinical_investigation.evaluation.models import (
    GoldCaseLabel,
    GoldFindingDisposition,
    GoldFindingLabel,
)


def make_report() -> dict[str, object]:
    """Build a minimal machine report."""

    return {
        "case_id": "case-001",
        "high_priority_findings": [
            {
                "finding_id": "finding-001",
                "finding_type": "unsupported_claim",
                "subtype": "insufficient_evidence_support",
                "severity": "medium",
                "requires_human_review": True,
            },
            {
                "finding_id": "finding-002",
                "finding_type": "medication_discrepancy",
                "subtype": "dose_conflict",
                "severity": "high",
                "requires_human_review": True,
            },
        ],
        "other_findings": [
            {
                "finding_id": "finding-003",
                "finding_type": "temporal_uncertainty",
                "subtype": "missing_event_time",
                "severity": "low",
                "requires_human_review": False,
            },
            {
                "finding_id": "finding-004",
                "finding_type": "medication_discrepancy",
                "subtype": "ambiguous_status",
                "severity": "low",
                "requires_human_review": False,
            },
        ],
    }


def make_gold_labels() -> GoldCaseLabel:
    """Build evaluation labels for three of four findings."""

    return GoldCaseLabel(
        case_id="case-001",
        evaluator="evaluator-a",
        finding_labels=[
            GoldFindingLabel(
                finding_id="finding-001",
                disposition=(GoldFindingDisposition.TRUE_POSITIVE),
            ),
            GoldFindingLabel(
                finding_id="finding-002",
                disposition=(GoldFindingDisposition.FALSE_POSITIVE),
            ),
            GoldFindingLabel(
                finding_id="finding-003",
                disposition=(GoldFindingDisposition.PARTIALLY_CORRECT),
            ),
        ],
    )


def test_score_case_findings_maps_gold_outcomes() -> None:
    result = score_case_findings(
        report=make_report(),
        gold_labels=make_gold_labels(),
    )

    outcomes = {score.finding_id: score.outcome for score in result.scores}

    assert outcomes == {
        "finding-001": FindingOutcome.TRUE_POSITIVE,
        "finding-002": FindingOutcome.FALSE_POSITIVE,
        "finding-003": FindingOutcome.PARTIALLY_CORRECT,
        "finding-004": FindingOutcome.NOT_EVALUATED,
    }


def test_score_case_findings_calculates_summary() -> None:
    result = score_case_findings(
        report=make_report(),
        gold_labels=make_gold_labels(),
    )

    summary = result.overall

    assert summary.total_findings == 4
    assert summary.evaluated_findings == 3

    assert summary.true_positive_count == 1
    assert summary.false_positive_count == 1
    assert summary.partially_correct_count == 1
    assert summary.not_evaluated_count == 1

    assert summary.precision == pytest.approx(1 / 3)

    assert summary.false_positive_rate == pytest.approx(1 / 3)

    assert summary.partial_correct_rate == pytest.approx(1 / 3)

    assert summary.evaluation_coverage == pytest.approx(3 / 4)

    assert summary.mean_score == pytest.approx(0.5)


def test_missing_gold_label_is_not_evaluated() -> None:
    result = score_case_findings(
        report=make_report(),
        gold_labels=make_gold_labels(),
    )

    score = next(item for item in result.scores if item.finding_id == "finding-004")

    assert score.outcome == FindingOutcome.NOT_EVALUATED

    assert score.score_value == 0.0


def test_group_metrics_are_created() -> None:
    result = score_case_findings(
        report=make_report(),
        gold_labels=make_gold_labels(),
    )

    type_groups = {group.group_value for group in result.by_finding_type}

    assert type_groups == {
        "medication_discrepancy",
        "temporal_uncertainty",
        "unsupported_claim",
    }

    severity_groups = {group.group_value for group in result.by_severity}

    assert severity_groups == {
        "high",
        "low",
        "medium",
    }


def test_review_requirement_groups_are_created() -> None:
    result = score_case_findings(
        report=make_report(),
        gold_labels=make_gold_labels(),
    )

    groups = {group.group_value: group.summary for group in result.by_review_requirement}

    assert set(groups) == {
        "False",
        "True",
    }

    assert groups["True"].total_findings == 2

    assert groups["False"].total_findings == 2


def test_case_id_mismatch_is_rejected() -> None:
    gold = make_gold_labels().model_copy(
        update={
            "case_id": "different-case",
        }
    )

    with pytest.raises(
        ValueError,
        match="Case ID mismatch",
    ):
        score_case_findings(
            report=make_report(),
            gold_labels=gold,
        )


def test_empty_scores_have_defined_zero_coverage() -> None:
    summary = summarize_scores([])

    assert summary.total_findings == 0
    assert summary.evaluated_findings == 0
    assert summary.evaluation_coverage == 0.0

    assert summary.precision is None
    assert summary.false_positive_rate is None
    assert summary.partial_correct_rate is None
    assert summary.mean_score is None


def test_unknown_gold_finding_id_is_rejected() -> None:
    """Gold labels must not reference nonexistent machine findings."""

    base_gold = make_gold_labels()

    gold = base_gold.model_copy(
        update={
            "finding_labels": (
                base_gold.finding_labels
                + [
                    GoldFindingLabel(
                        finding_id="finding-999",
                        disposition=(GoldFindingDisposition.TRUE_POSITIVE),
                    )
                ]
            )
        }
    )

    with pytest.raises(
        ValueError,
        match="unknown machine findings",
    ):
        score_case_findings(
            report=make_report(),
            gold_labels=gold,
        )

from __future__ import annotations

import pytest

from clinical_investigation.evaluation.finding_aggregate import (
    aggregate_finding_evaluations,
)
from clinical_investigation.evaluation.finding_metrics import (
    FindingEvaluationResult,
    FindingMetricSummary,
    FindingOutcome,
    FindingScore,
)


def make_summary(
    *,
    total: int,
    evaluated: int,
    true_positive: int,
    false_positive: int,
    partial: int,
    not_evaluated: int,
) -> FindingMetricSummary:
    """Build a minimal metric summary."""

    if evaluated == 0:
        precision = None
        false_positive_rate = None
        partial_correct_rate = None
        mean_score = None
    else:
        precision = true_positive / evaluated
        false_positive_rate = false_positive / evaluated
        partial_correct_rate = partial / evaluated
        mean_score = (true_positive + (0.5 * partial)) / evaluated

    coverage = 0.0 if total == 0 else evaluated / total

    return FindingMetricSummary(
        total_findings=total,
        evaluated_findings=evaluated,
        true_positive_count=true_positive,
        false_positive_count=false_positive,
        partially_correct_count=partial,
        not_evaluated_count=not_evaluated,
        precision=precision,
        false_positive_rate=false_positive_rate,
        partial_correct_rate=partial_correct_rate,
        evaluation_coverage=coverage,
        mean_score=mean_score,
    )


def make_result(
    *,
    case_id: str,
    scores: list[FindingScore],
) -> FindingEvaluationResult:
    """Build a case-level evaluation result."""

    total = len(scores)

    evaluated_scores = [score for score in scores if score.outcome != FindingOutcome.NOT_EVALUATED]

    true_positive = sum(score.outcome == FindingOutcome.TRUE_POSITIVE for score in scores)

    false_positive = sum(score.outcome == FindingOutcome.FALSE_POSITIVE for score in scores)

    partial = sum(score.outcome == FindingOutcome.PARTIALLY_CORRECT for score in scores)

    not_evaluated = sum(score.outcome == FindingOutcome.NOT_EVALUATED for score in scores)

    summary = make_summary(
        total=total,
        evaluated=len(evaluated_scores),
        true_positive=true_positive,
        false_positive=false_positive,
        partial=partial,
        not_evaluated=not_evaluated,
    )

    return FindingEvaluationResult(
        case_id=case_id,
        scores=scores,
        overall=summary,
    )


def make_score(
    *,
    finding_id: str,
    outcome: FindingOutcome,
    finding_type: str,
    subtype: str,
    severity: str,
    requires_human_review: bool,
) -> FindingScore:
    """Build one finding score."""

    score_value = {
        FindingOutcome.TRUE_POSITIVE: 1.0,
        FindingOutcome.PARTIALLY_CORRECT: 0.5,
        FindingOutcome.FALSE_POSITIVE: 0.0,
        FindingOutcome.NOT_EVALUATED: 0.0,
    }[outcome]

    return FindingScore(
        finding_id=finding_id,
        outcome=outcome,
        finding_type=finding_type,
        subtype=subtype,
        severity=severity,
        requires_human_review=requires_human_review,
        score_value=score_value,
    )


def test_aggregate_combines_case_scores() -> None:
    result_1 = make_result(
        case_id="case-001",
        scores=[
            make_score(
                finding_id="finding-001",
                outcome=FindingOutcome.TRUE_POSITIVE,
                finding_type="unsupported_claim",
                subtype="insufficient_evidence_support",
                severity="medium",
                requires_human_review=True,
            )
        ],
    )

    result_2 = make_result(
        case_id="case-002",
        scores=[
            make_score(
                finding_id="finding-002",
                outcome=FindingOutcome.FALSE_POSITIVE,
                finding_type="medication_discrepancy",
                subtype="dose_conflict",
                severity="high",
                requires_human_review=True,
            ),
            make_score(
                finding_id="finding-003",
                outcome=FindingOutcome.PARTIALLY_CORRECT,
                finding_type="temporal_uncertainty",
                subtype="missing_event_time",
                severity="low",
                requires_human_review=False,
            ),
        ],
    )

    aggregate = aggregate_finding_evaluations(
        [
            result_1,
            result_2,
        ]
    )

    assert aggregate.case_count == 2
    assert aggregate.overall.total_findings == 3
    assert aggregate.overall.evaluated_findings == 3

    assert aggregate.overall.true_positive_count == 1

    assert aggregate.overall.false_positive_count == 1

    assert aggregate.overall.partially_correct_count == 1

    assert aggregate.overall.precision == pytest.approx(1 / 3)

    assert aggregate.overall.mean_score == pytest.approx(0.5)


def test_aggregate_builds_group_metrics() -> None:
    result = make_result(
        case_id="case-001",
        scores=[
            make_score(
                finding_id="finding-001",
                outcome=FindingOutcome.TRUE_POSITIVE,
                finding_type="unsupported_claim",
                subtype="insufficient_evidence_support",
                severity="medium",
                requires_human_review=True,
            ),
            make_score(
                finding_id="finding-002",
                outcome=FindingOutcome.FALSE_POSITIVE,
                finding_type="temporal_uncertainty",
                subtype="missing_event_time",
                severity="low",
                requires_human_review=False,
            ),
        ],
    )

    aggregate = aggregate_finding_evaluations([result])

    finding_types = {group.group_value for group in aggregate.by_finding_type}

    assert finding_types == {
        "temporal_uncertainty",
        "unsupported_claim",
    }

    review_groups = {group.group_value for group in aggregate.by_review_requirement}

    assert review_groups == {
        "False",
        "True",
    }


def test_aggregate_sorts_case_ids() -> None:
    result_b = make_result(
        case_id="case-b",
        scores=[],
    )

    result_a = make_result(
        case_id="case-a",
        scores=[],
    )

    aggregate = aggregate_finding_evaluations(
        [
            result_b,
            result_a,
        ]
    )

    assert aggregate.evaluated_case_ids == [
        "case-a",
        "case-b",
    ]


def test_empty_aggregate_is_valid() -> None:
    aggregate = aggregate_finding_evaluations([])

    assert aggregate.case_count == 0

    assert aggregate.overall.total_findings == 0

    assert aggregate.overall.evaluation_coverage == 0.0

    assert aggregate.overall.precision is None
    assert aggregate.evaluated_case_ids == []

from __future__ import annotations

from clinical_investigation.evaluation.finding_metrics import (
    AggregateFindingEvaluationResult,
    FindingEvaluationResult,
    FindingScore,
)
from clinical_investigation.evaluation.finding_scorer import (
    build_group_metrics,
    summarize_scores,
)


def aggregate_finding_evaluations(
    results: list[FindingEvaluationResult],
) -> AggregateFindingEvaluationResult:
    """Aggregate multiple case-level finding evaluations."""

    all_scores: list[FindingScore] = []

    for result in results:
        all_scores.extend(result.scores)

    overall = summarize_scores(all_scores)

    by_finding_type = build_group_metrics(
        scores=all_scores,
        group_name="finding_type",
        value_getter=lambda score: score.finding_type,
    )

    by_subtype = build_group_metrics(
        scores=all_scores,
        group_name="subtype",
        value_getter=lambda score: score.subtype,
    )

    by_severity = build_group_metrics(
        scores=all_scores,
        group_name="severity",
        value_getter=lambda score: score.severity,
    )

    by_review_requirement = build_group_metrics(
        scores=all_scores,
        group_name="requires_human_review",
        value_getter=lambda score: score.requires_human_review,
    )

    evaluated_case_ids = sorted(result.case_id for result in results)

    return AggregateFindingEvaluationResult(
        case_count=len(results),
        overall=overall,
        by_finding_type=by_finding_type,
        by_subtype=by_subtype,
        by_severity=by_severity,
        by_review_requirement=(by_review_requirement),
        evaluated_case_ids=evaluated_case_ids,
    )

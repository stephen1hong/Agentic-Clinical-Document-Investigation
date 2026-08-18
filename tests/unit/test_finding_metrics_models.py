from __future__ import annotations

from clinical_investigation.evaluation.finding_metrics import (
    FindingEvaluationResult,
    FindingMetricSummary,
    FindingOutcome,
    FindingScore,
)


def test_finding_score_preserves_outcome() -> None:
    score = FindingScore(
        finding_id="finding-001",
        outcome=FindingOutcome.TRUE_POSITIVE,
        finding_type="unsupported_claim",
        subtype="insufficient_evidence_support",
        severity="medium",
        requires_human_review=True,
        evidence_support="supported",
        score_value=1.0,
    )

    assert score.outcome == FindingOutcome.TRUE_POSITIVE

    assert score.score_value == 1.0


def test_metric_summary_supports_empty_evaluation() -> None:
    summary = FindingMetricSummary(
        total_findings=5,
        evaluated_findings=0,
        true_positive_count=0,
        false_positive_count=0,
        partially_correct_count=0,
        not_evaluated_count=5,
        precision=None,
        false_positive_rate=None,
        partial_correct_rate=None,
        evaluation_coverage=0.0,
        mean_score=None,
    )

    assert summary.precision is None
    assert summary.mean_score is None
    assert summary.evaluation_coverage == 0.0


def test_case_evaluation_result_defaults() -> None:
    summary = FindingMetricSummary(
        total_findings=0,
        evaluated_findings=0,
        true_positive_count=0,
        false_positive_count=0,
        partially_correct_count=0,
        not_evaluated_count=0,
        precision=None,
        false_positive_rate=None,
        partial_correct_rate=None,
        evaluation_coverage=0.0,
        mean_score=None,
    )

    result = FindingEvaluationResult(
        case_id="case-001",
        overall=summary,
    )

    assert result.scores == []
    assert result.by_finding_type == []
    assert result.by_subtype == []
    assert result.by_severity == []
    assert result.by_review_requirement == []

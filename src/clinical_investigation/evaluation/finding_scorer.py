from __future__ import annotations

from collections import defaultdict
from typing import Any

from clinical_investigation.evaluation.finding_metrics import (
    FindingEvaluationResult,
    FindingGroupMetric,
    FindingMetricSummary,
    FindingOutcome,
    FindingScore,
)
from clinical_investigation.evaluation.models import (
    GoldCaseLabel,
    GoldFindingDisposition,
)

SCORE_VALUE_BY_OUTCOME = {
    FindingOutcome.TRUE_POSITIVE: 1.0,
    FindingOutcome.PARTIALLY_CORRECT: 0.5,
    FindingOutcome.FALSE_POSITIVE: 0.0,
}


OUTCOME_BY_DISPOSITION = {
    GoldFindingDisposition.TRUE_POSITIVE: (FindingOutcome.TRUE_POSITIVE),
    GoldFindingDisposition.FALSE_POSITIVE: (FindingOutcome.FALSE_POSITIVE),
    GoldFindingDisposition.PARTIALLY_CORRECT: (FindingOutcome.PARTIALLY_CORRECT),
    GoldFindingDisposition.NOT_EVALUATED: (FindingOutcome.NOT_EVALUATED),
}


def get_report_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all findings from a final investigation report."""

    return list(
        report.get(
            "high_priority_findings",
            [],
        )
    ) + list(
        report.get(
            "other_findings",
            [],
        )
    )


def summarize_scores(
    scores: list[FindingScore],
) -> FindingMetricSummary:
    """Calculate aggregate metrics for a collection of findings."""

    total_findings = len(scores)

    true_positive_count = sum(score.outcome == FindingOutcome.TRUE_POSITIVE for score in scores)

    false_positive_count = sum(score.outcome == FindingOutcome.FALSE_POSITIVE for score in scores)

    partially_correct_count = sum(
        score.outcome == FindingOutcome.PARTIALLY_CORRECT for score in scores
    )

    not_evaluated_count = sum(score.outcome == FindingOutcome.NOT_EVALUATED for score in scores)

    evaluated_findings = true_positive_count + false_positive_count + partially_correct_count

    evaluation_coverage = 0.0 if total_findings == 0 else evaluated_findings / total_findings

    if evaluated_findings == 0:
        precision = None
        false_positive_rate = None
        partial_correct_rate = None
        mean_score = None
    else:
        precision = true_positive_count / evaluated_findings

        false_positive_rate = false_positive_count / evaluated_findings

        partial_correct_rate = partially_correct_count / evaluated_findings

        evaluated_score_values = [
            score.score_value for score in scores if score.outcome != FindingOutcome.NOT_EVALUATED
        ]

        mean_score = sum(evaluated_score_values) / len(evaluated_score_values)

    return FindingMetricSummary(
        total_findings=total_findings,
        evaluated_findings=evaluated_findings,
        true_positive_count=true_positive_count,
        false_positive_count=false_positive_count,
        partially_correct_count=partially_correct_count,
        not_evaluated_count=not_evaluated_count,
        precision=precision,
        false_positive_rate=false_positive_rate,
        partial_correct_rate=partial_correct_rate,
        evaluation_coverage=evaluation_coverage,
        mean_score=mean_score,
    )


def score_one_finding(
    *,
    finding: dict[str, Any],
    gold_label: Any | None,
) -> FindingScore:
    """Score one machine finding against its gold label."""

    if gold_label is None:
        outcome = FindingOutcome.NOT_EVALUATED
        score_value = 0.0
        evidence_support = None
        reviewer = ""
        rationale = ""
    else:
        outcome = OUTCOME_BY_DISPOSITION[gold_label.disposition]

        score_value = SCORE_VALUE_BY_OUTCOME.get(
            outcome,
            0.0,
        )

        evidence_support = gold_label.evidence_support.value

        reviewer = gold_label.reviewer

        rationale = gold_label.rationale

    return FindingScore(
        finding_id=str(finding["finding_id"]),
        outcome=outcome,
        finding_type=str(
            finding.get(
                "finding_type",
                "",
            )
        ),
        subtype=str(
            finding.get(
                "subtype",
                "",
            )
        ),
        severity=str(
            finding.get(
                "severity",
                "",
            )
        ),
        requires_human_review=bool(
            finding.get(
                "requires_human_review",
                False,
            )
        ),
        evidence_support=evidence_support,
        score_value=score_value,
        reviewer=reviewer,
        rationale=rationale,
    )


def build_group_metrics(
    *,
    scores: list[FindingScore],
    group_name: str,
    value_getter: Any,
) -> list[FindingGroupMetric]:
    """Build metric summaries grouped by one finding attribute."""

    grouped: dict[
        str,
        list[FindingScore],
    ] = defaultdict(list)

    for score in scores:
        group_value = str(value_getter(score))

        grouped[group_value].append(score)

    return [
        FindingGroupMetric(
            group_name=group_name,
            group_value=group_value,
            summary=summarize_scores(grouped_scores),
        )
        for group_value, grouped_scores in sorted(grouped.items())
    ]


def score_case_findings(
    *,
    report: dict[str, Any],
    gold_labels: GoldCaseLabel,
) -> FindingEvaluationResult:
    """Evaluate all machine findings in one case."""

    report_case_id = str(
        report.get(
            "case_id",
            "",
        )
    )

    if report_case_id != gold_labels.case_id:
        raise ValueError("Case ID mismatch between machine report and gold labels.")

    machine_findings = get_report_findings(report)

    gold_by_finding_id = {label.finding_id: label for label in gold_labels.finding_labels}

    machine_finding_ids = {str(finding["finding_id"]) for finding in machine_findings}

    unknown_gold_ids = sorted(set(gold_by_finding_id) - machine_finding_ids)

    if unknown_gold_ids:
        raise ValueError(f"Gold labels reference unknown machine findings: {unknown_gold_ids}")

    scores = [
        score_one_finding(
            finding=finding,
            gold_label=gold_by_finding_id.get(str(finding["finding_id"])),
        )
        for finding in machine_findings
    ]

    overall = summarize_scores(scores)

    by_finding_type = build_group_metrics(
        scores=scores,
        group_name="finding_type",
        value_getter=lambda score: score.finding_type,
    )

    by_subtype = build_group_metrics(
        scores=scores,
        group_name="subtype",
        value_getter=lambda score: score.subtype,
    )

    by_severity = build_group_metrics(
        scores=scores,
        group_name="severity",
        value_getter=lambda score: score.severity,
    )

    by_review_requirement = build_group_metrics(
        scores=scores,
        group_name=("requires_human_review"),
        value_getter=lambda score: score.requires_human_review,
    )

    return FindingEvaluationResult(
        case_id=report_case_id,
        scores=scores,
        overall=overall,
        by_finding_type=by_finding_type,
        by_subtype=by_subtype,
        by_severity=by_severity,
        by_review_requirement=(by_review_requirement),
    )

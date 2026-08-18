from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.evaluation.aggregate_persistence import (
    AGGREGATE_FINDING_EVALUATION_FILENAME,
    load_aggregate_finding_evaluation,
    persist_aggregate_finding_evaluation,
)
from clinical_investigation.evaluation.finding_metrics import (
    AggregateFindingEvaluationResult,
    FindingMetricSummary,
)


def make_aggregate() -> AggregateFindingEvaluationResult:
    """Build minimal aggregate metrics."""

    summary = FindingMetricSummary(
        total_findings=2,
        evaluated_findings=2,
        true_positive_count=1,
        false_positive_count=1,
        partially_correct_count=0,
        not_evaluated_count=0,
        precision=0.5,
        false_positive_rate=0.5,
        partial_correct_rate=0.0,
        evaluation_coverage=1.0,
        mean_score=0.5,
    )

    return AggregateFindingEvaluationResult(
        case_count=2,
        overall=summary,
        evaluated_case_ids=[
            "case-001",
            "case-002",
        ],
    )


def test_persist_aggregate_evaluation(
    tmp_path: Path,
) -> None:
    result = make_aggregate()

    path = persist_aggregate_finding_evaluation(
        output_dir=tmp_path,
        result=result,
    )

    assert path == (tmp_path / AGGREGATE_FINDING_EVALUATION_FILENAME)

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    assert payload == result.model_dump(
        mode="json",
    )


def test_aggregate_evaluation_round_trip(
    tmp_path: Path,
) -> None:
    result = make_aggregate()

    path = persist_aggregate_finding_evaluation(
        output_dir=tmp_path,
        result=result,
    )

    loaded = load_aggregate_finding_evaluation(path)

    assert loaded == result

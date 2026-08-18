from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.evaluation.finding_metrics import (
    FindingEvaluationResult,
    FindingMetricSummary,
)
from clinical_investigation.evaluation.finding_persistence import (
    FINDING_EVALUATION_FILENAME,
    load_finding_evaluation,
    persist_finding_evaluation,
)


def make_result() -> FindingEvaluationResult:
    """Build a minimal finding evaluation result."""

    summary = FindingMetricSummary(
        total_findings=1,
        evaluated_findings=1,
        true_positive_count=1,
        false_positive_count=0,
        partially_correct_count=0,
        not_evaluated_count=0,
        precision=1.0,
        false_positive_rate=0.0,
        partial_correct_rate=0.0,
        evaluation_coverage=1.0,
        mean_score=1.0,
    )

    return FindingEvaluationResult(
        case_id="case-001",
        overall=summary,
    )


def test_persist_finding_evaluation(
    tmp_path: Path,
) -> None:
    result = make_result()

    path = persist_finding_evaluation(
        output_dir=tmp_path,
        result=result,
    )

    assert path == (tmp_path / FINDING_EVALUATION_FILENAME)

    assert path.exists()

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    assert payload == result.model_dump(
        mode="json",
    )


def test_finding_evaluation_round_trip(
    tmp_path: Path,
) -> None:
    result = make_result()

    path = persist_finding_evaluation(
        output_dir=tmp_path,
        result=result,
    )

    loaded = load_finding_evaluation(path)

    assert loaded == result

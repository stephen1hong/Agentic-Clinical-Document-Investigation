from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.evaluation.finding_metrics import (
    AggregateFindingEvaluationResult,
)

AGGREGATE_FINDING_EVALUATION_FILENAME = "aggregate_finding_evaluation.json"


def persist_aggregate_finding_evaluation(
    *,
    output_dir: Path,
    result: AggregateFindingEvaluationResult,
) -> Path:
    """Persist aggregate finding evaluation metrics."""

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = output_dir / AGGREGATE_FINDING_EVALUATION_FILENAME

    output_path.write_text(
        json.dumps(
            result.model_dump(
                mode="json",
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return output_path


def load_aggregate_finding_evaluation(
    path: Path,
) -> AggregateFindingEvaluationResult:
    """Load persisted aggregate finding evaluation metrics."""

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    return AggregateFindingEvaluationResult.model_validate(payload)

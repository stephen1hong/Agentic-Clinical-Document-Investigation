from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.evaluation.finding_metrics import (
    FindingEvaluationResult,
)

FINDING_EVALUATION_FILENAME = "finding_evaluation.json"


def persist_finding_evaluation(
    *,
    output_dir: Path,
    result: FindingEvaluationResult,
) -> Path:
    """Persist one case-level finding evaluation result."""

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = output_dir / FINDING_EVALUATION_FILENAME

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


def load_finding_evaluation(
    path: Path,
) -> FindingEvaluationResult:
    """Load one persisted finding evaluation result."""

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    return FindingEvaluationResult.model_validate(payload)

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clinical_investigation.evaluation.finding_metrics import (
    FindingEvaluationResult,
)
from clinical_investigation.evaluation.finding_persistence import (
    persist_finding_evaluation,
)
from clinical_investigation.evaluation.finding_scorer import (
    score_case_findings,
)
from clinical_investigation.evaluation.persistence import (
    load_gold_labels,
)

FINAL_REPORT_FILENAME = "final_investigation_report.json"
GOLD_LABEL_FILENAME = "gold_labels.json"


def load_final_report(
    case_dir: Path,
) -> dict[str, Any]:
    """Load one machine-generated final investigation report."""

    path = case_dir / FINAL_REPORT_FILENAME

    if not path.exists():
        raise FileNotFoundError(f"Final report not found: {path}")

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(payload, dict):
        raise ValueError("Final report must contain a JSON object.")

    return payload


def evaluate_case_findings(
    *,
    case_dir: Path,
    gold_label_dir: Path,
    output_dir: Path,
) -> FindingEvaluationResult:
    """Evaluate and persist finding metrics for one case."""

    report = load_final_report(case_dir)

    gold_path = gold_label_dir / GOLD_LABEL_FILENAME

    if not gold_path.exists():
        raise FileNotFoundError(f"Gold labels not found: {gold_path}")

    gold_labels = load_gold_labels(gold_path)

    result = score_case_findings(
        report=report,
        gold_labels=gold_labels,
    )

    persist_finding_evaluation(
        output_dir=output_dir,
        result=result,
    )

    return result

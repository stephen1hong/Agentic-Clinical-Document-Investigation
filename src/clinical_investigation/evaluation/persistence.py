from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.evaluation.models import (
    GoldCaseLabel,
)

GOLD_LABEL_FILENAME = "gold_labels.json"


def persist_gold_labels(
    *,
    output_dir: Path,
    gold_labels: GoldCaseLabel,
) -> Path:
    """Persist one case's gold-standard evaluation labels."""

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = output_dir / GOLD_LABEL_FILENAME

    output_path.write_text(
        json.dumps(
            gold_labels.model_dump(
                mode="json",
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return output_path


def load_gold_labels(
    path: Path,
) -> GoldCaseLabel:
    """Load one gold-label artifact."""

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    return GoldCaseLabel.model_validate(payload)

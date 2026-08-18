from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.review.models import (
    CaseReviewRecord,
)

HUMAN_REVIEW_FILENAME = "human_review.json"


def persist_human_review(
    *,
    case_dir: Path,
    review: CaseReviewRecord,
) -> Path:
    """Persist the human-review record."""

    output_path = case_dir / HUMAN_REVIEW_FILENAME

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            review.model_dump(
                mode="json",
            ),
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return output_path


def load_human_review(
    case_dir: Path,
) -> CaseReviewRecord | None:
    """Load an existing human-review record."""

    path = case_dir / HUMAN_REVIEW_FILENAME

    if not path.exists():
        return None

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    return CaseReviewRecord.model_validate(payload)

from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.review.models import (
    ReviewerBundle,
)

REVIEWER_BUNDLE_FILENAME = "reviewer_bundle.json"
REVIEWER_REPORT_FILENAME = "reviewer_report.md"


def write_json(
    path: Path,
    payload: object,
) -> None:
    """Write deterministic formatted JSON."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def write_text(
    path: Path,
    text: str,
) -> None:
    """Write normalized UTF-8 text."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        text.rstrip() + "\n",
        encoding="utf-8",
    )


def persist_reviewer_bundle(
    *,
    case_dir: Path,
    bundle: ReviewerBundle,
) -> Path:
    """Persist the reviewer bundle for one case."""

    output_path = case_dir / REVIEWER_BUNDLE_FILENAME

    write_json(
        output_path,
        bundle.model_dump(
            mode="json",
        ),
    )

    return output_path


def persist_reviewer_report(
    *,
    case_dir: Path,
    markdown: str,
) -> Path:
    """Persist the reviewer-facing Markdown report."""

    output_path = case_dir / REVIEWER_REPORT_FILENAME

    write_text(
        output_path,
        markdown,
    )

    return output_path

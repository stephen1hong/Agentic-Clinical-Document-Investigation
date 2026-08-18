from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clinical_investigation.review.bundle import (
    build_reviewer_bundle,
)
from clinical_investigation.review.persistence import (
    persist_reviewer_bundle,
    persist_reviewer_report,
)
from clinical_investigation.review.renderer import (
    render_reviewer_report,
)

FINAL_REPORT_FILENAME = "final_investigation_report.json"


def load_final_report(
    case_dir: Path,
) -> dict[str, Any]:
    """Load the persisted final investigation report."""

    report_path = case_dir / FINAL_REPORT_FILENAME

    if not report_path.exists():
        raise FileNotFoundError(f"Final investigation report not found: {report_path}")

    payload = json.loads(
        report_path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(payload, dict):
        raise ValueError("Final investigation report must contain a JSON object.")

    return payload


def generate_reviewer_artifacts(
    case_dir: Path,
) -> tuple[Path, Path]:
    """Generate and persist reviewer-facing artifacts for one case."""

    report = load_final_report(case_dir)

    bundle = build_reviewer_bundle(report)

    markdown = render_reviewer_report(bundle)

    bundle_path = persist_reviewer_bundle(
        case_dir=case_dir,
        bundle=bundle,
    )

    report_path = persist_reviewer_report(
        case_dir=case_dir,
        markdown=markdown,
    )

    return (
        bundle_path,
        report_path,
    )

from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.evaluation.models import (
    GoldFindingDisposition,
)
from clinical_investigation.evaluation.template import (
    build_gold_label_template,
)


def test_build_gold_label_template(
    tmp_path: Path,
) -> None:
    """Template should contain every machine finding."""

    case_dir = tmp_path / "case-001"

    case_dir.mkdir()

    report = {
        "case_id": "case-001",
        "high_priority_findings": [
            {
                "finding_id": "finding-001",
                "finding_type": "unsupported_claim",
                "subtype": "insufficient_evidence_support",
            }
        ],
        "other_findings": [
            {
                "finding_id": "finding-002",
                "finding_type": "temporal_uncertainty",
                "subtype": "missing_event_time",
            }
        ],
    }

    (case_dir / "final_investigation_report.json").write_text(
        json.dumps(
            report,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    gold = build_gold_label_template(case_dir)

    assert gold.case_id == "case-001"

    assert {label.finding_id for label in gold.finding_labels} == {
        "finding-001",
        "finding-002",
    }

    assert all(
        label.disposition == GoldFindingDisposition.NOT_EVALUATED for label in gold.finding_labels
    )

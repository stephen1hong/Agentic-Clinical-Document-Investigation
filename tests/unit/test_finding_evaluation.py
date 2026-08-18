from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.evaluation.finding_evaluation import (
    evaluate_case_findings,
)
from clinical_investigation.evaluation.models import (
    GoldCaseLabel,
    GoldFindingDisposition,
    GoldFindingLabel,
)
from clinical_investigation.evaluation.persistence import (
    persist_gold_labels,
)


def test_evaluate_case_findings_persists_result(
    tmp_path: Path,
) -> None:
    case_dir = tmp_path / "investigation" / "case-001"

    gold_dir = tmp_path / "gold" / "case-001"

    output_dir = tmp_path / "results" / "case-001"

    case_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    report = {
        "case_id": "case-001",
        "high_priority_findings": [
            {
                "finding_id": "finding-001",
                "finding_type": "unsupported_claim",
                "subtype": "insufficient_evidence_support",
                "severity": "medium",
                "requires_human_review": True,
            }
        ],
        "other_findings": [],
    }

    (case_dir / "final_investigation_report.json").write_text(
        json.dumps(
            report,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    gold = GoldCaseLabel(
        case_id="case-001",
        finding_labels=[
            GoldFindingLabel(
                finding_id="finding-001",
                disposition=(GoldFindingDisposition.TRUE_POSITIVE),
            )
        ],
    )

    persist_gold_labels(
        output_dir=gold_dir,
        gold_labels=gold,
    )

    result = evaluate_case_findings(
        case_dir=case_dir,
        gold_label_dir=gold_dir,
        output_dir=output_dir,
    )

    assert result.case_id == "case-001"
    assert result.overall.total_findings == 1
    assert result.overall.true_positive_count == 1
    assert result.overall.precision == 1.0

    assert (output_dir / "finding_evaluation.json").exists()

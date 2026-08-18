from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.evaluation.models import (
    EvidenceSupportLabel,
    GoldCaseLabel,
    GoldFindingDisposition,
    GoldFindingLabel,
)
from clinical_investigation.evaluation.persistence import (
    load_gold_labels,
    persist_gold_labels,
)


def test_gold_case_label_defaults() -> None:
    """Gold case should start with empty evaluation collections."""

    gold = GoldCaseLabel(case_id="case-001")

    assert gold.case_id == "case-001"
    assert gold.finding_labels == []
    assert gold.timeline_labels == []
    assert gold.medication_labels == []


def test_gold_finding_label() -> None:
    """Finding labels should preserve evaluation judgments."""

    label = GoldFindingLabel(
        finding_id="finding-001",
        disposition=(GoldFindingDisposition.TRUE_POSITIVE),
        evidence_support=(EvidenceSupportLabel.SUPPORTED),
    )

    assert label.disposition == GoldFindingDisposition.TRUE_POSITIVE

    assert label.evidence_support == EvidenceSupportLabel.SUPPORTED


def test_gold_labels_round_trip(
    tmp_path: Path,
) -> None:
    """Persisted gold labels should round-trip without changes."""

    gold = GoldCaseLabel(
        case_id="case-001",
        evaluator="reviewer-a",
        finding_labels=[
            GoldFindingLabel(
                finding_id="finding-001",
                disposition=(GoldFindingDisposition.TRUE_POSITIVE),
            )
        ],
    )

    path = persist_gold_labels(
        output_dir=tmp_path,
        gold_labels=gold,
    )

    assert path.exists()

    persisted_payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    assert persisted_payload == (
        gold.model_dump(
            mode="json",
        )
    )

    loaded = load_gold_labels(path)

    assert loaded == gold

from __future__ import annotations

import json
from pathlib import Path

from clinical_investigation.evaluation.annotation_context import (
    extract_records,
    format_clinical_claim,
    format_evidence_item,
    index_records,
    load_clinical_claims,
    load_evidence_items,
    resolve_records,
)


def test_extract_records_from_list() -> None:
    payload = [
        {
            "evidence_id": "evidence-001",
        }
    ]

    records = extract_records(
        payload,
        wrapper_keys=("evidence_items",),
    )

    assert len(records) == 1


def test_extract_records_from_wrapper() -> None:
    payload = {
        "evidence_items": [
            {
                "evidence_id": "evidence-001",
            }
        ]
    }

    records = extract_records(
        payload,
        wrapper_keys=("evidence_items",),
    )

    assert len(records) == 1


def test_index_and_resolve_records() -> None:
    records = [
        {
            "evidence_id": "evidence-001",
            "text": "First evidence.",
        },
        {
            "evidence_id": "evidence-002",
            "text": "Second evidence.",
        },
    ]

    index = index_records(
        records,
        id_field="evidence_id",
    )

    resolved = resolve_records(
        [
            "evidence-002",
            "evidence-001",
        ],
        index=index,
    )

    assert [item["evidence_id"] for item in resolved] == [
        "evidence-002",
        "evidence-001",
    ]


def test_load_evidence_items(
    tmp_path: Path,
) -> None:
    payload = [
        {
            "evidence_id": "evidence-001",
            "text": "Evidence text.",
        }
    ]

    (tmp_path / "evidence_items.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    records = load_evidence_items(tmp_path)

    assert len(records) == 1
    assert records[0]["evidence_id"] == "evidence-001"


def test_load_clinical_claims(
    tmp_path: Path,
) -> None:
    payload = [
        {
            "claim_id": "claim-001",
            "claim_text": "Clinical claim.",
        }
    ]

    (tmp_path / "clinical_claims.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    records = load_clinical_claims(tmp_path)

    assert len(records) == 1
    assert records[0]["claim_id"] == "claim-001"


def test_format_evidence_item_contains_text() -> None:
    rendered = format_evidence_item(
        {
            "evidence_id": "evidence-001",
            "document_type": "discharge_summary",
            "section": "Medications",
            "text": "Simvastatin was discontinued.",
        }
    )

    assert "evidence-001" in rendered
    assert "discharge_summary" in rendered
    assert "Medications" in rendered
    assert "Simvastatin was discontinued." in rendered


def test_format_clinical_claim_contains_text() -> None:
    rendered = format_clinical_claim(
        {
            "claim_id": "claim-001",
            "claim_type": "medication",
            "claim_text": ("Simvastatin remained active."),
        }
    )

    assert "claim-001" in rendered
    assert "medication" in rendered
    assert "Simvastatin remained active." in rendered

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVIDENCE_FILENAME = "evidence_items.json"
CLAIMS_FILENAME = "clinical_claims.json"


def load_json(path: Path) -> Any:
    """Load JSON from disk."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def extract_records(
    payload: Any,
    *,
    wrapper_keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Extract records from either a list or wrapped JSON object."""

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        for key in wrapper_keys:
            value = payload.get(key)

            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    return []


def load_evidence_items(
    case_dir: Path,
) -> list[dict[str, Any]]:
    """Load evidence items for one investigation case."""

    path = case_dir / EVIDENCE_FILENAME

    if not path.exists():
        return []

    payload = load_json(path)

    return extract_records(
        payload,
        wrapper_keys=(
            "evidence_items",
            "evidence",
            "items",
        ),
    )


def load_clinical_claims(
    case_dir: Path,
) -> list[dict[str, Any]]:
    """Load clinical claims for one investigation case."""

    path = case_dir / CLAIMS_FILENAME

    if not path.exists():
        return []

    payload = load_json(path)

    return extract_records(
        payload,
        wrapper_keys=(
            "clinical_claims",
            "claims",
            "items",
        ),
    )


def index_records(
    records: list[dict[str, Any]],
    *,
    id_field: str,
) -> dict[str, dict[str, Any]]:
    """Index records by their identifier."""

    indexed: dict[str, dict[str, Any]] = {}

    for record in records:
        record_id = record.get(id_field)

        if record_id is None:
            continue

        indexed[str(record_id)] = record

    return indexed


def resolve_records(
    record_ids: list[str],
    *,
    index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve record IDs while preserving requested order."""

    return [index[record_id] for record_id in record_ids if record_id in index]


def first_text_value(
    record: dict[str, Any],
    *keys: str,
) -> str:
    """Return the first non-empty scalar text field."""

    for key in keys:
        value = record.get(key)

        if value is None:
            continue

        text = str(value).strip()

        if text:
            return text

    return ""


def format_evidence_item(
    evidence: dict[str, Any],
) -> str:
    """Render one evidence item for CLI display."""

    evidence_id = first_text_value(
        evidence,
        "evidence_id",
    )

    document_type = first_text_value(
        evidence,
        "document_type",
        "source_type",
    )

    source_document = first_text_value(
        evidence,
        "source_file",
        "source_document",
        "document_name",
        "filename",
        "document",
    )

    section = first_text_value(
        evidence,
        "section",
        "section_name",
    )

    location = first_text_value(
        evidence,
        "source_line",
        "source_location",
        "location",
        "line_range",
    )

    text = first_text_value(
        evidence,
        "text_span",
        "normalized_fact",
        "text",
        "evidence_text",
        "content",
        "snippet",
        "source_text",
    )

    lines = [
        f"Evidence ID: {evidence_id or '(unknown)'}",
    ]

    if document_type:
        lines.append(f"Document type: {document_type}")

    if source_document:
        lines.append(f"Source document: {source_document}")

    if section:
        lines.append(f"Section: {section}")

    if location:
        lines.append(f"Location: {location}")

    lines.extend(
        [
            "Evidence text:",
            text or "(text field unavailable)",
        ]
    )

    return "\n".join(lines)


def format_clinical_claim(
    claim: dict[str, Any],
) -> str:
    """Render one clinical claim for CLI display."""

    claim_id = first_text_value(
        claim,
        "claim_id",
    )

    claim_type = first_text_value(
        claim,
        "claim_type",
        "type",
    )

    document_type = first_text_value(
        claim,
        "document_type",
    )

    section = first_text_value(
        claim,
        "section",
        "section_name",
    )

    text = first_text_value(
        claim,
        "claim_text",
        "text",
        "content",
        "statement",
    )

    if not text:
        subject = first_text_value(
            claim,
            "subject",
        )

        predicate = first_text_value(
            claim,
            "predicate",
        )

        value = first_text_value(
            claim,
            "value",
        )

        text = " ".join(
            part
            for part in (
                subject,
                predicate,
                value,
            )
            if part
        )

    lines = [
        f"Claim ID: {claim_id or '(unknown)'}",
    ]

    if claim_type:
        lines.append(f"Claim type: {claim_type}")

    if document_type:
        lines.append(f"Document type: {document_type}")

    if section:
        lines.append(f"Section: {section}")

    lines.extend(
        [
            "Claim text:",
            text or "(text field unavailable)",
        ]
    )

    return "\n".join(lines)

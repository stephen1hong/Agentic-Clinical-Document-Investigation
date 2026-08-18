"""Validate extracted evidence and clinical claims."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from clinical_investigation.investigation.models import (
    ClinicalClaim,
    DocumentType,
    EvidenceItem,
    ExtractionManifest,
)

REQUIRED_FILES = {
    "evidence_items.json",
    "clinical_claims.json",
    "extraction_manifest.json",
}


def read_json(path: Path) -> Any:
    """Read one JSON file."""

    return json.loads(path.read_text(encoding="utf-8"))


def validate_investigation_case(
    case_dir: Path,
) -> list[str]:
    """Validate one extracted investigation case."""

    errors: list[str] = []

    existing_files = {path.name for path in case_dir.iterdir() if path.is_file()}

    missing_files = REQUIRED_FILES - existing_files

    for filename in sorted(missing_files):
        errors.append(f"Missing required file: {filename}")

    if errors:
        return errors

    try:
        raw_evidence = read_json(case_dir / "evidence_items.json")
        raw_claims = read_json(case_dir / "clinical_claims.json")
        raw_manifest = read_json(case_dir / "extraction_manifest.json")
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON: {exc}"]

    if not isinstance(raw_evidence, list):
        errors.append("evidence_items.json must contain a list")
        return errors

    if not isinstance(raw_claims, list):
        errors.append("clinical_claims.json must contain a list")
        return errors

    evidence_items: list[EvidenceItem] = []
    claims: list[ClinicalClaim] = []

    for index, payload in enumerate(raw_evidence):
        try:
            evidence_items.append(EvidenceItem.model_validate(payload))
        except ValidationError as exc:
            errors.append(f"Invalid evidence item {index}: {exc}")

    for index, payload in enumerate(raw_claims):
        try:
            claims.append(ClinicalClaim.model_validate(payload))
        except ValidationError as exc:
            errors.append(f"Invalid clinical claim {index}: {exc}")

    try:
        manifest = ExtractionManifest.model_validate(raw_manifest)
    except ValidationError as exc:
        errors.append(f"Invalid extraction manifest: {exc}")
        return errors

    case_id = case_dir.name

    if manifest.case_id != case_id:
        errors.append("Manifest case_id does not match the directory name")

    evidence_ids = [item.evidence_id for item in evidence_items]

    if len(evidence_ids) != len(set(evidence_ids)):
        errors.append("Duplicate evidence IDs found")

    claim_ids = [claim.claim_id for claim in claims]

    if len(claim_ids) != len(set(claim_ids)):
        errors.append("Duplicate claim IDs found")

    evidence_id_set = set(evidence_ids)

    for claim in claims:
        missing_evidence_ids = set(claim.source_evidence_ids) - evidence_id_set

        if missing_evidence_ids:
            errors.append(
                f"Claim {claim.claim_id} references "
                "missing evidence IDs: "
                f"{sorted(missing_evidence_ids)}"
            )

    evidence_document_types = {item.document_type for item in evidence_items}

    expected_document_types = set(DocumentType)

    missing_document_types = expected_document_types - evidence_document_types

    for document_type in sorted(
        missing_document_types,
        key=lambda item: item.value,
    ):
        errors.append(f"No evidence extracted from document: {document_type.value}")

    if manifest.evidence_count != len(evidence_items):
        errors.append("Manifest evidence_count does not match evidence_items.json")

    if manifest.claim_count != len(claims):
        errors.append("Manifest claim_count does not match clinical_claims.json")

    for evidence in evidence_items:
        if evidence.source_table is not None and evidence.source_row is None:
            errors.append(
                f"Evidence {evidence.evidence_id} has a source table but no valid source row"
            )

    return errors

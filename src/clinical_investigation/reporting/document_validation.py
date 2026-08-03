"""Validate generated clinical document sets."""

import json
from pathlib import Path
from typing import Any

REQUIRED_DOCUMENTS = {
    "admission_note.md",
    "progress_note.md",
    "lab_report.md",
    "medication_reconciliation.md",
    "discharge_summary.md",
    "follow_up_note.md",
    "document_index.json",
    "manifest.json",
}


def read_json(path: Path) -> Any:
    """Read one JSON file."""

    return json.loads(path.read_text(encoding="utf-8"))


def validate_document_set(
    document_dir: Path,
) -> list[str]:
    """Validate one generated clinical document directory."""

    errors: list[str] = []

    existing_files = {path.name for path in document_dir.iterdir() if path.is_file()}

    missing = REQUIRED_DOCUMENTS - existing_files

    for filename in sorted(missing):
        errors.append(f"Missing required file: {filename}")

    if errors:
        return errors

    index = read_json(document_dir / "document_index.json")

    manifest = read_json(document_dir / "manifest.json")

    case_id = document_dir.name

    if index.get("case_id") != case_id:
        errors.append("document_index.json case_id mismatch")

    if manifest.get("case_id") != case_id:
        errors.append("manifest.json case_id mismatch")

    documents = index.get("documents")

    if not isinstance(documents, list):
        errors.append("document_index.json documents must be a list")
        return errors

    if len(documents) != 6:
        errors.append(f"Expected 6 documents, found {len(documents)}")

    for item in documents:
        filename = item.get("filename")

        if not filename:
            errors.append("Document index entry has no filename")
            continue

        path = document_dir / filename

        if not path.exists():
            errors.append(f"Indexed document does not exist: {filename}")
            continue

        text = path.read_text(encoding="utf-8")

        if not text.strip():
            errors.append(f"Document is empty: {filename}")

        if "Synthetic clinical document" not in text:
            errors.append(f"Synthetic-data disclaimer missing: {filename}")

    lab_text = (document_dir / "lab_report.md").read_text(encoding="utf-8")

    if "Explicitly flagged abnormal" not in lab_text:
        errors.append("Lab report does not use the required abnormality wording")

    return errors

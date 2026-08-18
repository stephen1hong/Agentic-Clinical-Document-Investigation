"""Validate medication mutation evaluation data."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from clinical_investigation.evaluation.medication_mutation_models import (
    GoldMedicationDiscrepancy,
    MutationRecord,
)


def validate_mutation_dataset(
    *,
    mutation_cases_root: Path,
    mutation_records_path: Path,
    gold_discrepancies_path: Path,
) -> list[str]:
    """Validate mutation cases and gold labels."""

    errors: list[str] = []

    try:
        mutation_payload = json.loads(mutation_records_path.read_text(encoding="utf-8"))

        gold_payload = json.loads(gold_discrepancies_path.read_text(encoding="utf-8"))
    except (
        FileNotFoundError,
        json.JSONDecodeError,
    ) as exc:
        return [str(exc)]

    try:
        mutations = [MutationRecord.model_validate(item) for item in mutation_payload]

        gold_records = [GoldMedicationDiscrepancy.model_validate(item) for item in gold_payload]
    except ValidationError as exc:
        return [f"Mutation schema validation failed: {exc}"]

    mutation_ids = {item.mutation_id for item in mutations}

    if len(mutation_ids) != len(mutations):
        errors.append("Duplicate mutation IDs found")

    gold_ids = {item.gold_id for item in gold_records}

    if len(gold_ids) != len(gold_records):
        errors.append("Duplicate gold IDs found")

    for gold in gold_records:
        if gold.mutation_id not in mutation_ids:
            errors.append(f"Gold record {gold.gold_id} references a missing mutation")

    required_documents = {
        "admission_note.md",
        "progress_note.md",
        "lab_report.md",
        "medication_reconciliation.md",
        "discharge_summary.md",
        "follow_up_note.md",
    }

    for mutation in mutations:
        case_dir = mutation_cases_root / mutation.mutation_case_id

        documents_dir = case_dir / "documents"

        if not documents_dir.exists():
            errors.append(f"Missing documents directory: {documents_dir}")
            continue

        existing = {path.name for path in documents_dir.iterdir() if path.is_file()}

        missing = required_documents - existing

        if missing:
            errors.append(f"{mutation.mutation_case_id} is missing documents: {sorted(missing)}")

        mutation_record_path = case_dir / "mutation_record.json"

        if not mutation_record_path.exists():
            errors.append(f"Missing mutation_record.json for {mutation.mutation_case_id}")

    return errors

"""Generate controlled medication discrepancies."""

from __future__ import annotations

import json
import random
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from clinical_investigation.evaluation.medication_mutation_models import (
    GoldDiscrepancyType,
    GoldMedicationDiscrepancy,
    MedicationMutationType,
    MutationRecord,
)
from clinical_investigation.investigation.medication_reconciliation import (
    normalize_medication_name,
)


class MedicationMutationError(RuntimeError):
    """Raised when mutation generation fails."""


MEDICATION_DOCUMENT_FILES = (
    "admission_note.md",
    "progress_note.md",
    "medication_reconciliation.md",
    "discharge_summary.md",
    "follow_up_note.md",
)


MEDICATION_LINE_PATTERN = re.compile(
    r"(?i)\b("
    r"active|continued|started|stopped|"
    r"discontinued"
    r")\b"
)

DOSE_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*"
    r"(?:mg|mcg|g|ml|units?|iu)\b",
    flags=re.IGNORECASE,
)


def stable_identifier(
    namespace: str,
    *parts: object,
) -> str:
    """Create deterministic identifiers."""

    payload = "|".join(str(part) for part in parts)

    return str(
        uuid5(
            NAMESPACE_URL,
            f"{namespace}:{payload}",
        )
    )


def read_json(path: Path) -> Any:
    """Read JSON."""

    return json.loads(path.read_text(encoding="utf-8"))


def write_json(
    path: Path,
    payload: Any,
) -> None:
    """Write formatted JSON."""

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


def copy_case_documents(
    source_dir: Path,
    target_dir: Path,
) -> None:
    """Copy generated clinical documents into a mutation case."""

    required_documents = (
        "admission_note.md",
        "progress_note.md",
        "lab_report.md",
        "medication_reconciliation.md",
        "discharge_summary.md",
        "follow_up_note.md",
    )

    if not source_dir.exists():
        raise MedicationMutationError(f"Source document directory does not exist: {source_dir}")

    if not source_dir.is_dir():
        raise MedicationMutationError(f"Source document path is not a directory: {source_dir}")

    missing_documents = [
        filename for filename in required_documents if not (source_dir / filename).is_file()
    ]

    if missing_documents:
        raise MedicationMutationError(
            f"Source case {source_dir.name} is missing "
            f"required documents: {missing_documents}. "
            f"Source directory: {source_dir}"
        )

    if target_dir.exists():
        shutil.rmtree(target_dir)

    target_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for filename in required_documents:
        source_file = source_dir / filename

        target_file = target_dir / filename

        shutil.copy2(
            source_file,
            target_file,
        )


def load_medication_mentions(
    investigation_case_dir: Path,
) -> list[dict[str, Any]]:
    """Load medication mentions from a clean case."""

    path = investigation_case_dir / "medication_mentions.json"

    if not path.exists():
        raise MedicationMutationError(f"Missing medication mentions: {path}")

    payload = read_json(path)

    if not isinstance(payload, list):
        raise MedicationMutationError("medication_mentions.json must contain a list")

    return payload


def eligible_mentions(
    mentions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return document-backed medication mutation candidates."""

    return [
        mention
        for mention in mentions
        if (
            mention.get("document_type")
            in {
                "admission_note",
                "progress_note",
                "medication_reconciliation",
                "discharge_summary",
                "follow_up_note",
            }
            and mention.get("normalized_key")
            and mention.get("medication_name_raw")
        )
    ]


def find_medication_lines(
    *,
    document_path: Path,
    medication_name: str,
) -> list[tuple[int, str]]:
    """Find lines containing a medication name."""

    text = document_path.read_text(encoding="utf-8")

    normalized_name, _ = normalize_medication_name(medication_name)

    search_terms = {
        medication_name.lower(),
        normalized_name.lower(),
    }

    matches: list[tuple[int, str]] = []

    for line_number, line in enumerate(
        text.splitlines(),
        start=1,
    ):
        lower_line = line.lower()

        if any(term and term in lower_line for term in search_terms):
            matches.append(
                (
                    line_number,
                    line,
                )
            )

    return matches


def replace_line(
    *,
    document_path: Path,
    line_number: int,
    replacement: str,
) -> None:
    """Replace one one-based document line."""

    lines = document_path.read_text(encoding="utf-8").splitlines()

    index = line_number - 1

    if index < 0 or index >= len(lines):
        raise MedicationMutationError(f"Invalid line number {line_number}")

    lines[index] = replacement

    document_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def remove_line(
    *,
    document_path: Path,
    line_number: int,
) -> str:
    """Remove one one-based document line."""

    lines = document_path.read_text(encoding="utf-8").splitlines()

    index = line_number - 1

    if index < 0 or index >= len(lines):
        raise MedicationMutationError(f"Invalid line number {line_number}")

    removed = lines.pop(index)

    document_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return removed


STATUS_REPLACEMENTS = {
    "active": "stopped",
    "continued": "stopped",
    "started": "stopped",
    "stopped": "active",
    "discontinued": "active",
}


def mutate_status_flip(
    *,
    document_path: Path,
    medication_name: str,
) -> tuple[int, str, str]:
    """Flip one explicit medication lifecycle status."""

    candidates = find_medication_lines(
        document_path=document_path,
        medication_name=medication_name,
    )

    for line_number, original_line in candidates:
        match = MEDICATION_LINE_PATTERN.search(original_line)

        if match is None:
            continue

        original_status = match.group(1).lower()

        replacement_status = STATUS_REPLACEMENTS[original_status]

        mutated_line = (
            original_line[: match.start()] + replacement_status + original_line[match.end() :]
        )

        replace_line(
            document_path=document_path,
            line_number=line_number,
            replacement=mutated_line,
        )

        return (
            line_number,
            original_line,
            mutated_line,
        )

    raise MedicationMutationError(
        f"No status-bearing medication line found for {medication_name} in {document_path}"
    )


def mutate_remove_from_discharge(
    *,
    document_path: Path,
    medication_name: str,
) -> tuple[int, str, None]:
    """Remove one medication from discharge documentation."""

    candidates = find_medication_lines(
        document_path=document_path,
        medication_name=medication_name,
    )

    if not candidates:
        raise MedicationMutationError(f"No discharge medication line found for {medication_name}")

    line_number, _ = candidates[0]

    removed_line = remove_line(
        document_path=document_path,
        line_number=line_number,
    )

    return (
        line_number,
        removed_line,
        None,
    )


def mutate_dose_change(
    *,
    document_path: Path,
    medication_name: str,
) -> tuple[int, str, str]:
    """Change an explicit dose while preserving the medication."""

    candidates = find_medication_lines(
        document_path=document_path,
        medication_name=medication_name,
    )

    for line_number, original_line in candidates:
        dose_match = DOSE_PATTERN.search(original_line)

        if dose_match is None:
            continue

        original_dose = dose_match.group(0)

        numeric_match = re.search(
            r"\d+(?:\.\d+)?",
            original_dose,
        )

        if numeric_match is None:
            continue

        original_value = float(numeric_match.group(0))

        mutated_value = original_value * 2 if original_value > 0 else 1.0

        if mutated_value.is_integer():
            mutated_number = str(int(mutated_value))
        else:
            mutated_number = str(mutated_value)

        mutated_dose = (
            original_dose[: numeric_match.start()]
            + mutated_number
            + original_dose[numeric_match.end() :]
        )

        mutated_line = (
            original_line[: dose_match.start()] + mutated_dose + original_line[dose_match.end() :]
        )

        replace_line(
            document_path=document_path,
            line_number=line_number,
            replacement=mutated_line,
        )

        return (
            line_number,
            original_line,
            mutated_line,
        )

    raise MedicationMutationError(
        f"No explicit dose found for {medication_name} in {document_path}"
    )


SYNTHETIC_DISCHARGE_MEDICATIONS = (
    "MutationDrugAlpha 10 mg oral daily active",
    "MutationDrugBeta 5 mg oral daily active",
    "MutationDrugGamma 20 mg oral daily active",
)


def mutate_add_discharge_only_medication(
    *,
    document_path: Path,
    random_generator: random.Random,
) -> tuple[int, None, str, str]:
    """Append a synthetic discharge-only medication."""

    medication_text = random_generator.choice(SYNTHETIC_DISCHARGE_MEDICATIONS)

    text = document_path.read_text(encoding="utf-8")

    lines = text.splitlines()

    inserted_line = f"- {medication_text} [Synthetic mutation]"

    lines.append(inserted_line)

    document_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    medication_name = medication_text.split(
        " ",
        maxsplit=1,
    )[0]

    return (
        len(lines),
        None,
        inserted_line,
        medication_name,
    )


def mutation_expected_discrepancy(
    mutation_type: MedicationMutationType,
) -> GoldDiscrepancyType:
    """Map mutations to expected discrepancy labels."""

    mapping = {
        MedicationMutationType.STATUS_FLIP: (GoldDiscrepancyType.CONFLICTING_STATUS),
        MedicationMutationType.REMOVE_FROM_DISCHARGE: (GoldDiscrepancyType.MISSING_AT_DISCHARGE),
        MedicationMutationType.DOSE_CHANGE: (GoldDiscrepancyType.DOSE_CONFLICT),
        MedicationMutationType.ADD_DISCHARGE_ONLY_MEDICATION: (
            GoldDiscrepancyType.DISCHARGE_ONLY_MEDICATION
        ),
    }

    return mapping[mutation_type]


def build_mutation_record(
    *,
    source_case_id: str,
    mutation_case_id: str,
    mutation_type: MedicationMutationType,
    medication_name: str,
    source_document: str,
    source_line: int,
    original_text: str | None,
    mutated_text: str | None,
    random_seed: int,
) -> tuple[
    MutationRecord,
    GoldMedicationDiscrepancy,
]:
    """Build mutation metadata and gold label."""

    normalized_name, normalized_key = normalize_medication_name(medication_name)

    mutation_id = stable_identifier(
        "medication-mutation",
        mutation_case_id,
        mutation_type.value,
        normalized_key,
    )

    expected_type = mutation_expected_discrepancy(mutation_type)

    mutation = MutationRecord(
        mutation_id=mutation_id,
        mutation_case_id=mutation_case_id,
        source_case_id=source_case_id,
        mutation_type=mutation_type,
        medication_name=normalized_name,
        normalized_medication_key=(normalized_key),
        source_document=source_document,
        mutated_document=source_document,
        original_text=original_text,
        mutated_text=mutated_text,
        source_line=source_line,
        expected_discrepancy_type=(expected_type),
        generated_at=datetime.now(UTC),
        random_seed=random_seed,
    )

    gold_id = stable_identifier(
        "gold-medication-discrepancy",
        mutation_id,
        expected_type.value,
        normalized_key,
    )

    gold = GoldMedicationDiscrepancy(
        gold_id=gold_id,
        mutation_id=mutation_id,
        mutation_case_id=mutation_case_id,
        source_case_id=source_case_id,
        medication_name=normalized_name,
        medication_key=normalized_key,
        discrepancy_type=expected_type,
        source_document=source_document,
        expected_detected=True,
        rationale=(f"Mutation {mutation_type.value} was applied to {normalized_name}."),
    )

    return mutation, gold


def select_candidate_for_document(
    *,
    mentions: list[dict[str, Any]],
    document_type: str,
) -> dict[str, Any] | None:
    """Choose the first eligible mention for a document."""

    candidates = [mention for mention in mentions if mention.get("document_type") == document_type]

    if not candidates:
        return None

    return sorted(
        candidates,
        key=lambda item: (
            item.get("normalized_key", ""),
            item.get("mention_id", ""),
        ),
    )[0]


def generate_mutation_dataset(
    *,
    investigation_root: Path,
    source_documents_root: Path,
    output_cases_root: Path,
    gold_root: Path,
    mutations_per_case: int = 1,
    random_seed: int = 42,
) -> tuple[
    list[MutationRecord],
    list[GoldMedicationDiscrepancy],
]:
    """Generate deterministic medication mutation cases."""

    random_generator = random.Random(random_seed)

    mutation_records: list[MutationRecord] = []

    gold_records: list[GoldMedicationDiscrepancy] = []

    case_dirs = sorted(path for path in investigation_root.iterdir() if path.is_dir())

    mutation_types = list(MedicationMutationType)

    for case_index, investigation_case in enumerate(case_dirs):
        source_case_id = investigation_case.name

        source_document_dir = source_documents_root / source_case_id

        if not source_document_dir.exists():
            continue

        mentions = eligible_mentions(load_medication_mentions(investigation_case))

        if not mentions:
            continue

        for mutation_index in range(mutations_per_case):
            mutation_type = mutation_types[(case_index + mutation_index) % len(mutation_types)]

            mutation_case_id = (
                f"mut-{case_index + 1:03d}-{mutation_index + 1:02d}-{mutation_type.value}"
            )

            target_case_dir = output_cases_root / mutation_case_id

            target_documents_dir = target_case_dir / "documents"

            copy_case_documents(
                source_document_dir,
                target_documents_dir,
            )

            if mutation_type == MedicationMutationType.ADD_DISCHARGE_ONLY_MEDICATION:
                document_name = "discharge_summary.md"

                (
                    line_number,
                    original_text,
                    mutated_text,
                    medication_name,
                ) = mutate_add_discharge_only_medication(
                    document_path=(target_documents_dir / document_name),
                    random_generator=(random_generator),
                )

            else:
                if (mutation_type == MedicationMutationType.REMOVE_FROM_DISCHARGE) or (
                    mutation_type == MedicationMutationType.DOSE_CHANGE
                ):
                    document_type = "discharge_summary"
                    document_name = "discharge_summary.md"

                else:
                    document_type = "medication_reconciliation"
                    document_name = "medication_reconciliation.md"

                candidate = select_candidate_for_document(
                    mentions=mentions,
                    document_type=document_type,
                )

                if candidate is None:
                    continue

                medication_name = candidate["medication_name_raw"]

                document_path = target_documents_dir / document_name

                try:
                    if mutation_type == MedicationMutationType.STATUS_FLIP:
                        (
                            line_number,
                            original_text,
                            mutated_text,
                        ) = mutate_status_flip(
                            document_path=document_path,
                            medication_name=medication_name,
                        )

                    elif mutation_type == MedicationMutationType.REMOVE_FROM_DISCHARGE:
                        (
                            line_number,
                            original_text,
                            mutated_text,
                        ) = mutate_remove_from_discharge(
                            document_path=document_path,
                            medication_name=(medication_name),
                        )

                    else:
                        (
                            line_number,
                            original_text,
                            mutated_text,
                        ) = mutate_dose_change(
                            document_path=document_path,
                            medication_name=medication_name,
                        )

                except MedicationMutationError:
                    shutil.rmtree(
                        target_case_dir,
                        ignore_errors=True,
                    )
                    continue

            mutation, gold = build_mutation_record(
                source_case_id=source_case_id,
                mutation_case_id=mutation_case_id,
                mutation_type=mutation_type,
                medication_name=medication_name,
                source_document=document_name,
                source_line=line_number,
                original_text=original_text,
                mutated_text=mutated_text,
                random_seed=random_seed,
            )

            write_json(
                target_case_dir / "mutation_record.json",
                mutation.model_dump(mode="json"),
            )

            mutation_records.append(mutation)
            gold_records.append(gold)

    write_json(
        gold_root / "mutation_records.json",
        [item.model_dump(mode="json") for item in mutation_records],
    )

    write_json(
        gold_root / "gold_discrepancies.json",
        [item.model_dump(mode="json") for item in gold_records],
    )

    return mutation_records, gold_records

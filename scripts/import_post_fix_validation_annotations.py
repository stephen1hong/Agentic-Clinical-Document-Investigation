from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "post_fix_validation_sample"
    / "annotation_review_proposed.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "post_fix_validation_sample" / "annotations.json"
)


EXPECTED_SAMPLE_SIZE = 80

VALID_CORRECTNESS_LABELS = {
    "true_positive",
    "false_positive",
    "partially_correct",
}

VALID_GROUNDING_LABELS = {
    "supported",
    "partially_supported",
    "unsupported",
}


def load_json(path: Path) -> Any:
    """Load a JSON file."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def validate_record(
    record: dict[str, Any],
) -> None:
    """Validate one approved adjudication record."""

    sample_index = record.get("sample_index")

    finding_id = record.get("finding_id")

    if not isinstance(sample_index, int):
        raise ValueError(f"Annotation record has invalid sample_index: {sample_index!r}")

    if not isinstance(finding_id, str) or not finding_id:
        raise ValueError(f"Sample {sample_index} has no valid finding_id.")

    adjudication = record.get("adjudication")

    if not isinstance(adjudication, dict):
        raise ValueError(f"Sample {sample_index} has no adjudication object.")

    correctness = adjudication.get("finding_correctness")

    grounding = adjudication.get("evidence_grounding")

    if correctness not in VALID_CORRECTNESS_LABELS:
        raise ValueError(
            f"Sample {sample_index} has invalid finding_correctness label: {correctness!r}"
        )

    if grounding not in VALID_GROUNDING_LABELS:
        raise ValueError(
            f"Sample {sample_index} has invalid evidence_grounding label: {grounding!r}"
        )

    notes = adjudication.get("review_notes")

    if not isinstance(notes, str) or not notes.strip():
        raise ValueError(f"Sample {sample_index} has no review_notes.")


def build_final_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    """Create compact final gold annotation record."""

    adjudication = record["adjudication"]

    return {
        "sample_index": record["sample_index"],
        "case_id": record["case_id"],
        "finding_id": record["finding_id"],
        "finding_type": record.get("finding_type"),
        "subtype": record.get("subtype"),
        "severity": record.get("severity"),
        "finding_correctness": (adjudication["finding_correctness"]),
        "evidence_grounding": (adjudication["evidence_grounding"]),
        "review_notes": adjudication["review_notes"],
    }


def main() -> int:
    """Import approved post-fix annotations."""

    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Approved proposal file not found: {INPUT_PATH}")

    source = load_json(INPUT_PATH)

    if not isinstance(source, dict):
        raise ValueError("Expected annotation proposal to be a JSON object.")

    records = source.get("records")

    if not isinstance(records, list):
        raise ValueError("Annotation proposal does not contain a records list.")

    if len(records) != EXPECTED_SAMPLE_SIZE:
        raise ValueError(
            f"Unexpected annotation count. Expected {EXPECTED_SAMPLE_SIZE}, found {len(records)}."
        )

    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Annotation records must be JSON objects.")

        validate_record(record)

    sample_indices = [record["sample_index"] for record in records]

    if len(set(sample_indices)) != len(sample_indices):
        raise ValueError("Duplicate sample_index values were found.")

    finding_ids = [record["finding_id"] for record in records]

    if len(set(finding_ids)) != len(finding_ids):
        raise ValueError("Duplicate finding_id values were found.")

    final_records = [
        build_final_record(record)
        for record in sorted(
            records,
            key=lambda item: item["sample_index"],
        )
    ]

    correctness_counts = Counter(record["finding_correctness"] for record in final_records)

    grounding_counts = Counter(record["evidence_grounding"] for record in final_records)

    subtype_counts = Counter(str(record["subtype"]) for record in final_records)

    finding_type_counts = Counter(str(record["finding_type"]) for record in final_records)

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8C.6.3",
        "annotation_status": "final_approved",
        "annotation_method": (
            "Fresh post-fix AI-assisted, "
            "human-approved adjudication of "
            "finding correctness and evidence "
            "grounding."
        ),
        "approved_at": datetime.now(UTC).isoformat(),
        "sample_size": len(final_records),
        "summary": {
            "finding_correctness": dict(sorted(correctness_counts.items())),
            "evidence_grounding": dict(sorted(grounding_counts.items())),
            "finding_types": dict(sorted(finding_type_counts.items())),
            "subtypes": dict(sorted(subtype_counts.items())),
        },
        "records": final_records,
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("STEP 8C.6.3 FINAL APPROVED ANNOTATIONS")
    print("=" * 72)

    print(f"Annotations imported:         {len(final_records)}")

    print()
    print("Finding correctness")
    print("-" * 72)

    for label in (
        "true_positive",
        "partially_correct",
        "false_positive",
    ):
        print(f"{label:<28}{correctness_counts[label]:>6}")

    print()
    print("Evidence grounding")
    print("-" * 72)

    for label in (
        "supported",
        "partially_supported",
        "unsupported",
    ):
        print(f"{label:<28}{grounding_counts[label]:>6}")

    print()
    print("Subtype distribution")
    print("-" * 72)

    for subtype, count in sorted(subtype_counts.items()):
        print(f"{subtype:<36}{count:>6}")

    print()
    print("Saved final annotations to:")
    print(OUTPUT_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

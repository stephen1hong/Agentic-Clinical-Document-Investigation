from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SAMPLE_PATH = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "post_fix_validation_sample"
    / "finding_sample_manifest.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "post_fix_validation_sample" / "annotation_review.json"
)


CASE_ARTIFACTS = (
    "evidence_items.json",
    "clinical_claims.json",
    "canonical_timeline.json",
    "medication_mentions.json",
    "medication_profiles.json",
    "medication_discrepancies.json",
)


ID_FIELDS = (
    "evidence_ids",
    "claim_ids",
    "source_claim_ids",
    "timeline_event_ids",
    "event_ids",
    "mention_ids",
    "profile_ids",
    "discrepancy_ids",
)


CORRECTNESS_LABELS = (
    "true_positive",
    "false_positive",
    "partially_correct",
)

GROUNDING_LABELS = (
    "supported",
    "partially_supported",
    "unsupported",
)


def load_json(path: Path) -> Any:
    """Load a JSON artifact."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def flatten_records(value: Any) -> list[dict[str, Any]]:
    """Return dictionaries contained in a top-level JSON structure."""

    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]

    if isinstance(value, dict):
        for key in (
            "events",
            "records",
            "items",
            "claims",
            "findings",
            "mentions",
            "profiles",
            "discrepancies",
        ):
            nested = value.get(key)

            if isinstance(nested, list):
                return [item for item in nested if isinstance(item, dict)]

        return [value]

    return []


def iter_strings(value: Any) -> Iterable[str]:
    """Yield strings recursively from nested JSON."""

    if isinstance(value, str):
        yield value
        return

    if isinstance(value, list):
        for item in value:
            yield from iter_strings(item)

    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)


def collect_explicit_ids(
    value: Any,
) -> set[str]:
    """Collect IDs explicitly referenced by a finding."""

    collected: set[str] = set()

    if not isinstance(value, dict):
        return collected

    for key, item in value.items():
        if key in ID_FIELDS:
            if isinstance(item, str):
                if item:
                    collected.add(item)

            elif isinstance(item, list):
                collected.update(str(entry) for entry in item if entry)

        if isinstance(item, dict):
            collected.update(collect_explicit_ids(item))

        elif isinstance(item, list):
            for entry in item:
                if isinstance(entry, dict):
                    collected.update(collect_explicit_ids(entry))

    return collected


def record_identifiers(
    record: dict[str, Any],
) -> set[str]:
    """Collect identifier-looking values from one source record."""

    identifiers: set[str] = set()

    for key, value in record.items():
        if key == "id" or key.endswith("_id") or key.endswith("_ids"):
            if isinstance(value, str):
                if value:
                    identifiers.add(value)

            elif isinstance(value, list):
                identifiers.update(str(item) for item in value if item)

    return identifiers


def resolve_referenced_records(
    *,
    finding: dict[str, Any],
    case_dir: Path,
) -> dict[str, list[dict[str, Any]]]:
    """Resolve records explicitly referenced by the sampled finding."""

    explicit_ids = collect_explicit_ids(finding)

    resolved: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for filename in CASE_ARTIFACTS:
        artifact_path = case_dir / filename

        if not artifact_path.exists():
            resolved[filename] = []
            continue

        records = flatten_records(load_json(artifact_path))

        if explicit_ids:
            matches = [record for record in records if (record_identifiers(record) & explicit_ids)]
        else:
            matches = []

        resolved[filename] = matches

    return resolved


def medication_name_candidates(
    finding: dict[str, Any],
) -> set[str]:
    """Extract useful medication-name strings from a finding."""

    values: set[str] = set()

    for key in (
        "medication_name",
        "normalized_name",
        "subject",
    ):
        value = finding.get(key)

        if isinstance(value, str) and value.strip():
            values.add(value.strip().lower())

    return values


def add_medication_context(
    *,
    finding: dict[str, Any],
    case_dir: Path,
    context: dict[str, list[dict[str, Any]]],
) -> None:
    """
    Add medication records for medication-discrepancy findings.

    This supplements explicit-ID resolution without replacing it.
    """

    if finding.get("finding_type") != "medication_discrepancy":
        return

    candidates = medication_name_candidates(finding)

    for filename in (
        "medication_mentions.json",
        "medication_profiles.json",
        "medication_discrepancies.json",
    ):
        artifact_path = case_dir / filename

        if not artifact_path.exists():
            continue

        records = flatten_records(load_json(artifact_path))

        selected = list(
            context.get(
                filename,
                [],
            )
        )

        selected_ids = {id(record) for record in selected}

        for record in records:
            searchable = " ".join(iter_strings(record)).lower()

        if (
            any(candidate in searchable for candidate in candidates)
            and id(record) not in selected_ids
        ):
            selected.append(record)

        context[filename] = selected


def build_review_record(
    sample_record: dict[str, Any],
) -> dict[str, Any]:
    """Build one adjudication record."""

    case_id = str(sample_record["case_id"])

    case_dir = PROJECT_ROOT / "data" / "investigation_cases" / case_id

    finding = sample_record.get("finding")

    if not isinstance(finding, dict):
        raise ValueError("Sample record does not contain a valid finding object.")

    context = resolve_referenced_records(
        finding=finding,
        case_dir=case_dir,
    )

    add_medication_context(
        finding=finding,
        case_dir=case_dir,
        context=context,
    )

    return {
        "sample_index": sample_record["sample_index"],
        "case_id": case_id,
        "finding_id": sample_record["finding_id"],
        "finding_type": sample_record.get("finding_type"),
        "subtype": sample_record.get("subtype"),
        "severity": sample_record.get("severity"),
        "finding": finding,
        "review_context": context,
        "adjudication": {
            "finding_correctness": None,
            "evidence_grounding": None,
            "review_notes": None,
        },
    }


def main() -> int:
    """Export the fresh post-fix adjudication bundle."""

    if not SAMPLE_PATH.exists():
        raise FileNotFoundError(f"Sample manifest not found: {SAMPLE_PATH}")

    manifest = load_json(SAMPLE_PATH)

    if not isinstance(manifest, dict):
        raise ValueError("Expected sample manifest JSON object.")

    records = manifest.get("records")

    if not isinstance(records, list):
        raise ValueError("Sample manifest does not contain a records list.")

    if len(records) != 80:
        raise ValueError(f"Expected 80 fresh validation findings, found {len(records)}.")

    review_records = [build_review_record(record) for record in records if isinstance(record, dict)]

    if len(review_records) != 80:
        raise ValueError("Could not build all 80 review records.")

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8C.6.2",
        "evaluation_method": (
            "Fresh post-fix finding correctness and evidence-grounding adjudication."
        ),
        "finding_correctness_labels": list(CORRECTNESS_LABELS),
        "evidence_grounding_labels": list(GROUNDING_LABELS),
        "sample_size": len(review_records),
        "records": review_records,
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

    resolved_counts = {
        filename: sum(
            len(
                record["review_context"].get(
                    filename,
                    [],
                )
            )
            for record in review_records
        )
        for filename in CASE_ARTIFACTS
    }

    print()
    print("=" * 72)
    print("STEP 8C.6.2 POST-FIX ANNOTATION REVIEW EXPORT")
    print("=" * 72)

    print(f"Review records:               {len(review_records)}")

    print()
    print("Resolved context records")
    print("-" * 72)

    for filename, count in resolved_counts.items():
        print(f"{filename:<36}{count:>6}")

    print()
    print("Saved review artifact to:")
    print(OUTPUT_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

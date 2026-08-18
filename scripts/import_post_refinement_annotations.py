from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

VALID_DISPOSITIONS = {
    "true_positive",
    "false_positive",
    "partially_correct",
    "not_evaluated",
}

VALID_EVIDENCE_SUPPORT = {
    "supported",
    "partially_supported",
    "unsupported",
    "not_evaluated",
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Import approved post-refinement batch-review annotations "
            "into the standard finding-sample annotation artifact."
        )
    )

    parser.add_argument(
        "--evaluator",
        default="Steve",
        help="Evaluator name or identifier.",
    )

    return parser.parse_args()


def project_root() -> Path:
    """Return repository root."""

    return Path(__file__).resolve().parents[1]


def load_json(
    path: Path,
) -> dict[str, Any]:
    """Load a JSON object."""

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")

    return payload


def main() -> int:
    """Import approved post-refinement annotations."""

    args = parse_args()

    root = project_root()

    sample_dir = root / "data" / "evaluation" / "post_refinement_sample"

    review_path = sample_dir / "annotation_review_proposed.json"

    manifest_path = sample_dir / "finding_sample_manifest.json"

    output_path = sample_dir / "finding_sample_annotations.json"

    if not review_path.exists():
        print(f"Approved review file not found: {review_path}")
        return 1

    if not manifest_path.exists():
        print(f"Sample manifest not found: {manifest_path}")
        return 1

    review = load_json(review_path)

    manifest = load_json(manifest_path)

    records = review.get(
        "records",
        [],
    )

    if not isinstance(records, list):
        raise ValueError("annotation_review_proposed.json must contain a records list.")

    manifest_findings = manifest.get(
        "findings",
        [],
    )

    if not isinstance(
        manifest_findings,
        list,
    ):
        raise ValueError("Manifest must contain a findings list.")

    expected_by_id = {
        str(record.get("finding_id")): record
        for record in manifest_findings
        if (isinstance(record, dict) and record.get("finding_id"))
    }

    annotations: list[dict[str, Any]] = []

    seen_ids: set[str] = set()
    seen_indices: set[int] = set()

    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Every review record must be a JSON object.")

        finding_id = str(
            record.get(
                "finding_id",
                "",
            )
        )

        if not finding_id:
            raise ValueError("Review record is missing finding_id.")

        if finding_id not in expected_by_id:
            raise ValueError(f"Unknown finding ID: {finding_id}")

        if finding_id in seen_ids:
            raise ValueError(f"Duplicate finding ID: {finding_id}")

        seen_ids.add(finding_id)

        sample_index = int(
            record.get(
                "sample_index",
                0,
            )
        )

        if sample_index <= 0:
            raise ValueError(f"Invalid sample index for {finding_id}")

        if sample_index in seen_indices:
            raise ValueError(f"Duplicate sample index: {sample_index}")

        seen_indices.add(sample_index)

        disposition = str(
            record.get(
                "disposition",
                "",
            )
        )

        evidence_support = str(
            record.get(
                "evidence_support",
                "",
            )
        )

        if disposition not in VALID_DISPOSITIONS:
            raise ValueError(f"Invalid disposition for {finding_id}: {disposition!r}")

        if evidence_support not in VALID_EVIDENCE_SUPPORT:
            raise ValueError(f"Invalid evidence support for {finding_id}: {evidence_support!r}")

        if disposition == "not_evaluated" and evidence_support != "not_evaluated":
            raise ValueError(
                f"{finding_id}: not_evaluated disposition requires not_evaluated evidence support."
            )

        expected = expected_by_id[finding_id]

        if str(expected.get("case_id")) != str(record.get("case_id")):
            raise ValueError(f"Case ID mismatch for {finding_id}")

        if (
            int(
                expected.get(
                    "sample_index",
                    0,
                )
            )
            != sample_index
        ):
            raise ValueError(f"Sample index mismatch for {finding_id}")

        annotations.append(
            {
                "sample_index": sample_index,
                "case_id": record.get("case_id"),
                "finding_id": finding_id,
                "finding_type": record.get("finding_type"),
                "subtype": record.get("subtype"),
                "severity": record.get("severity"),
                "requires_human_review": bool(
                    record.get(
                        "requires_human_review",
                        False,
                    )
                ),
                "disposition": disposition,
                "evidence_support": (evidence_support),
                "rationale": str(
                    record.get(
                        "rationale",
                        "",
                    )
                ),
                "evaluator": args.evaluator,
                "annotated_at": (datetime.now(UTC).isoformat()),
                "sample_weight": record.get("sample_weight"),
                "sampling_probability": record.get("sampling_probability"),
            }
        )

    expected_count = int(
        manifest.get(
            "actual_sample_size",
            0,
        )
    )

    if len(annotations) != expected_count:
        raise ValueError(
            "Annotation count does not match "
            f"manifest sample size: "
            f"{len(annotations)} != "
            f"{expected_count}"
        )

    if len(seen_ids) != len(expected_by_id):
        missing_ids = sorted(set(expected_by_id) - seen_ids)

        raise ValueError("Missing annotations for finding IDs: " + ", ".join(missing_ids))

    annotations.sort(key=lambda item: int(item["sample_index"]))

    now = datetime.now(UTC).isoformat()

    output = {
        "schema_version": "1.0",
        "created_at": now,
        "updated_at": now,
        "evaluator": args.evaluator,
        "sample_manifest": ("finding_sample_manifest.json"),
        "sample_seed": manifest.get("seed"),
        "population_size": manifest.get("population_size"),
        "sample_size": manifest.get("actual_sample_size"),
        "annotations": annotations,
    }

    output_path.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    disposition_counts = {
        disposition: sum(
            1 for annotation in annotations if annotation["disposition"] == disposition
        )
        for disposition in sorted(VALID_DISPOSITIONS)
    }

    print()
    print("=" * 72)
    print("POST-REFINEMENT ANNOTATION IMPORT")
    print("=" * 72)

    print(f"Imported annotations: {len(annotations)}")

    print(f"Evaluator: {args.evaluator}")

    print()
    print("Disposition counts:")

    for (
        disposition,
        count,
    ) in disposition_counts.items():
        print(f"  {disposition}: {count}")

    print()
    print(f"Output: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

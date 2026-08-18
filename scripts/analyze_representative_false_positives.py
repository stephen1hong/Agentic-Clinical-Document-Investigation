from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MANIFEST_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "representative_sample" / "finding_sample_manifest.json"
)

ANNOTATIONS_PATH = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "representative_sample"
    / "finding_sample_annotations.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "representative_sample" / "false_positive_analysis.json"
)


ROOT_CAUSE_TABLE_HEADER = "table_header_extracted_as_event"
ROOT_CAUSE_PLACEHOLDER = "placeholder_text_extracted_as_event"
ROOT_CAUSE_METADATA = "metadata_or_explanatory_text_extracted_as_event"
ROOT_CAUSE_OTHER = "other"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            payload,
            file,
            indent=2,
            ensure_ascii=False,
        )


def find_record_list(
    payload: Any,
    required_key: str,
) -> list[dict[str, Any]]:
    candidates: list[list[dict[str, Any]]] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            records = [item for item in value if isinstance(item, dict)]

            if records and any(required_key in record for record in records):
                candidates.append(records)

            for item in value:
                walk(item)

        elif isinstance(value, dict):
            for child in value.values():
                walk(child)

    walk(payload)

    if not candidates:
        raise ValueError(f"Could not find a record list containing key {required_key!r}.")

    return max(candidates, key=len)


def normalize_disposition(value: Any) -> str:
    if value is None:
        return "not_evaluated"

    text = str(value).strip().lower()

    mapping = {
        "1": "true_positive",
        "true_positive": "true_positive",
        "true positive": "true_positive",
        "tp": "true_positive",
        "2": "false_positive",
        "false_positive": "false_positive",
        "false positive": "false_positive",
        "fp": "false_positive",
        "3": "partially_correct",
        "partially_correct": "partially_correct",
        "partially correct": "partially_correct",
        "partial": "partially_correct",
        "4": "not_evaluated",
        "not_evaluated": "not_evaluated",
        "not evaluated": "not_evaluated",
    }

    if text not in mapping:
        raise ValueError(f"Unknown disposition value: {value!r}")

    return mapping[text]


def build_manifest_index(
    manifest_payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    findings = manifest_payload.get("findings")

    if not isinstance(findings, list):
        raise ValueError("Manifest does not contain a valid 'findings' list.")

    index: dict[str, dict[str, Any]] = {}

    for finding in findings:
        if not isinstance(finding, dict):
            continue

        finding_id = finding.get("finding_id")

        if finding_id:
            index[str(finding_id)] = finding

    return index


def classify_root_cause(
    annotation: dict[str, Any],
    manifest_record: dict[str, Any],
) -> tuple[str, str]:
    """
    Classify FP root cause using the human annotation rationale first.

    This intentionally does not attempt clinical inference.
    It categorizes documented annotation errors only.
    """

    rationale = str(annotation.get("rationale", "")).lower()

    title = str(manifest_record.get("title", "")).lower()

    summary = str(manifest_record.get("summary", "")).lower()

    combined = " ".join(
        (
            rationale,
            title,
            summary,
        )
    )

    table_header_terms = (
        "table header",
        "header row",
        "column header",
        "lab-results table header",
        "lab results table header",
        "medication table header",
    )

    if any(term in combined for term in table_header_terms):
        return (
            ROOT_CAUSE_TABLE_HEADER,
            "Annotation rationale indicates that a "
            "document/table header was incorrectly "
            "promoted to a clinical event.",
        )

    placeholder_terms = (
        "placeholder",
        "no observations available",
        "no observation available",
        "no results available",
    )

    if any(term in combined for term in placeholder_terms):
        return (
            ROOT_CAUSE_PLACEHOLDER,
            "Annotation indicates that placeholder "
            "or empty-state text was incorrectly "
            "promoted to a clinical event.",
        )

    metadata_terms = (
        "explanatory",
        "metadata",
        "meta text",
        "meta-text",
        "reconciliation boundary",
        "derived from",
        "instructional text",
    )

    if any(term in combined for term in metadata_terms):
        return (
            ROOT_CAUSE_METADATA,
            "Annotation indicates that explanatory "
            "or metadata text was incorrectly "
            "promoted to a clinical event.",
        )

    return (
        ROOT_CAUSE_OTHER,
        "The annotation identifies a false positive, "
        "but it does not match one of the predefined "
        "artifact categories.",
    )


def main() -> None:
    print("Representative False-Positive Root-Cause Analysis")
    print("=" * 55)

    manifest_payload = load_json(MANIFEST_PATH)
    annotations_payload = load_json(ANNOTATIONS_PATH)

    if not isinstance(manifest_payload, dict):
        raise ValueError("Expected manifest JSON to be an object.")

    manifest_index = build_manifest_index(manifest_payload)

    annotation_records = find_record_list(
        annotations_payload,
        required_key="finding_id",
    )

    false_positives: list[dict[str, Any]] = []

    for annotation in annotation_records:
        disposition = normalize_disposition(
            annotation.get(
                "disposition",
                annotation.get("gold_disposition"),
            )
        )

        if disposition != "false_positive":
            continue

        finding_id = str(annotation.get("finding_id", ""))

        if not finding_id:
            raise ValueError("False-positive annotation is missing finding_id.")

        manifest_record = manifest_index.get(finding_id)

        if manifest_record is None:
            raise ValueError(f"Finding is missing from manifest: {finding_id}")

        root_cause, explanation = classify_root_cause(
            annotation,
            manifest_record,
        )

        false_positives.append(
            {
                "sample_index": annotation.get("sample_index"),
                "finding_id": finding_id,
                "case_id": annotation.get(
                    "case_id",
                    manifest_record.get("case_id"),
                ),
                "finding_type": annotation.get(
                    "finding_type",
                    manifest_record.get(
                        "finding_type",
                        manifest_record.get("type"),
                    ),
                ),
                "subtype": annotation.get(
                    "subtype",
                    manifest_record.get("subtype"),
                ),
                "severity": annotation.get(
                    "severity",
                    manifest_record.get("severity"),
                ),
                "evidence_support": annotation.get("evidence_support"),
                "rationale": annotation.get("rationale"),
                "sample_weight": annotation.get("sample_weight"),
                "sampling_probability": annotation.get("sampling_probability"),
                "root_cause": root_cause,
                "root_cause_explanation": explanation,
                "title": manifest_record.get("title"),
                "summary": manifest_record.get("summary"),
            }
        )

    false_positives.sort(
        key=lambda item: item["sample_index"] if item["sample_index"] is not None else 10**9
    )

    if not false_positives:
        raise ValueError("No false-positive annotations found.")

    root_cause_counts = Counter(finding["root_cause"] for finding in false_positives)

    type_counts = Counter(str(finding["finding_type"]) for finding in false_positives)

    subtype_counts = Counter(str(finding["subtype"]) for finding in false_positives)

    root_cause_weighted_counts: dict[
        str,
        float,
    ] = defaultdict(float)

    for finding in false_positives:
        weight = finding.get("sample_weight")

        if weight is None:
            continue

        root_cause_weighted_counts[finding["root_cause"]] += float(weight)

    print(f"\nFalse positives:              {len(false_positives)}")

    print("\nBy finding type")
    print("-" * 55)

    for finding_type, count in sorted(type_counts.items()):
        print(f"{finding_type:<36} {count}")

    print("\nBy subtype")
    print("-" * 55)

    for subtype, count in sorted(subtype_counts.items()):
        print(f"{subtype:<36} {count}")

    print("\nBy root cause")
    print("-" * 55)

    for root_cause, count in root_cause_counts.most_common():
        weighted = root_cause_weighted_counts.get(root_cause)

        if weighted is None:
            print(f"{root_cause:<44} {count}")
        else:
            print(f"{root_cause:<44} {count} (weighted≈{weighted:.1f})")

    print("\nFalse-positive details")
    print("-" * 55)

    for finding in false_positives:
        print(f"\nSample {finding['sample_index']}")
        print(f"Finding ID: {finding['finding_id']}")
        print(f"Type: {finding['finding_type']}")
        print(f"Subtype: {finding['subtype']}")
        print(f"Root cause: {finding['root_cause']}")
        print(f"Rationale: {finding['rationale']}")

    output = {
        "schema_version": "1.0",
        "source_manifest": str(MANIFEST_PATH.relative_to(PROJECT_ROOT)),
        "source_annotations": str(ANNOTATIONS_PATH.relative_to(PROJECT_ROOT)),
        "false_positive_count": len(false_positives),
        "by_finding_type": dict(sorted(type_counts.items())),
        "by_subtype": dict(sorted(subtype_counts.items())),
        "by_root_cause": dict(root_cause_counts.most_common()),
        "estimated_population_fp_by_root_cause": {
            key: round(value, 3) for key, value in sorted(root_cause_weighted_counts.items())
        },
        "false_positives": false_positives,
    }

    save_json(
        OUTPUT_PATH,
        output,
    )

    print("\nSaved analysis to:")
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()

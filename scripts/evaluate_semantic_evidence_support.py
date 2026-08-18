from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SAMPLE_DIR = PROJECT_ROOT / "data" / "evaluation" / "post_refinement_sample"

ANNOTATION_PATH = SAMPLE_DIR / "finding_sample_annotations.json"

MANIFEST_PATH = SAMPLE_DIR / "finding_sample_manifest.json"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "evidence_grounding"

OUTPUT_PATH = OUTPUT_DIR / "semantic_evidence_support_metrics.json"


VALID_SUPPORT_LABELS = {
    "supported",
    "partially_supported",
    "unsupported",
    "not_evaluated",
}


def load_json(
    path: Path,
) -> dict[str, Any]:
    """Load one JSON object."""

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")

    return payload


def percent(
    numerator: float,
    denominator: float,
) -> float:
    """Return percentage."""

    if denominator == 0:
        return 0.0

    return numerator / denominator * 100.0


def main() -> int:
    """Evaluate semantic evidence support."""

    if not ANNOTATION_PATH.exists():
        print(f"Annotation artifact not found: {ANNOTATION_PATH}")
        return 1

    if not MANIFEST_PATH.exists():
        print(f"Manifest not found: {MANIFEST_PATH}")
        return 1

    annotations_payload = load_json(ANNOTATION_PATH)

    manifest = load_json(MANIFEST_PATH)

    annotations = annotations_payload.get(
        "annotations",
        [],
    )

    if not isinstance(
        annotations,
        list,
    ):
        raise ValueError("Annotation artifact must contain an annotations list.")

    manifest_findings = manifest.get(
        "findings",
        [],
    )

    if not isinstance(
        manifest_findings,
        list,
    ):
        raise ValueError("Manifest must contain a findings list.")

    manifest_by_id = {
        str(
            item.get(
                "finding_id",
                "",
            )
        ): item
        for item in manifest_findings
        if (isinstance(item, dict) and item.get("finding_id"))
    }

    support_counts: Counter[str] = Counter()

    by_type: dict[
        str,
        Counter[str],
    ] = defaultdict(Counter)

    by_subtype: dict[
        str,
        Counter[str],
    ] = defaultdict(Counter)

    weighted_support: Counter[str] = Counter()

    evaluated_count = 0
    evaluated_weight = 0.0

    records: list[dict[str, Any]] = []

    for annotation in annotations:
        if not isinstance(
            annotation,
            dict,
        ):
            continue

        finding_id = str(
            annotation.get(
                "finding_id",
                "",
            )
        )

        if not finding_id:
            continue

        if finding_id not in manifest_by_id:
            raise ValueError(f"Unknown finding ID in annotations: {finding_id}")

        support = str(
            annotation.get(
                "evidence_support",
                "not_evaluated",
            )
        )

        if support not in VALID_SUPPORT_LABELS:
            raise ValueError(f"Invalid evidence-support label for {finding_id}: {support!r}")

        finding_type = str(
            annotation.get(
                "finding_type",
                "unknown",
            )
        )

        subtype = str(
            annotation.get(
                "subtype",
                "unknown",
            )
        )

        sample_record = manifest_by_id[finding_id]

        weight = float(
            sample_record.get(
                "sample_weight",
                1.0,
            )
        )

        support_counts[support] += 1

        by_type[finding_type][support] += 1

        by_subtype[subtype][support] += 1

        weighted_support[support] += weight

        if support != "not_evaluated":
            evaluated_count += 1
            evaluated_weight += weight

        records.append(
            {
                "sample_index": (annotation.get("sample_index")),
                "case_id": (annotation.get("case_id")),
                "finding_id": (finding_id),
                "finding_type": (finding_type),
                "subtype": (subtype),
                "evidence_support": (support),
                "sample_weight": (weight),
            }
        )

    supported = support_counts["supported"]

    partial = support_counts["partially_supported"]

    unsupported = support_counts["unsupported"]

    not_evaluated = support_counts["not_evaluated"]

    strict_support_rate = percent(
        supported,
        evaluated_count,
    )

    partial_credit_support_rate = percent(
        supported + (0.5 * partial),
        evaluated_count,
    )

    unsupported_rate = percent(
        unsupported,
        evaluated_count,
    )

    weighted_supported = weighted_support["supported"]

    weighted_partial = weighted_support["partially_supported"]

    weighted_unsupported = weighted_support["unsupported"]

    weighted_strict_rate = percent(
        weighted_supported,
        evaluated_weight,
    )

    weighted_partial_rate = percent(
        weighted_supported + (0.5 * weighted_partial),
        evaluated_weight,
    )

    weighted_unsupported_rate = percent(
        weighted_unsupported,
        evaluated_weight,
    )

    def summarize_group(
        groups: dict[
            str,
            Counter[str],
        ],
    ) -> dict[str, Any]:
        result: dict[
            str,
            Any,
        ] = {}

        for name, counts in sorted(groups.items()):
            group_evaluated = (
                counts["supported"] + counts["partially_supported"] + counts["unsupported"]
            )

            result[name] = {
                "n": sum(counts.values()),
                "evaluated": (group_evaluated),
                "supported": (counts["supported"]),
                "partially_supported": (counts["partially_supported"]),
                "unsupported": (counts["unsupported"]),
                "not_evaluated": (counts["not_evaluated"]),
                "strict_support_rate": (
                    percent(
                        counts["supported"],
                        group_evaluated,
                    )
                ),
                "partial_credit_support_rate": (
                    percent(
                        counts["supported"] + (0.5 * counts["partially_supported"]),
                        group_evaluated,
                    )
                ),
            }

        return result

    by_type_metrics = summarize_group(by_type)

    by_subtype_metrics = summarize_group(by_subtype)

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8C.2",
        "evaluation_method": (
            "Fresh post-refinement stratified "
            "held-out sample using AI-assisted, "
            "human-approved semantic evidence-support "
            "adjudication."
        ),
        "population_size": manifest.get("population_size"),
        "sample_size": manifest.get("actual_sample_size"),
        "seed": manifest.get("seed"),
        "overall": {
            "evaluated": (evaluated_count),
            "supported": supported,
            "partially_supported": (partial),
            "unsupported": (unsupported),
            "not_evaluated": (not_evaluated),
            "strict_support_rate": (strict_support_rate),
            "partial_credit_support_rate": (partial_credit_support_rate),
            "unsupported_rate": (unsupported_rate),
        },
        "population_weighted": {
            "evaluated_weight": (evaluated_weight),
            "supported_weight": (weighted_supported),
            "partially_supported_weight": (weighted_partial),
            "unsupported_weight": (weighted_unsupported),
            "strict_support_rate": (weighted_strict_rate),
            "partial_credit_support_rate": (weighted_partial_rate),
            "unsupported_rate": (weighted_unsupported_rate),
        },
        "by_finding_type": (by_type_metrics),
        "by_subtype": (by_subtype_metrics),
        "records": records,
    }

    OUTPUT_DIR.mkdir(
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
    print("STEP 8C.2 SEMANTIC EVIDENCE-SUPPORT EVALUATION")
    print("=" * 72)

    print(f"Population findings:          {manifest.get('population_size')}")

    print(f"Sample findings:              {len(annotations)}")

    print(f"Evaluated:                    {evaluated_count}")

    print()
    print("Overall semantic grounding")
    print("-" * 72)

    print(f"Supported:                    {supported}")

    print(f"Partially supported:          {partial}")

    print(f"Unsupported:                  {unsupported}")

    print(f"Not evaluated:                {not_evaluated}")

    print(f"Strict support rate:          {strict_support_rate:.1f}%")

    print(f"Partial-credit support rate:  {partial_credit_support_rate:.1f}%")

    print(f"Unsupported rate:             {unsupported_rate:.1f}%")

    print()
    print("By finding type")
    print("-" * 72)

    for (
        finding_type,
        metrics,
    ) in by_type_metrics.items():
        print(
            f"{finding_type:<30}"
            f" n={metrics['n']:<3}"
            f" Supported={metrics['supported']:<3}"
            f" Partial={metrics['partially_supported']:<3}"
            f" Unsupported={metrics['unsupported']:<3}"
            f" Rate={metrics['strict_support_rate']:.1f}%"
        )

    print()
    print("By subtype")
    print("-" * 72)

    for (
        subtype,
        metrics,
    ) in by_subtype_metrics.items():
        print(
            f"{subtype:<35}"
            f" n={metrics['n']:<3}"
            f" Supported={metrics['supported']:<3}"
            f" Partial={metrics['partially_supported']:<3}"
            f" Unsupported={metrics['unsupported']:<3}"
            f" Rate={metrics['strict_support_rate']:.1f}%"
        )

    print()
    print("Population-weighted semantic grounding")
    print("-" * 72)

    print(f"Weighted strict support rate:   {weighted_strict_rate:.1f}%")

    print(f"Weighted partial support rate:  {weighted_partial_rate:.1f}%")

    print(f"Weighted unsupported rate:      {weighted_unsupported_rate:.1f}%")

    print()
    print("Saved metrics to:")

    print(OUTPUT_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

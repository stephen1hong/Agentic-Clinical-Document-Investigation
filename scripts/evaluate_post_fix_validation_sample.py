from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
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

ANNOTATION_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "post_fix_validation_sample" / "annotations.json"
)

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "post_fix_validation_sample"
    / "post_fix_validation_metrics.json"
)


EXPECTED_SAMPLE_SIZE = 80

CORRECTNESS_WEIGHTS = {
    "true_positive": 1.0,
    "partially_correct": 0.5,
    "false_positive": 0.0,
}

GROUNDING_WEIGHTS = {
    "supported": 1.0,
    "partially_supported": 0.5,
    "unsupported": 0.0,
}


def load_json(path: Path) -> Any:
    """Load JSON from disk."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def wilson_interval(
    successes: int,
    total: int,
    z: float = 1.959963984540054,
) -> tuple[float, float]:
    """Return a two-sided 95% Wilson score confidence interval."""

    if total <= 0:
        return 0.0, 0.0

    p_hat = successes / total

    denominator = 1.0 + (z**2 / total)

    center = (p_hat + z**2 / (2.0 * total)) / denominator

    margin = (
        z * math.sqrt((p_hat * (1.0 - p_hat) / total) + (z**2 / (4.0 * total**2))) / denominator
    )

    return (
        max(0.0, center - margin),
        min(1.0, center + margin),
    )


def percentage(value: float) -> float:
    """Convert proportion to percentage."""

    return value * 100.0


def metric_summary(
    labels: list[str],
    *,
    full_success_label: str,
    weights: dict[str, float],
) -> dict[str, Any]:
    """Compute strict, weighted, and confidence metrics."""

    total = len(labels)

    counts = Counter(labels)

    full_successes = counts[full_success_label]

    strict_rate = full_successes / total if total else 0.0

    weighted_score = sum(weights[label] for label in labels)

    weighted_rate = weighted_score / total if total else 0.0

    ci_low, ci_high = wilson_interval(
        full_successes,
        total,
    )

    return {
        "n": total,
        "counts": dict(sorted(counts.items())),
        "strict_successes": full_successes,
        "strict_rate": strict_rate,
        "strict_percentage": percentage(strict_rate),
        "weighted_score": weighted_score,
        "weighted_rate": weighted_rate,
        "weighted_percentage": percentage(weighted_rate),
        "wilson_95_ci": {
            "lower": ci_low,
            "upper": ci_high,
            "lower_percentage": percentage(ci_low),
            "upper_percentage": percentage(ci_high),
        },
    }


def validate_annotations(
    annotations: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate final approved annotations."""

    if annotations.get("annotation_status") != "final_approved":
        raise ValueError("annotations.json is not marked final_approved.")

    records = annotations.get("records")

    if not isinstance(records, list):
        raise ValueError("annotations.json does not contain a records list.")

    if len(records) != EXPECTED_SAMPLE_SIZE:
        raise ValueError(
            f"Unexpected annotation count. Expected {EXPECTED_SAMPLE_SIZE}, found {len(records)}."
        )

    return records


def validate_sample_alignment(
    sample: dict[str, Any],
    annotations: list[dict[str, Any]],
) -> None:
    """Ensure annotations correspond exactly to the sampled findings."""

    sample_records = sample.get("records")

    if not isinstance(
        sample_records,
        list,
    ):
        raise ValueError("Sample manifest does not contain a records list.")

    sample_ids = {record.get("finding_id") for record in sample_records if isinstance(record, dict)}

    annotation_ids = {record.get("finding_id") for record in annotations}

    if sample_ids != annotation_ids:
        missing_annotations = sample_ids - annotation_ids

        unexpected_annotations = annotation_ids - sample_ids

        raise ValueError(
            "Sample/annotation finding IDs "
            "do not match. "
            f"Missing annotations: "
            f"{sorted(missing_annotations)}; "
            f"Unexpected annotations: "
            f"{sorted(unexpected_annotations)}"
        )


def grouped_metrics(
    records: list[dict[str, Any]],
    group_field: str,
) -> dict[str, Any]:
    """Compute correctness and grounding metrics by a field."""

    groups: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for record in records:
        group_value = str(
            record.get(
                group_field,
                "unknown",
            )
        )

        groups[group_value].append(record)

    output: dict[
        str,
        Any,
    ] = {}

    for group_value, group_records in sorted(groups.items()):
        correctness_labels = [str(record["finding_correctness"]) for record in group_records]

        grounding_labels = [str(record["evidence_grounding"]) for record in group_records]

        output[group_value] = {
            "finding_correctness": metric_summary(
                correctness_labels,
                full_success_label=("true_positive"),
                weights=CORRECTNESS_WEIGHTS,
            ),
            "evidence_grounding": metric_summary(
                grounding_labels,
                full_success_label=("supported"),
                weights=GROUNDING_WEIGHTS,
            ),
        }

    return output


def main() -> int:
    """Compute Step 8C.6.4 post-fix validation metrics."""

    if not SAMPLE_PATH.exists():
        raise FileNotFoundError(f"Sample manifest not found: {SAMPLE_PATH}")

    if not ANNOTATION_PATH.exists():
        raise FileNotFoundError(f"Final annotations not found: {ANNOTATION_PATH}")

    sample = load_json(SAMPLE_PATH)

    annotations_data = load_json(ANNOTATION_PATH)

    if not isinstance(sample, dict):
        raise ValueError("Sample manifest must be a JSON object.")

    if not isinstance(
        annotations_data,
        dict,
    ):
        raise ValueError("annotations.json must be a JSON object.")

    records = validate_annotations(annotations_data)

    validate_sample_alignment(
        sample,
        records,
    )

    correctness_labels = [str(record["finding_correctness"]) for record in records]

    grounding_labels = [str(record["evidence_grounding"]) for record in records]

    overall_correctness = metric_summary(
        correctness_labels,
        full_success_label=("true_positive"),
        weights=CORRECTNESS_WEIGHTS,
    )

    overall_grounding = metric_summary(
        grounding_labels,
        full_success_label="supported",
        weights=GROUNDING_WEIGHTS,
    )

    metrics = {
        "schema_version": "1.0",
        "evaluation_step": "8C.6.4",
        "evaluation_scope": (
            "Fresh post-fix validation of finding correctness and evidence grounding."
        ),
        "sample_size": len(records),
        "sampling_design": {
            "population_size": (
                sample.get(
                    "population",
                    {},
                ).get("finding_count")
            ),
            "sample_size": len(records),
            "method": (sample.get("sampling_method")),
            "random_seed": sample.get("random_seed"),
            "note": (
                "The missing_event_time stratum "
                "was randomly sampled. The single "
                "dose_conflict finding was "
                "force-included and therefore "
                "represents complete coverage of "
                "that subtype rather than a "
                "random sample."
            ),
        },
        "overall": {
            "finding_correctness": (overall_correctness),
            "evidence_grounding": (overall_grounding),
        },
        "by_finding_type": grouped_metrics(
            records,
            "finding_type",
        ),
        "by_subtype": grouped_metrics(
            records,
            "subtype",
        ),
        "interpretation": {
            "strict_definition": (
                "Only true_positive counts as "
                "strict correctness success, and "
                "only supported counts as strict "
                "grounding success."
            ),
            "weighted_definition": (
                "Partially correct and partially "
                "supported labels receive weight "
                "0.5. Full success receives 1.0 "
                "and failure receives 0.0."
            ),
            "confidence_interval": (
                "Wilson score 95% confidence "
                "interval is reported for the "
                "observed strict success rate. "
                "For the force-included "
                "dose_conflict subtype, the "
                "interval should not be "
                "interpreted as sampling "
                "uncertainty because the entire "
                "current subtype population was "
                "evaluated."
            ),
        },
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            metrics,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("STEP 8C.6.4 POST-FIX VALIDATION METRICS")
    print("=" * 72)

    print(f"Sample size:                    {len(records)}")

    print()
    print("Finding correctness")
    print("-" * 72)

    print(
        f"True positives:                 {overall_correctness['counts'].get('true_positive', 0)}"
    )

    print(
        f"Partially correct:              "
        f"{overall_correctness['counts'].get('partially_correct', 0)}"
    )

    print(
        f"False positives:                {overall_correctness['counts'].get('false_positive', 0)}"
    )

    print(f"Strict correctness:             {overall_correctness['strict_percentage']:.1f}%")

    print(f"Weighted correctness:           {overall_correctness['weighted_percentage']:.1f}%")

    correctness_ci = overall_correctness["wilson_95_ci"]

    print(
        "Wilson 95% CI:                 "
        f"[{correctness_ci['lower_percentage']:.1f}%, "
        f"{correctness_ci['upper_percentage']:.1f}%]"
    )

    print()
    print("Evidence grounding")
    print("-" * 72)

    print(f"Supported:                      {overall_grounding['counts'].get('supported', 0)}")

    print(
        f"Partially supported:            "
        f"{overall_grounding['counts'].get('partially_supported', 0)}"
    )

    print(f"Unsupported:                    {overall_grounding['counts'].get('unsupported', 0)}")

    print(f"Strict grounding:               {overall_grounding['strict_percentage']:.1f}%")

    print(f"Weighted grounding:             {overall_grounding['weighted_percentage']:.1f}%")

    grounding_ci = overall_grounding["wilson_95_ci"]

    print(
        "Wilson 95% CI:                 "
        f"[{grounding_ci['lower_percentage']:.1f}%, "
        f"{grounding_ci['upper_percentage']:.1f}%]"
    )

    print()
    print("Subtype results")
    print("-" * 72)

    subtype_metrics = metrics["by_subtype"]

    for subtype, values in sorted(subtype_metrics.items()):
        correctness = values["finding_correctness"]

        grounding = values["evidence_grounding"]

        print(
            f"{subtype:<28}"
            f"n={correctness['n']:<4} "
            f"correct={correctness['strict_percentage']:.1f}% "
            f"grounded={grounding['strict_percentage']:.1f}%"
        )

    print()
    print("Saved metrics to:")
    print(OUTPUT_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

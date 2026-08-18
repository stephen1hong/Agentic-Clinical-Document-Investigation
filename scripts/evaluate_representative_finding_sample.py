from __future__ import annotations

import json
import math
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
    PROJECT_ROOT / "data" / "evaluation" / "representative_sample" / "finding_sample_metrics.json"
)


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"\nSaved metrics to:\n{path}")


def find_record_list(
    payload: Any,
    required_key: str,
) -> list[dict[str, Any]]:
    """
    Find the most likely list of records inside either:
      - a top-level list
      - a wrapper object containing a record list

    This avoids depending on one exact wrapper key.
    """

    candidates: list[list[dict[str, Any]]] = []

    def walk(value: Any) -> None:
        if isinstance(value, list):
            records = [x for x in value if isinstance(x, dict)]
            if records and any(required_key in x for x in records):
                candidates.append(records)

            for item in value:
                walk(item)

        elif isinstance(value, dict):
            for child in value.values():
                walk(child)

    walk(payload)

    if not candidates:
        raise ValueError(f"Could not find a record list containing key {required_key!r}.")

    # Prefer the largest plausible record collection.
    return max(candidates, key=len)


# ---------------------------------------------------------------------------
# Annotation normalization
# ---------------------------------------------------------------------------


def normalize_gold_disposition(value: Any) -> str:
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
        raise ValueError(f"Unknown gold disposition value: {value!r}")

    return mapping[text]


def normalize_evidence_support(value: Any) -> str:
    if value is None:
        return "not_evaluated"

    text = str(value).strip().lower()

    mapping = {
        "1": "supported",
        "supported": "supported",
        "2": "partially_supported",
        "partially_supported": "partially_supported",
        "partially supported": "partially_supported",
        "partial": "partially_supported",
        "3": "unsupported",
        "unsupported": "unsupported",
        "4": "not_evaluated",
        "not_evaluated": "not_evaluated",
        "not evaluated": "not_evaluated",
    }

    if text not in mapping:
        raise ValueError(f"Unknown evidence support value: {value!r}")

    return mapping[text]


def get_annotation_field(
    record: dict[str, Any],
    candidates: tuple[str, ...],
) -> Any:
    for key in candidates:
        if key in record:
            return record[key]

    return None


# ---------------------------------------------------------------------------
# Manifest/sample helpers
# ---------------------------------------------------------------------------


def build_sample_index(
    manifest_payload: Any,
) -> dict[str, dict[str, Any]]:
    records = find_record_list(
        manifest_payload,
        required_key="finding_id",
    )

    result: dict[str, dict[str, Any]] = {}

    for record in records:
        finding_id = record.get("finding_id")
        if finding_id:
            result[str(finding_id)] = record

    return result


def find_population_size(payload: Any) -> int | None:
    possible_keys = {
        "population_size",
        "population_count",
        "total_population",
        "total_findings",
    }

    def walk(value: Any) -> int | None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in possible_keys:
                    try:
                        return int(child)
                    except (TypeError, ValueError):
                        pass

            for child in value.values():
                found = walk(child)
                if found is not None:
                    return found

        elif isinstance(value, list):
            for child in value:
                found = walk(child)
                if found is not None:
                    return found

        return None

    return walk(payload)


def find_stratum_counts(
    payload: Any,
) -> dict[str, dict[str, int]]:
    allocations = payload.get("stratum_allocations")

    if not isinstance(allocations, dict):
        raise ValueError("Manifest does not contain a valid 'stratum_allocations' object.")

    result: dict[str, dict[str, int]] = {}

    for stratum, counts in allocations.items():
        if not isinstance(counts, dict):
            raise ValueError(f"Invalid allocation entry for stratum {stratum!r}: expected object.")

        population = counts.get("population")
        sample = counts.get("sample")

        if population is None or sample is None:
            raise ValueError(f"Missing population/sample counts for stratum {stratum!r}.")

        population_int = int(population)
        sample_int = int(sample)

        if population_int <= 0:
            raise ValueError(f"Population must be > 0 for stratum {stratum!r}.")

        if sample_int <= 0:
            raise ValueError(f"Sample must be > 0 for stratum {stratum!r}.")

        result[str(stratum)] = {
            "population_count": population_int,
            "sample_count": sample_int,
        }

    return result


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------


def mean(values: list[float]) -> float:
    if not values:
        return 0.0

    return sum(values) / len(values)


def sample_variance(values: list[float]) -> float:
    n = len(values)

    if n <= 1:
        return 0.0

    x_bar = mean(values)

    return sum((x - x_bar) ** 2 for x in values) / (n - 1)


def stratified_estimate(
    values_by_stratum: dict[str, list[float]],
    stratum_counts: dict[str, dict[str, int]],
) -> dict[str, float] | None:
    """
    Design-based stratified estimator with finite-population correction.

        p_hat = Σ W_h * p_h

        Var(p_hat) =
            Σ W_h² * (1 - n_h/N_h) * s_h²/n_h
    """

    usable_strata: list[tuple[str, int, int, list[float]]] = []

    for stratum, values in values_by_stratum.items():
        counts = stratum_counts.get(stratum)

        if not counts:
            return None

        n_h = len(values)
        N_h = counts["population_count"]

        if n_h == 0 or N_h <= 0:
            continue

        usable_strata.append((stratum, N_h, n_h, values))

    if not usable_strata:
        return None

    total_population = sum(N_h for _, N_h, _, _ in usable_strata)

    if total_population <= 0:
        return None

    estimate = 0.0
    variance = 0.0

    for _, N_h, n_h, values in usable_strata:
        weight = N_h / total_population
        stratum_mean = mean(values)

        estimate += weight * stratum_mean

        if n_h > 1:
            f_h = min(n_h / N_h, 1.0)
            s2_h = sample_variance(values)

            variance += weight**2 * (1.0 - f_h) * s2_h / n_h

    se = math.sqrt(max(variance, 0.0))

    lower = max(
        0.0,
        estimate - 1.96 * se,
    )

    upper = min(
        1.0,
        estimate + 1.96 * se,
    )

    return {
        "estimate": estimate,
        "standard_error": se,
        "ci_95_lower": lower,
        "ci_95_upper": upper,
    }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def evaluate_group(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    evaluated = [r for r in records if r["gold_disposition"] != "not_evaluated"]

    disposition_counts = Counter(r["gold_disposition"] for r in records)

    n = len(evaluated)

    tp = disposition_counts["true_positive"]
    fp = disposition_counts["false_positive"]
    partial = disposition_counts["partially_correct"]

    strict_precision = tp / n if n else None

    partial_credit_precision = (tp + 0.5 * partial) / n if n else None

    false_positive_proportion = fp / n if n else None

    return {
        "total_records": len(records),
        "evaluated_records": n,
        "true_positive": tp,
        "partially_correct": partial,
        "false_positive": fp,
        "not_evaluated": disposition_counts["not_evaluated"],
        "strict_precision": strict_precision,
        "partial_credit_precision": (partial_credit_precision),
        "false_positive_proportion": (false_positive_proportion),
    }


def evaluate_evidence(
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = Counter(r["evidence_support"] for r in records)

    evaluated = counts["supported"] + counts["partially_supported"] + counts["unsupported"]

    return {
        "evaluated_records": evaluated,
        "supported": counts["supported"],
        "partially_supported": (counts["partially_supported"]),
        "unsupported": counts["unsupported"],
        "not_evaluated": counts["not_evaluated"],
        "supported_rate": (counts["supported"] / evaluated if evaluated else None),
        "partially_supported_rate": (
            counts["partially_supported"] / evaluated if evaluated else None
        ),
        "unsupported_rate": (counts["unsupported"] / evaluated if evaluated else None),
    }


def group_metrics(
    records: list[dict[str, Any]],
    field_name: str,
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for record in records:
        value = record.get(field_name)

        if value is None:
            value = "unknown"

        groups[str(value)].append(record)

    return {key: evaluate_group(group) for key, group in sorted(groups.items())}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"

    return f"{100.0 * value:.1f}%"


def print_group_table(
    title: str,
    metrics: dict[str, Any],
) -> None:
    print(f"\n{title}")
    print("-" * 72)

    for name, result in metrics.items():
        print(
            f"{name:<32}"
            f" n={result['evaluated_records']:<3}"
            f" TP={result['true_positive']:<3}"
            f" Partial={result['partially_correct']:<3}"
            f" FP={result['false_positive']:<3}"
            f" Precision="
            f"{format_percent(result['strict_precision'])}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("Representative Finding Evaluation\n=================================")

    manifest_payload = load_json(MANIFEST_PATH)
    annotations_payload = load_json(ANNOTATIONS_PATH)

    manifest_index = build_sample_index(manifest_payload)

    annotation_records_raw = find_record_list(
        annotations_payload,
        required_key="finding_id",
    )

    normalized_records: list[dict[str, Any]] = []
    seen_finding_ids: set[str] = set()

    for raw in annotation_records_raw:
        finding_id_raw = raw.get("finding_id")

        if not finding_id_raw:
            continue

        finding_id = str(finding_id_raw)

        if finding_id in seen_finding_ids:
            raise ValueError(f"Duplicate annotation for finding_id: {finding_id}")

        seen_finding_ids.add(finding_id)

        manifest_record = manifest_index.get(
            finding_id,
            {},
        )

        gold_value = get_annotation_field(
            raw,
            (
                "gold_disposition",
                "disposition",
                "gold_label",
            ),
        )

        evidence_value = get_annotation_field(
            raw,
            (
                "evidence_support",
                "evidence_support_label",
                "support_label",
            ),
        )

        finding_type = (
            raw.get("finding_type")
            or raw.get("type")
            or manifest_record.get("finding_type")
            or manifest_record.get("type")
            or "unknown"
        )

        subtype = (
            raw.get("subtype")
            or raw.get("finding_subtype")
            or manifest_record.get("subtype")
            or manifest_record.get("finding_subtype")
            or "unknown"
        )

        normalized_records.append(
            {
                "finding_id": finding_id,
                "sample_index": (raw.get("sample_index") or manifest_record.get("sample_index")),
                "finding_type": str(finding_type),
                "subtype": str(subtype),
                "gold_disposition": (normalize_gold_disposition(gold_value)),
                "evidence_support": (normalize_evidence_support(evidence_value)),
            }
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    manifest_ids = set(manifest_index)
    annotation_ids = set(seen_finding_ids)

    missing_annotations = sorted(manifest_ids - annotation_ids)

    unexpected_annotations = sorted(annotation_ids - manifest_ids)

    if missing_annotations:
        raise ValueError(
            "Missing annotations for "
            f"{len(missing_annotations)} sampled findings:\n" + "\n".join(missing_annotations)
        )

    if unexpected_annotations:
        raise ValueError(
            "Annotations contain findings not present "
            "in the sample manifest:\n" + "\n".join(unexpected_annotations)
        )

    not_evaluated = [r for r in normalized_records if r["gold_disposition"] == "not_evaluated"]

    print(f"\nSample findings:              {len(manifest_ids)}")
    print(f"Annotation records:           {len(normalized_records)}")
    print(f"Not evaluated:                {len(not_evaluated)}")

    if len(normalized_records) != 80:
        print("\nWARNING: expected 80 representative sample annotations.")

    # ------------------------------------------------------------------
    # Overall metrics
    # ------------------------------------------------------------------

    overall = evaluate_group(normalized_records)

    evidence = evaluate_evidence(normalized_records)

    by_type = group_metrics(
        normalized_records,
        "finding_type",
    )

    by_subtype = group_metrics(
        normalized_records,
        "subtype",
    )

    print("\nOverall finding quality")
    print("-" * 72)
    print(f"True positive:                {overall['true_positive']}")
    print(f"Partially correct:            {overall['partially_correct']}")
    print(f"False positive:               {overall['false_positive']}")
    print(f"Strict precision:             {format_percent(overall['strict_precision'])}")
    print(f"Partial-credit precision:     {format_percent(overall['partial_credit_precision'])}")
    print(f"False-positive proportion:    {format_percent(overall['false_positive_proportion'])}")

    print("\nEvidence grounding")
    print("-" * 72)
    print(f"Supported:                    {evidence['supported']}")
    print(f"Partially supported:          {evidence['partially_supported']}")
    print(f"Unsupported:                  {evidence['unsupported']}")
    print(f"Supported rate:               {format_percent(evidence['supported_rate'])}")
    print(f"Unsupported rate:             {format_percent(evidence['unsupported_rate'])}")

    print_group_table(
        "By finding type",
        by_type,
    )

    print_group_table(
        "By subtype",
        by_subtype,
    )

    # ------------------------------------------------------------------
    # Stratified population estimates
    # ------------------------------------------------------------------

    population_size = find_population_size(manifest_payload)

    stratum_counts = find_stratum_counts(manifest_payload)

    values_strict: dict[
        str,
        list[float],
    ] = defaultdict(list)

    values_partial: dict[
        str,
        list[float],
    ] = defaultdict(list)

    values_fp: dict[
        str,
        list[float],
    ] = defaultdict(list)

    for record in normalized_records:
        disposition = record["gold_disposition"]

        if disposition == "not_evaluated":
            continue

        stratum = record["finding_type"]

        strict_value = 1.0 if disposition == "true_positive" else 0.0

        if disposition == "true_positive":
            partial_value = 1.0
        elif disposition == "partially_correct":
            partial_value = 0.5
        else:
            partial_value = 0.0

        fp_value = 1.0 if disposition == "false_positive" else 0.0

        values_strict[stratum].append(strict_value)
        values_partial[stratum].append(partial_value)
        values_fp[stratum].append(fp_value)

    weighted_strict = stratified_estimate(
        values_strict,
        stratum_counts,
    )

    weighted_partial = stratified_estimate(
        values_partial,
        stratum_counts,
    )

    weighted_fp = stratified_estimate(
        values_fp,
        stratum_counts,
    )

    print("\nPopulation-weighted estimates")
    print("-" * 72)

    if population_size is not None:
        print(f"Population findings:          {population_size}")

    if weighted_strict is None:
        print(
            "Weighted metrics unavailable because "
            "population/sample allocation counts could "
            "not be recovered from the manifest."
        )
    else:
        print(f"Weighted strict precision:    {format_percent(weighted_strict['estimate'])}")
        print(
            f"95% CI:                       "
            f"[{format_percent(weighted_strict['ci_95_lower'])}, "
            f"{format_percent(weighted_strict['ci_95_upper'])}]"
        )

        print(f"Weighted partial precision:   {format_percent(weighted_partial['estimate'])}")
        print(f"Weighted FP proportion:       {format_percent(weighted_fp['estimate'])}")

    # ------------------------------------------------------------------
    # Save machine-readable artifact
    # ------------------------------------------------------------------

    output = {
        "population_size": population_size,
        "sample_size": len(normalized_records),
        "validation": {
            "manifest_findings": len(manifest_ids),
            "annotation_records": len(normalized_records),
            "missing_annotations": (missing_annotations),
            "unexpected_annotations": (unexpected_annotations),
            "not_evaluated_count": len(not_evaluated),
        },
        "overall": overall,
        "evidence_grounding": evidence,
        "by_finding_type": by_type,
        "by_subtype": by_subtype,
        "stratum_counts": stratum_counts,
        "population_weighted": {
            "strict_precision": (weighted_strict),
            "partial_credit_precision": (weighted_partial),
            "false_positive_proportion": (weighted_fp),
        },
    }

    save_json(
        OUTPUT_PATH,
        output,
    )


if __name__ == "__main__":
    main()

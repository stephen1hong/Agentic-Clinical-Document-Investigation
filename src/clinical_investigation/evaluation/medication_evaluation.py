"""Evaluate medication discrepancy predictions against mutation gold labels."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from clinical_investigation.evaluation.medication_mutation_models import (
    EvaluationMatch,
    EvaluationMatchStatus,
    GoldMedicationDiscrepancy,
    MedicationEvaluationMetrics,
)
from clinical_investigation.investigation.medication_models import (
    MedicationDiscrepancy,
)


def read_json(path: Path) -> Any:
    """Read JSON."""

    return json.loads(path.read_text(encoding="utf-8"))


def write_json(
    path: Path,
    payload: Any,
) -> None:
    """Write JSON."""

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


def stable_identifier(
    namespace: str,
    *parts: object,
) -> str:
    """Create deterministic IDs."""

    payload = "|".join(str(part) for part in parts)

    return str(
        uuid5(
            NAMESPACE_URL,
            f"{namespace}:{payload}",
        )
    )


def load_gold_discrepancies(
    gold_path: Path,
) -> list[GoldMedicationDiscrepancy]:
    """Load gold discrepancy labels."""

    payload = read_json(gold_path)

    return [GoldMedicationDiscrepancy.model_validate(item) for item in payload]


def load_predicted_discrepancies(
    mutation_cases_root: Path,
) -> list[MedicationDiscrepancy]:
    """Load all medication discrepancy predictions."""

    predictions: list[MedicationDiscrepancy] = []

    for case_dir in sorted(path for path in mutation_cases_root.iterdir() if path.is_dir()):
        prediction_path = case_dir / "medication_discrepancies.json"

        if not prediction_path.exists():
            continue

        payload = read_json(prediction_path)

        predictions.extend(MedicationDiscrepancy.model_validate(item) for item in payload)

    return predictions


def gold_match_key(
    gold: GoldMedicationDiscrepancy,
) -> tuple[str, str, str]:
    """Build exact gold matching key."""

    return (
        gold.mutation_case_id,
        gold.medication_key,
        gold.discrepancy_type.value,
    )


def prediction_match_key(
    prediction: MedicationDiscrepancy,
) -> tuple[str, str, str]:
    """Build exact prediction matching key."""

    return (
        prediction.case_id,
        prediction.medication_key,
        prediction.discrepancy_type.value,
    )


def evaluate_predictions(
    *,
    gold_records: list[GoldMedicationDiscrepancy],
    predictions: list[MedicationDiscrepancy],
) -> tuple[
    list[EvaluationMatch],
    MedicationEvaluationMetrics,
]:
    """Compare predicted discrepancies against gold."""

    gold_by_key = {gold_match_key(item): item for item in gold_records}

    predictions_by_key: dict[
        tuple[str, str, str],
        list[MedicationDiscrepancy],
    ] = defaultdict(list)

    for prediction in predictions:
        predictions_by_key[prediction_match_key(prediction)].append(prediction)

    matches: list[EvaluationMatch] = []

    true_positive_count = 0
    false_positive_count = 0
    false_negative_count = 0

    all_keys = set(gold_by_key) | set(predictions_by_key)

    for key in sorted(all_keys):
        case_id, medication_key, discrepancy_type = key

        gold = gold_by_key.get(key)
        predicted_items = predictions_by_key.get(
            key,
            [],
        )

        if gold is not None and predicted_items:
            selected_prediction = predicted_items[0]

            true_positive_count += 1

            matches.append(
                EvaluationMatch(
                    match_id=stable_identifier(
                        "evaluation-match",
                        *key,
                        "tp",
                    ),
                    mutation_case_id=case_id,
                    medication_key=(medication_key),
                    discrepancy_type=(discrepancy_type),
                    status=(EvaluationMatchStatus.TRUE_POSITIVE),
                    gold_id=gold.gold_id,
                    predicted_discrepancy_id=(selected_prediction.discrepancy_id),
                )
            )

            for extra_prediction in predicted_items[1:]:
                false_positive_count += 1

                matches.append(
                    EvaluationMatch(
                        match_id=(
                            stable_identifier(
                                "evaluation-match",
                                extra_prediction.discrepancy_id,
                                "duplicate-fp",
                            )
                        ),
                        mutation_case_id=case_id,
                        medication_key=(medication_key),
                        discrepancy_type=(discrepancy_type),
                        status=(EvaluationMatchStatus.FALSE_POSITIVE),
                        predicted_discrepancy_id=(extra_prediction.discrepancy_id),
                    )
                )

        elif gold is not None:
            false_negative_count += 1

            matches.append(
                EvaluationMatch(
                    match_id=stable_identifier(
                        "evaluation-match",
                        *key,
                        "fn",
                    ),
                    mutation_case_id=case_id,
                    medication_key=(medication_key),
                    discrepancy_type=(discrepancy_type),
                    status=(EvaluationMatchStatus.FALSE_NEGATIVE),
                    gold_id=gold.gold_id,
                )
            )

        else:
            for prediction in predicted_items:
                false_positive_count += 1

                matches.append(
                    EvaluationMatch(
                        match_id=(
                            stable_identifier(
                                "evaluation-match",
                                prediction.discrepancy_id,
                                "fp",
                            )
                        ),
                        mutation_case_id=case_id,
                        medication_key=(medication_key),
                        discrepancy_type=(discrepancy_type),
                        status=(EvaluationMatchStatus.FALSE_POSITIVE),
                        predicted_discrepancy_id=(prediction.discrepancy_id),
                    )
                )

    precision_denominator = true_positive_count + false_positive_count

    recall_denominator = true_positive_count + false_negative_count

    precision = true_positive_count / precision_denominator if precision_denominator else 0.0

    recall = true_positive_count / recall_denominator if recall_denominator else 0.0

    f1_score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    metrics_by_type = calculate_metrics_by_type(matches)

    metrics = MedicationEvaluationMetrics(
        generated_at=datetime.now(UTC),
        evaluated_case_count=len({item.mutation_case_id for item in gold_records}),
        gold_discrepancy_count=len(gold_records),
        predicted_discrepancy_count=len(predictions),
        true_positive_count=(true_positive_count),
        false_positive_count=(false_positive_count),
        false_negative_count=(false_negative_count),
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        metrics_by_discrepancy_type=(metrics_by_type),
    )

    return matches, metrics


def calculate_metrics_by_type(
    matches: list[EvaluationMatch],
) -> dict[str, dict[str, float | int]]:
    """Calculate precision, recall, and F1 by type."""

    grouped: dict[
        str,
        list[EvaluationMatch],
    ] = defaultdict(list)

    for match in matches:
        grouped[match.discrepancy_type].append(match)

    results: dict[
        str,
        dict[str, float | int],
    ] = {}

    for discrepancy_type, items in grouped.items():
        tp = sum(item.status == EvaluationMatchStatus.TRUE_POSITIVE for item in items)

        fp = sum(item.status == EvaluationMatchStatus.FALSE_POSITIVE for item in items)

        fn = sum(item.status == EvaluationMatchStatus.FALSE_NEGATIVE for item in items)

        precision = tp / (tp + fp) if tp + fp else 0.0

        recall = tp / (tp + fn) if tp + fn else 0.0

        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

        results[discrepancy_type] = {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
        }

    return results


def run_medication_evaluation(
    *,
    mutation_cases_root: Path,
    gold_path: Path,
    predictions_output_path: Path,
    matches_output_path: Path,
    metrics_output_path: Path,
) -> MedicationEvaluationMetrics:
    """Run complete mutation-based evaluation."""

    gold_records = load_gold_discrepancies(gold_path)

    predictions = load_predicted_discrepancies(mutation_cases_root)

    matches, metrics = evaluate_predictions(
        gold_records=gold_records,
        predictions=predictions,
    )

    write_json(
        predictions_output_path,
        [item.model_dump(mode="json") for item in predictions],
    )

    write_json(
        matches_output_path,
        [item.model_dump(mode="json") for item in matches],
    )

    write_json(
        metrics_output_path,
        metrics.model_dump(mode="json"),
    )

    return metrics


def load_json_file(
    path: Path,
) -> Any:
    """Load JSON content from a file."""

    if not path.exists():
        raise FileNotFoundError(f"JSON file does not exist: {path}")

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def normalize_medication_key(
    value: str | None,
) -> str:
    """Normalize medication key for evaluation matching."""

    if value is None:
        return ""

    return " ".join(str(value).strip().lower().split())


def normalize_discrepancy_type(
    value: str | None,
) -> str:
    """Normalize discrepancy type for evaluation matching."""

    if value is None:
        return ""

    return str(value).strip().lower()


def discrepancy_signature(
    discrepancy: dict[str, Any],
) -> tuple[str, str]:
    """Create a stable discrepancy signature.

    Baseline subtraction intentionally uses only:

        medication_key
        discrepancy_type

    because these are the core fields used by mutation evaluation.
    """

    medication_key = normalize_medication_key(
        discrepancy.get("medication_key")
        or discrepancy.get("normalized_medication_key")
        or discrepancy.get("normalized_name")
        or discrepancy.get("medication_name")
    )

    discrepancy_type = normalize_discrepancy_type(discrepancy.get("discrepancy_type"))

    return (
        medication_key,
        discrepancy_type,
    )


def subtract_clean_baseline(
    *,
    mutated_discrepancies: list[dict[str, Any]],
    clean_discrepancies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return discrepancies introduced by the mutation.

    A discrepancy is considered pre-existing when the clean case
    contains the same normalized:

        medication_key
        discrepancy_type
    """

    clean_signatures = {discrepancy_signature(discrepancy) for discrepancy in clean_discrepancies}

    introduced_discrepancies: list[dict[str, Any]] = []

    seen_signatures: set[tuple[str, str]] = set()

    for discrepancy in mutated_discrepancies:
        signature = discrepancy_signature(discrepancy)

        if signature in clean_signatures:
            continue

        if signature in seen_signatures:
            continue

        seen_signatures.add(signature)

        introduced_discrepancies.append(discrepancy)

    return introduced_discrepancies


def build_clean_baseline_comparison(
    *,
    mutation_case_dir: Path,
    clean_cases_root: Path,
) -> dict[str, Any]:
    """Compare one mutation case against its clean source case."""

    mutation_record_path = mutation_case_dir / "mutation_record.json"

    mutation_record = load_json_file(mutation_record_path)

    source_case_id = mutation_record.get("source_case_id")

    if not source_case_id:
        raise ValueError(f"Mutation record has no source_case_id: {mutation_record_path}")

    clean_case_dir = clean_cases_root / source_case_id

    clean_discrepancies_path = clean_case_dir / "medication_discrepancies.json"

    mutated_discrepancies_path = mutation_case_dir / "medication_discrepancies.json"

    clean_discrepancies = load_json_file(clean_discrepancies_path)

    mutated_discrepancies = load_json_file(mutated_discrepancies_path)

    introduced_discrepancies = subtract_clean_baseline(
        mutated_discrepancies=(mutated_discrepancies),
        clean_discrepancies=(clean_discrepancies),
    )

    comparison = {
        "mutation_case_id": (mutation_case_dir.name),
        "source_case_id": (source_case_id),
        "clean_discrepancy_count": len(clean_discrepancies),
        "mutated_discrepancy_count": len(mutated_discrepancies),
        "introduced_discrepancy_count": (len(introduced_discrepancies)),
        "clean_discrepancies": (clean_discrepancies),
        "mutated_discrepancies": (mutated_discrepancies),
        "introduced_discrepancies": (introduced_discrepancies),
    }

    return comparison


def write_clean_baseline_comparison(
    *,
    mutation_case_dir: Path,
    clean_cases_root: Path,
) -> Path:
    """Build and persist clean-baseline comparison."""

    comparison = build_clean_baseline_comparison(
        mutation_case_dir=(mutation_case_dir),
        clean_cases_root=(clean_cases_root),
    )

    output_path = mutation_case_dir / "baseline_comparison.json"

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            comparison,
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output_path

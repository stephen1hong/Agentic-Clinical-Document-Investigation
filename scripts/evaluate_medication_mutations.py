"""Evaluate medication discrepancies on mutation cases."""

from rich.console import Console
from rich.table import Table

from clinical_investigation.config import settings
from clinical_investigation.evaluation.medication_evaluation import (
    run_medication_evaluation,
)

console = Console()


def main() -> int:
    """Run mutation-based medication evaluation."""

    metrics = run_medication_evaluation(
        mutation_cases_root=(settings.medication_mutation_cases_dir),
        gold_path=(settings.medication_mutation_gold_dir / "gold_discrepancies.json"),
        predictions_output_path=(
            settings.medication_mutation_predictions_dir / "predicted_discrepancies.json"
        ),
        matches_output_path=(
            settings.medication_mutation_predictions_dir / "evaluation_matches.json"
        ),
        metrics_output_path=(
            settings.medication_mutation_reports_dir / "medication_evaluation_metrics.json"
        ),
    )

    table = Table(title="Medication mutation evaluation")
    table.add_column("Metric")
    table.add_column("Value")

    table.add_row(
        "Cases",
        str(metrics.evaluated_case_count),
    )
    table.add_row(
        "Gold discrepancies",
        str(metrics.gold_discrepancy_count),
    )
    table.add_row(
        "Predictions",
        str(metrics.predicted_discrepancy_count),
    )
    table.add_row(
        "True positives",
        str(metrics.true_positive_count),
    )
    table.add_row(
        "False positives",
        str(metrics.false_positive_count),
    )
    table.add_row(
        "False negatives",
        str(metrics.false_negative_count),
    )
    table.add_row(
        "Precision",
        f"{metrics.precision:.3f}",
    )
    table.add_row(
        "Recall",
        f"{metrics.recall:.3f}",
    )
    table.add_row(
        "F1",
        f"{metrics.f1_score:.3f}",
    )

    console.print(table)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

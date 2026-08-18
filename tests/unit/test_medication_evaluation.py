"""Tests for medication mutation evaluation."""

from clinical_investigation.evaluation.medication_evaluation import (
    evaluate_predictions,
)
from clinical_investigation.evaluation.medication_mutation_models import (
    GoldDiscrepancyType,
    GoldMedicationDiscrepancy,
)
from clinical_investigation.investigation.medication_models import (
    DiscrepancySeverity,
    MedicationDiscrepancy,
    MedicationDiscrepancyType,
)


def test_exact_prediction_match() -> None:
    """Exact medication and discrepancy match should be a TP."""

    gold = GoldMedicationDiscrepancy(
        gold_id="gold-1",
        mutation_id="mutation-1",
        mutation_case_id="case-1",
        source_case_id="source-1",
        medication_name="Lisinopril",
        medication_key="lisinopril",
        discrepancy_type=(GoldDiscrepancyType.CONFLICTING_STATUS),
        source_document=("medication_reconciliation.md"),
        rationale="Controlled status mutation.",
    )

    prediction = MedicationDiscrepancy(
        discrepancy_id="prediction-1",
        case_id="case-1",
        medication_key="lisinopril",
        medication_name="Lisinopril",
        discrepancy_type=(MedicationDiscrepancyType.CONFLICTING_STATUS),
        severity=DiscrepancySeverity.HIGH,
        summary="Conflicting status.",
        rationale="Active and stopped.",
        conflicting_values=[
            "active",
            "stopped",
        ],
        mention_ids=["mention-1"],
        evidence_ids=["evidence-1"],
        confidence=1.0,
    )

    matches, metrics = evaluate_predictions(
        gold_records=[gold],
        predictions=[prediction],
    )

    assert len(matches) == 1
    assert metrics.true_positive_count == 1
    assert metrics.false_positive_count == 0
    assert metrics.false_negative_count == 0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1_score == 1.0

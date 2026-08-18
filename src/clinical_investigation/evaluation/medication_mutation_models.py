"""Models for mutation-based medication evaluation."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MedicationMutationType(StrEnum):
    """Supported synthetic medication mutations."""

    STATUS_FLIP = "status_flip"
    REMOVE_FROM_DISCHARGE = "remove_from_discharge"
    DOSE_CHANGE = "dose_change"
    ADD_DISCHARGE_ONLY_MEDICATION = "add_discharge_only_medication"


class GoldDiscrepancyType(StrEnum):
    """Gold labels expected from medication mutations."""

    CONFLICTING_STATUS = "conflicting_status"
    MISSING_AT_DISCHARGE = "missing_at_discharge"
    DOSE_CONFLICT = "dose_conflict"
    DISCHARGE_ONLY_MEDICATION = "discharge_only_medication"


class MutationRecord(BaseModel):
    """One controlled document mutation."""

    model_config = ConfigDict(extra="forbid")

    mutation_id: str
    mutation_case_id: str
    source_case_id: str

    mutation_type: MedicationMutationType

    medication_name: str
    normalized_medication_key: str

    source_document: str
    mutated_document: str

    original_text: str | None = None
    mutated_text: str | None = None

    source_line: int | None = Field(
        default=None,
        ge=1,
    )

    expected_discrepancy_type: GoldDiscrepancyType

    generated_at: datetime
    random_seed: int

    @field_validator(
        "mutation_id",
        "mutation_case_id",
        "source_case_id",
        "medication_name",
        "normalized_medication_key",
        "source_document",
        "mutated_document",
    )
    @classmethod
    def reject_empty_text(
        cls,
        value: str,
    ) -> str:
        """Reject empty text fields."""

        normalized = value.strip()

        if not normalized:
            raise ValueError("Mutation text fields must not be empty")

        return normalized


class GoldMedicationDiscrepancy(BaseModel):
    """One expected discrepancy created by mutation."""

    model_config = ConfigDict(extra="forbid")

    gold_id: str
    mutation_id: str
    mutation_case_id: str
    source_case_id: str

    medication_name: str
    medication_key: str

    discrepancy_type: GoldDiscrepancyType

    source_document: str
    expected_detected: bool = True

    rationale: str


class EvaluationMatchStatus(StrEnum):
    """Prediction-to-gold matching result."""

    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"


class EvaluationMatch(BaseModel):
    """One evaluation comparison record."""

    model_config = ConfigDict(extra="forbid")

    match_id: str
    mutation_case_id: str
    medication_key: str
    discrepancy_type: str
    status: EvaluationMatchStatus

    gold_id: str | None = None
    predicted_discrepancy_id: str | None = None


class MedicationEvaluationMetrics(BaseModel):
    """Aggregate discrepancy detection metrics."""

    model_config = ConfigDict(extra="forbid")

    generated_at: datetime

    evaluated_case_count: int = Field(ge=0)
    gold_discrepancy_count: int = Field(ge=0)
    predicted_discrepancy_count: int = Field(ge=0)

    true_positive_count: int = Field(ge=0)
    false_positive_count: int = Field(ge=0)
    false_negative_count: int = Field(ge=0)

    precision: float = Field(
        ge=0.0,
        le=1.0,
    )
    recall: float = Field(
        ge=0.0,
        le=1.0,
    )
    f1_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    metrics_by_discrepancy_type: dict[
        str,
        dict[str, float | int],
    ]

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class GoldFindingDisposition(StrEnum):
    """Gold-standard judgment for a machine finding."""

    TRUE_POSITIVE = "true_positive"
    FALSE_POSITIVE = "false_positive"
    PARTIALLY_CORRECT = "partially_correct"
    NOT_EVALUATED = "not_evaluated"


class EvidenceSupportLabel(StrEnum):
    """Gold-standard judgment of evidence support."""

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    NOT_EVALUATED = "not_evaluated"


class TimelineAccuracyLabel(StrEnum):
    """Gold-standard judgment for a timeline event."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIALLY_CORRECT = "partially_correct"
    MISSING_FROM_SYSTEM = "missing_from_system"
    NOT_EVALUATED = "not_evaluated"


class MedicationAccuracyLabel(StrEnum):
    """Gold-standard judgment for medication reconciliation."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    PARTIALLY_CORRECT = "partially_correct"
    MISSING_FROM_SYSTEM = "missing_from_system"
    NOT_EVALUATED = "not_evaluated"


class GoldFindingLabel(BaseModel):
    """Human gold label for one machine-generated finding."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    disposition: GoldFindingDisposition
    expected_finding_type: str | None = None
    expected_subtype: str | None = None
    rationale: str = ""
    reviewer: str = ""
    evidence_support: EvidenceSupportLabel = EvidenceSupportLabel.NOT_EVALUATED
    gold_evidence_ids: list[str] = Field(default_factory=list)


class GoldTimelineEvent(BaseModel):
    """Human gold label for one timeline event."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    label: TimelineAccuracyLabel
    expected_event_type: str | None = None
    expected_time: str | None = None
    rationale: str = ""
    gold_evidence_ids: list[str] = Field(default_factory=list)


class GoldMedicationItem(BaseModel):
    """Human gold label for one medication item."""

    model_config = ConfigDict(extra="forbid")

    medication_key: str
    label: MedicationAccuracyLabel
    expected_status: str | None = None
    expected_dose: str | None = None
    expected_frequency: str | None = None
    rationale: str = ""
    gold_evidence_ids: list[str] = Field(default_factory=list)


class GoldCaseLabel(BaseModel):
    """Gold-standard evaluation record for one investigation case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    evaluator: str = ""
    evaluated_at: str | None = None

    finding_labels: list[GoldFindingLabel] = Field(default_factory=list)

    timeline_labels: list[GoldTimelineEvent] = Field(default_factory=list)

    medication_labels: list[GoldMedicationItem] = Field(default_factory=list)

    case_notes: str = ""

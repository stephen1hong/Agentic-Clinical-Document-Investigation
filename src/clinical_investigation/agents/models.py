from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FindingType(StrEnum):
    """Top-level investigation finding categories."""

    TIMELINE_CONFLICT = "timeline_conflict"
    TEMPORAL_UNCERTAINTY = "temporal_uncertainty"
    MEDICATION_DISCREPANCY = "medication_discrepancy"
    CONTRADICTION = "contradiction"
    MISSING_FOLLOW_UP = "missing_follow_up"
    UNSUPPORTED_CLAIM = "unsupported_claim"
    OTHER = "other"


class FindingSeverity(StrEnum):
    """Investigation finding severity."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FindingSource(StrEnum):
    """Subsystem that produced the finding."""

    TIMELINE_RECONSTRUCTION = "timeline_reconstruction"
    MEDICATION_RECONCILIATION = "medication_reconciliation"
    CONTRADICTION_ANALYSIS = "contradiction_analysis"
    FOLLOW_UP_ANALYSIS = "follow_up_analysis"
    UNSUPPORTED_CLAIM_ANALYSIS = "unsupported_claim_analysis"
    SYNTHESIS = "synthesis"


class InvestigationFinding(BaseModel):
    """Canonical finding produced by the investigation workflow."""

    model_config = ConfigDict(
        extra="forbid",
    )

    finding_id: str
    case_id: str

    finding_type: FindingType
    subtype: str

    severity: FindingSeverity

    title: str
    summary: str

    evidence_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)

    medication_key: str | None = None

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    requires_human_review: bool = False

    source: FindingSource

"""Models for cross-document medication reconciliation."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MedicationStatus(StrEnum):
    """Normalized medication lifecycle states."""

    ACTIVE = "active"
    STARTED = "started"
    STOPPED = "stopped"
    DISCONTINUED = "discontinued"
    CONTINUED = "continued"
    HISTORICAL = "historical"
    UNKNOWN = "unknown"


class MedicationSourceType(StrEnum):
    """Source representation that produced a medication mention."""

    CLAIM = "claim"
    EVIDENCE = "evidence"
    TIMELINE = "timeline"


class MedicationDiscrepancyType(StrEnum):
    """Supported medication discrepancy categories."""

    CONFLICTING_STATUS = "conflicting_status"
    MISSING_AT_DISCHARGE = "missing_at_discharge"
    DISCHARGED_AS_ACTIVE_AFTER_STOP = "discharged_as_active_after_stop"
    STOPPED_BUT_LATER_CONTINUED = "stopped_but_later_continued"
    STARTED_WITHOUT_DISCHARGE_STATUS = "started_without_discharge_status"
    DISCHARGE_ONLY_MEDICATION = "discharge_only_medication"
    STRUCTURED_ONLY_MEDICATION = "structured_only_medication"
    DOSE_CONFLICT = "dose_conflict"
    FREQUENCY_CONFLICT = "frequency_conflict"
    ROUTE_CONFLICT = "route_conflict"
    DUPLICATE_MEDICATION = "duplicate_medication"
    AMBIGUOUS_STATUS = "ambiguous_status"


class DiscrepancySeverity(StrEnum):
    """Severity for medication discrepancy findings."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class MedicationMention(BaseModel):
    """One medication mention from one source."""

    model_config = ConfigDict(extra="forbid")

    mention_id: str
    case_id: str

    medication_name_raw: str
    normalized_name: str
    normalized_key: str

    status: MedicationStatus

    dose: str | None = None
    route: str | None = None
    frequency: str | None = None

    start_time: datetime | None = None
    stop_time: datetime | None = None
    event_time: datetime | None = None

    document_type: str | None = None
    document_section: str | None = None
    source_type: MedicationSourceType

    source_claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)
    timeline_event_ids: list[str] = Field(default_factory=list)

    source_tables: list[str] = Field(default_factory=list)
    source_rows: list[int] = Field(default_factory=list)

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    @field_validator(
        "mention_id",
        "case_id",
        "medication_name_raw",
        "normalized_name",
        "normalized_key",
    )
    @classmethod
    def reject_empty_text(
        cls,
        value: str,
    ) -> str:
        """Reject empty text fields."""

        normalized = value.strip()

        if not normalized:
            raise ValueError("Medication text fields must not be empty")

        return normalized

    @field_validator(
        "source_claim_ids",
        "evidence_ids",
        "timeline_event_ids",
        "source_tables",
        "source_rows",
    )
    @classmethod
    def deduplicate_lists(
        cls,
        value: list,
    ) -> list:
        """Deduplicate list values while preserving order."""

        return list(dict.fromkeys(value))


class MedicationProfile(BaseModel):
    """Aggregated representation of one medication."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str
    case_id: str
    normalized_name: str
    normalized_key: str

    raw_names: list[str]
    statuses: list[MedicationStatus]

    earliest_start_time: datetime | None = None
    latest_stop_time: datetime | None = None
    latest_event_time: datetime | None = None

    doses: list[str] = Field(default_factory=list)
    routes: list[str] = Field(default_factory=list)
    frequencies: list[str] = Field(default_factory=list)

    document_types: list[str] = Field(default_factory=list)
    mention_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    source_claim_ids: list[str] = Field(default_factory=list)
    timeline_event_ids: list[str] = Field(default_factory=list)

    inferred_status_at_discharge: MedicationStatus
    status_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )


class MedicationDiscrepancy(BaseModel):
    """One evidence-grounded medication discrepancy."""

    model_config = ConfigDict(extra="forbid")

    discrepancy_id: str
    case_id: str
    medication_key: str
    medication_name: str

    discrepancy_type: MedicationDiscrepancyType
    severity: DiscrepancySeverity

    summary: str
    rationale: str

    conflicting_values: list[str] = Field(default_factory=list)
    missing_evidence_description: str | None = None

    mention_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    source_claim_ids: list[str] = Field(default_factory=list)
    timeline_event_ids: list[str] = Field(default_factory=list)

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    requires_human_review: bool = True


class MedicationReconciliationManifest(BaseModel):
    """Metadata for one medication reconciliation run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    case_id: str
    generated_at: datetime
    reconciliation_method: str

    source_evidence_count: int = Field(ge=0)
    source_claim_count: int = Field(ge=0)
    source_timeline_event_count: int = Field(ge=0)

    medication_mention_count: int = Field(ge=0)
    medication_profile_count: int = Field(ge=0)
    discrepancy_count: int = Field(ge=0)

    mention_count_by_document: dict[str, int]
    discrepancy_count_by_type: dict[str, int]

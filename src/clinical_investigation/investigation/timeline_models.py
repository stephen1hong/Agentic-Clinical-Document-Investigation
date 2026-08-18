"""Models for canonical clinical timeline reconstruction."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimelineEventType(StrEnum):
    """Supported canonical timeline event types."""

    ENCOUNTER_START = "encounter_start"
    ENCOUNTER_STOP = "encounter_stop"
    CONDITION_EVENT = "condition_event"
    MEDICATION_START = "medication_start"
    MEDICATION_STOP = "medication_stop"
    MEDICATION_STATUS = "medication_status"
    OBSERVATION_RESULT = "observation_result"
    PROCEDURE_EVENT = "procedure_event"
    FOLLOW_UP_ACTION = "follow_up_action"
    NARRATIVE_EVENT = "narrative_event"


class TimePrecision(StrEnum):
    """Precision associated with a normalized event time."""

    DATETIME = "datetime"
    DATE = "date"
    INFERRED_FROM_DOCUMENT = "inferred_from_document"
    UNKNOWN = "unknown"


class TimeSource(StrEnum):
    """Source used to assign an event time."""

    CLAIM_FIELD = "claim_field"
    EVIDENCE_FIELD = "evidence_field"
    DOCUMENT_TEXT = "document_text"
    ENCOUNTER_CONTEXT = "encounter_context"
    UNKNOWN = "unknown"


class TimelineConflictType(StrEnum):
    """Supported timeline conflict categories."""

    ENCOUNTER_STOP_BEFORE_START = "encounter_stop_before_start"
    MEDICATION_STOP_BEFORE_START = "medication_stop_before_start"
    EVENT_OUTSIDE_ENCOUNTER = "event_outside_encounter"
    CONFLICTING_EVENT_TIMES = "conflicting_event_times"
    MISSING_EVENT_TIME = "missing_event_time"
    AMBIGUOUS_EVENT_ORDER = "ambiguous_event_order"


class ConflictSeverity(StrEnum):
    """Severity assigned to temporal conflicts."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CanonicalEvent(BaseModel):
    """One normalized event in the canonical timeline."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    case_id: str
    event_type: TimelineEventType

    subject: str
    description: str

    normalized_time: datetime | None = None
    time_end: datetime | None = None
    time_precision: TimePrecision
    time_source: TimeSource

    source_claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(min_length=1)
    source_document_types: list[str] = Field(min_length=1)

    source_tables: list[str] = Field(default_factory=list)
    source_rows: list[int] = Field(default_factory=list)

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    @field_validator(
        "event_id",
        "case_id",
        "subject",
        "description",
    )
    @classmethod
    def reject_empty_text(
        cls,
        value: str,
    ) -> str:
        """Reject empty string values."""

        normalized = value.strip()

        if not normalized:
            raise ValueError("Timeline text fields must not be empty")

        return normalized

    @field_validator(
        "source_claim_ids",
        "evidence_ids",
        "source_document_types",
        "source_tables",
        "source_rows",
    )
    @classmethod
    def deduplicate_lists(
        cls,
        value: list,
    ) -> list:
        """Remove duplicate list entries while preserving order."""

        return list(dict.fromkeys(value))


class TimelineConflict(BaseModel):
    """One potential temporal inconsistency."""

    model_config = ConfigDict(extra="forbid")

    conflict_id: str
    case_id: str
    conflict_type: TimelineConflictType
    severity: ConflictSeverity

    summary: str
    rationale: str

    event_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    requires_human_review: bool = True


class TimelineManifest(BaseModel):
    """Metadata for one timeline reconstruction."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    case_id: str
    generated_at: datetime
    reconstruction_method: str

    source_evidence_count: int = Field(ge=0)
    source_claim_count: int = Field(ge=0)

    canonical_event_count: int = Field(ge=0)
    dated_event_count: int = Field(ge=0)
    undated_event_count: int = Field(ge=0)
    merged_event_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)

    event_count_by_type: dict[str, int]
    conflict_count_by_type: dict[str, int]

"""Structured models for clinical evidence and claims."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentType(StrEnum):
    """Supported generated clinical document types."""

    ADMISSION_NOTE = "admission_note"
    PROGRESS_NOTE = "progress_note"
    LAB_REPORT = "lab_report"
    MEDICATION_RECONCILIATION = "medication_reconciliation"
    DISCHARGE_SUMMARY = "discharge_summary"
    FOLLOW_UP_NOTE = "follow_up_note"


class ClaimType(StrEnum):
    """Supported normalized clinical claim categories."""

    CONDITION_PRESENCE = "condition_presence"
    MEDICATION_STATUS = "medication_status"
    OBSERVATION_RESULT = "observation_result"
    PROCEDURE_EVENT = "procedure_event"
    FOLLOW_UP_ACTION = "follow_up_action"
    ENCOUNTER_EVENT = "encounter_event"
    NARRATIVE_STATEMENT = "narrative_statement"


class ExtractionMethod(StrEnum):
    """Method used to generate evidence or a claim."""

    DETERMINISTIC_MARKDOWN = "deterministic_markdown"
    DETERMINISTIC_TABLE = "deterministic_table"
    DETERMINISTIC_PROVENANCE = "deterministic_provenance"


class EvidenceItem(BaseModel):
    """One traceable passage extracted from a clinical document."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    case_id: str
    document_type: DocumentType
    source_file: str
    source_line: int = Field(ge=1)
    section: str
    text_span: str
    normalized_fact: str

    source_table: str | None = None
    source_row: int | None = Field(default=None, ge=0)

    event_time: datetime | None = None
    extraction_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
    )
    extraction_method: ExtractionMethod

    @field_validator(
        "evidence_id",
        "case_id",
        "source_file",
        "section",
        "text_span",
        "normalized_fact",
    )
    @classmethod
    def reject_empty_text(cls, value: str) -> str:
        """Reject empty string values."""

        normalized = value.strip()

        if not normalized:
            raise ValueError("Value must not be empty")

        return normalized


class ClinicalClaim(BaseModel):
    """One normalized atomic claim extracted from evidence."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str
    case_id: str
    claim_type: ClaimType

    subject: str
    predicate: str
    value: str

    time_start: datetime | None = None
    time_end: datetime | None = None

    source_evidence_ids: list[str] = Field(min_length=1)

    extraction_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
    )
    extraction_method: ExtractionMethod

    @field_validator(
        "claim_id",
        "case_id",
        "subject",
        "predicate",
        "value",
    )
    @classmethod
    def reject_empty_claim_values(
        cls,
        value: str,
    ) -> str:
        """Reject empty claim fields."""

        normalized = value.strip()

        if not normalized:
            raise ValueError("Claim field must not be empty")

        return normalized

    @field_validator("source_evidence_ids")
    @classmethod
    def reject_duplicate_evidence_ids(
        cls,
        value: list[str],
    ) -> list[str]:
        """Reject duplicate or empty evidence references."""

        if any(not item.strip() for item in value):
            raise ValueError("Evidence IDs must not be empty")

        if len(value) != len(set(value)):
            raise ValueError("Duplicate evidence IDs are not allowed")

        return value


class ExtractionManifest(BaseModel):
    """Metadata for one evidence-extraction run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    case_id: str
    generated_at: datetime
    extraction_method: str

    source_documents: list[str]
    source_document_hashes: dict[str, str]

    evidence_count: int = Field(ge=0)
    claim_count: int = Field(ge=0)

    evidence_count_by_document: dict[str, int]
    claim_count_by_type: dict[str, int]

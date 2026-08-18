from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReportFinding(BaseModel):
    """One finding rendered in the final investigation report."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    finding_type: str
    subtype: str
    severity: str
    title: str
    summary: str

    evidence_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    event_ids: list[str] = Field(default_factory=list)

    confidence: float
    requires_human_review: bool


class InvestigationReport(BaseModel):
    """Final structured output of one clinical investigation."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    investigation_question: str

    executive_summary: str

    high_priority_findings: list[ReportFinding] = Field(default_factory=list)
    other_findings: list[ReportFinding] = Field(default_factory=list)

    validation_errors: list[str] = Field(default_factory=list)

    review_status: str
    review_reasons: list[str] = Field(default_factory=list)

    finding_count: int
    review_finding_count: int

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FindingReviewDecision(StrEnum):
    """Human decision for one investigation finding."""

    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    NEEDS_FOLLOW_UP = "needs_follow_up"


class CaseReviewStatus(StrEnum):
    """Human-review lifecycle for an investigation case."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class FindingReviewRecord(BaseModel):
    """Human review result for one investigation finding."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str
    decision: FindingReviewDecision

    rationale: str = ""

    reviewer: str = ""

    reviewed_at: str

    evidence_ids: list[str] = Field(default_factory=list)


class CaseReviewRecord(BaseModel):
    """Human-review state and decisions for one case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str

    status: CaseReviewStatus

    reviewer: str = ""

    started_at: str | None = None
    completed_at: str | None = None

    finding_reviews: list[FindingReviewRecord] = Field(default_factory=list)

    case_notes: str = ""


class ReviewerFinding(BaseModel):
    """Finding prepared for human review."""

    model_config = ConfigDict(extra="forbid")

    finding_id: str

    finding_type: str
    subtype: str
    severity: str

    title: str
    summary: str

    confidence: float

    requires_human_review: bool

    evidence_ids: list[str] = Field(default_factory=list)

    claim_ids: list[str] = Field(default_factory=list)

    event_ids: list[str] = Field(default_factory=list)


class ReviewerBundle(BaseModel):
    """Complete reviewer-facing representation of one case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str

    investigation_question: str

    executive_summary: str

    review_status: str

    findings_requiring_review: list[ReviewerFinding] = Field(default_factory=list)

    contextual_findings: list[ReviewerFinding] = Field(default_factory=list)

    finding_count: int

    review_finding_count: int

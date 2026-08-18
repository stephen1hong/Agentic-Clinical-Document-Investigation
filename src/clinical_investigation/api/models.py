from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """API health response."""

    status: str


class CaseListResponse(BaseModel):
    """Persisted investigation case listing."""

    cases: list[str]
    count: int


class InvestigationResponse(BaseModel):
    """Public API summary for one investigation run."""

    case_id: str
    case_dir: str
    finding_count: int
    validation_error_count: int
    requires_human_review: bool
    review_status: str
    final_report_path: str


class ErrorResponse(BaseModel):
    """Stable API error payload."""

    status: str
    error_type: str
    message: str
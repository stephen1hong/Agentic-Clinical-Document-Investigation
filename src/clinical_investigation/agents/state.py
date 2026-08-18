from typing import Any, TypedDict

from clinical_investigation.agents.models import (
    InvestigationFinding,
)


class InvestigationState(TypedDict, total=False):
    """Shared state for the clinical investigation workflow."""

    case_id: str
    investigation_question: str

    evidence_items: list[dict[str, Any]]
    clinical_claims: list[dict[str, Any]]

    canonical_timeline: list[dict[str, Any]]
    timeline_conflicts: list[dict[str, Any]]

    medication_profiles: list[dict[str, Any]]
    medication_discrepancies: list[dict[str, Any]]

    timeline_findings: list[InvestigationFinding]

    medication_findings: list[InvestigationFinding]

    contradiction_findings: list[InvestigationFinding]

    follow_up_findings: list[InvestigationFinding]

    unsupported_claim_findings: list[InvestigationFinding]

    investigation_findings: list[InvestigationFinding]

    validation_errors: list[str]

    requires_human_review: bool

    review_status: str
    review_reasons: list[str]

    final_report: dict[str, Any]

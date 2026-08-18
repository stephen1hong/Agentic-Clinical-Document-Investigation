from __future__ import annotations

from typing import Any

from clinical_investigation.agents.contradiction import (
    detect_medication_status_contradictions,
)
from clinical_investigation.agents.follow_up import (
    detect_missing_follow_ups,
)
from clinical_investigation.agents.models import (
    FindingSeverity,
    FindingSource,
    FindingType,
    InvestigationFinding,
)
from clinical_investigation.agents.report_persistence import (
    persist_final_report,
)
from clinical_investigation.agents.reporting import (
    generate_investigation_report,
)
from clinical_investigation.agents.review_policy import (
    should_require_human_review,
)
from clinical_investigation.agents.state import (
    InvestigationState,
)
from clinical_investigation.agents.tools import (
    load_case_context_tool,
)
from clinical_investigation.agents.unsupported_claim import (
    detect_unsupported_claims,
)
from clinical_investigation.agents.validation import (
    validate_investigation_findings,
)
from clinical_investigation.config import settings

DEFAULT_INVESTIGATION_QUESTION = (
    "Identify clinically relevant timeline inconsistencies, "
    "medication discrepancies, contradictions, missing "
    "follow-up actions, and potentially unsupported statements."
)


HIGH_VALUE_TIMELINE_CONFLICT_TYPES = {
    "encounter_stop_before_start",
    "medication_stop_before_start",
    "conflicting_event_times",
    "event_outside_encounter",
}


TEMPORAL_UNCERTAINTY_TYPES = {
    "missing_event_time",
    "ambiguous_event_order",
}


SEVERITY_ORDER = {
    "high": 0,
    "medium": 1,
    "low": 2,
    "info": 3,
}


def initialize_investigation(
    state: InvestigationState,
) -> dict[str, Any]:
    """Initialize workflow state for one investigation."""

    case_id = state.get("case_id", "").strip()

    if not case_id:
        raise ValueError("Investigation requires a non-empty case_id.")

    investigation_question = (
        state.get(
            "investigation_question",
            DEFAULT_INVESTIGATION_QUESTION,
        )
        or DEFAULT_INVESTIGATION_QUESTION
    )

    return {
        "case_id": case_id,
        "investigation_question": (investigation_question),
        "timeline_findings": [],
        "medication_findings": [],
        "contradiction_findings": [],
        "follow_up_findings": [],
        "unsupported_claim_findings": [],
        "investigation_findings": [],
        "validation_errors": [],
        "requires_human_review": False,
        "review_status": "not_required",
        "review_reasons": [],
        "final_report": {},
    }


def retrieve_case_context(
    state: InvestigationState,
) -> dict[str, Any]:
    """Load deterministic investigation artifacts for the case."""

    case_id = state.get("case_id")

    if not case_id:
        raise ValueError("retrieve_case_context requires case_id.")

    context = load_case_context_tool(case_id)

    return {
        "evidence_items": context["evidence_items"],
        "clinical_claims": context["clinical_claims"],
        "canonical_timeline": context["canonical_timeline"],
        "timeline_conflicts": context["timeline_conflicts"],
        "medication_profiles": context["medication_profiles"],
        "medication_discrepancies": context["medication_discrepancies"],
    }


def analyze_timeline(
    state: InvestigationState,
) -> dict[str, Any]:
    """Convert timeline conflicts into typed investigation findings."""

    case_id = state.get(
        "case_id",
        "",
    )

    timeline_conflicts = state.get(
        "timeline_conflicts",
        [],
    )

    findings: list[InvestigationFinding] = []

    for conflict in timeline_conflicts:
        conflict_type = str(
            conflict.get(
                "conflict_type",
                "unknown",
            )
        )

        raw_severity = str(
            conflict.get(
                "severity",
                "info",
            )
        ).lower()

        try:
            severity = FindingSeverity(raw_severity)
        except ValueError:
            severity = FindingSeverity.INFO

        if conflict_type in HIGH_VALUE_TIMELINE_CONFLICT_TYPES:
            finding_type = FindingType.TIMELINE_CONFLICT

        elif conflict_type in TEMPORAL_UNCERTAINTY_TYPES:
            finding_type = FindingType.TEMPORAL_UNCERTAINTY

        else:
            finding_type = FindingType.OTHER

        finding_id = str(conflict.get("conflict_id") or "")

        if not finding_id:
            continue

        upstream_requires_review = bool(
            conflict.get(
                "requires_human_review",
                False,
            )
        )

        requires_human_review = should_require_human_review(
            finding_type=finding_type,
            subtype=conflict_type,
            severity=severity,
            upstream_requires_review=upstream_requires_review,
        )

        finding = InvestigationFinding(
            finding_id=finding_id,
            case_id=case_id,
            finding_type=finding_type,
            subtype=conflict_type,
            severity=severity,
            title=(conflict.get("summary") or "Timeline finding"),
            summary=(conflict.get("rationale") or conflict.get("summary") or ""),
            event_ids=list(
                conflict.get(
                    "event_ids",
                    [],
                )
                or []
            ),
            evidence_ids=list(
                conflict.get(
                    "evidence_ids",
                    [],
                )
                or []
            ),
            claim_ids=[],
            confidence=float(
                conflict.get(
                    "confidence",
                    1.0,
                )
            ),
            requires_human_review=requires_human_review,
            source=(FindingSource.TIMELINE_RECONSTRUCTION),
        )

        findings.append(finding)

    return {
        "timeline_findings": findings,
    }


def analyze_medications(
    state: InvestigationState,
) -> dict[str, Any]:
    """Convert medication discrepancies into typed findings."""

    case_id = state.get(
        "case_id",
        "",
    )

    discrepancies = state.get(
        "medication_discrepancies",
        [],
    )

    findings: list[InvestigationFinding] = []

    for discrepancy in discrepancies:
        discrepancy_type = str(
            discrepancy.get(
                "discrepancy_type",
                "unknown",
            )
        )

        raw_severity = str(
            discrepancy.get(
                "severity",
                "info",
            )
        ).lower()

        try:
            severity = FindingSeverity(raw_severity)
        except ValueError:
            severity = FindingSeverity.INFO

        medication_key = (
            discrepancy.get("medication_key")
            or discrepancy.get("normalized_medication_key")
            or discrepancy.get("medication_name")
            or ""
        )

        discrepancy_id = str(discrepancy.get("discrepancy_id") or "")

        if not discrepancy_id:
            continue

        title = discrepancy.get("summary") or (f"Medication discrepancy: {medication_key}")

        upstream_requires_review = bool(
            discrepancy.get(
                "requires_human_review",
                True,
            )
        )

        requires_human_review = should_require_human_review(
            finding_type=FindingType.MEDICATION_DISCREPANCY,
            subtype=discrepancy_type,
            severity=severity,
            upstream_requires_review=upstream_requires_review,
        )

        finding = InvestigationFinding(
            finding_id=discrepancy_id,
            case_id=case_id,
            finding_type=(FindingType.MEDICATION_DISCREPANCY),
            subtype=(discrepancy_type),
            severity=severity,
            title=title,
            summary=(discrepancy.get("rationale") or discrepancy.get("summary") or ""),
            medication_key=str(medication_key) if medication_key else None,
            event_ids=list(
                discrepancy.get(
                    "event_ids",
                    [],
                )
                or []
            ),
            evidence_ids=list(
                discrepancy.get(
                    "evidence_ids",
                    [],
                )
                or []
            ),
            claim_ids=list(
                discrepancy.get(
                    "claim_ids",
                    [],
                )
                or []
            ),
            confidence=float(
                discrepancy.get(
                    "confidence",
                    1.0,
                )
            ),
            requires_human_review=requires_human_review,
            source=(FindingSource.MEDICATION_RECONCILIATION),
        )

        findings.append(finding)

    return {
        "medication_findings": findings,
    }


def detect_contradictions(
    state: InvestigationState,
) -> dict[str, Any]:
    """Detect evidence-grounded cross-document contradictions."""

    case_id = state.get(
        "case_id",
        "",
    )

    if not case_id:
        raise ValueError("detect_contradictions requires case_id.")

    clinical_claims = state.get(
        "clinical_claims",
        [],
    )

    evidence_items = state.get(
        "evidence_items",
        [],
    )

    findings = detect_medication_status_contradictions(
        case_id=case_id,
        clinical_claims=clinical_claims,
        evidence_items=evidence_items,
    )

    return {
        "contradiction_findings": (findings),
    }


def detect_missing_followups(
    state: InvestigationState,
) -> dict[str, Any]:
    """Detect explicitly requested follow-ups without documented completion."""

    case_id = state.get(
        "case_id",
        "",
    )

    if not case_id:
        raise ValueError("detect_missing_followups requires case_id.")

    findings = detect_missing_follow_ups(
        case_id=case_id,
        clinical_claims=state.get(
            "clinical_claims",
            [],
        ),
        evidence_items=state.get(
            "evidence_items",
            [],
        ),
        canonical_timeline=state.get(
            "canonical_timeline",
            [],
        ),
    )

    return {
        "follow_up_findings": findings,
    }


def detect_unsupported_claims_node(
    state: InvestigationState,
) -> dict[str, Any]:
    """Detect clinical claims lacking adequate evidence support."""

    case_id = state.get(
        "case_id",
        "",
    )

    if not case_id:
        raise ValueError("detect_unsupported_claims_node requires case_id.")

    findings = detect_unsupported_claims(
        case_id=case_id,
        clinical_claims=state.get(
            "clinical_claims",
            [],
        ),
        evidence_items=state.get(
            "evidence_items",
            [],
        ),
    )

    return {
        "unsupported_claim_findings": (findings),
    }


def synthesize_findings(
    state: InvestigationState,
) -> dict[str, Any]:
    """Combine and prioritize typed investigation findings."""

    timeline_findings = state.get(
        "timeline_findings",
        [],
    )

    medication_findings = state.get(
        "medication_findings",
        [],
    )

    contradiction_findings = state.get(
        "contradiction_findings",
        [],
    )

    follow_up_findings = state.get(
        "follow_up_findings",
        [],
    )

    unsupported_claim_findings = state.get(
        "unsupported_claim_findings",
        [],
    )

    findings = [
        *timeline_findings,
        *medication_findings,
        *contradiction_findings,
        *follow_up_findings,
        *unsupported_claim_findings,
    ]

    severity_order = {
        FindingSeverity.HIGH: 0,
        FindingSeverity.MEDIUM: 1,
        FindingSeverity.LOW: 2,
        FindingSeverity.INFO: 3,
    }

    findings.sort(
        key=lambda finding: (
            severity_order.get(
                finding.severity,
                99,
            ),
            finding.finding_type.value,
            finding.finding_id,
        )
    )

    requires_human_review = any(finding.requires_human_review for finding in findings)

    return {
        "investigation_findings": findings,
        "requires_human_review": (requires_human_review),
    }


def validate_investigation(
    state: InvestigationState,
) -> dict[str, Any]:
    """Validate synthesized findings and provenance references."""

    case_id = state.get(
        "case_id",
        "",
    )

    if not case_id:
        raise ValueError("validate_investigation requires case_id.")

    findings = state.get(
        "investigation_findings",
        [],
    )

    validation_errors = validate_investigation_findings(
        case_id=case_id,
        findings=findings,
        clinical_claims=state.get(
            "clinical_claims",
            [],
        ),
        evidence_items=state.get(
            "evidence_items",
            [],
        ),
        canonical_timeline=state.get(
            "canonical_timeline",
            [],
        ),
    )

    existing_review_flag = bool(
        state.get(
            "requires_human_review",
            False,
        )
    )

    requires_human_review = existing_review_flag or bool(validation_errors)

    return {
        "validation_errors": (validation_errors),
        "requires_human_review": (requires_human_review),
    }


def human_review(
    state: InvestigationState,
) -> dict[str, Any]:
    """Mark an investigation as requiring human review."""

    validation_errors = state.get(
        "validation_errors",
        [],
    )

    findings = state.get(
        "investigation_findings",
        [],
    )

    review_reasons: list[str] = []

    for error in validation_errors:
        review_reasons.append(f"Validation error: {error}")

    for finding in findings:
        if finding.requires_human_review:
            review_reasons.append(
                f"Finding requires review: "
                f"{finding.finding_id} "
                f"({finding.finding_type.value}/"
                f"{finding.subtype})"
            )

    review_reasons = list(dict.fromkeys(review_reasons))

    return {
        "review_status": "pending",
        "review_reasons": review_reasons,
        "requires_human_review": True,
    }


def mark_validation_passed(
    state: InvestigationState,
) -> dict[str, Any]:
    """Mark a validated investigation as not requiring review."""

    return {
        "review_status": "not_required",
        "review_reasons": [],
    }


def generate_final_report(
    state: InvestigationState,
) -> dict[str, Any]:
    """Generate the final structured investigation report."""

    report = generate_investigation_report(state)

    return {
        "final_report": report.model_dump(mode="json"),
    }


def persist_final_report_node(
    state: InvestigationState,
) -> dict[str, Any]:
    """Persist the generated final investigation report."""

    case_id = state.get(
        "case_id",
        "",
    )

    if not case_id:
        raise ValueError("Cannot persist final report without case_id.")

    final_report = state.get(
        "final_report",
        {},
    )

    if not final_report:
        raise ValueError("Cannot persist an empty final report.")

    case_dir = settings.investigation_cases_dir / case_id

    persist_final_report(
        case_dir=case_dir,
        report=final_report,
    )

    return {}

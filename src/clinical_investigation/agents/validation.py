from __future__ import annotations

from collections import Counter
from typing import Any

from clinical_investigation.agents.models import (
    FindingType,
    InvestigationFinding,
)


def build_claim_index(
    clinical_claims: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index clinical claims by claim_id."""

    return {str(claim["claim_id"]): claim for claim in clinical_claims if claim.get("claim_id")}


def build_evidence_index(
    evidence_items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index evidence items by evidence_id."""

    return {
        str(evidence["evidence_id"]): evidence
        for evidence in evidence_items
        if evidence.get("evidence_id")
    }


def build_event_index(
    canonical_timeline: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index canonical timeline events by event_id."""

    return {str(event["event_id"]): event for event in canonical_timeline if event.get("event_id")}


def find_duplicate_finding_ids(
    findings: list[InvestigationFinding],
) -> list[str]:
    """Return finding IDs that appear more than once."""

    counts = Counter(finding.finding_id for finding in findings)

    return sorted(finding_id for finding_id, count in counts.items() if count > 1)


def validate_claim_references(
    *,
    finding: InvestigationFinding,
    claim_index: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate claim IDs referenced by one finding."""

    errors: list[str] = []

    for claim_id in finding.claim_ids:
        if claim_id not in claim_index:
            errors.append(f"Finding {finding.finding_id} references unknown claim_id: {claim_id}")

    return errors


def validate_evidence_references(
    *,
    finding: InvestigationFinding,
    evidence_index: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate evidence IDs referenced by one finding."""

    errors: list[str] = []

    for evidence_id in finding.evidence_ids:
        if evidence_id not in evidence_index:
            errors.append(
                f"Finding {finding.finding_id} references unknown evidence_id: {evidence_id}"
            )

    return errors


def validate_event_references(
    *,
    finding: InvestigationFinding,
    event_index: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate timeline event IDs referenced by one finding."""

    errors: list[str] = []

    for event_id in finding.event_ids:
        if event_id not in event_index:
            errors.append(f"Finding {finding.finding_id} references unknown event_id: {event_id}")

    return errors


def validate_finding_case_id(
    *,
    case_id: str,
    finding: InvestigationFinding,
) -> list[str]:
    """Ensure finding belongs to the current investigation case."""

    if finding.case_id == case_id:
        return []

    return [
        (
            f"Finding {finding.finding_id} "
            f"has case_id {finding.case_id}, "
            f"but workflow case_id is {case_id}."
        )
    ]


def validate_finding_evidence_requirements(
    finding: InvestigationFinding,
) -> list[str]:
    """Validate minimum provenance requirements by finding type."""

    errors: list[str] = []

    if finding.finding_type in {
        FindingType.TIMELINE_CONFLICT,
        FindingType.TEMPORAL_UNCERTAINTY,
    }:
        if not (finding.event_ids or finding.claim_ids or finding.evidence_ids):
            errors.append(
                f"Finding {finding.finding_id} "
                "has no supporting event, claim, "
                "or evidence references."
            )

    elif finding.finding_type == FindingType.MEDICATION_DISCREPANCY:
        if not (finding.event_ids or finding.claim_ids or finding.evidence_ids):
            errors.append(f"Medication finding {finding.finding_id} has no provenance references.")

    elif finding.finding_type == FindingType.CONTRADICTION:
        if len(finding.claim_ids) < 2:
            errors.append(
                f"Contradiction finding {finding.finding_id} must reference at least two claims."
            )

        if len(finding.evidence_ids) < 2:
            errors.append(
                f"Contradiction finding "
                f"{finding.finding_id} "
                "must reference at least two "
                "evidence items."
            )

    elif finding.finding_type == FindingType.MISSING_FOLLOW_UP:
        if not finding.claim_ids:
            errors.append(
                f"Missing follow-up finding "
                f"{finding.finding_id} "
                "must reference the originating "
                "follow-up claim."
            )

        if not finding.evidence_ids:
            errors.append(
                f"Missing follow-up finding "
                f"{finding.finding_id} "
                "must reference source evidence "
                "for the requested follow-up."
            )

    elif finding.finding_type == FindingType.UNSUPPORTED_CLAIM:
        if not finding.claim_ids:
            errors.append(
                f"Unsupported-claim finding {finding.finding_id} must reference at least one claim."
            )

        if finding.subtype == "insufficient_evidence_support" and not finding.evidence_ids:
            errors.append(
                f"Unsupported-claim finding "
                f"{finding.finding_id} "
                "with subtype "
                "insufficient_evidence_support "
                "must reference evidence."
            )

        if finding.subtype == "missing_source_evidence" and not finding.evidence_ids:
            errors.append(
                f"Unsupported-claim finding "
                f"{finding.finding_id} "
                "with subtype "
                "missing_source_evidence "
                "must preserve the unresolved "
                "evidence ID references."
            )

    elif finding.finding_type == FindingType.OTHER and not (
        finding.event_ids or finding.claim_ids or finding.evidence_ids
    ):
        errors.append(f"Finding {finding.finding_id} has no provenance references.")

    return errors


def validate_investigation_findings(
    *,
    case_id: str,
    findings: list[InvestigationFinding],
    clinical_claims: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
    canonical_timeline: list[dict[str, Any]],
) -> list[str]:
    """Validate all synthesized investigation findings."""

    errors: list[str] = []

    claim_index = build_claim_index(clinical_claims)

    evidence_index = build_evidence_index(evidence_items)

    event_index = build_event_index(canonical_timeline)

    duplicate_finding_ids = find_duplicate_finding_ids(findings)

    for finding_id in duplicate_finding_ids:
        errors.append(f"Duplicate finding_id detected: {finding_id}")

    for finding in findings:
        errors.extend(
            validate_finding_case_id(
                case_id=case_id,
                finding=finding,
            )
        )

        errors.extend(
            validate_claim_references(
                finding=finding,
                claim_index=claim_index,
            )
        )

        errors.extend(
            validate_evidence_references(
                finding=finding,
                evidence_index=evidence_index,
            )
        )

        errors.extend(
            validate_event_references(
                finding=finding,
                event_index=event_index,
            )
        )

        errors.extend(validate_finding_evidence_requirements(finding))

    return errors

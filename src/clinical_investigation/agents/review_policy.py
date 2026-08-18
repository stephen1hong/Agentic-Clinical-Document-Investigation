from __future__ import annotations

from clinical_investigation.agents.models import (
    FindingSeverity,
    FindingType,
)

NON_REVIEW_SUBTYPES = {
    "missing_event_time",
    "ambiguous_status",
    "discharge_only_medication",
}


REVIEW_SUBTYPES = {
    "insufficient_evidence_support",
    "dose_conflict",
    "conflicting_status",
    "stopped_but_later_continued",
    "discharged_as_active_after_stop",
}


def should_require_human_review(
    *,
    finding_type: FindingType,
    subtype: str,
    severity: FindingSeverity,
    upstream_requires_review: bool,
) -> bool:
    """Return whether a finding should force case-level human review."""

    if subtype in NON_REVIEW_SUBTYPES:
        return False

    if subtype in REVIEW_SUBTYPES:
        return True

    if severity == FindingSeverity.HIGH:
        return True

    if severity == FindingSeverity.MEDIUM:
        return upstream_requires_review

    return False

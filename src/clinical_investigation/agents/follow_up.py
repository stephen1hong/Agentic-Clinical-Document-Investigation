from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from clinical_investigation.agents.models import (
    FindingSeverity,
    FindingSource,
    FindingType,
    InvestigationFinding,
)

COMPLETION_TERMS = {
    "completed",
    "performed",
    "obtained",
    "done",
    "attended",
    "seen",
    "followed",
    "follow-up completed",
    "follow up completed",
    "returned",
}


PLANNING_TERMS = {
    "recommend",
    "recommended",
    "plan",
    "planned",
    "schedule",
    "scheduled",
    "should",
    "needs",
    "need",
    "follow up",
    "follow-up",
}


STOP_WORDS = {
    "a",
    "an",
    "and",
    "at",
    "be",
    "by",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
}


def normalize_text(
    value: Any,
) -> str:
    """Normalize arbitrary text for deterministic matching."""

    if value is None:
        return ""

    text = str(value).strip().lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def tokenize_action(
    text: str,
) -> set[str]:
    """Extract meaningful action tokens."""

    words = set(
        re.findall(
            r"[a-z0-9]+",
            normalize_text(text),
        )
    )

    return {word for word in words if word not in STOP_WORDS and len(word) > 2}


def parse_datetime(
    value: Any,
) -> datetime | None:
    """Parse an ISO datetime when available."""

    if not value:
        return None

    text = str(value).strip()

    if not text:
        return None

    try:
        return datetime.fromisoformat(
            text.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None


def get_follow_up_action_text(
    claim: dict[str, Any],
) -> str:
    """Build a searchable representation of a follow-up claim."""

    parts = [
        claim.get(
            "subject",
            "",
        ),
        claim.get(
            "predicate",
            "",
        ),
        claim.get(
            "value",
            "",
        ),
    ]

    return " ".join(normalize_text(part) for part in parts if part).strip()


def get_claim_time(
    claim: dict[str, Any],
) -> datetime | None:
    """Return the best available explicit claim time."""

    for field_name in (
        "time_start",
        "event_time",
        "timestamp",
        "time",
    ):
        parsed = parse_datetime(claim.get(field_name))

        if parsed is not None:
            return parsed

    return None


def get_timeline_event_time(
    event: dict[str, Any],
) -> datetime | None:
    """Return the best available timeline event time."""

    for field_name in (
        "normalized_time",
        "event_time",
        "time_start",
        "timestamp",
    ):
        parsed = parse_datetime(event.get(field_name))

        if parsed is not None:
            return parsed

    return None


def build_searchable_timeline_text(
    event: dict[str, Any],
) -> str:
    """Build deterministic searchable text for a timeline event."""

    fields = (
        "subject",
        "event_type",
        "description",
        "summary",
        "status",
        "value",
        "source_text",
    )

    return " ".join(
        normalize_text(
            event.get(
                field_name,
                "",
            )
        )
        for field_name in fields
        if event.get(field_name)
    )


def build_searchable_evidence_text(
    evidence: dict[str, Any],
) -> str:
    """Build deterministic searchable text for evidence."""

    fields = (
        "normalized_fact",
        "text_span",
        "section",
        "document_type",
        "value",
        "subject",
    )

    return " ".join(
        normalize_text(
            evidence.get(
                field_name,
                "",
            )
        )
        for field_name in fields
        if evidence.get(field_name)
    )


def has_completion_signal(
    text: str,
) -> bool:
    """Return True when text explicitly suggests completion."""

    normalized = normalize_text(text)

    return any(term in normalized for term in COMPLETION_TERMS)


def is_planning_only(
    text: str,
) -> bool:
    """Return True when text appears to describe only a plan."""

    normalized = normalize_text(text)

    has_plan = any(term in normalized for term in PLANNING_TERMS)

    return has_plan and not has_completion_signal(normalized)


def action_matches_text(
    action_text: str,
    candidate_text: str,
) -> bool:
    """Conservatively determine whether candidate concerns the action."""

    action_tokens = tokenize_action(action_text)

    candidate_tokens = tokenize_action(candidate_text)

    if not action_tokens:
        return False

    shared_tokens = action_tokens & candidate_tokens

    required_overlap = min(
        2,
        len(action_tokens),
    )

    return len(shared_tokens) >= required_overlap


def event_is_later_or_undated(
    *,
    request_time: datetime | None,
    event_time: datetime | None,
) -> bool:
    """Reject events known to occur before the follow-up request."""

    if request_time is None or event_time is None:
        return True

    return event_time >= request_time


def find_timeline_completion(
    *,
    action_text: str,
    request_time: datetime | None,
    canonical_timeline: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find explicit completion evidence in the canonical timeline."""

    for event in canonical_timeline:
        event_text = build_searchable_timeline_text(event)

        if not event_text:
            continue

        if not action_matches_text(
            action_text,
            event_text,
        ):
            continue

        if not has_completion_signal(event_text):
            continue

        if is_planning_only(event_text):
            continue

        event_time = get_timeline_event_time(event)

        if not event_is_later_or_undated(
            request_time=request_time,
            event_time=event_time,
        ):
            continue

        return event

    return None


def find_evidence_completion(
    *,
    action_text: str,
    source_evidence_ids: set[str],
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find explicit completion evidence in extracted evidence."""

    for evidence in evidence_items:
        evidence_id = str(
            evidence.get(
                "evidence_id",
                "",
            )
        )

        if evidence_id in source_evidence_ids:
            continue

        evidence_text = build_searchable_evidence_text(evidence)

        if not evidence_text:
            continue

        if not action_matches_text(
            action_text,
            evidence_text,
        ):
            continue

        if not has_completion_signal(evidence_text):
            continue

        if is_planning_only(evidence_text):
            continue

        return evidence

    return None


def build_missing_follow_up_id(
    *,
    case_id: str,
    claim_id: str,
) -> str:
    """Create a deterministic finding ID."""

    return str(
        uuid5(
            NAMESPACE_URL,
            (f"missing-follow-up:{case_id}:{claim_id}"),
        )
    )


def detect_missing_follow_ups(
    *,
    case_id: str,
    clinical_claims: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
    canonical_timeline: list[dict[str, Any]],
) -> list[InvestigationFinding]:
    """Detect requested follow-ups lacking documented completion."""

    findings: list[InvestigationFinding] = []

    follow_up_claims = [
        claim
        for claim in clinical_claims
        if str(
            claim.get(
                "claim_type",
                "",
            )
        )
        == "follow_up_action"
    ]

    for claim in follow_up_claims:
        claim_id = str(
            claim.get(
                "claim_id",
                "",
            )
        )

        if not claim_id:
            continue

        action_text = get_follow_up_action_text(claim)

        if not action_text:
            continue

        source_evidence_ids = {
            str(evidence_id)
            for evidence_id in (
                claim.get(
                    "source_evidence_ids",
                    [],
                )
                or []
            )
        }

        request_time = get_claim_time(claim)

        timeline_completion = find_timeline_completion(
            action_text=action_text,
            request_time=request_time,
            canonical_timeline=(canonical_timeline),
        )

        if timeline_completion is not None:
            continue

        evidence_completion = find_evidence_completion(
            action_text=action_text,
            source_evidence_ids=(source_evidence_ids),
            evidence_items=(evidence_items),
        )

        if evidence_completion is not None:
            continue

        finding = InvestigationFinding(
            finding_id=(
                build_missing_follow_up_id(
                    case_id=case_id,
                    claim_id=claim_id,
                )
            ),
            case_id=case_id,
            finding_type=(FindingType.MISSING_FOLLOW_UP),
            subtype=("no_documented_completion"),
            severity=(FindingSeverity.MEDIUM),
            title=("Follow-up completion not documented"),
            summary=(
                "An explicit follow-up action "
                "was documented, but no later "
                "completion was found in the "
                "available timeline or evidence: "
                f"{action_text}"
            ),
            evidence_ids=sorted(source_evidence_ids),
            claim_ids=[claim_id],
            event_ids=[],
            medication_key=None,
            confidence=0.8,
            requires_human_review=True,
            source=(FindingSource.FOLLOW_UP_ANALYSIS),
        )

        findings.append(finding)

    return findings

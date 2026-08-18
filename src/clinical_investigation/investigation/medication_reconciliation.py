"""Cross-document medication reconciliation and discrepancy detection."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import ValidationError

from clinical_investigation.investigation.medication_models import (
    DiscrepancySeverity,
    MedicationDiscrepancy,
    MedicationDiscrepancyType,
    MedicationMention,
    MedicationProfile,
    MedicationReconciliationManifest,
    MedicationSourceType,
    MedicationStatus,
)
from clinical_investigation.investigation.models import (
    ClaimType,
    ClinicalClaim,
    EvidenceItem,
)
from clinical_investigation.investigation.timeline_models import (
    CanonicalEvent,
    TimelineEventType,
)


class MedicationReconciliationError(RuntimeError):
    """Raised when medication reconciliation fails."""


MEDICATION_DOCUMENT_TYPES = {
    "admission_note",
    "progress_note",
    "medication_reconciliation",
    "discharge_summary",
    "follow_up_note",
}


STATUS_PATTERNS: tuple[
    tuple[MedicationStatus, tuple[str, ...]],
    ...,
] = (
    (
        MedicationStatus.DISCONTINUED,
        (
            "discontinued",
            "discontinue",
        ),
    ),
    (
        MedicationStatus.STOPPED,
        (
            "stopped",
            "medication stopped",
            "medication discontinued",
        ),
    ),
    (
        MedicationStatus.CONTINUED,
        (
            "continued",
            "continue",
        ),
    ),
    (
        MedicationStatus.STARTED,
        (
            "started",
            "initiated",
            "medication started",
        ),
    ),
    (
        MedicationStatus.ACTIVE,
        (
            "active during encounter",
            "currently active",
            "active",
        ),
    ),
    (
        MedicationStatus.HISTORICAL,
        (
            "historical",
            "prior medication",
        ),
    ),
)

DOSE_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*"
    r"(?:mg|mcg|g|ml|units?|iu)\b",
    flags=re.IGNORECASE,
)

FREQUENCY_PATTERN = re.compile(
    r"\b("
    r"once daily|twice daily|three times daily|"
    r"four times daily|daily|bid|tid|qid|"
    r"every \d+ hours?|q\d+h|as needed|prn"
    r")\b",
    flags=re.IGNORECASE,
)

ROUTE_PATTERN = re.compile(
    r"\b("
    r"oral|orally|po|intravenous|iv|"
    r"intramuscular|im|subcutaneous|sc|"
    r"topical|inhaled|nasal"
    r")\b",
    flags=re.IGNORECASE,
)

TABLE_METADATA_PATTERN = re.compile(
    r"\b(?:start|stop|status)\s*=",
    flags=re.IGNORECASE,
)

SYNTHETIC_DISCHARGE_MEDICATION_PREFIX_PATTERN = re.compile(
    r"^\s*medication(?:started|stopped)neardischarge\s*:\s*",
    flags=re.IGNORECASE,
)

SYNTHETIC_DISCHARGE_DATETIME_SUFFIX_PATTERN = re.compile(
    r"\s+at\s+"
    r"(?:"
    r"january|february|march|april|may|june|"
    r"july|august|september|october|november|december"
    r")"
    r"\s+\d{1,2},?\s+\d{4}"
    r"\s+at\s+\d{1,2}:\d{2}\s+UTC\s*$",
    flags=re.IGNORECASE,
)


def read_json(path: Path) -> Any:
    """Read one JSON file."""

    if not path.exists():
        raise MedicationReconciliationError(f"Required file not found: {path}")

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MedicationReconciliationError(f"Invalid JSON file {path}: {exc}") from exc


def write_json(
    path: Path,
    payload: Any,
) -> None:
    """Write formatted JSON."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def stable_identifier(
    namespace: str,
    *parts: object,
) -> str:
    """Create a deterministic identifier."""

    payload = "|".join(str(part) for part in parts)

    return str(
        uuid5(
            NAMESPACE_URL,
            f"{namespace}:{payload}",
        )
    )


def normalize_whitespace(value: str) -> str:
    """Collapse repeated whitespace."""

    return " ".join(value.split())


def normalize_datetime(
    value: datetime | None,
) -> datetime | None:
    """Normalize a datetime to UTC."""

    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


MEDICATION_SUFFIX_TERMS = {
    "tablet",
    "tablets",
    "capsule",
    "capsules",
    "oral",
    "solution",
    "injection",
    "extended release",
    "delayed release",
}


def strip_medication_metadata(
    value: str,
) -> str:
    """Remove timing and status metadata from a medication label."""

    text = value.strip()

    if ";" in text:
        text = text.split(
            ";",
            maxsplit=1,
        )[0]

    text = TABLE_METADATA_PATTERN.split(
        text,
        maxsplit=1,
    )[0]

    return normalize_whitespace(text)


def strip_synthetic_discharge_medication_wrapper(
    value: str,
) -> str:
    """Remove generated discharge-event wrapper text from a medication name."""

    cleaned = SYNTHETIC_DISCHARGE_MEDICATION_PREFIX_PATTERN.sub(
        "",
        value,
    )

    cleaned = SYNTHETIC_DISCHARGE_DATETIME_SUFFIX_PATTERN.sub(
        "",
        cleaned,
    )

    return normalize_whitespace(cleaned)


def normalize_medication_name(
    value: str,
) -> tuple[str, str]:
    """Create display and comparison forms of a medication name."""

    raw_name = strip_medication_metadata(value)

    raw_name = strip_synthetic_discharge_medication_wrapper(
        raw_name,
    )

    without_dose = DOSE_PATTERN.sub(
        "",
        raw_name,
    )

    without_route = ROUTE_PATTERN.sub(
        "",
        without_dose,
    )

    cleaned = re.sub(
        r"[^\w\s-]",
        " ",
        without_route,
    )

    cleaned = normalize_whitespace(cleaned).strip("- ")

    words = cleaned.split()

    while words and words[-1].lower() in MEDICATION_SUFFIX_TERMS:
        words.pop()

    normalized_name = " ".join(words).strip()

    if not normalized_name:
        normalized_name = raw_name

    normalized_key = re.sub(
        r"[^a-z0-9]+",
        "",
        normalized_name.lower(),
    )

    if not normalized_key:
        normalized_key = re.sub(
            r"[^a-z0-9]+",
            "",
            raw_name.lower(),
        )

    return normalized_name, normalized_key


def infer_medication_status(
    text: str,
) -> MedicationStatus:
    """Infer a medication status from explicit source wording."""

    normalized = text.lower()

    for status, terms in STATUS_PATTERNS:
        if any(term in normalized for term in terms):
            return status

    return MedicationStatus.UNKNOWN


def extract_dose(
    text: str,
) -> str | None:
    """Extract an explicitly documented medication dose."""

    match = DOSE_PATTERN.search(text)

    if match is None:
        return None

    return normalize_whitespace(match.group(0))


def extract_frequency(
    text: str,
) -> str | None:
    """Extract an explicitly documented frequency."""

    match = FREQUENCY_PATTERN.search(text)

    if match is None:
        return None

    return normalize_whitespace(match.group(0))


def normalize_route(
    value: str,
) -> str:
    """Normalize common route abbreviations."""

    normalized = value.lower()

    aliases = {
        "orally": "oral",
        "po": "oral",
        "intravenous": "iv",
        "intramuscular": "im",
        "subcutaneous": "sc",
    }

    return aliases.get(
        normalized,
        normalized,
    )


def extract_route(
    text: str,
) -> str | None:
    """Extract an explicitly documented route."""

    match = ROUTE_PATTERN.search(text)

    if match is None:
        return None

    return normalize_route(match.group(0))


def load_reconciliation_inputs(
    case_dir: Path,
) -> tuple[
    list[EvidenceItem],
    list[ClinicalClaim],
    list[CanonicalEvent],
]:
    """Load evidence, claims, and canonical timeline events."""

    raw_evidence = read_json(case_dir / "evidence_items.json")
    raw_claims = read_json(case_dir / "clinical_claims.json")
    raw_timeline = read_json(case_dir / "canonical_timeline.json")

    if not isinstance(raw_evidence, list):
        raise MedicationReconciliationError("evidence_items.json must contain a list")

    if not isinstance(raw_claims, list):
        raise MedicationReconciliationError("clinical_claims.json must contain a list")

    if not isinstance(raw_timeline, list):
        raise MedicationReconciliationError("canonical_timeline.json must contain a list")

    try:
        evidence_items = [EvidenceItem.model_validate(item) for item in raw_evidence]

        claims = [ClinicalClaim.model_validate(item) for item in raw_claims]

        timeline_events = [CanonicalEvent.model_validate(item) for item in raw_timeline]
    except ValidationError as exc:
        raise MedicationReconciliationError(f"Invalid reconciliation input: {exc}") from exc

    return (
        evidence_items,
        claims,
        timeline_events,
    )


def build_evidence_lookup(
    evidence_items: list[EvidenceItem],
) -> dict[str, EvidenceItem]:
    """Index evidence items by ID."""

    return {item.evidence_id: item for item in evidence_items}


def build_claim_lookup(
    claims: list[ClinicalClaim],
) -> dict[str, ClinicalClaim]:
    """Index clinical claims by ID."""

    return {claim.claim_id: claim for claim in claims}


def medication_claims(
    claims: list[ClinicalClaim],
) -> list[ClinicalClaim]:
    """Return claims explicitly classified as medication claims."""

    return [claim for claim in claims if claim.claim_type == ClaimType.MEDICATION_STATUS]


def claim_supporting_evidence(
    claim: ClinicalClaim,
    evidence_by_id: dict[str, EvidenceItem],
) -> list[EvidenceItem]:
    """Resolve evidence referenced by a claim."""

    return [
        evidence_by_id[evidence_id]
        for evidence_id in claim.source_evidence_ids
        if evidence_id in evidence_by_id
    ]


def mention_text_from_claim(
    claim: ClinicalClaim,
    evidence_items: list[EvidenceItem],
) -> str:
    """Build source text for parsing a medication mention."""

    return normalize_whitespace(
        " ".join(
            [
                claim.subject,
                claim.predicate,
                claim.value,
                *[item.normalized_fact for item in evidence_items],
            ]
        )
    )


def build_claim_medication_mention(
    *,
    claim: ClinicalClaim,
    evidence_items: list[EvidenceItem],
) -> MedicationMention:
    """Build one medication mention from one medication claim."""

    source_text = mention_text_from_claim(
        claim,
        evidence_items,
    )

    normalized_name, normalized_key = normalize_medication_name(claim.subject)

    document_types = [item.document_type.value for item in evidence_items]

    document_type = document_types[0] if document_types else None

    sections = [item.section for item in evidence_items]

    mention_id = stable_identifier(
        "medication-mention",
        claim.case_id,
        claim.claim_id,
        normalized_key,
        source_text,
    )

    source_tables = [item.source_table for item in evidence_items if item.source_table is not None]

    source_rows = [item.source_row for item in evidence_items if item.source_row is not None]

    return MedicationMention(
        mention_id=mention_id,
        case_id=claim.case_id,
        medication_name_raw=claim.subject,
        normalized_name=normalized_name,
        normalized_key=normalized_key,
        status=infer_medication_status(source_text),
        dose=extract_dose(source_text),
        route=extract_route(source_text),
        frequency=extract_frequency(source_text),
        start_time=normalize_datetime(claim.time_start),
        stop_time=normalize_datetime(claim.time_end),
        event_time=normalize_datetime(claim.time_start),
        document_type=document_type,
        document_section=(sections[0] if sections else None),
        source_type=MedicationSourceType.CLAIM,
        source_claim_ids=[claim.claim_id],
        evidence_ids=[item.evidence_id for item in evidence_items],
        source_tables=source_tables,
        source_rows=source_rows,
        confidence=claim.extraction_confidence,
    )


MEDICATION_TIMELINE_TYPES = {
    TimelineEventType.MEDICATION_START,
    TimelineEventType.MEDICATION_STOP,
    TimelineEventType.MEDICATION_STATUS,
}


def timeline_status(
    event: CanonicalEvent,
) -> MedicationStatus:
    """Map a timeline event type to medication status."""

    if event.event_type == TimelineEventType.MEDICATION_START:
        return MedicationStatus.STARTED

    if event.event_type == TimelineEventType.MEDICATION_STOP:
        return MedicationStatus.STOPPED

    return infer_medication_status(event.description)


def build_timeline_medication_mention(
    event: CanonicalEvent,
) -> MedicationMention:
    """Build one medication mention from a timeline event."""

    normalized_name, normalized_key = normalize_medication_name(event.subject)

    mention_id = stable_identifier(
        "timeline-medication-mention",
        event.case_id,
        event.event_id,
        normalized_key,
        event.event_type.value,
    )

    status = timeline_status(event)

    return MedicationMention(
        mention_id=mention_id,
        case_id=event.case_id,
        medication_name_raw=event.subject,
        normalized_name=normalized_name,
        normalized_key=normalized_key,
        status=status,
        dose=extract_dose(event.description),
        route=extract_route(event.description),
        frequency=extract_frequency(event.description),
        start_time=(event.normalized_time if status == MedicationStatus.STARTED else None),
        stop_time=(event.normalized_time if status == MedicationStatus.STOPPED else None),
        event_time=event.normalized_time,
        document_type=(event.source_document_types[0] if event.source_document_types else None),
        document_section=None,
        source_type=MedicationSourceType.TIMELINE,
        source_claim_ids=(event.source_claim_ids),
        evidence_ids=event.evidence_ids,
        timeline_event_ids=[event.event_id],
        source_tables=event.source_tables,
        source_rows=event.source_rows,
        confidence=event.confidence,
    )


def extract_medication_mentions(
    *,
    evidence_items: list[EvidenceItem],
    claims: list[ClinicalClaim],
    timeline_events: list[CanonicalEvent],
) -> list[MedicationMention]:
    """Extract all medication mentions from claims and timeline."""

    evidence_by_id = build_evidence_lookup(evidence_items)

    mentions: list[MedicationMention] = []

    for claim in medication_claims(claims):
        supporting_evidence = claim_supporting_evidence(
            claim,
            evidence_by_id,
        )

        if not supporting_evidence:
            continue

        mentions.append(
            build_claim_medication_mention(
                claim=claim,
                evidence_items=(supporting_evidence),
            )
        )

    for event in timeline_events:
        if event.event_type not in MEDICATION_TIMELINE_TYPES:
            continue

        mentions.append(build_timeline_medication_mention(event))

    return deduplicate_mentions(mentions)


def mention_merge_key(
    mention: MedicationMention,
) -> tuple[
    str,
    str,
    str,
    str,
]:
    """Create a conservative medication mention key."""

    return (
        mention.normalized_key,
        mention.status.value,
        (mention.event_time.isoformat() if mention.event_time else "unknown"),
        mention.document_type or "unknown",
    )


def merge_mentions(
    mentions: list[MedicationMention],
) -> MedicationMention:
    """Merge equivalent medication mentions."""

    primary = max(
        mentions,
        key=lambda item: item.confidence,
    )

    return primary.model_copy(
        update={
            "source_claim_ids": list(
                dict.fromkeys(
                    claim_id for mention in mentions for claim_id in (mention.source_claim_ids)
                )
            ),
            "evidence_ids": list(
                dict.fromkeys(
                    evidence_id for mention in mentions for evidence_id in (mention.evidence_ids)
                )
            ),
            "timeline_event_ids": list(
                dict.fromkeys(
                    event_id for mention in mentions for event_id in (mention.timeline_event_ids)
                )
            ),
            "source_tables": list(
                dict.fromkeys(table for mention in mentions for table in (mention.source_tables))
            ),
            "source_rows": list(
                dict.fromkeys(row for mention in mentions for row in (mention.source_rows))
            ),
            "confidence": max(mention.confidence for mention in mentions),
        }
    )


def deduplicate_mentions(
    mentions: list[MedicationMention],
) -> list[MedicationMention]:
    """Merge conservatively equivalent medication mentions."""

    groups: dict[
        tuple[str, str, str, str],
        list[MedicationMention],
    ] = {}

    for mention in mentions:
        groups.setdefault(
            mention_merge_key(mention),
            [],
        ).append(mention)

    return [merge_mentions(group) for group in groups.values()]


def status_priority(
    status: MedicationStatus,
) -> int:
    """Define recency-independent status precedence."""

    priorities = {
        MedicationStatus.DISCONTINUED: 70,
        MedicationStatus.STOPPED: 60,
        MedicationStatus.CONTINUED: 50,
        MedicationStatus.ACTIVE: 40,
        MedicationStatus.STARTED: 30,
        MedicationStatus.HISTORICAL: 20,
        MedicationStatus.UNKNOWN: 10,
    }

    return priorities[status]


def latest_status_mention(
    mentions: list[MedicationMention],
) -> MedicationMention:
    """Choose the strongest latest medication mention."""

    return max(
        mentions,
        key=lambda mention: (
            mention.event_time or datetime.min.replace(tzinfo=UTC),
            status_priority(mention.status),
            mention.confidence,
        ),
    )


def infer_profile_status(
    mentions: list[MedicationMention],
) -> tuple[
    MedicationStatus,
    float,
]:
    """Infer medication status at encounter end."""

    discharge_mentions = [
        mention for mention in mentions if mention.document_type == "discharge_summary"
    ]

    if discharge_mentions:
        selected = latest_status_mention(discharge_mentions)

        return (
            selected.status,
            selected.confidence,
        )

    selected = latest_status_mention(mentions)

    return (
        selected.status,
        selected.confidence * 0.9,
    )


def build_medication_profile(
    mentions: list[MedicationMention],
) -> MedicationProfile:
    """Aggregate all mentions for one medication."""

    first = mentions[0]

    start_times = [mention.start_time for mention in mentions if mention.start_time is not None]

    stop_times = [mention.stop_time for mention in mentions if mention.stop_time is not None]

    event_times = [mention.event_time for mention in mentions if mention.event_time is not None]

    inferred_status, confidence = infer_profile_status(mentions)

    profile_id = stable_identifier(
        "medication-profile",
        first.case_id,
        first.normalized_key,
    )

    return MedicationProfile(
        profile_id=profile_id,
        case_id=first.case_id,
        normalized_name=first.normalized_name,
        normalized_key=first.normalized_key,
        raw_names=list(dict.fromkeys(mention.medication_name_raw for mention in mentions)),
        statuses=list(dict.fromkeys(mention.status for mention in mentions)),
        earliest_start_time=(min(start_times) if start_times else None),
        latest_stop_time=(max(stop_times) if stop_times else None),
        latest_event_time=(max(event_times) if event_times else None),
        doses=list(dict.fromkeys(mention.dose for mention in mentions if mention.dose)),
        routes=list(dict.fromkeys(mention.route for mention in mentions if mention.route)),
        frequencies=list(
            dict.fromkeys(mention.frequency for mention in mentions if mention.frequency)
        ),
        document_types=list(
            dict.fromkeys(mention.document_type for mention in mentions if mention.document_type)
        ),
        mention_ids=[mention.mention_id for mention in mentions],
        evidence_ids=list(
            dict.fromkeys(
                evidence_id for mention in mentions for evidence_id in (mention.evidence_ids)
            )
        ),
        source_claim_ids=list(
            dict.fromkeys(
                claim_id for mention in mentions for claim_id in (mention.source_claim_ids)
            )
        ),
        timeline_event_ids=list(
            dict.fromkeys(
                event_id for mention in mentions for event_id in (mention.timeline_event_ids)
            )
        ),
        inferred_status_at_discharge=(inferred_status),
        status_confidence=confidence,
    )


def build_medication_profiles(
    mentions: list[MedicationMention],
) -> list[MedicationProfile]:
    """Group medication mentions into canonical profiles."""

    grouped: dict[
        str,
        list[MedicationMention],
    ] = {}

    for mention in mentions:
        grouped.setdefault(
            mention.normalized_key,
            [],
        ).append(mention)

    return [build_medication_profile(group) for group in grouped.values()]


def build_discrepancy(
    *,
    profile: MedicationProfile,
    discrepancy_type: MedicationDiscrepancyType,
    severity: DiscrepancySeverity,
    summary: str,
    rationale: str,
    mentions: list[MedicationMention],
    conflicting_values: list[str] | None = None,
    missing_evidence_description: str | None = None,
    confidence: float,
) -> MedicationDiscrepancy:
    """Create one evidence-grounded discrepancy."""

    discrepancy_id = stable_identifier(
        "medication-discrepancy",
        profile.case_id,
        profile.normalized_key,
        discrepancy_type.value,
        summary,
    )

    return MedicationDiscrepancy(
        discrepancy_id=discrepancy_id,
        case_id=profile.case_id,
        medication_key=profile.normalized_key,
        medication_name=profile.normalized_name,
        discrepancy_type=discrepancy_type,
        severity=severity,
        summary=summary,
        rationale=rationale,
        conflicting_values=(conflicting_values or []),
        missing_evidence_description=(missing_evidence_description),
        mention_ids=[mention.mention_id for mention in mentions],
        evidence_ids=list(
            dict.fromkeys(
                evidence_id for mention in mentions for evidence_id in (mention.evidence_ids)
            )
        ),
        source_claim_ids=list(
            dict.fromkeys(
                claim_id for mention in mentions for claim_id in (mention.source_claim_ids)
            )
        ),
        timeline_event_ids=list(
            dict.fromkeys(
                event_id for mention in mentions for event_id in (mention.timeline_event_ids)
            )
        ),
        confidence=confidence,
        requires_human_review=True,
    )


ACTIVE_LIKE_STATUSES = {
    MedicationStatus.ACTIVE,
    MedicationStatus.CONTINUED,
}

STOPPED_LIKE_STATUSES = {
    MedicationStatus.STOPPED,
    MedicationStatus.DISCONTINUED,
}


def is_explicit_status_mention(
    mention: MedicationMention,
) -> bool:
    """Return whether a mention carries an explicit comparable status."""

    if mention.source_type == MedicationSourceType.TIMELINE:
        return False

    return mention.status in (ACTIVE_LIKE_STATUSES | STOPPED_LIKE_STATUSES)


def detect_conflicting_status(
    profile: MedicationProfile,
    mentions: list[MedicationMention],
) -> list[MedicationDiscrepancy]:
    """Detect incompatible explicit medication status assertions."""

    comparable_mentions = [mention for mention in mentions if is_explicit_status_mention(mention)]

    active_mentions = [
        mention for mention in comparable_mentions if mention.status in ACTIVE_LIKE_STATUSES
    ]

    stopped_mentions = [
        mention for mention in comparable_mentions if mention.status in STOPPED_LIKE_STATUSES
    ]

    if not active_mentions or not stopped_mentions:
        return []

    conflicting_mentions = [
        *active_mentions,
        *stopped_mentions,
    ]

    conflicting_values = list(
        dict.fromkeys(mention.status.value for mention in conflicting_mentions)
    )

    confidence = min(mention.confidence for mention in conflicting_mentions)

    return [
        build_discrepancy(
            profile=profile,
            discrepancy_type=(MedicationDiscrepancyType.CONFLICTING_STATUS),
            severity=DiscrepancySeverity.HIGH,
            summary=(f"{profile.normalized_name} has conflicting active and stopped statuses."),
            rationale=(
                "Independent non-timeline medication mentions "
                "contain explicitly incompatible active/continued "
                "and stopped/discontinued statuses."
            ),
            mentions=conflicting_mentions,
            conflicting_values=conflicting_values,
            confidence=confidence,
        )
    ]


def detect_stopped_but_later_continued(
    profile: MedicationProfile,
    mentions: list[MedicationMention],
) -> list[MedicationDiscrepancy]:
    """Detect continuation after an explicit stop."""

    stop_mentions = [
        mention
        for mention in mentions
        if (mention.status in STOPPED_LIKE_STATUSES and mention.event_time is not None)
    ]

    active_mentions = [
        mention
        for mention in mentions
        if (mention.status in ACTIVE_LIKE_STATUSES and mention.event_time is not None)
    ]

    discrepancies: list[MedicationDiscrepancy] = []

    for stopped in stop_mentions:
        later_active = [
            mention for mention in active_mentions if (mention.event_time > stopped.event_time)
        ]

        if not later_active:
            continue

        relevant_mentions = [
            stopped,
            *later_active,
        ]

        discrepancies.append(
            build_discrepancy(
                profile=profile,
                discrepancy_type=(MedicationDiscrepancyType.STOPPED_BUT_LATER_CONTINUED),
                severity=(DiscrepancySeverity.HIGH),
                summary=(
                    f"{profile.normalized_name} is represented as active after an explicit stop."
                ),
                rationale=(
                    f"A stop was documented at "
                    f"{stopped.event_time.isoformat()}, "
                    "but a later source represented the "
                    "medication as active or continued."
                ),
                mentions=relevant_mentions,
                conflicting_values=[
                    stopped.status.value,
                    *[mention.status.value for mention in later_active],
                ],
                confidence=1.0,
            )
        )

    return discrepancies


def detect_missing_at_discharge(
    profile: MedicationProfile,
    mentions: list[MedicationMention],
) -> list[MedicationDiscrepancy]:
    """Detect active medication absent from discharge documentation."""

    pre_discharge_active = [
        mention
        for mention in mentions
        if (mention.status in ACTIVE_LIKE_STATUSES and mention.document_type != "discharge_summary")
    ]

    discharge_mentions = [
        mention for mention in mentions if mention.document_type == "discharge_summary"
    ]

    if not pre_discharge_active or discharge_mentions:
        return []

    return [
        build_discrepancy(
            profile=profile,
            discrepancy_type=(MedicationDiscrepancyType.MISSING_AT_DISCHARGE),
            severity=DiscrepancySeverity.MEDIUM,
            summary=(
                f"{profile.normalized_name} was active "
                "before discharge but was not found in "
                "the discharge summary."
            ),
            rationale=(
                "At least one pre-discharge source "
                "represented the medication as active, "
                "started, or continued. No matching "
                "discharge-summary medication mention "
                "was found."
            ),
            mentions=pre_discharge_active,
            missing_evidence_description=(
                "A discharge-summary medication status was not found in the supplied records."
            ),
            confidence=0.9,
        )
    ]


def detect_discharge_only_medication(
    profile: MedicationProfile,
    mentions: list[MedicationMention],
) -> list[MedicationDiscrepancy]:
    """Detect medications documented only in discharge material."""

    discharge_mentions = [
        mention for mention in mentions if mention.document_type == "discharge_summary"
    ]

    non_discharge_mentions = [
        mention for mention in mentions if mention.document_type != "discharge_summary"
    ]

    if not discharge_mentions or non_discharge_mentions:
        return []

    return [
        build_discrepancy(
            profile=profile,
            discrepancy_type=(MedicationDiscrepancyType.DISCHARGE_ONLY_MEDICATION),
            severity=DiscrepancySeverity.LOW,
            summary=(f"{profile.normalized_name} appears only in discharge documentation."),
            rationale=(
                "No matching medication mention was "
                "found in admission, progress, "
                "reconciliation, follow-up, or timeline "
                "sources."
            ),
            mentions=discharge_mentions,
            missing_evidence_description=(
                "Pre-discharge medication evidence was not found in the supplied records."
            ),
            confidence=0.85,
        )
    ]


def normalized_attribute(
    value: str,
) -> str:
    """Normalize a medication attribute for comparison."""

    return re.sub(
        r"\s+",
        "",
        value.lower(),
    )


def detect_dose_conflict(
    profile: MedicationProfile,
    mentions: list[MedicationMention],
) -> list[MedicationDiscrepancy]:
    """Detect conflicting explicit doses."""

    dose_mentions = [mention for mention in mentions if mention.dose]

    normalized_doses = {
        normalized_attribute(mention.dose) for mention in dose_mentions if mention.dose
    }

    if len(normalized_doses) <= 1:
        return []

    return [
        build_discrepancy(
            profile=profile,
            discrepancy_type=(MedicationDiscrepancyType.DOSE_CONFLICT),
            severity=DiscrepancySeverity.HIGH,
            summary=(f"{profile.normalized_name} has conflicting documented doses."),
            rationale=(
                "Multiple explicit dose values were found for the same normalized medication."
            ),
            mentions=dose_mentions,
            conflicting_values=profile.doses,
            confidence=1.0,
        )
    ]


def detect_frequency_conflict(
    profile: MedicationProfile,
    mentions: list[MedicationMention],
) -> list[MedicationDiscrepancy]:
    """Detect conflicting explicit frequencies."""

    frequency_mentions = [mention for mention in mentions if mention.frequency]

    normalized_values = {
        normalized_attribute(mention.frequency)
        for mention in frequency_mentions
        if mention.frequency
    }

    if len(normalized_values) <= 1:
        return []

    return [
        build_discrepancy(
            profile=profile,
            discrepancy_type=(MedicationDiscrepancyType.FREQUENCY_CONFLICT),
            severity=DiscrepancySeverity.MEDIUM,
            summary=(f"{profile.normalized_name} has conflicting documented frequencies."),
            rationale=(
                "Multiple explicit frequency values were found for the same normalized medication."
            ),
            mentions=frequency_mentions,
            conflicting_values=(profile.frequencies),
            confidence=1.0,
        )
    ]


def detect_route_conflict(
    profile: MedicationProfile,
    mentions: list[MedicationMention],
) -> list[MedicationDiscrepancy]:
    """Detect conflicting explicit routes."""

    route_mentions = [mention for mention in mentions if mention.route]

    normalized_values = {
        normalized_attribute(mention.route) for mention in route_mentions if mention.route
    }

    if len(normalized_values) <= 1:
        return []

    return [
        build_discrepancy(
            profile=profile,
            discrepancy_type=(MedicationDiscrepancyType.ROUTE_CONFLICT),
            severity=DiscrepancySeverity.MEDIUM,
            summary=(f"{profile.normalized_name} has conflicting documented routes."),
            rationale=(
                "Multiple explicit administration "
                "routes were found for the same "
                "normalized medication."
            ),
            mentions=route_mentions,
            conflicting_values=profile.routes,
            confidence=1.0,
        )
    ]


def detect_ambiguous_status(
    profile: MedicationProfile,
    mentions: list[MedicationMention],
) -> list[MedicationDiscrepancy]:
    """Flag medications with no explicit lifecycle status."""

    if any(mention.status != MedicationStatus.UNKNOWN for mention in mentions):
        return []

    return [
        build_discrepancy(
            profile=profile,
            discrepancy_type=(MedicationDiscrepancyType.AMBIGUOUS_STATUS),
            severity=DiscrepancySeverity.INFO,
            summary=(f"The encounter status of {profile.normalized_name} is unclear."),
            rationale=(
                "Medication mentions were found, but no "
                "explicit active, started, continued, "
                "stopped, or discontinued status was "
                "identified."
            ),
            mentions=mentions,
            missing_evidence_description=("An explicit medication lifecycle status was not found."),
            confidence=1.0,
        )
    ]


def detect_profile_discrepancies(
    profile: MedicationProfile,
    mentions: list[MedicationMention],
) -> list[MedicationDiscrepancy]:
    """Run all medication discrepancy rules."""

    return [
        *detect_conflicting_status(
            profile,
            mentions,
        ),
        *detect_stopped_but_later_continued(
            profile,
            mentions,
        ),
        *detect_missing_at_discharge(
            profile,
            mentions,
        ),
        *detect_discharge_only_medication(
            profile,
            mentions,
        ),
        *detect_dose_conflict(
            profile,
            mentions,
        ),
        *detect_frequency_conflict(
            profile,
            mentions,
        ),
        *detect_route_conflict(
            profile,
            mentions,
        ),
        *detect_ambiguous_status(
            profile,
            mentions,
        ),
    ]


def deduplicate_discrepancies(
    discrepancies: list[MedicationDiscrepancy],
) -> list[MedicationDiscrepancy]:
    """Remove exact duplicate discrepancy findings."""

    return list(
        {discrepancy.discrepancy_id: (discrepancy) for discrepancy in discrepancies}.values()
    )


def detect_medication_discrepancies(
    *,
    profiles: list[MedicationProfile],
    mentions: list[MedicationMention],
) -> list[MedicationDiscrepancy]:
    """Detect discrepancies for all medication profiles."""

    mentions_by_key: dict[
        str,
        list[MedicationMention],
    ] = {}

    for mention in mentions:
        mentions_by_key.setdefault(
            mention.normalized_key,
            [],
        ).append(mention)

    discrepancies: list[MedicationDiscrepancy] = []

    for profile in profiles:
        profile_mentions = mentions_by_key.get(
            profile.normalized_key,
            [],
        )

        discrepancies.extend(
            detect_profile_discrepancies(
                profile,
                profile_mentions,
            )
        )

    return deduplicate_discrepancies(discrepancies)


def reconcile_case_medications(
    case_dir: Path,
) -> tuple[
    list[MedicationMention],
    list[MedicationProfile],
    list[MedicationDiscrepancy],
]:
    """Reconcile medications for one investigation case."""

    (
        evidence_items,
        claims,
        timeline_events,
    ) = load_reconciliation_inputs(case_dir)

    mentions = extract_medication_mentions(
        evidence_items=evidence_items,
        claims=claims,
        timeline_events=timeline_events,
    )

    profiles = build_medication_profiles(mentions)

    discrepancies = detect_medication_discrepancies(
        profiles=profiles,
        mentions=mentions,
    )

    return (
        mentions,
        profiles,
        discrepancies,
    )


def build_medication_reconciliation(
    case_dir: Path,
) -> Path:
    """Write medication reconciliation outputs."""

    (
        evidence_items,
        claims,
        timeline_events,
    ) = load_reconciliation_inputs(case_dir)

    (
        mentions,
        profiles,
        discrepancies,
    ) = reconcile_case_medications(case_dir)

    write_json(
        case_dir / "medication_mentions.json",
        [mention.model_dump(mode="json") for mention in mentions],
    )

    write_json(
        case_dir / "medication_profiles.json",
        [profile.model_dump(mode="json") for profile in profiles],
    )

    write_json(
        case_dir / "medication_discrepancies.json",
        [discrepancy.model_dump(mode="json") for discrepancy in discrepancies],
    )

    mention_counts = Counter(mention.document_type or "unknown" for mention in mentions)

    discrepancy_counts = Counter(
        discrepancy.discrepancy_type.value for discrepancy in discrepancies
    )

    manifest = MedicationReconciliationManifest(
        schema_version="1.0",
        case_id=case_dir.name,
        generated_at=datetime.now(UTC),
        reconciliation_method=("deterministic_cross_document_v1"),
        source_evidence_count=len(evidence_items),
        source_claim_count=len(claims),
        source_timeline_event_count=len(timeline_events),
        medication_mention_count=len(mentions),
        medication_profile_count=len(profiles),
        discrepancy_count=len(discrepancies),
        mention_count_by_document=dict(mention_counts),
        discrepancy_count_by_type=dict(discrepancy_counts),
    )

    write_json(
        case_dir / "medication_reconciliation_manifest.json",
        manifest.model_dump(mode="json"),
    )

    return case_dir

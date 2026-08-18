"""Reconstruct canonical timelines from evidence and claims."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import ValidationError

from clinical_investigation.investigation.models import (
    ClaimType,
    ClinicalClaim,
    EvidenceItem,
)
from clinical_investigation.investigation.timeline_models import (
    CanonicalEvent,
    ConflictSeverity,
    TimelineConflict,
    TimelineConflictType,
    TimelineEventType,
    TimelineManifest,
    TimePrecision,
    TimeSource,
)


class TimelineReconstructionError(RuntimeError):
    """Raised when timeline reconstruction fails."""


ISO_DATETIME_PATTERN = re.compile(
    r"\b\d{4}-\d{2}-\d{2}"
    r"(?:T[0-2]\d:[0-5]\d"
    r"(?::[0-5]\d(?:\.\d+)?)?"
    r"(?:Z|[+-]\d{2}:\d{2})?)?\b"
)

HUMAN_DATETIME_PATTERN = re.compile(
    r"\b("
    r"January|February|March|April|May|June|"
    r"July|August|September|October|November|December"
    r")\s+\d{1,2},\s+\d{4}"
    r"(?:\s+at\s+\d{1,2}:\d{2}\s+UTC)?\b",
    flags=re.IGNORECASE,
)

UNKNOWN_TIME_TERMS = {
    "",
    "unknown",
    "not documented",
    "none",
    "null",
    "—",
}


@dataclass(frozen=True)
class ParsedTime:
    """A parsed timestamp and its metadata."""

    value: datetime | None
    precision: TimePrecision
    source: TimeSource


def read_json(path: Path) -> Any:
    """Read a JSON file."""

    if not path.exists():
        raise TimelineReconstructionError(f"Required file not found: {path}")

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TimelineReconstructionError(f"Invalid JSON file {path}: {exc}") from exc


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
    """Create a reproducible identifier."""

    payload = "|".join(str(part) for part in parts)

    return str(
        uuid5(
            NAMESPACE_URL,
            f"{namespace}:{payload}",
        )
    )


def normalize_datetime(
    value: datetime,
) -> datetime:
    """Normalize a datetime to UTC."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def parse_iso_time(
    value: str,
) -> ParsedTime | None:
    """Parse an ISO-formatted date or datetime."""

    text = value.strip()

    if not text:
        return None

    normalized = f"{text[:-1]}+00:00" if text.endswith("Z") else text

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(normalized)
        except ValueError:
            return None

        return ParsedTime(
            value=datetime.combine(
                parsed_date,
                datetime.min.time(),
                tzinfo=UTC,
            ),
            precision=TimePrecision.DATE,
            source=TimeSource.DOCUMENT_TEXT,
        )

    has_time = "T" in text or " " in text

    return ParsedTime(
        value=normalize_datetime(parsed),
        precision=(TimePrecision.DATETIME if has_time else TimePrecision.DATE),
        source=TimeSource.DOCUMENT_TEXT,
    )


def parse_human_time(
    value: str,
) -> ParsedTime | None:
    """Parse generated human-readable clinical dates."""

    text = value.strip()

    formats = (
        "%B %d, %Y at %H:%M UTC",
        "%B %d, %Y",
    )

    for format_string in formats:
        try:
            parsed = datetime.strptime(
                text,
                format_string,
            )
        except ValueError:
            continue

        return ParsedTime(
            value=parsed.replace(tzinfo=UTC),
            precision=(TimePrecision.DATETIME if " at " in text else TimePrecision.DATE),
            source=TimeSource.DOCUMENT_TEXT,
        )

    return None


def extract_time_from_text(
    text: str,
) -> ParsedTime:
    """Extract the first recognizable timestamp from text."""

    normalized = text.strip()

    if normalized.lower() in UNKNOWN_TIME_TERMS:
        return ParsedTime(
            value=None,
            precision=TimePrecision.UNKNOWN,
            source=TimeSource.UNKNOWN,
        )

    iso_match = ISO_DATETIME_PATTERN.search(normalized)

    if iso_match:
        parsed = parse_iso_time(iso_match.group(0))

        if parsed is not None:
            return parsed

    human_match = HUMAN_DATETIME_PATTERN.search(normalized)

    if human_match:
        parsed = parse_human_time(human_match.group(0))

        if parsed is not None:
            return parsed

    return ParsedTime(
        value=None,
        precision=TimePrecision.UNKNOWN,
        source=TimeSource.UNKNOWN,
    )


def resolve_event_time(
    claim: ClinicalClaim,
    evidence_items: list[EvidenceItem],
) -> ParsedTime:
    """Resolve the strongest timestamp for a claim."""

    if claim.time_start is not None:
        return ParsedTime(
            value=normalize_datetime(claim.time_start),
            precision=TimePrecision.DATETIME,
            source=TimeSource.CLAIM_FIELD,
        )

    for evidence in evidence_items:
        if evidence.event_time is not None:
            return ParsedTime(
                value=normalize_datetime(evidence.event_time),
                precision=TimePrecision.DATETIME,
                source=TimeSource.EVIDENCE_FIELD,
            )

    text_candidates = [
        claim.value,
        claim.subject,
        *[evidence.normalized_fact for evidence in evidence_items],
    ]

    for candidate in text_candidates:
        parsed = extract_time_from_text(candidate)

        if parsed.value is not None:
            return parsed

    return ParsedTime(
        value=None,
        precision=TimePrecision.UNKNOWN,
        source=TimeSource.UNKNOWN,
    )


def normalized_text(value: str) -> str:
    """Normalize text for rule matching."""

    return " ".join(value.lower().strip().split())


def infer_event_type(
    claim: ClinicalClaim,
) -> TimelineEventType:
    """Map a clinical claim to a timeline event type."""

    text = normalized_text(f"{claim.subject} {claim.predicate} {claim.value}")

    if claim.claim_type == ClaimType.ENCOUNTER_EVENT:
        if any(
            term in text
            for term in (
                "encounter start",
                "admission",
                "entered",
            )
        ):
            return TimelineEventType.ENCOUNTER_START

        if any(
            term in text
            for term in (
                "encounter stop",
                "discharge",
                "encounter end",
            )
        ):
            return TimelineEventType.ENCOUNTER_STOP

        return TimelineEventType.NARRATIVE_EVENT

    if claim.claim_type == ClaimType.CONDITION_PRESENCE:
        return TimelineEventType.CONDITION_EVENT

    if claim.claim_type == ClaimType.MEDICATION_STATUS:
        if any(
            term in text
            for term in (
                "stopped",
                "discontinued",
                "stop=",
            )
        ):
            return TimelineEventType.MEDICATION_STOP

        if any(
            term in text
            for term in (
                "started",
                "initiated",
                "start=",
            )
        ):
            return TimelineEventType.MEDICATION_START

        return TimelineEventType.MEDICATION_STATUS

    if claim.claim_type == ClaimType.OBSERVATION_RESULT:
        return TimelineEventType.OBSERVATION_RESULT

    if claim.claim_type == ClaimType.PROCEDURE_EVENT:
        return TimelineEventType.PROCEDURE_EVENT

    if claim.claim_type == ClaimType.FOLLOW_UP_ACTION:
        return TimelineEventType.FOLLOW_UP_ACTION

    return TimelineEventType.NARRATIVE_EVENT


def evidence_lookup(
    evidence_items: list[EvidenceItem],
) -> dict[str, EvidenceItem]:
    """Index evidence by evidence ID."""

    return {item.evidence_id: item for item in evidence_items}


def build_event_from_claim(
    claim: ClinicalClaim,
    evidence_by_id: dict[str, EvidenceItem],
) -> CanonicalEvent:
    """Convert one claim into one canonical event."""

    supporting_evidence = [
        evidence_by_id[evidence_id]
        for evidence_id in claim.source_evidence_ids
        if evidence_id in evidence_by_id
    ]

    if not supporting_evidence:
        raise TimelineReconstructionError(
            f"Claim {claim.claim_id} has no available supporting evidence"
        )

    parsed_time = resolve_event_time(
        claim,
        supporting_evidence,
    )

    event_type = infer_event_type(claim)

    document_types = [item.document_type.value for item in supporting_evidence]

    source_tables = [
        item.source_table for item in supporting_evidence if item.source_table is not None
    ]

    source_rows = [item.source_row for item in supporting_evidence if item.source_row is not None]

    event_id = stable_identifier(
        "canonical-event",
        claim.case_id,
        event_type.value,
        claim.subject,
        claim.predicate,
        claim.value,
        (parsed_time.value.isoformat() if parsed_time.value else "unknown"),
    )

    return CanonicalEvent(
        event_id=event_id,
        case_id=claim.case_id,
        event_type=event_type,
        subject=claim.subject,
        description=(f"{claim.predicate}: {claim.value}"),
        normalized_time=parsed_time.value,
        time_end=(normalize_datetime(claim.time_end) if claim.time_end is not None else None),
        time_precision=parsed_time.precision,
        time_source=parsed_time.source,
        source_claim_ids=[claim.claim_id],
        evidence_ids=claim.source_evidence_ids,
        source_document_types=document_types,
        source_tables=source_tables,
        source_rows=source_rows,
        confidence=claim.extraction_confidence,
    )


def header_value(
    evidence: EvidenceItem,
    label: str,
) -> str | None:
    """Read a value from a generated document header."""

    fact = evidence.normalized_fact

    prefix = f"{label.lower()}:"

    if not fact.lower().startswith(prefix):
        return None

    value = fact.split(
        ":",
        maxsplit=1,
    )[1].strip()

    return value or None


def build_encounter_boundary_events(
    *,
    case_id: str,
    evidence_items: list[EvidenceItem],
) -> list[CanonicalEvent]:
    """Build encounter start and stop events from headers."""

    boundaries = (
        (
            "Encounter Start",
            TimelineEventType.ENCOUNTER_START,
        ),
        (
            "Encounter Stop",
            TimelineEventType.ENCOUNTER_STOP,
        ),
    )

    events: list[CanonicalEvent] = []

    for label, event_type in boundaries:
        matching_items: list[EvidenceItem] = []
        parsed_times: list[ParsedTime] = []

        for evidence in evidence_items:
            value = header_value(
                evidence,
                label,
            )

            if value is None:
                continue

            parsed = extract_time_from_text(value)

            if parsed.value is None:
                continue

            matching_items.append(evidence)
            parsed_times.append(parsed)

        if not matching_items:
            continue

        unique_times = sorted({parsed.value for parsed in parsed_times if parsed.value is not None})

        for normalized_time in unique_times:
            related_items = [
                evidence
                for evidence in matching_items
                if extract_time_from_text(
                    header_value(
                        evidence,
                        label,
                    )
                    or ""
                ).value
                == normalized_time
            ]

            event_id = stable_identifier(
                "encounter-boundary",
                case_id,
                event_type.value,
                normalized_time.isoformat(),
            )

            events.append(
                CanonicalEvent(
                    event_id=event_id,
                    case_id=case_id,
                    event_type=event_type,
                    subject="Clinical encounter",
                    description=label,
                    normalized_time=normalized_time,
                    time_precision=(TimePrecision.DATETIME),
                    time_source=(TimeSource.DOCUMENT_TEXT),
                    source_claim_ids=[],
                    evidence_ids=[item.evidence_id for item in related_items],
                    source_document_types=[item.document_type.value for item in related_items],
                    source_tables=[
                        item.source_table for item in related_items if item.source_table
                    ],
                    source_rows=[
                        item.source_row for item in related_items if item.source_row is not None
                    ],
                    confidence=1.0,
                )
            )

    return events


MEDICATION_START_PATTERN = re.compile(
    r"\bstart\s*=\s*([^;|]+)",
    flags=re.IGNORECASE,
)

MEDICATION_STOP_PATTERN = re.compile(
    r"\bstop\s*=\s*([^;|]+)",
    flags=re.IGNORECASE,
)


def parse_named_time(
    text: str,
    pattern: re.Pattern[str],
) -> ParsedTime:
    """Extract a named timestamp such as start= or stop=."""

    match = pattern.search(text)

    if match is None:
        return ParsedTime(
            value=None,
            precision=TimePrecision.UNKNOWN,
            source=TimeSource.UNKNOWN,
        )

    return extract_time_from_text(match.group(1).strip())


def build_medication_boundary_event(
    *,
    claim: ClinicalClaim,
    evidence_items: list[EvidenceItem],
    event_type: TimelineEventType,
    parsed_time: ParsedTime,
    label: str,
) -> CanonicalEvent:
    """Create a medication start or stop event."""

    event_id = stable_identifier(
        "medication-boundary",
        claim.case_id,
        claim.subject,
        event_type.value,
        (parsed_time.value.isoformat() if parsed_time.value else "unknown"),
        claim.claim_id,
    )

    return CanonicalEvent(
        event_id=event_id,
        case_id=claim.case_id,
        event_type=event_type,
        subject=claim.subject,
        description=(f"{label}: {claim.value}"),
        normalized_time=parsed_time.value,
        time_precision=parsed_time.precision,
        time_source=parsed_time.source,
        source_claim_ids=[claim.claim_id],
        evidence_ids=[item.evidence_id for item in evidence_items],
        source_document_types=[item.document_type.value for item in evidence_items],
        source_tables=[
            item.source_table for item in evidence_items if item.source_table is not None
        ],
        source_rows=[item.source_row for item in evidence_items if item.source_row is not None],
        confidence=claim.extraction_confidence,
    )


def expand_medication_events(
    claim: ClinicalClaim,
    evidence_items: list[EvidenceItem],
) -> list[CanonicalEvent]:
    """Create explicit medication start and stop events."""

    if claim.claim_type != ClaimType.MEDICATION_STATUS:
        return []

    combined_text = " ".join(
        [
            claim.value,
            *[item.normalized_fact for item in evidence_items],
        ]
    )

    start_time = parse_named_time(
        combined_text,
        MEDICATION_START_PATTERN,
    )

    stop_time = parse_named_time(
        combined_text,
        MEDICATION_STOP_PATTERN,
    )

    events: list[CanonicalEvent] = []

    if start_time.value is not None:
        events.append(
            build_medication_boundary_event(
                claim=claim,
                evidence_items=evidence_items,
                event_type=(TimelineEventType.MEDICATION_START),
                parsed_time=start_time,
                label="Medication start",
            )
        )

    if stop_time.value is not None:
        events.append(
            build_medication_boundary_event(
                claim=claim,
                evidence_items=evidence_items,
                event_type=(TimelineEventType.MEDICATION_STOP),
                parsed_time=stop_time,
                label="Medication stop",
            )
        )

    return events


def event_merge_key(
    event: CanonicalEvent,
) -> tuple[str, str, str]:
    """Create a conservative duplicate-event key."""

    normalized_subject = normalized_text(event.subject)

    normalized_time = event.normalized_time.isoformat() if event.normalized_time else "unknown"

    return (
        event.event_type.value,
        normalized_subject,
        normalized_time,
    )


def merge_event_group(
    events: list[CanonicalEvent],
) -> CanonicalEvent:
    """Merge duplicate representations of one event."""

    primary = max(
        events,
        key=lambda item: item.confidence,
    )

    return primary.model_copy(
        update={
            "source_claim_ids": list(
                dict.fromkeys(claim_id for event in events for claim_id in (event.source_claim_ids))
            ),
            "evidence_ids": list(
                dict.fromkeys(
                    evidence_id for event in events for evidence_id in (event.evidence_ids)
                )
            ),
            "source_document_types": list(
                dict.fromkeys(
                    document_type
                    for event in events
                    for document_type in (event.source_document_types)
                )
            ),
            "source_tables": list(
                dict.fromkeys(
                    source_table for event in events for source_table in (event.source_tables)
                )
            ),
            "source_rows": list(
                dict.fromkeys(source_row for event in events for source_row in (event.source_rows))
            ),
            "confidence": max(event.confidence for event in events),
        }
    )


def merge_duplicate_events(
    events: list[CanonicalEvent],
) -> tuple[
    list[CanonicalEvent],
    int,
]:
    """Merge conservatively equivalent timeline events."""

    grouped: dict[
        tuple[str, str, str],
        list[CanonicalEvent],
    ] = {}

    for event in events:
        grouped.setdefault(
            event_merge_key(event),
            [],
        ).append(event)

    merged = [merge_event_group(group) for group in grouped.values()]

    merged_count = len(events) - len(merged)

    return merged, merged_count


EVENT_TYPE_ORDER = {
    TimelineEventType.ENCOUNTER_START: 10,
    TimelineEventType.CONDITION_EVENT: 20,
    TimelineEventType.MEDICATION_START: 30,
    TimelineEventType.MEDICATION_STATUS: 40,
    TimelineEventType.OBSERVATION_RESULT: 50,
    TimelineEventType.PROCEDURE_EVENT: 60,
    TimelineEventType.MEDICATION_STOP: 70,
    TimelineEventType.ENCOUNTER_STOP: 80,
    TimelineEventType.FOLLOW_UP_ACTION: 90,
    TimelineEventType.NARRATIVE_EVENT: 100,
}


def timeline_sort_key(
    event: CanonicalEvent,
) -> tuple[
    bool,
    datetime,
    int,
    str,
]:
    """Sort dated events before undated events."""

    fallback = datetime.max.replace(tzinfo=UTC)

    return (
        event.normalized_time is None,
        event.normalized_time or fallback,
        EVENT_TYPE_ORDER[event.event_type],
        event.event_id,
    )


def sort_timeline(
    events: list[CanonicalEvent],
) -> list[CanonicalEvent]:
    """Sort a canonical timeline deterministically."""

    return sorted(
        events,
        key=timeline_sort_key,
    )


def build_conflict(
    *,
    case_id: str,
    conflict_type: TimelineConflictType,
    severity: ConflictSeverity,
    summary: str,
    rationale: str,
    events: list[CanonicalEvent],
    confidence: float,
) -> TimelineConflict:
    """Create one evidence-grounded conflict."""

    event_ids = [event.event_id for event in events]

    evidence_ids = list(
        dict.fromkeys(evidence_id for event in events for evidence_id in event.evidence_ids)
    )

    conflict_id = stable_identifier(
        "timeline-conflict",
        case_id,
        conflict_type.value,
        *event_ids,
    )

    return TimelineConflict(
        conflict_id=conflict_id,
        case_id=case_id,
        conflict_type=conflict_type,
        severity=severity,
        summary=summary,
        rationale=rationale,
        event_ids=event_ids,
        evidence_ids=evidence_ids,
        confidence=confidence,
        requires_human_review=True,
    )


def encounter_boundaries(
    events: list[CanonicalEvent],
) -> tuple[
    list[CanonicalEvent],
    list[CanonicalEvent],
]:
    """Return encounter start and stop events."""

    starts = [
        event
        for event in events
        if event.event_type == TimelineEventType.ENCOUNTER_START
        and event.normalized_time is not None
    ]

    stops = [
        event
        for event in events
        if event.event_type == TimelineEventType.ENCOUNTER_STOP
        and event.normalized_time is not None
    ]

    return starts, stops


def detect_encounter_boundary_conflicts(
    case_id: str,
    events: list[CanonicalEvent],
) -> list[TimelineConflict]:
    """Detect invalid or conflicting encounter boundaries."""

    conflicts: list[TimelineConflict] = []

    starts, stops = encounter_boundaries(events)

    for start in starts:
        for stop in stops:
            if stop.normalized_time < start.normalized_time:
                conflicts.append(
                    build_conflict(
                        case_id=case_id,
                        conflict_type=(TimelineConflictType.ENCOUNTER_STOP_BEFORE_START),
                        severity=ConflictSeverity.HIGH,
                        summary=("Encounter stop occurs before encounter start."),
                        rationale=(
                            f"Encounter stop "
                            f"{stop.normalized_time.isoformat()} "
                            f"precedes encounter start "
                            f"{start.normalized_time.isoformat()}."
                        ),
                        events=[start, stop],
                        confidence=1.0,
                    )
                )

    unique_start_times = {event.normalized_time for event in starts}

    if len(unique_start_times) > 1:
        conflicts.append(
            build_conflict(
                case_id=case_id,
                conflict_type=(TimelineConflictType.CONFLICTING_EVENT_TIMES),
                severity=ConflictSeverity.MEDIUM,
                summary=("Multiple encounter-start times were found."),
                rationale=(
                    "Different documents contain different timestamps for the encounter start."
                ),
                events=starts,
                confidence=1.0,
            )
        )

    unique_stop_times = {event.normalized_time for event in stops}

    if len(unique_stop_times) > 1:
        conflicts.append(
            build_conflict(
                case_id=case_id,
                conflict_type=(TimelineConflictType.CONFLICTING_EVENT_TIMES),
                severity=ConflictSeverity.MEDIUM,
                summary=("Multiple encounter-stop times were found."),
                rationale=(
                    "Different documents contain different timestamps for the encounter stop."
                ),
                events=stops,
                confidence=1.0,
            )
        )

    return conflicts


def medication_subject_key(
    event: CanonicalEvent,
) -> str:
    """Normalize medication subject text."""

    return normalized_text(event.subject)


def detect_medication_time_conflicts(
    case_id: str,
    events: list[CanonicalEvent],
) -> list[TimelineConflict]:
    """Detect medication stop events before starts."""

    conflicts: list[TimelineConflict] = []

    starts_by_subject: dict[
        str,
        list[CanonicalEvent],
    ] = {}

    stops_by_subject: dict[
        str,
        list[CanonicalEvent],
    ] = {}

    for event in events:
        if event.normalized_time is None:
            continue

        subject = medication_subject_key(event)

        if event.event_type == TimelineEventType.MEDICATION_START:
            starts_by_subject.setdefault(
                subject,
                [],
            ).append(event)

        elif event.event_type == TimelineEventType.MEDICATION_STOP:
            stops_by_subject.setdefault(
                subject,
                [],
            ).append(event)

    common_subjects = starts_by_subject.keys() & stops_by_subject.keys()

    for subject in common_subjects:
        for start in starts_by_subject[subject]:
            for stop in stops_by_subject[subject]:
                #
                # A start/stop pair is only considered the same
                # medication episode when they share provenance.
                #
                shared_claim_ids = set(start.source_claim_ids) & set(stop.source_claim_ids)

                shared_evidence_ids = set(start.evidence_ids) & set(stop.evidence_ids)

                same_episode = bool(shared_claim_ids or shared_evidence_ids)

                if not same_episode:
                    continue

                if start.normalized_time is None or stop.normalized_time is None:
                    continue

                if stop.normalized_time >= start.normalized_time:
                    continue

                conflicts.append(
                    build_conflict(
                        case_id=case_id,
                        conflict_type=(TimelineConflictType.MEDICATION_STOP_BEFORE_START),
                        severity=(ConflictSeverity.HIGH),
                        summary=("Medication stop occurs before medication start."),
                        rationale=(
                            f"{start.subject} has a "
                            f"stop time of "
                            f"{stop.normalized_time.isoformat()} "
                            f"before its start time of "
                            f"{start.normalized_time.isoformat()} "
                            "within the same documented "
                            "medication episode."
                        ),
                        events=[
                            start,
                            stop,
                        ],
                        confidence=1.0,
                    )
                )

    return conflicts


def detect_events_outside_encounter(
    case_id: str,
    events: list[CanonicalEvent],
) -> list[TimelineConflict]:
    """Detect encounter-scoped events outside the encounter."""

    starts, stops = encounter_boundaries(events)

    if len(starts) != 1 or len(stops) != 1:
        return []

    encounter_start = starts[0]
    encounter_stop = stops[0]

    scoped_types = {
        TimelineEventType.OBSERVATION_RESULT,
        TimelineEventType.PROCEDURE_EVENT,
        TimelineEventType.MEDICATION_START,
        TimelineEventType.MEDICATION_STOP,
    }

    conflicts: list[TimelineConflict] = []

    for event in events:
        if event.event_type not in scoped_types or event.normalized_time is None:
            continue

        if (
            event.normalized_time < encounter_start.normalized_time
            or event.normalized_time > encounter_stop.normalized_time
        ):
            conflicts.append(
                build_conflict(
                    case_id=case_id,
                    conflict_type=(TimelineConflictType.EVENT_OUTSIDE_ENCOUNTER),
                    severity=ConflictSeverity.LOW,
                    summary=("An encounter-scoped event falls outside the encounter."),
                    rationale=(
                        f"{event.event_type.value} at "
                        f"{event.normalized_time.isoformat()} "
                        "is outside the documented "
                        "encounter boundaries."
                    ),
                    events=[
                        encounter_start,
                        event,
                        encounter_stop,
                    ],
                    confidence=0.9,
                )
            )

    return conflicts


def detect_missing_event_times(
    case_id: str,
    events: list[CanonicalEvent],
) -> list[TimelineConflict]:
    """Record important events with no usable time."""

    important_types = {
        TimelineEventType.MEDICATION_START,
        TimelineEventType.MEDICATION_STOP,
        TimelineEventType.OBSERVATION_RESULT,
        TimelineEventType.PROCEDURE_EVENT,
        TimelineEventType.FOLLOW_UP_ACTION,
    }

    conflicts: list[TimelineConflict] = []

    for event in events:
        if event.event_type in important_types and event.normalized_time is None:
            conflicts.append(
                build_conflict(
                    case_id=case_id,
                    conflict_type=(TimelineConflictType.MISSING_EVENT_TIME),
                    severity=ConflictSeverity.INFO,
                    summary=("An event has no normalized timestamp."),
                    rationale=(
                        f"No usable timestamp was found "
                        f"for {event.event_type.value}: "
                        f"{event.subject}."
                    ),
                    events=[event],
                    confidence=1.0,
                )
            )

    return conflicts


def detect_timeline_conflicts(
    case_id: str,
    events: list[CanonicalEvent],
) -> list[TimelineConflict]:
    """Run all deterministic timeline checks."""

    conflicts = [
        *detect_encounter_boundary_conflicts(
            case_id,
            events,
        ),
        *detect_medication_time_conflicts(
            case_id,
            events,
        ),
        *detect_events_outside_encounter(
            case_id,
            events,
        ),
        *detect_missing_event_times(
            case_id,
            events,
        ),
    ]

    unique: dict[
        str,
        TimelineConflict,
    ] = {conflict.conflict_id: conflict for conflict in conflicts}

    return list(unique.values())


def load_milestone_one_inputs(
    case_dir: Path,
) -> tuple[
    list[EvidenceItem],
    list[ClinicalClaim],
]:
    """Load and validate Milestone 1 outputs."""

    raw_evidence = read_json(case_dir / "evidence_items.json")
    raw_claims = read_json(case_dir / "clinical_claims.json")

    if not isinstance(raw_evidence, list):
        raise TimelineReconstructionError("evidence_items.json must contain a list")

    if not isinstance(raw_claims, list):
        raise TimelineReconstructionError("clinical_claims.json must contain a list")

    try:
        evidence_items = [EvidenceItem.model_validate(item) for item in raw_evidence]

        claims = [ClinicalClaim.model_validate(item) for item in raw_claims]
    except ValidationError as exc:
        raise TimelineReconstructionError(f"Invalid Milestone 1 input: {exc}") from exc

    return evidence_items, claims


def reconstruct_case_timeline(
    case_dir: Path,
) -> tuple[
    list[CanonicalEvent],
    list[TimelineConflict],
    int,
]:
    """Reconstruct one canonical timeline."""

    evidence_items, claims = load_milestone_one_inputs(case_dir)

    case_id = case_dir.name

    evidence_by_id = evidence_lookup(evidence_items)

    raw_events: list[CanonicalEvent] = []

    for claim in claims:
        supporting_evidence = [
            evidence_by_id[evidence_id]
            for evidence_id in (claim.source_evidence_ids)
            if evidence_id in evidence_by_id
        ]

        raw_events.append(
            build_event_from_claim(
                claim,
                evidence_by_id,
            )
        )

        raw_events.extend(
            expand_medication_events(
                claim,
                supporting_evidence,
            )
        )

    raw_events.extend(
        build_encounter_boundary_events(
            case_id=case_id,
            evidence_items=evidence_items,
        )
    )

    merged_events, merged_count = merge_duplicate_events(raw_events)

    ordered_events = sort_timeline(merged_events)

    conflicts = detect_timeline_conflicts(
        case_id,
        ordered_events,
    )

    return (
        ordered_events,
        conflicts,
        merged_count,
    )


def build_canonical_timeline(
    case_dir: Path,
) -> Path:
    """Write canonical timeline outputs for one case."""

    evidence_items, claims = load_milestone_one_inputs(case_dir)

    (
        events,
        conflicts,
        merged_count,
    ) = reconstruct_case_timeline(case_dir)

    write_json(
        case_dir / "canonical_timeline.json",
        [event.model_dump(mode="json") for event in events],
    )

    write_json(
        case_dir / "timeline_conflicts.json",
        [conflict.model_dump(mode="json") for conflict in conflicts],
    )

    event_counts = Counter(event.event_type.value for event in events)

    conflict_counts = Counter(conflict.conflict_type.value for conflict in conflicts)

    dated_count = sum(event.normalized_time is not None for event in events)

    manifest = TimelineManifest(
        schema_version="1.0",
        case_id=case_dir.name,
        generated_at=datetime.now(UTC),
        reconstruction_method=("deterministic_canonical_timeline_v1"),
        source_evidence_count=len(evidence_items),
        source_claim_count=len(claims),
        canonical_event_count=len(events),
        dated_event_count=dated_count,
        undated_event_count=(len(events) - dated_count),
        merged_event_count=merged_count,
        conflict_count=len(conflicts),
        event_count_by_type=dict(event_counts),
        conflict_count_by_type=dict(conflict_counts),
    )

    write_json(
        case_dir / "timeline_manifest.json",
        manifest.model_dump(mode="json"),
    )

    return case_dir

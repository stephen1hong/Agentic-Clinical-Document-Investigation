"""Validate canonical timeline outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from clinical_investigation.investigation.models import (
    ClinicalClaim,
    EvidenceItem,
)
from clinical_investigation.investigation.timeline_models import (
    CanonicalEvent,
    TimelineConflict,
    TimelineManifest,
)
from clinical_investigation.investigation.timeline_reconstruction import (
    timeline_sort_key,
)

REQUIRED_TIMELINE_FILES = {
    "canonical_timeline.json",
    "timeline_conflicts.json",
    "timeline_manifest.json",
}


def read_json(path: Path) -> Any:
    """Read JSON."""

    return json.loads(path.read_text(encoding="utf-8"))


def validate_canonical_timeline(
    case_dir: Path,
) -> list[str]:
    """Validate one canonical timeline."""

    errors: list[str] = []

    existing_files = {path.name for path in case_dir.iterdir() if path.is_file()}

    for filename in sorted(REQUIRED_TIMELINE_FILES - existing_files):
        errors.append(f"Missing required file: {filename}")

    if errors:
        return errors

    try:
        raw_evidence = read_json(case_dir / "evidence_items.json")
        raw_claims = read_json(case_dir / "clinical_claims.json")
        raw_events = read_json(case_dir / "canonical_timeline.json")
        raw_conflicts = read_json(case_dir / "timeline_conflicts.json")
        raw_manifest = read_json(case_dir / "timeline_manifest.json")
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON: {exc}"]

    try:
        evidence_items = [EvidenceItem.model_validate(item) for item in raw_evidence]
        claims = [ClinicalClaim.model_validate(item) for item in raw_claims]
        events = [CanonicalEvent.model_validate(item) for item in raw_events]
        conflicts = [TimelineConflict.model_validate(item) for item in raw_conflicts]
        manifest = TimelineManifest.model_validate(raw_manifest)
    except ValidationError as exc:
        return [f"Timeline schema validation failed: {exc}"]

    if manifest.case_id != case_dir.name:
        errors.append("Timeline manifest case_id mismatch")

    evidence_ids = {item.evidence_id for item in evidence_items}

    claim_ids = {claim.claim_id for claim in claims}

    event_ids = [event.event_id for event in events]

    if len(event_ids) != len(set(event_ids)):
        errors.append("Duplicate canonical event IDs found")

    event_id_set = set(event_ids)

    for event in events:
        missing_evidence = set(event.evidence_ids) - evidence_ids

        if missing_evidence:
            errors.append(
                f"Event {event.event_id} references missing evidence: {sorted(missing_evidence)}"
            )

        missing_claims = set(event.source_claim_ids) - claim_ids

        if missing_claims:
            errors.append(
                f"Event {event.event_id} references missing claims: {sorted(missing_claims)}"
            )

    for conflict in conflicts:
        missing_events = set(conflict.event_ids) - event_id_set

        if missing_events:
            errors.append(
                f"Conflict {conflict.conflict_id} "
                f"references missing events: "
                f"{sorted(missing_events)}"
            )

        missing_evidence = set(conflict.evidence_ids) - evidence_ids

        if missing_evidence:
            errors.append(
                f"Conflict {conflict.conflict_id} "
                f"references missing evidence: "
                f"{sorted(missing_evidence)}"
            )

    dated_events = [event for event in events if event.normalized_time is not None]

    sorted_dated_events = sorted(
        dated_events,
        key=timeline_sort_key,
    )

    actual_dated_ids = [event.event_id for event in dated_events]

    expected_dated_ids = [event.event_id for event in sorted_dated_events]

    if actual_dated_ids != expected_dated_ids:
        errors.append("Dated canonical events are not chronologically ordered")

    seen_undated_event = False

    for event in events:
        if event.normalized_time is None:
            seen_undated_event = True
            continue

        if seen_undated_event:
            errors.append("A dated event appears after an undated event")
            break

    if manifest.canonical_event_count != len(events):
        errors.append("Manifest canonical_event_count mismatch")

    if manifest.conflict_count != len(conflicts):
        errors.append("Manifest conflict_count mismatch")

    dated_count = len(dated_events)

    if manifest.dated_event_count != dated_count:
        errors.append("Manifest dated_event_count mismatch")

    if manifest.undated_event_count != len(events) - dated_count:
        errors.append("Manifest undated_event_count mismatch")

    return errors

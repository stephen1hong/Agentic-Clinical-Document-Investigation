from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from clinical_investigation.investigation.timeline_reconstruction import (
    normalized_text,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "timeline"

OUTPUT_PATH = OUTPUT_DIR / "timeline_conflict_detection_quality.json"


# Production semantics observed in timeline_reconstruction.py.
IMPORTANT_MISSING_TIME_TYPES = {
    "medication_start",
    "medication_stop",
    "observation_result",
    "procedure_event",
    "follow_up_action",
}

ENCOUNTER_SCOPED_TYPES = {
    "observation_result",
    "procedure_event",
    "medication_start",
    "medication_stop",
}

ENCOUNTER_START_TYPES = {
    "encounter_start",
    "encounter_admission",
}

ENCOUNTER_STOP_TYPES = {
    "encounter_stop",
    "encounter_end",
    "encounter_discharge",
}


def load_json(path: Path) -> Any:
    """Load JSON from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_records(
    raw: Any,
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Extract records from common JSON wrapper structures."""

    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]

    if isinstance(raw, dict):
        for key in keys:
            value = raw.get(key)

            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    return []


def load_timeline(
    case_dir: Path,
) -> list[dict[str, Any]]:
    """Load canonical timeline events."""

    path = case_dir / "canonical_timeline.json"

    if not path.exists():
        return []

    return flatten_records(
        load_json(path),
        (
            "events",
            "timeline",
            "records",
        ),
    )


def load_conflicts(
    case_dir: Path,
) -> list[dict[str, Any]]:
    """Load deterministic timeline conflicts."""

    path = case_dir / "timeline_conflicts.json"

    if not path.exists():
        return []

    return flatten_records(
        load_json(path),
        (
            "conflicts",
            "timeline_conflicts",
            "records",
        ),
    )


def string_ids(value: Any) -> list[str]:
    """Normalize scalar/list IDs."""

    if isinstance(value, str):
        return [value] if value else []

    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]

    return []


def conflict_type(
    conflict: dict[str, Any],
) -> str:
    """Return normalized conflict type."""

    value = conflict.get("conflict_type")

    if value is None:
        value = conflict.get("type")

    return str(value or "unknown")


def conflict_event_ids(
    conflict: dict[str, Any],
) -> list[str]:
    """Extract event IDs from a timeline conflict."""

    values: list[str] = []

    for field in (
        "event_ids",
        "timeline_event_ids",
    ):
        values.extend(string_ids(conflict.get(field)))

    provenance = conflict.get("provenance")

    if isinstance(provenance, dict):
        for field in (
            "event_ids",
            "timeline_event_ids",
        ):
            values.extend(string_ids(provenance.get(field)))

    return list(dict.fromkeys(values))


def event_type(
    event: dict[str, Any],
) -> str:
    """Return normalized timeline event type."""
    return str(
        event.get(
            "event_type",
            "unknown",
        )
    )


def normalize_subject(
    value: Any,
) -> str:
    """Normalize medication subject using production semantics."""

    if not isinstance(
        value,
        str,
    ):
        return ""

    return normalized_text(value)


def temporal_value(
    event: dict[str, Any],
) -> str | None:
    """Return normalized timeline time value."""

    value = event.get("normalized_time")

    if not isinstance(value, str):
        return None

    cleaned = value.strip()

    return cleaned or None


def build_expected_missing_time(
    timeline: list[dict[str, Any]],
) -> set[tuple[str, tuple[str, ...]]]:
    """Independently identify expected missing-event-time conflicts."""

    expected: set[tuple[str, tuple[str, ...]]] = set()

    for event in timeline:
        event_id = event.get("event_id")

        if not isinstance(event_id, str) or not event_id:
            continue

        if event_type(event) in IMPORTANT_MISSING_TIME_TYPES and temporal_value(event) is None:
            expected.add(
                (
                    "missing_event_time",
                    (event_id,),
                )
            )

    return expected


def build_expected_medication_stop_before_start(
    timeline: list[dict[str, Any]],
) -> set[tuple[str, tuple[str, ...]]]:
    """
    Independently identify medication stop-before-start
    conflicts using the production medication-episode
    semantics.

    A medication start and stop belong to the same
    documented medication episode only when:

    1. Their normalized medication subjects match.
    2. Both events have usable timestamps.
    3. They share at least one source claim ID or
       evidence ID.
    4. The stop timestamp precedes the start timestamp.
    """

    starts: defaultdict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    stops: defaultdict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for event in timeline:
        subject = normalize_subject(event.get("subject"))

        if not subject:
            continue

        current_type = event_type(event)

        if current_type == "medication_start":
            starts[subject].append(event)

        elif current_type == "medication_stop":
            stops[subject].append(event)

    expected: set[tuple[str, tuple[str, ...]]] = set()

    for subject in starts.keys() & stops.keys():
        for start in starts[subject]:
            start_time = temporal_value(start)

            start_id = start.get("event_id")

            if (
                start_time is None
                or not isinstance(
                    start_id,
                    str,
                )
                or not start_id
            ):
                continue

            start_claim_ids = set(string_ids(start.get("source_claim_ids")))

            start_evidence_ids = set(string_ids(start.get("evidence_ids")))

            for stop in stops[subject]:
                stop_time = temporal_value(stop)

                stop_id = stop.get("event_id")

                if (
                    stop_time is None
                    or not isinstance(
                        stop_id,
                        str,
                    )
                    or not stop_id
                ):
                    continue

                stop_claim_ids = set(string_ids(stop.get("source_claim_ids")))

                stop_evidence_ids = set(string_ids(stop.get("evidence_ids")))

                shared_claim_ids = start_claim_ids & stop_claim_ids

                shared_evidence_ids = start_evidence_ids & stop_evidence_ids

                same_episode = bool(shared_claim_ids or shared_evidence_ids)

                if not same_episode:
                    continue

                if stop_time >= start_time:
                    continue

                expected.add(
                    (
                        "medication_stop_before_start",
                        tuple(
                            sorted(
                                (
                                    start_id,
                                    stop_id,
                                )
                            )
                        ),
                    )
                )

    return expected


def encounter_boundaries(
    timeline: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Find encounter boundary events conservatively."""

    starts = [
        event
        for event in timeline
        if event_type(event) in ENCOUNTER_START_TYPES and temporal_value(event) is not None
    ]

    stops = [
        event
        for event in timeline
        if event_type(event) in ENCOUNTER_STOP_TYPES and temporal_value(event) is not None
    ]

    return starts, stops


def build_expected_outside_encounter(
    timeline: list[dict[str, Any]],
) -> set[tuple[str, tuple[str, ...]]]:
    """Independently identify encounter-scoped events outside boundaries."""

    starts, stops = encounter_boundaries(timeline)

    # Matches production behavior:
    # no outside-encounter detection unless exactly
    # one start and one stop boundary are available.
    if len(starts) != 1 or len(stops) != 1:
        return set()

    encounter_start = starts[0]
    encounter_stop = stops[0]

    start_time = temporal_value(encounter_start)

    stop_time = temporal_value(encounter_stop)

    start_id = encounter_start.get("event_id")

    stop_id = encounter_stop.get("event_id")

    if (
        start_time is None
        or stop_time is None
        or not isinstance(
            start_id,
            str,
        )
        or not isinstance(
            stop_id,
            str,
        )
    ):
        return set()

    expected: set[tuple[str, tuple[str, ...]]] = set()

    for event in timeline:
        if event_type(event) not in ENCOUNTER_SCOPED_TYPES:
            continue

        current_time = temporal_value(event)

        current_id = event.get("event_id")

        if current_time is None or not isinstance(
            current_id,
            str,
        ):
            continue

        if current_time < start_time or current_time > stop_time:
            expected.add(
                (
                    "event_outside_encounter",
                    tuple(
                        sorted(
                            (
                                start_id,
                                current_id,
                                stop_id,
                            )
                        )
                    ),
                )
            )

    return expected


def canonical_conflict_key(
    conflict: dict[str, Any],
) -> tuple[
    str,
    tuple[str, ...],
]:
    """Create a normalized conflict comparison key."""

    return (
        conflict_type(conflict),
        tuple(sorted(conflict_event_ids(conflict))),
    )


def main() -> int:
    """Run Step 8D.6 timeline conflict quality evaluation."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    reports_scanned = 0
    timeline_events = 0
    emitted_conflicts = 0

    emitted_by_type: Counter[str] = Counter()

    expected_by_type: Counter[str] = Counter()

    true_positive_by_type: Counter[str] = Counter()

    false_positive_by_type: Counter[str] = Counter()

    false_negative_by_type: Counter[str] = Counter()

    unresolved_event_refs: list[dict[str, Any]] = []

    duplicate_conflicts: list[dict[str, Any]] = []

    false_positives: list[dict[str, Any]] = []

    false_negatives: list[dict[str, Any]] = []

    unsupported_conflict_types: Counter[str] = Counter()

    seen_conflict_ids: set[str] = set()

    evaluated_types = {
        "missing_event_time",
        "medication_stop_before_start",
        "event_outside_encounter",
    }

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        timeline_path = case_dir / "canonical_timeline.json"

        conflict_path = case_dir / "timeline_conflicts.json"

        if not timeline_path.exists() or not conflict_path.exists():
            continue

        reports_scanned += 1

        case_id = case_dir.name

        timeline = load_timeline(case_dir)

        conflicts = load_conflicts(case_dir)

        timeline_events += len(timeline)

        emitted_conflicts += len(conflicts)

        event_ids = {str(event["event_id"]) for event in timeline if event.get("event_id")}

        emitted_keys: set[tuple[str, tuple[str, ...]]] = set()

        for conflict in conflicts:
            current_type = conflict_type(conflict)

            emitted_by_type[current_type] += 1

            conflict_id = conflict.get("conflict_id")

            if (
                isinstance(
                    conflict_id,
                    str,
                )
                and conflict_id
            ):
                if conflict_id in seen_conflict_ids:
                    duplicate_conflicts.append(
                        {
                            "case_id": (case_id),
                            "conflict_id": (conflict_id),
                        }
                    )

                seen_conflict_ids.add(conflict_id)

            ids = conflict_event_ids(conflict)

            missing_ids = [event_id for event_id in ids if event_id not in event_ids]

            if missing_ids:
                unresolved_event_refs.append(
                    {
                        "case_id": case_id,
                        "conflict_id": (conflict_id),
                        "conflict_type": (current_type),
                        "missing_event_ids": (missing_ids),
                    }
                )

            if current_type not in evaluated_types:
                unsupported_conflict_types[current_type] += 1

                continue

            emitted_keys.add(canonical_conflict_key(conflict))

        expected_keys = set()

        expected_keys.update(build_expected_missing_time(timeline))

        expected_keys.update(build_expected_medication_stop_before_start(timeline))

        expected_keys.update(build_expected_outside_encounter(timeline))

        for expected_type, _ in expected_keys:
            expected_by_type[expected_type] += 1

        true_positive_keys = emitted_keys & expected_keys

        false_positive_keys = emitted_keys - expected_keys

        false_negative_keys = expected_keys - emitted_keys

        for current_type, _ in true_positive_keys:
            true_positive_by_type[current_type] += 1

        for (
            current_type,
            current_event_ids,
        ) in sorted(false_positive_keys):
            false_positive_by_type[current_type] += 1

            false_positives.append(
                {
                    "case_id": case_id,
                    "conflict_type": (current_type),
                    "event_ids": list(current_event_ids),
                }
            )

        for (
            current_type,
            current_event_ids,
        ) in sorted(false_negative_keys):
            false_negative_by_type[current_type] += 1

            false_negatives.append(
                {
                    "case_id": case_id,
                    "conflict_type": (current_type),
                    "event_ids": list(current_event_ids),
                }
            )

    true_positives = sum(true_positive_by_type.values())

    false_positive_count = sum(false_positive_by_type.values())

    false_negative_count = sum(false_negative_by_type.values())

    evaluated_emitted = true_positives + false_positive_count

    expected_total = true_positives + false_negative_count

    precision = true_positives / evaluated_emitted if evaluated_emitted else 1.0

    recall = true_positives / expected_total if expected_total else 1.0

    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)

    integrity_issue_count = len(unresolved_event_refs) + len(duplicate_conflicts)

    detection_issue_count = false_positive_count + false_negative_count

    if integrity_issue_count or detection_issue_count:
        status = "FAIL"

    elif unsupported_conflict_types:
        status = "PASS_WITH_UNEVALUATED_CONFLICT_TYPES"

    else:
        status = "PASS"

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8D.6",
        "status": status,
        "evaluation_method": (
            "Independent deterministic validation "
            "of timeline conflict detection against "
            "canonical timeline semantics. Evaluated "
            "conflict types are missing_event_time, "
            "medication_stop_before_start, and "
            "event_outside_encounter. Precision and "
            "recall are computed from normalized "
            "conflict type plus referenced event IDs."
        ),
        "reports_scanned": (reports_scanned),
        "timeline_events": (timeline_events),
        "emitted_conflicts": (emitted_conflicts),
        "evaluated_conflict_types": (sorted(evaluated_types)),
        "overall_metrics": {
            "true_positives": (true_positives),
            "false_positives": (false_positive_count),
            "false_negatives": (false_negative_count),
            "precision": precision,
            "precision_percentage": (precision * 100.0),
            "recall": recall,
            "recall_percentage": (recall * 100.0),
            "f1": f1,
            "f1_percentage": (f1 * 100.0),
        },
        "by_conflict_type": {
            conflict_name: {
                "emitted": (emitted_by_type[conflict_name]),
                "expected": (expected_by_type[conflict_name]),
                "true_positives": (true_positive_by_type[conflict_name]),
                "false_positives": (false_positive_by_type[conflict_name]),
                "false_negatives": (false_negative_by_type[conflict_name]),
            }
            for conflict_name in sorted(evaluated_types)
        },
        "other_emitted_conflict_types": (dict(sorted(unsupported_conflict_types.items()))),
        "integrity": {
            "unresolved_event_references": (len(unresolved_event_refs)),
            "duplicate_conflict_ids": (len(duplicate_conflicts)),
            "integrity_issue_count": (integrity_issue_count),
        },
        "issues": {
            "false_positives": (false_positives),
            "false_negatives": (false_negatives),
            "unresolved_event_references": (unresolved_event_refs),
            "duplicate_conflict_ids": (duplicate_conflicts),
        },
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("STEP 8D.6 TIMELINE CONFLICT DETECTION QUALITY")
    print("=" * 72)

    print(f"Status:                         {status}")

    print(f"Cases scanned:                  {reports_scanned}")

    print(f"Timeline events:                {timeline_events}")

    print(f"All emitted conflicts:          {emitted_conflicts}")

    print()
    print("Evaluated conflict detection")
    print("-" * 72)

    print(f"True positives:                 {true_positives}")

    print(f"False positives:                {false_positive_count}")

    print(f"False negatives:                {false_negative_count}")

    print(f"Precision:                      {precision * 100.0:.1f}%")

    print(f"Recall:                         {recall * 100.0:.1f}%")

    print(f"F1:                             {f1 * 100.0:.1f}%")

    print()
    print("By conflict type")
    print("-" * 72)

    for conflict_name in sorted(evaluated_types):
        print(f"{conflict_name}")

        print(
            "  emitted / expected:           "
            f"{emitted_by_type[conflict_name]}"
            " / "
            f"{expected_by_type[conflict_name]}"
        )

        print(
            "  TP / FP / FN:                 "
            f"{true_positive_by_type[conflict_name]}"
            " / "
            f"{false_positive_by_type[conflict_name]}"
            " / "
            f"{false_negative_by_type[conflict_name]}"
        )

    print()
    print("Reference integrity")
    print("-" * 72)

    print(f"Unresolved event references:    {len(unresolved_event_refs)}")

    print(f"Duplicate conflict IDs:         {len(duplicate_conflicts)}")

    if unsupported_conflict_types:
        print()
        print("Other emitted conflict types")
        print("-" * 72)

        for (
            current_type,
            count,
        ) in sorted(unsupported_conflict_types.items()):
            print(f"{current_type:<40}{count:>6}")

    print()
    print("Saved evaluation to:")

    print(OUTPUT_PATH)

    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())

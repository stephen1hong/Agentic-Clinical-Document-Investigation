from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "timeline"

OUTPUT_PATH = OUTPUT_DIR / "timeline_ordering_consistency.json"


def load_json(path: Path) -> Any:
    """Load JSON from disk."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def load_timeline(
    path: Path,
) -> list[dict[str, Any]]:
    """Load canonical timeline events."""

    raw = load_json(path)

    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]

    if isinstance(raw, dict):
        for key in (
            "events",
            "timeline",
            "records",
        ):
            value = raw.get(key)

            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    raise ValueError("canonical_timeline.json must contain a list of timeline events.")


def parse_datetime(
    value: Any,
) -> datetime | None:
    """Parse ISO-8601 timestamp."""

    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(f"Timestamp must be string or null: {value!r}")

    cleaned = value.strip()

    if not cleaned:
        return None

    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"

    return datetime.fromisoformat(cleaned)


def main() -> int:
    """Run Step 8D.3 timeline ordering evaluation."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    reports_scanned = 0
    total_events = 0

    timed_events = 0
    unknown_time_events = 0
    interval_events = 0

    invalid_intervals: list[dict[str, Any]] = []

    ordering_regressions: list[dict[str, Any]] = []

    timed_projection_regressions: list[dict[str, Any]] = []

    invalid_timestamp_values: list[dict[str, Any]] = []

    same_timestamp_pairs = 0

    cases_with_ordering_issues: set[str] = set()

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        timeline_path = case_dir / "canonical_timeline.json"

        report_path = case_dir / "final_investigation_report.json"

        if not timeline_path.exists() or not report_path.exists():
            continue

        reports_scanned += 1

        events = load_timeline(timeline_path)

        total_events += len(events)

        parsed_events: list[
            tuple[
                int,
                dict[str, Any],
                datetime | None,
                datetime | None,
            ]
        ] = []

        for index, event in enumerate(events):
            event_id = event.get("event_id")

            raw_start = event.get("normalized_time")

            raw_end = event.get("time_end")

            try:
                start_dt = parse_datetime(raw_start)
            except (
                TypeError,
                ValueError,
            ) as exc:
                invalid_timestamp_values.append(
                    {
                        "case_id": case_dir.name,
                        "event_id": event_id,
                        "field": "normalized_time",
                        "value": raw_start,
                        "error": str(exc),
                    }
                )

                start_dt = None

            try:
                end_dt = parse_datetime(raw_end)
            except (
                TypeError,
                ValueError,
            ) as exc:
                invalid_timestamp_values.append(
                    {
                        "case_id": case_dir.name,
                        "event_id": event_id,
                        "field": "time_end",
                        "value": raw_end,
                        "error": str(exc),
                    }
                )

                end_dt = None

            if start_dt is None:
                unknown_time_events += 1
            else:
                timed_events += 1

            if end_dt is not None:
                interval_events += 1

            if start_dt is not None and end_dt is not None and end_dt < start_dt:
                invalid_intervals.append(
                    {
                        "case_id": case_dir.name,
                        "event_id": event_id,
                        "event_type": event.get("event_type"),
                        "subject": event.get("subject"),
                        "normalized_time": raw_start,
                        "time_end": raw_end,
                    }
                )

                cases_with_ordering_issues.add(case_dir.name)

            parsed_events.append(
                (
                    index,
                    event,
                    start_dt,
                    end_dt,
                )
            )

        #
        # Check ordering in the persisted sequence.
        #
        previous_timed: (
            tuple[
                int,
                dict[str, Any],
                datetime,
            ]
            | None
        ) = None

        for (
            index,
            event,
            start_dt,
            _,
        ) in parsed_events:
            if start_dt is None:
                continue

            if previous_timed is not None:
                (
                    previous_index,
                    previous_event,
                    previous_time,
                ) = previous_timed

                if start_dt < previous_time:
                    ordering_regressions.append(
                        {
                            "case_id": case_dir.name,
                            "previous_index": (previous_index),
                            "previous_event_id": (previous_event.get("event_id")),
                            "previous_event_type": (previous_event.get("event_type")),
                            "previous_subject": (previous_event.get("subject")),
                            "previous_time": (previous_event.get("normalized_time")),
                            "current_index": index,
                            "current_event_id": (event.get("event_id")),
                            "current_event_type": (event.get("event_type")),
                            "current_subject": (event.get("subject")),
                            "current_time": (event.get("normalized_time")),
                        }
                    )

                    cases_with_ordering_issues.add(case_dir.name)

                elif start_dt == previous_time:
                    same_timestamp_pairs += 1

            previous_timed = (
                index,
                event,
                start_dt,
            )

        #
        # Independently project only timed events
        # and verify their timestamps are monotonic.
        #
        timed_projection = [
            (
                index,
                event,
                start_dt,
            )
            for (
                index,
                event,
                start_dt,
                _,
            ) in parsed_events
            if start_dt is not None
        ]

        for position in range(
            1,
            len(timed_projection),
        ):
            (
                previous_index,
                previous_event,
                previous_time,
            ) = timed_projection[position - 1]

            (
                current_index,
                current_event,
                current_time,
            ) = timed_projection[position]

            if current_time < previous_time:
                timed_projection_regressions.append(
                    {
                        "case_id": case_dir.name,
                        "previous_index": (previous_index),
                        "previous_event_id": (previous_event.get("event_id")),
                        "previous_time": (previous_event.get("normalized_time")),
                        "current_index": (current_index),
                        "current_event_id": (current_event.get("event_id")),
                        "current_time": (current_event.get("normalized_time")),
                    }
                )

                cases_with_ordering_issues.add(case_dir.name)

    total_issue_count = sum(
        (
            len(invalid_timestamp_values),
            len(invalid_intervals),
            len(ordering_regressions),
            len(timed_projection_regressions),
        )
    )

    timed_ordering_accuracy = (
        (timed_events - len(timed_projection_regressions)) / timed_events if timed_events else 1.0
    )

    status = "PASS" if total_issue_count == 0 else "FAIL"

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8D.3",
        "status": status,
        "evaluation_method": (
            "Evaluate chronological monotonicity "
            "of all timed canonical events in their "
            "persisted ordering, validate temporal "
            "interval direction, and independently "
            "verify the timed-only projection. "
            "Untimed events are retained in the "
            "population but excluded from monotonic "
            "timestamp comparisons."
        ),
        "reports_scanned": (reports_scanned),
        "total_events": (total_events),
        "timeline_population": {
            "timed_events": (timed_events),
            "unknown_time_events": (unknown_time_events),
            "interval_events": (interval_events),
            "same_timestamp_adjacent_pairs": (same_timestamp_pairs),
        },
        "ordering_validation": {
            "persisted_order_regressions": (len(ordering_regressions)),
            "timed_projection_regressions": (len(timed_projection_regressions)),
            "timed_ordering_accuracy": (timed_ordering_accuracy),
            "timed_ordering_percentage": (timed_ordering_accuracy * 100.0),
            "cases_with_ordering_issues": (len(cases_with_ordering_issues)),
        },
        "interval_validation": {
            "interval_events": (interval_events),
            "invalid_intervals": (len(invalid_intervals)),
        },
        "timestamp_validation": {
            "invalid_timestamp_values": (len(invalid_timestamp_values)),
        },
        "total_issue_count": (total_issue_count),
        "issues": {
            "invalid_timestamp_values": (invalid_timestamp_values),
            "invalid_intervals": (invalid_intervals),
            "ordering_regressions": (ordering_regressions),
            "timed_projection_regressions": (timed_projection_regressions),
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
    print("STEP 8D.3 TIMELINE ORDERING AND INTERVAL CONSISTENCY")
    print("=" * 72)

    print(f"Status:                         {status}")

    print(f"Reports scanned:                {reports_scanned}")

    print(f"Timeline events:                {total_events}")

    print()
    print("Timeline population")
    print("-" * 72)

    print(f"Timed events:                   {timed_events}")

    print(f"Unknown-time events:            {unknown_time_events}")

    print(f"Interval events:                {interval_events}")

    print(f"Same-timestamp adjacent pairs:  {same_timestamp_pairs}")

    print()
    print("Ordering consistency")
    print("-" * 72)

    print(f"Persisted-order regressions:    {len(ordering_regressions)}")

    print(f"Timed-projection regressions:   {len(timed_projection_regressions)}")

    print(f"Cases with ordering issues:     {len(cases_with_ordering_issues)}")

    print(f"Timed ordering accuracy:        {timed_ordering_accuracy * 100.0:.1f}%")

    print()
    print("Interval consistency")
    print("-" * 72)

    print(f"Invalid intervals:              {len(invalid_intervals)}")

    print()
    print("Timestamp validity")
    print("-" * 72)

    print(f"Invalid timestamp values:       {len(invalid_timestamp_values)}")

    print()
    print(f"Total issues:                   {total_issue_count}")

    print()
    print("Saved evaluation to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

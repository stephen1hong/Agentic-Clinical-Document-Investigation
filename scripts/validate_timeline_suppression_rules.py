from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "timeline"

OUTPUT_PATH = OUTPUT_DIR / "timeline_suppression_rule_validation.json"


IMPORTANT_EVENT_TYPES = {
    "medication_start",
    "medication_stop",
    "observation_result",
    "procedure_event",
    "follow_up_action",
}


def load_json(path: Path) -> Any:
    """Load JSON from disk."""
    return json.loads(path.read_text(encoding="utf-8"))


def flatten_records(
    raw: Any,
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Extract records from common JSON structures."""

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
    """Load canonical timeline."""

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


def load_final_findings(
    case_dir: Path,
) -> list[dict[str, Any]]:
    """Load authoritative final findings."""

    path = case_dir / "final_investigation_report.json"

    if not path.exists():
        return []

    report = load_json(path)

    if not isinstance(report, dict):
        return []

    findings: list[dict[str, Any]] = []

    for key in (
        "high_priority_findings",
        "other_findings",
    ):
        value = report.get(key)

        if isinstance(value, list):
            findings.extend(item for item in value if isinstance(item, dict))

    return findings


def string_ids(value: Any) -> list[str]:
    """Normalize scalar/list IDs."""

    if isinstance(value, str):
        return [value] if value else []

    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]

    return []


def finding_event_ids(
    finding: dict[str, Any],
) -> list[str]:
    """Return timeline event IDs referenced by a finding."""

    values: list[str] = []

    for field in (
        "event_ids",
        "timeline_event_ids",
    ):
        values.extend(string_ids(finding.get(field)))

    provenance = finding.get("provenance")

    if isinstance(provenance, dict):
        for field in (
            "event_ids",
            "timeline_event_ids",
        ):
            values.extend(string_ids(provenance.get(field)))

    return list(dict.fromkeys(values))


def main() -> int:
    """Validate Step 8D.5b suppression semantics."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    reports_scanned = 0
    timeline_events = 0
    untimed_events = 0

    expected_eligible = 0
    expected_suppressed = 0

    actual_covered: set[tuple[str, str]] = set()

    expected_eligible_ids: set[tuple[str, str]] = set()

    expected_suppressed_ids: set[tuple[str, str]] = set()

    suppressed_by_type: Counter[str] = Counter()
    eligible_by_type: Counter[str] = Counter()

    missing_expected_findings: list[dict[str, Any]] = []

    unexpected_findings: list[dict[str, Any]] = []

    suppressed_events_with_findings: list[dict[str, Any]] = []

    eligible_events_without_findings: list[dict[str, Any]] = []

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        timeline_path = case_dir / "canonical_timeline.json"

        report_path = case_dir / "final_investigation_report.json"

        if not timeline_path.exists() or not report_path.exists():
            continue

        reports_scanned += 1

        case_id = case_dir.name

        timeline = load_timeline(case_dir)

        findings = load_final_findings(case_dir)

        timeline_events += len(timeline)

        event_index = {str(event["event_id"]): event for event in timeline if event.get("event_id")}

        for event_id, event in event_index.items():
            if event.get("normalized_time") is not None:
                continue

            untimed_events += 1

            event_type = str(
                event.get(
                    "event_type",
                    "unknown",
                )
            )

            key = (
                case_id,
                event_id,
            )

            if event_type in IMPORTANT_EVENT_TYPES:
                expected_eligible += 1

                expected_eligible_ids.add(key)

                eligible_by_type[event_type] += 1

            else:
                expected_suppressed += 1

                expected_suppressed_ids.add(key)

                suppressed_by_type[event_type] += 1

        for finding in findings:
            if finding.get("subtype") != "missing_event_time":
                continue

            finding_id = finding.get("finding_id")

            for event_id in finding_event_ids(finding):
                key = (
                    case_id,
                    event_id,
                )

                event = event_index.get(event_id)

                if event is None:
                    unexpected_findings.append(
                        {
                            "case_id": case_id,
                            "finding_id": finding_id,
                            "event_id": event_id,
                            "reason": ("unresolved_event"),
                        }
                    )

                    continue

                actual_covered.add(key)

                if key in expected_suppressed_ids:
                    suppressed_events_with_findings.append(
                        {
                            "case_id": case_id,
                            "finding_id": finding_id,
                            "event_id": event_id,
                            "event_type": (event.get("event_type")),
                        }
                    )

                if key not in expected_eligible_ids and key not in expected_suppressed_ids:
                    unexpected_findings.append(
                        {
                            "case_id": case_id,
                            "finding_id": finding_id,
                            "event_id": event_id,
                            "event_type": (event.get("event_type")),
                            "reason": ("event_not_in_untimed_population"),
                        }
                    )

    missing_expected_ids = expected_eligible_ids - actual_covered

    for (
        case_id,
        event_id,
    ) in sorted(missing_expected_ids):
        case_dir = CASE_ROOT / case_id

        event_index = {
            str(event["event_id"]): event
            for event in load_timeline(case_dir)
            if event.get("event_id")
        }

        event = event_index[event_id]

        record = {
            "case_id": case_id,
            "event_id": event_id,
            "event_type": event.get("event_type"),
            "subject": event.get("subject"),
        }

        missing_expected_findings.append(record)

        eligible_events_without_findings.append(record)

    unexpected_covered_ids = actual_covered - expected_eligible_ids

    rule_violation_count = sum(
        (
            len(eligible_events_without_findings),
            len(suppressed_events_with_findings),
            len(unexpected_findings),
        )
    )

    eligible_coverage_rate = (
        (len(expected_eligible_ids & actual_covered) / expected_eligible)
        if expected_eligible
        else 1.0
    )

    suppression_accuracy = (
        (len(expected_suppressed_ids - actual_covered) / expected_suppressed)
        if expected_suppressed
        else 1.0
    )

    status = "PASS" if rule_violation_count == 0 else "FAIL"

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8D.5b",
        "status": status,
        "production_rule": {
            "missing_event_time_eligible_event_types": (sorted(IMPORTANT_EVENT_TYPES)),
            "intentionally_suppressed_event_types": (sorted(suppressed_by_type)),
        },
        "reports_scanned": (reports_scanned),
        "timeline_events": (timeline_events),
        "untimed_events": (untimed_events),
        "eligibility": {
            "expected_eligible": (expected_eligible),
            "expected_suppressed": (expected_suppressed),
            "actual_covered": len(actual_covered),
            "eligible_coverage_rate": (eligible_coverage_rate),
            "eligible_coverage_percentage": (eligible_coverage_rate * 100.0),
            "suppression_accuracy": (suppression_accuracy),
            "suppression_accuracy_percentage": (suppression_accuracy * 100.0),
        },
        "eligible_by_event_type": dict(sorted(eligible_by_type.items())),
        "suppressed_by_event_type": dict(sorted(suppressed_by_type.items())),
        "validation": {
            "eligible_events_without_findings": (len(eligible_events_without_findings)),
            "suppressed_events_with_findings": (len(suppressed_events_with_findings)),
            "unexpected_findings": (len(unexpected_findings)),
            "unexpected_covered_event_ids": (len(unexpected_covered_ids)),
            "rule_violation_count": (rule_violation_count),
        },
        "issues": {
            "eligible_events_without_findings": (eligible_events_without_findings),
            "suppressed_events_with_findings": (suppressed_events_with_findings),
            "unexpected_findings": (unexpected_findings),
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
    print("STEP 8D.5b PRODUCTION SUPPRESSION-RULE VALIDATION")
    print("=" * 72)

    print(f"Status:                         {status}")

    print(f"Reports scanned:                {reports_scanned}")

    print(f"Timeline events:                {timeline_events}")

    print(f"Untimed events:                 {untimed_events}")

    print()
    print("Production eligibility")
    print("-" * 72)

    print(f"Expected eligible:              {expected_eligible}")

    print(f"Expected suppressed:            {expected_suppressed}")

    print(f"Actual covered events:          {len(actual_covered)}")

    print(f"Eligible-event coverage:        {eligible_coverage_rate * 100.0:.1f}%")

    print(f"Suppression accuracy:           {suppression_accuracy * 100.0:.1f}%")

    print()
    print("Rule validation")
    print("-" * 72)

    print(f"Eligible events missed:         {len(eligible_events_without_findings)}")

    print(f"Suppressed events with finding: {len(suppressed_events_with_findings)}")

    print(f"Unexpected findings:            {len(unexpected_findings)}")

    print(f"Rule violations:                {rule_violation_count}")

    print()
    print("Expected suppressed population")
    print("-" * 72)

    for event_type, count in sorted(suppressed_by_type.items()):
        print(f"{event_type:<32}{count:>8}")

    print()
    print("Saved evaluation to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

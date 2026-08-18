from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "timeline"

OUTPUT_PATH = OUTPUT_DIR / "timeline_integrity.json"


def load_json(path: Path) -> Any:
    """Load JSON from disk."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def flatten_records(
    value: Any,
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Extract records from common top-level JSON structures."""

    if isinstance(value, list):
        return [record for record in value if isinstance(record, dict)]

    if isinstance(value, dict):
        for key in keys:
            records = value.get(key)

            if isinstance(records, list):
                return [record for record in records if isinstance(record, dict)]

    return []


def load_evidence_items(
    case_dir: Path,
) -> list[dict[str, Any]]:
    """Load case evidence records."""

    path = case_dir / "evidence_items.json"

    if not path.exists():
        return []

    return flatten_records(
        load_json(path),
        (
            "evidence_items",
            "items",
            "records",
        ),
    )


def load_claims(
    case_dir: Path,
) -> list[dict[str, Any]]:
    """Load case clinical claims."""

    path = case_dir / "clinical_claims.json"

    if not path.exists():
        return []

    return flatten_records(
        load_json(path),
        (
            "clinical_claims",
            "claims",
            "records",
        ),
    )


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


def load_final_findings(
    case_dir: Path,
) -> list[dict[str, Any]]:
    """Load authoritative current findings."""

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
        records = report.get(key)

        if isinstance(records, list):
            findings.extend(record for record in records if isinstance(record, dict))

    return findings


def parse_datetime(
    value: Any,
) -> datetime | None:
    """Parse an ISO-8601 timestamp when present."""

    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(f"Timestamp is not a string: {value!r}")

    cleaned = value.strip()

    if not cleaned:
        return None

    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"

    return datetime.fromisoformat(cleaned)


def string_ids(
    value: Any,
) -> list[str]:
    """Return non-empty string IDs from a value."""

    if isinstance(value, str):
        return [value] if value else []

    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]

    return []


def main() -> int:
    """Evaluate Step 8D.1 timeline integrity."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    reports_scanned = 0
    total_events = 0

    event_type_counts: Counter[str] = Counter()

    precision_counts: Counter[str] = Counter()

    events_with_time = 0
    events_without_time = 0

    duplicate_event_ids: list[dict[str, Any]] = []

    case_id_mismatches: list[dict[str, Any]] = []

    unresolved_evidence: list[dict[str, Any]] = []

    unresolved_claims: list[dict[str, Any]] = []

    invalid_timestamps: list[dict[str, Any]] = []

    invalid_intervals: list[dict[str, Any]] = []

    missing_time_findings = 0
    missing_time_findings_valid = 0

    unresolved_missing_time_events: list[dict[str, Any]] = []

    incorrect_missing_time_findings: list[dict[str, Any]] = []

    all_event_ids: set[str] = set()

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        timeline_path = case_dir / "canonical_timeline.json"

        report_path = case_dir / "final_investigation_report.json"

        if not timeline_path.exists() or not report_path.exists():
            continue

        reports_scanned += 1

        evidence_items = load_evidence_items(case_dir)

        claims = load_claims(case_dir)

        events = load_timeline(case_dir)

        findings = load_final_findings(case_dir)

        evidence_ids = {
            record["evidence_id"]
            for record in evidence_items
            if isinstance(
                record.get("evidence_id"),
                str,
            )
        }

        claim_ids = {
            record["claim_id"]
            for record in claims
            if isinstance(
                record.get("claim_id"),
                str,
            )
        }

        event_index: dict[
            str,
            dict[str, Any],
        ] = {}

        for event in events:
            total_events += 1

            event_id = event.get("event_id")

            if not isinstance(event_id, str) or not event_id:
                duplicate_event_ids.append(
                    {
                        "case_id": (case_dir.name),
                        "event_id": event_id,
                        "issue": ("missing_or_invalid_event_id"),
                    }
                )
                continue

            if event_id in all_event_ids:
                duplicate_event_ids.append(
                    {
                        "case_id": (case_dir.name),
                        "event_id": event_id,
                        "issue": ("duplicate_event_id"),
                    }
                )

            all_event_ids.add(event_id)

            event_index[event_id] = event

            event_case_id = event.get("case_id")

            if event_case_id != case_dir.name:
                case_id_mismatches.append(
                    {
                        "case_id": (case_dir.name),
                        "event_id": event_id,
                        "event_case_id": (event_case_id),
                    }
                )

            event_type = str(
                event.get(
                    "event_type",
                    "unknown",
                )
            )

            event_type_counts[event_type] += 1

            precision = str(
                event.get(
                    "time_precision",
                    "unknown",
                )
            )

            precision_counts[precision] += 1

            normalized_time = event.get("normalized_time")

            time_end = event.get("time_end")

            if normalized_time is None:
                events_without_time += 1
            else:
                events_with_time += 1

            start_dt = None
            end_dt = None

            try:
                start_dt = parse_datetime(normalized_time)
            except (
                TypeError,
                ValueError,
            ) as exc:
                invalid_timestamps.append(
                    {
                        "case_id": (case_dir.name),
                        "event_id": event_id,
                        "field": ("normalized_time"),
                        "value": (normalized_time),
                        "error": str(exc),
                    }
                )

            try:
                end_dt = parse_datetime(time_end)
            except (
                TypeError,
                ValueError,
            ) as exc:
                invalid_timestamps.append(
                    {
                        "case_id": (case_dir.name),
                        "event_id": event_id,
                        "field": "time_end",
                        "value": time_end,
                        "error": str(exc),
                    }
                )

            if start_dt is not None and end_dt is not None and end_dt < start_dt:
                invalid_intervals.append(
                    {
                        "case_id": (case_dir.name),
                        "event_id": event_id,
                        "normalized_time": (normalized_time),
                        "time_end": (time_end),
                    }
                )

            for evidence_id in string_ids(event.get("evidence_ids")):
                if evidence_id not in evidence_ids:
                    unresolved_evidence.append(
                        {
                            "case_id": (case_dir.name),
                            "event_id": event_id,
                            "evidence_id": (evidence_id),
                        }
                    )

            for claim_id in string_ids(event.get("source_claim_ids")):
                if claim_id not in claim_ids:
                    unresolved_claims.append(
                        {
                            "case_id": (case_dir.name),
                            "event_id": event_id,
                            "claim_id": (claim_id),
                        }
                    )

        for finding in findings:
            if finding.get("subtype") != "missing_event_time":
                continue

            missing_time_findings += 1

            event_ids = string_ids(finding.get("event_ids"))

            if not event_ids:
                unresolved_missing_time_events.append(
                    {
                        "case_id": (case_dir.name),
                        "finding_id": (finding.get("finding_id")),
                        "event_ids": [],
                    }
                )
                continue

            finding_valid = True

            for event_id in event_ids:
                event = event_index.get(event_id)

                if event is None:
                    finding_valid = False

                    unresolved_missing_time_events.append(
                        {
                            "case_id": (case_dir.name),
                            "finding_id": (finding.get("finding_id")),
                            "event_id": (event_id),
                        }
                    )

                    continue

                if event.get("normalized_time") is not None:
                    finding_valid = False

                    incorrect_missing_time_findings.append(
                        {
                            "case_id": (case_dir.name),
                            "finding_id": (finding.get("finding_id")),
                            "event_id": (event_id),
                            "normalized_time": (event.get("normalized_time")),
                        }
                    )

            if finding_valid:
                missing_time_findings_valid += 1

    integrity_issue_count = sum(
        (
            len(duplicate_event_ids),
            len(case_id_mismatches),
            len(unresolved_evidence),
            len(unresolved_claims),
            len(invalid_timestamps),
            len(invalid_intervals),
            len(unresolved_missing_time_events),
            len(incorrect_missing_time_findings),
        )
    )

    missing_time_validation_rate = (
        (missing_time_findings_valid / missing_time_findings) if missing_time_findings else 1.0
    )

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8D.1",
        "reports_scanned": (reports_scanned),
        "total_timeline_events": (total_events),
        "timeline_summary": {
            "events_with_normalized_time": (events_with_time),
            "events_without_normalized_time": (events_without_time),
            "event_type_counts": dict(sorted(event_type_counts.items())),
            "time_precision_counts": dict(sorted(precision_counts.items())),
        },
        "provenance_integrity": {
            "duplicate_event_ids": len(duplicate_event_ids),
            "case_id_mismatches": len(case_id_mismatches),
            "unresolved_evidence_references": (len(unresolved_evidence)),
            "unresolved_claim_references": (len(unresolved_claims)),
        },
        "temporal_integrity": {
            "invalid_timestamps": len(invalid_timestamps),
            "invalid_intervals": len(invalid_intervals),
        },
        "missing_event_time_validation": {
            "findings_evaluated": (missing_time_findings),
            "valid_findings": (missing_time_findings_valid),
            "unresolved_event_references": (len(unresolved_missing_time_events)),
            "findings_pointing_to_timed_events": (len(incorrect_missing_time_findings)),
            "validation_rate": (missing_time_validation_rate),
            "validation_percentage": (missing_time_validation_rate * 100.0),
        },
        "integrity_issue_count": (integrity_issue_count),
        "issues": {
            "duplicate_event_ids": (duplicate_event_ids),
            "case_id_mismatches": (case_id_mismatches),
            "unresolved_evidence": (unresolved_evidence),
            "unresolved_claims": (unresolved_claims),
            "invalid_timestamps": (invalid_timestamps),
            "invalid_intervals": (invalid_intervals),
            "unresolved_missing_time_events": (unresolved_missing_time_events),
            "incorrect_missing_time_findings": (incorrect_missing_time_findings),
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
    print("STEP 8D.1 TIMELINE INTEGRITY")
    print("=" * 72)

    print(f"Reports scanned:                  {reports_scanned}")

    print(f"Timeline events:                  {total_events}")

    print()
    print("Timeline timestamp coverage")
    print("-" * 72)

    print(f"With normalized time:             {events_with_time}")

    print(f"Without normalized time:          {events_without_time}")

    print()
    print("Provenance integrity")
    print("-" * 72)

    print(f"Duplicate event IDs:              {len(duplicate_event_ids)}")

    print(f"Case-ID mismatches:               {len(case_id_mismatches)}")

    print(f"Unresolved evidence references:   {len(unresolved_evidence)}")

    print(f"Unresolved claim references:      {len(unresolved_claims)}")

    print()
    print("Temporal integrity")
    print("-" * 72)

    print(f"Invalid timestamps:               {len(invalid_timestamps)}")

    print(f"Invalid intervals:                {len(invalid_intervals)}")

    print()
    print("Current missing_event_time findings")
    print("-" * 72)

    print(f"Findings evaluated:               {missing_time_findings}")

    print(f"Valid missing-time findings:      {missing_time_findings_valid}")

    print(f"Unresolved event references:      {len(unresolved_missing_time_events)}")

    print(f"Pointing to timed events:         {len(incorrect_missing_time_findings)}")

    print(f"Validation rate:                  {missing_time_validation_rate * 100.0:.1f}%")

    print()
    print(f"Integrity issues:                 {integrity_issue_count}")

    print()
    print("Saved evaluation to:")

    print(OUTPUT_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "timeline"

OUTPUT_PATH = OUTPUT_DIR / "missing_event_time_verification.json"


# Strong structured fields whose presence directly challenges a
# missing-event-time assertion.
STRONG_TEMPORAL_FIELDS = (
    "event_time",
    "time_start",
    "start_time",
)

# These may be relevant but are not always sufficient by themselves to
# establish an event start time.
WEAK_TEMPORAL_FIELDS = (
    "time_end",
    "end_time",
    "document_date",
    "note_date",
    "encounter_date",
    "recorded_date",
    "authored_time",
    "issued_time",
)

# Evidence text fields commonly used by the extraction pipeline.
TEXT_FIELDS = (
    "text",
    "content",
    "raw_text",
    "source_text",
    "excerpt",
    "statement",
    "description",
)

MONTH_NAMES = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)

MONTH_PATTERN = "|".join(MONTH_NAMES)

ISO_DATETIME_PATTERN = re.compile(
    r"\b"
    r"\d{4}-\d{2}-\d{2}"
    r"(?:[T\s]\d{1,2}:\d{2}"
    r"(?::\d{2}(?:\.\d+)?)?"
    r"(?:Z|[+-]\d{2}:\d{2})?"
    r")?"
    r"\b",
    flags=re.IGNORECASE,
)

MONTH_DATETIME_PATTERN = re.compile(
    rf"\b(?:{MONTH_PATTERN})\s+"
    r"\d{1,2},?\s+\d{4}"
    r"(?:\s+at\s+\d{1,2}:\d{2}"
    r"(?:\s*(?:AM|PM|UTC))?"
    r")?"
    r"\b",
    flags=re.IGNORECASE,
)

US_DATE_PATTERN = re.compile(
    r"\b"
    r"(?:0?[1-9]|1[0-2])/"
    r"(?:0?[1-9]|[12]\d|3[01])/"
    r"(?:19|20)\d{2}"
    r"(?:\s+\d{1,2}:\d{2}"
    r"(?:\s*(?:AM|PM))?"
    r")?"
    r"\b",
    flags=re.IGNORECASE,
)

CLOCK_TIME_PATTERN = re.compile(
    r"\b"
    r"(?:[01]?\d|2[0-3]):[0-5]\d"
    r"(?::[0-5]\d)?"
    r"(?:\s*(?:AM|PM|UTC))?"
    r"\b",
    flags=re.IGNORECASE,
)


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
            records = raw.get(key)

            if isinstance(records, list):
                return [item for item in records if isinstance(item, dict)]

    return []


def load_evidence_items(case_dir: Path) -> list[dict[str, Any]]:
    """Load evidence items."""

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


def load_timeline(case_dir: Path) -> list[dict[str, Any]]:
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


def load_final_findings(case_dir: Path) -> list[dict[str, Any]]:
    """Load findings from the authoritative final report."""

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


def string_ids(value: Any) -> list[str]:
    """Normalize scalar/list IDs."""

    if isinstance(value, str):
        return [value] if value else []

    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]

    return []


def meaningful_value(value: Any) -> bool:
    """Return whether a temporal field contains a meaningful value."""

    if value is None:
        return False

    if isinstance(value, str):
        cleaned = value.strip().lower()

        return cleaned not in {
            "",
            "none",
            "null",
            "unknown",
            "n/a",
            "na",
            "not available",
            "not documented",
        }

    return True


def collect_text(evidence: dict[str, Any]) -> str:
    """Collect candidate natural-language evidence text."""

    parts: list[str] = []

    for field in TEXT_FIELDS:
        value = evidence.get(field)

        if isinstance(value, str) and value.strip():
            parts.append(value.strip())

    return "\n".join(parts)


def find_explicit_temporal_strings(text: str) -> list[str]:
    """Find explicit date/time expressions conservatively."""

    if not text:
        return []

    matches: list[str] = []

    for pattern in (
        ISO_DATETIME_PATTERN,
        MONTH_DATETIME_PATTERN,
        US_DATE_PATTERN,
    ):
        matches.extend(match.group(0) for match in pattern.finditer(text))

    # A standalone clock time is weaker than a date. Keep it as a
    # temporal signal but do not independently treat it as decisive.
    matches.extend(match.group(0) for match in CLOCK_TIME_PATTERN.finditer(text))

    return list(dict.fromkeys(matches))


def classify_evidence_temporal_signal(
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Classify temporal signals in one evidence item."""

    strong_fields: dict[str, Any] = {}

    weak_fields: dict[str, Any] = {}

    for field in STRONG_TEMPORAL_FIELDS:
        value = evidence.get(field)

        if meaningful_value(value):
            strong_fields[field] = value

    for field in WEAK_TEMPORAL_FIELDS:
        value = evidence.get(field)

        if meaningful_value(value):
            weak_fields[field] = value

    text = collect_text(evidence)

    temporal_strings = find_explicit_temporal_strings(text)

    date_like_strings = [
        value
        for value in temporal_strings
        if (
            ISO_DATETIME_PATTERN.fullmatch(value)
            or MONTH_DATETIME_PATTERN.fullmatch(value)
            or US_DATE_PATTERN.fullmatch(value)
        )
    ]

    clock_only_strings = [value for value in temporal_strings if value not in date_like_strings]

    if strong_fields:
        disposition = "strong_structured_time"

    elif date_like_strings:
        disposition = "explicit_date_in_source_text"

    elif weak_fields or clock_only_strings:
        disposition = "ambiguous_temporal_signal"

    else:
        disposition = "no_temporal_signal"

    return {
        "disposition": disposition,
        "strong_temporal_fields": strong_fields,
        "weak_temporal_fields": weak_fields,
        "explicit_date_strings": date_like_strings,
        "clock_only_strings": clock_only_strings,
    }


def evidence_ids_for_event(
    event: dict[str, Any],
) -> list[str]:
    """Get evidence IDs referenced by a timeline event."""

    values: list[str] = []

    for field in (
        "evidence_ids",
        "source_evidence_ids",
    ):
        values.extend(string_ids(event.get(field)))

    return list(dict.fromkeys(values))


def evidence_ids_for_finding(
    finding: dict[str, Any],
) -> list[str]:
    """Get direct evidence IDs referenced by a finding."""

    values: list[str] = []

    for field in (
        "evidence_ids",
        "source_evidence_ids",
    ):
        values.extend(string_ids(finding.get(field)))

    provenance = finding.get("provenance")

    if isinstance(provenance, dict):
        for field in (
            "evidence_ids",
            "source_evidence_ids",
        ):
            values.extend(string_ids(provenance.get(field)))

    return list(dict.fromkeys(values))


def main() -> int:
    """Run Step 8D.4 semantic missing-time verification."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    reports_scanned = 0
    timeline_events_scanned = 0

    untimed_timeline_events = 0

    findings_evaluated = 0

    verified_missing = 0
    contradicted_by_source_time = 0
    manual_review = 0

    unresolved_event_references = 0
    unresolved_evidence_references = 0

    disposition_counts: Counter[str] = Counter()

    results: list[dict[str, Any]] = []

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        report_path = case_dir / "final_investigation_report.json"
        timeline_path = case_dir / "canonical_timeline.json"

        if not report_path.exists() or not timeline_path.exists():
            continue

        reports_scanned += 1

        evidence_items = load_evidence_items(case_dir)
        timeline = load_timeline(case_dir)
        findings = load_final_findings(case_dir)

        timeline_events_scanned += len(timeline)

        untimed_timeline_events += sum(
            1 for event in timeline if event.get("normalized_time") is None
        )

        evidence_index = {
            str(record["evidence_id"]): record
            for record in evidence_items
            if record.get("evidence_id")
        }

        event_index = {str(event["event_id"]): event for event in timeline if event.get("event_id")}

        for finding in findings:
            if finding.get("subtype") != "missing_event_time":
                continue

            findings_evaluated += 1

            finding_id = finding.get("finding_id")

            event_ids = string_ids(finding.get("event_ids"))

            resolved_events: list[dict[str, Any]] = []

            missing_event_ids: list[str] = []

            for event_id in event_ids:
                event = event_index.get(event_id)

                if event is None:
                    missing_event_ids.append(event_id)
                    unresolved_event_references += 1
                    continue

                resolved_events.append(event)

            evidence_ids = evidence_ids_for_finding(finding)

            for event in resolved_events:
                evidence_ids.extend(evidence_ids_for_event(event))

            evidence_ids = list(dict.fromkeys(evidence_ids))

            resolved_evidence: list[dict[str, Any]] = []

            missing_evidence_ids: list[str] = []

            for evidence_id in evidence_ids:
                evidence = evidence_index.get(evidence_id)

                if evidence is None:
                    missing_evidence_ids.append(evidence_id)

                    unresolved_evidence_references += 1
                    continue

                resolved_evidence.append(evidence)

            evidence_checks: list[dict[str, Any]] = []

            has_strong_time = False
            has_explicit_text_date = False
            has_ambiguous_signal = False

            for evidence in resolved_evidence:
                check = classify_evidence_temporal_signal(evidence)

                disposition = check["disposition"]

                disposition_counts[disposition] += 1

                if disposition == "strong_structured_time":
                    has_strong_time = True

                elif disposition == "explicit_date_in_source_text":
                    has_explicit_text_date = True

                elif disposition == "ambiguous_temporal_signal":
                    has_ambiguous_signal = True

                evidence_checks.append(
                    {
                        "evidence_id": (evidence.get("evidence_id")),
                        "document_type": (evidence.get("document_type")),
                        "source_table": (evidence.get("source_table")),
                        "source_row": (evidence.get("source_row")),
                        **check,
                    }
                )

            if missing_event_ids or missing_evidence_ids:
                final_disposition = "manual_review"

            elif has_strong_time or has_explicit_text_date:
                final_disposition = "contradicted_by_source_time"

            elif has_ambiguous_signal:
                final_disposition = "manual_review"

            else:
                final_disposition = "verified_missing"

            if final_disposition == "verified_missing":
                verified_missing += 1

            elif final_disposition == "contradicted_by_source_time":
                contradicted_by_source_time += 1

            else:
                manual_review += 1

            results.append(
                {
                    "case_id": case_dir.name,
                    "finding_id": finding_id,
                    "finding_type": (finding.get("finding_type")),
                    "subtype": (finding.get("subtype")),
                    "event_ids": event_ids,
                    "missing_event_ids": (missing_event_ids),
                    "evidence_ids": (evidence_ids),
                    "missing_evidence_ids": (missing_evidence_ids),
                    "disposition": (final_disposition),
                    "evidence_checks": (evidence_checks),
                }
            )

    if contradicted_by_source_time:
        status = "FAIL"

    elif manual_review:
        status = "PASS_WITH_MANUAL_REVIEW"

    else:
        status = "PASS"

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8D.4",
        "status": status,
        "evaluation_method": (
            "Independent semantic challenge of "
            "missing_event_time findings. The "
            "verifier does not invoke the production "
            "timeline timestamp parser. It resolves "
            "each finding to its source timeline event "
            "and evidence, then checks for structured "
            "event times, explicit date/time strings, "
            "and weaker temporal signals."
        ),
        "reports_scanned": reports_scanned,
        "timeline_events_scanned": (timeline_events_scanned),
        "untimed_timeline_events": (untimed_timeline_events),
        "findings_evaluated": (findings_evaluated),
        "verification_summary": {
            "verified_missing": (verified_missing),
            "contradicted_by_source_time": (contradicted_by_source_time),
            "manual_review": manual_review,
            "unresolved_event_references": (unresolved_event_references),
            "unresolved_evidence_references": (unresolved_evidence_references),
        },
        "evidence_signal_counts": dict(sorted(disposition_counts.items())),
        "results": results,
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
    print("STEP 8D.4 MISSING-EVENT-TIME SEMANTIC VERIFICATION")
    print("=" * 72)

    print(f"Status:                         {status}")

    print(f"Reports scanned:                {reports_scanned}")

    print(f"Timeline events scanned:        {timeline_events_scanned}")

    print(f"Untimed timeline events:        {untimed_timeline_events}")

    print()
    print("Missing-event-time findings")
    print("-" * 72)

    print(f"Findings evaluated:             {findings_evaluated}")

    print(f"Verified missing:               {verified_missing}")

    print(f"Contradicted by source time:    {contradicted_by_source_time}")

    print(f"Manual review:                  {manual_review}")

    print()
    print("Reference integrity")
    print("-" * 72)

    print(f"Unresolved event references:    {unresolved_event_references}")

    print(f"Unresolved evidence references: {unresolved_evidence_references}")

    print()
    print("Evidence temporal signals")
    print("-" * 72)

    for key, count in sorted(disposition_counts.items()):
        print(f"{key:<32}{count:>8}")

    print()
    print("Saved evaluation to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

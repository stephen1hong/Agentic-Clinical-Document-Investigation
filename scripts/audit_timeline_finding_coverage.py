from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "timeline"

OUTPUT_PATH = OUTPUT_DIR / "timeline_finding_coverage_audit.json"


def load_json(path: Path) -> Any:
    """Load JSON from disk."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


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
        records = report.get(key)

        if isinstance(records, list):
            findings.extend(item for item in records if isinstance(item, dict))

    return findings


def string_ids(value: Any) -> list[str]:
    """Normalize a scalar/list field into string IDs."""

    if isinstance(value, str):
        return [value] if value else []

    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]

    return []


def finding_event_ids(
    finding: dict[str, Any],
) -> list[str]:
    """Return event IDs referenced by a finding."""

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


def sortable_value(value: Any) -> str:
    """Convert arbitrary values to stable labels."""

    if value is None:
        return "null"

    if isinstance(value, str):
        return value or "empty"

    return str(value)


def source_document_types(
    event: dict[str, Any],
) -> list[str]:
    """Extract document-type metadata when available."""

    values: list[str] = []

    for field in (
        "source_document_types",
        "document_types",
    ):
        raw = event.get(field)

        if isinstance(raw, str):
            if raw:
                values.append(raw)

        elif isinstance(raw, list):
            values.extend(item for item in raw if isinstance(item, str) and item)

    return list(dict.fromkeys(values))


def compact_event(
    case_id: str,
    event: dict[str, Any],
) -> dict[str, Any]:
    """Create an inspectable event summary."""

    return {
        "case_id": case_id,
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "subject": event.get("subject"),
        "normalized_time": event.get("normalized_time"),
        "time_end": event.get("time_end"),
        "time_precision": event.get("time_precision"),
        "time_source": event.get("time_source"),
        "evidence_ids": event.get("evidence_ids"),
        "source_claim_ids": event.get("source_claim_ids"),
        "source_document_types": (source_document_types(event)),
    }


def main() -> int:
    """Run Step 8D.5 timeline finding coverage audit."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    reports_scanned = 0
    total_timeline_events = 0
    untimed_events = 0

    missing_time_findings = 0

    covered_untimed_event_ids: set[tuple[str, str]] = set()

    all_untimed_event_ids: set[tuple[str, str]] = set()

    finding_to_event_pairs: list[tuple[str, str, str]] = []

    event_to_findings: defaultdict[
        tuple[str, str],
        list[str],
    ] = defaultdict(list)

    missing_time_findings_without_events: list[dict[str, Any]] = []

    unresolved_event_references: list[dict[str, Any]] = []

    timed_events_referenced_by_missing_findings: list[dict[str, Any]] = []

    duplicate_finding_event_pairs: list[dict[str, Any]] = []

    covered_events: list[dict[str, Any]] = []

    suppressed_events: list[dict[str, Any]] = []

    multi_covered_events: list[dict[str, Any]] = []

    suppressed_by_type: Counter[str] = Counter()

    covered_by_type: Counter[str] = Counter()

    suppressed_by_precision: Counter[str] = Counter()

    covered_by_precision: Counter[str] = Counter()

    suppressed_by_source: Counter[str] = Counter()

    covered_by_source: Counter[str] = Counter()

    suppressed_by_document_type: Counter[str] = Counter()

    covered_by_document_type: Counter[str] = Counter()

    case_summaries: list[dict[str, Any]] = []

    seen_finding_event_pairs: set[tuple[str, str, str]] = set()

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        timeline_path = case_dir / "canonical_timeline.json"

        report_path = case_dir / "final_investigation_report.json"

        if not timeline_path.exists() or not report_path.exists():
            continue

        reports_scanned += 1

        case_id = case_dir.name

        timeline = load_timeline(case_dir)

        findings = load_final_findings(case_dir)

        total_timeline_events += len(timeline)

        event_index: dict[
            str,
            dict[str, Any],
        ] = {str(event["event_id"]): event for event in timeline if event.get("event_id")}

        case_untimed_ids: set[str] = {
            event_id
            for event_id, event in event_index.items()
            if event.get("normalized_time") is None
        }

        untimed_events += len(case_untimed_ids)

        all_untimed_event_ids.update(
            (
                case_id,
                event_id,
            )
            for event_id in case_untimed_ids
        )

        case_missing_findings = 0

        for finding in findings:
            if finding.get("subtype") != "missing_event_time":
                continue

            missing_time_findings += 1
            case_missing_findings += 1

            finding_id = str(
                finding.get(
                    "finding_id",
                    "",
                )
            )

            event_ids = finding_event_ids(finding)

            if not event_ids:
                missing_time_findings_without_events.append(
                    {
                        "case_id": case_id,
                        "finding_id": (finding_id),
                    }
                )

                continue

            for event_id in event_ids:
                event = event_index.get(event_id)

                if event is None:
                    unresolved_event_references.append(
                        {
                            "case_id": (case_id),
                            "finding_id": (finding_id),
                            "event_id": (event_id),
                        }
                    )

                    continue

                pair = (
                    case_id,
                    finding_id,
                    event_id,
                )

                finding_to_event_pairs.append(pair)

                if pair in seen_finding_event_pairs:
                    duplicate_finding_event_pairs.append(
                        {
                            "case_id": (case_id),
                            "finding_id": (finding_id),
                            "event_id": (event_id),
                        }
                    )

                seen_finding_event_pairs.add(pair)

                event_to_findings[
                    (
                        case_id,
                        event_id,
                    )
                ].append(finding_id)

                if event.get("normalized_time") is not None:
                    timed_events_referenced_by_missing_findings.append(
                        {
                            "case_id": (case_id),
                            "finding_id": (finding_id),
                            "event_id": (event_id),
                            "normalized_time": (event.get("normalized_time")),
                        }
                    )

                    continue

                covered_untimed_event_ids.add(
                    (
                        case_id,
                        event_id,
                    )
                )

        case_covered = {
            event_id
            for (
                covered_case_id,
                event_id,
            ) in covered_untimed_event_ids
            if covered_case_id == case_id
        }

        case_suppressed = case_untimed_ids - case_covered

        case_summaries.append(
            {
                "case_id": case_id,
                "timeline_events": len(timeline),
                "untimed_events": len(case_untimed_ids),
                "missing_event_time_findings": (case_missing_findings),
                "covered_untimed_events": len(case_covered),
                "suppressed_untimed_events": len(case_suppressed),
            }
        )

    suppressed_ids = all_untimed_event_ids - covered_untimed_event_ids

    #
    # Second pass:
    # create detailed summaries for covered/suppressed events.
    #
    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        timeline_path = case_dir / "canonical_timeline.json"

        report_path = case_dir / "final_investigation_report.json"

        if not timeline_path.exists() or not report_path.exists():
            continue

        case_id = case_dir.name

        timeline = load_timeline(case_dir)

        for event in timeline:
            event_id = event.get("event_id")

            if not isinstance(event_id, str) or not event_id:
                continue

            key = (
                case_id,
                event_id,
            )

            if key not in all_untimed_event_ids:
                continue

            summary = compact_event(
                case_id,
                event,
            )

            event_type = sortable_value(event.get("event_type"))

            precision = sortable_value(event.get("time_precision"))

            time_source = sortable_value(event.get("time_source"))

            document_types = source_document_types(event)

            if not document_types:
                document_types = ["unknown"]

            finding_ids = event_to_findings.get(
                key,
                [],
            )

            summary["missing_event_time_finding_ids"] = finding_ids

            if key in covered_untimed_event_ids:
                covered_events.append(summary)

                covered_by_type[event_type] += 1

                covered_by_precision[precision] += 1

                covered_by_source[time_source] += 1

                for document_type in document_types:
                    covered_by_document_type[document_type] += 1

            else:
                suppressed_events.append(summary)

                suppressed_by_type[event_type] += 1

                suppressed_by_precision[precision] += 1

                suppressed_by_source[time_source] += 1

                for document_type in document_types:
                    suppressed_by_document_type[document_type] += 1

    for (
        case_id,
        event_id,
    ), finding_ids in sorted(event_to_findings.items()):
        unique_finding_ids = list(dict.fromkeys(finding_ids))

        if len(unique_finding_ids) <= 1:
            continue

        multi_covered_events.append(
            {
                "case_id": case_id,
                "event_id": event_id,
                "finding_ids": (unique_finding_ids),
                "finding_count": len(unique_finding_ids),
            }
        )

    covered_count = len(covered_untimed_event_ids)

    suppressed_count = len(suppressed_ids)

    if covered_count + suppressed_count != untimed_events:
        raise RuntimeError(
            "Coverage accounting mismatch: "
            f"{covered_count} covered + "
            f"{suppressed_count} suppressed "
            f"!= {untimed_events} untimed."
        )

    coverage_rate = covered_count / untimed_events if untimed_events else 1.0

    suppression_rate = suppressed_count / untimed_events if untimed_events else 0.0

    mapping_issue_count = sum(
        (
            len(missing_time_findings_without_events),
            len(unresolved_event_references),
            len(timed_events_referenced_by_missing_findings),
            len(duplicate_finding_event_pairs),
        )
    )

    #
    # Important:
    # suppression itself is NOT counted as an error here.
    # This audit establishes the population requiring
    # production-rule review.
    #
    if mapping_issue_count:
        status = "FAIL"
    elif suppressed_count:
        status = "PASS_WITH_DOCUMENTED_SUPPRESSION"
    else:
        status = "PASS"

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8D.5",
        "status": status,
        "evaluation_method": (
            "Audit coverage of untimed canonical "
            "timeline events by current "
            "missing_event_time findings. "
            "The audit distinguishes covered and "
            "suppressed untimed events, validates "
            "finding-to-event mappings, and "
            "characterizes the suppressed population. "
            "Suppression is not automatically treated "
            "as a false negative because production "
            "eligibility rules are evaluated separately."
        ),
        "reports_scanned": (reports_scanned),
        "total_timeline_events": (total_timeline_events),
        "untimed_events": (untimed_events),
        "missing_event_time_findings": (missing_time_findings),
        "coverage": {
            "covered_untimed_events": (covered_count),
            "suppressed_untimed_events": (suppressed_count),
            "coverage_rate": (coverage_rate),
            "coverage_percentage": (coverage_rate * 100.0),
            "suppression_rate": (suppression_rate),
            "suppression_percentage": (suppression_rate * 100.0),
        },
        "mapping_integrity": {
            "findings_without_event_ids": len(missing_time_findings_without_events),
            "unresolved_event_references": len(unresolved_event_references),
            "timed_events_referenced_by_missing_findings": len(
                timed_events_referenced_by_missing_findings
            ),
            "duplicate_finding_event_pairs": len(duplicate_finding_event_pairs),
            "events_covered_by_multiple_findings": len(multi_covered_events),
            "mapping_issue_count": (mapping_issue_count),
        },
        "covered_population": {
            "by_event_type": dict(sorted(covered_by_type.items())),
            "by_time_precision": dict(sorted(covered_by_precision.items())),
            "by_time_source": dict(sorted(covered_by_source.items())),
            "by_document_type": dict(sorted(covered_by_document_type.items())),
        },
        "suppressed_population": {
            "by_event_type": dict(sorted(suppressed_by_type.items())),
            "by_time_precision": dict(sorted(suppressed_by_precision.items())),
            "by_time_source": dict(sorted(suppressed_by_source.items())),
            "by_document_type": dict(sorted(suppressed_by_document_type.items())),
        },
        "case_summaries": (case_summaries),
        "issues": {
            "findings_without_event_ids": (missing_time_findings_without_events),
            "unresolved_event_references": (unresolved_event_references),
            "timed_events_referenced_by_missing_findings": (
                timed_events_referenced_by_missing_findings
            ),
            "duplicate_finding_event_pairs": (duplicate_finding_event_pairs),
            "events_covered_by_multiple_findings": (multi_covered_events),
        },
        "covered_events": (covered_events),
        "suppressed_events": (suppressed_events),
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
    print("STEP 8D.5 TIMELINE FINDING COVERAGE / SUPPRESSION AUDIT")
    print("=" * 72)

    print(f"Status:                         {status}")

    print(f"Reports scanned:                {reports_scanned}")

    print(f"Timeline events:                {total_timeline_events}")

    print()
    print("Untimed-event coverage")
    print("-" * 72)

    print(f"Untimed timeline events:        {untimed_events}")

    print(f"missing_event_time findings:    {missing_time_findings}")

    print(f"Covered untimed events:         {covered_count}")

    print(f"Suppressed untimed events:      {suppressed_count}")

    print(f"Coverage rate:                  {coverage_rate * 100.0:.1f}%")

    print(f"Suppression rate:               {suppression_rate * 100.0:.1f}%")

    print()
    print("Mapping integrity")
    print("-" * 72)

    print(f"Findings without event IDs:     {len(missing_time_findings_without_events)}")

    print(f"Unresolved event references:    {len(unresolved_event_references)}")

    print(f"Timed events incorrectly used:  {len(timed_events_referenced_by_missing_findings)}")

    print(f"Duplicate finding/event pairs:  {len(duplicate_finding_event_pairs)}")

    print(f"Events with multiple findings:  {len(multi_covered_events)}")

    print(f"Mapping issues:                 {mapping_issue_count}")

    print()
    print("Suppressed-event distribution")
    print("-" * 72)

    print("By event type:")

    for key, count in sorted(suppressed_by_type.items()):
        print(f"  {key:<30}{count:>6}")

    print()
    print("By time precision:")

    for key, count in sorted(suppressed_by_precision.items()):
        print(f"  {key:<30}{count:>6}")

    print()
    print("By time source:")

    for key, count in sorted(suppressed_by_source.items()):
        print(f"  {key:<30}{count:>6}")

    print()
    print("Saved evaluation to:")

    print(OUTPUT_PATH)

    return 1 if status == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())

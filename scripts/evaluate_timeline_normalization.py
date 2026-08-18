from __future__ import annotations

import inspect
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from clinical_investigation.investigation.timeline_reconstruction import (
    build_canonical_timeline,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "timeline"

OUTPUT_PATH = OUTPUT_DIR / "timestamp_normalization_correctness.json"


TIMELINE_OUTPUT_FILES = (
    "canonical_timeline.json",
    "timeline_conflicts.json",
    "timeline_manifest.json",
)


TEMPORAL_FIELDS = (
    "normalized_time",
    "time_end",
    "time_precision",
    "time_source",
)


PROVENANCE_FIELDS = (
    "source_claim_ids",
    "evidence_ids",
    "source_document_types",
    "source_tables",
    "source_rows",
)


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
    """Load canonical timeline records."""

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


def event_index(
    events: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index timeline events by event_id."""

    index: dict[str, dict[str, Any]] = {}

    for event in events:
        event_id = event.get("event_id")

        if not isinstance(event_id, str) or not event_id:
            raise ValueError("Timeline event is missing a valid event_id.")

        if event_id in index:
            raise ValueError(f"Duplicate timeline event ID: {event_id}")

        index[event_id] = event

    return index


def normalize_for_comparison(
    value: Any,
) -> Any:
    """
    Normalize unordered provenance collections.

    Temporal values themselves are intentionally
    left untouched.
    """

    if isinstance(value, list):
        try:
            return sorted(value)
        except TypeError:
            return value

    return value


def invoke_production_builder(
    case_dir: Path,
) -> None:
    """
    Invoke the actual production timeline builder.

    The evaluator deliberately uses the production
    implementation instead of duplicating timestamp
    precedence logic.
    """

    signature = inspect.signature(build_canonical_timeline)

    parameters = list(signature.parameters.values())

    required = [
        parameter
        for parameter in parameters
        if (
            parameter.default is inspect.Parameter.empty
            and parameter.kind
            in {
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            }
        )
    ]

    if len(required) != 1:
        raise RuntimeError(
            "Unable to safely invoke "
            "build_canonical_timeline(). "
            "Expected exactly one required "
            "argument but found "
            f"{len(required)}. Signature: "
            f"{signature}"
        )

    parameter = required[0]

    if parameter.kind == inspect.Parameter.KEYWORD_ONLY:
        build_canonical_timeline(
            **{
                parameter.name: case_dir,
            }
        )
    else:
        build_canonical_timeline(case_dir)


def rebuild_case_timeline(
    original_case_dir: Path,
    temporary_root: Path,
) -> Path:
    """
    Copy a case and regenerate its timeline using
    production code without touching authoritative data.
    """

    temporary_case_dir = temporary_root / original_case_dir.name

    shutil.copytree(
        original_case_dir,
        temporary_case_dir,
    )

    for filename in TIMELINE_OUTPUT_FILES:
        path = temporary_case_dir / filename

        if path.exists():
            path.unlink()

    invoke_production_builder(temporary_case_dir)

    rebuilt_path = temporary_case_dir / "canonical_timeline.json"

    if not rebuilt_path.exists():
        raise FileNotFoundError(f"Production builder did not create {rebuilt_path}")

    return rebuilt_path


def compare_event(
    *,
    case_id: str,
    persisted: dict[str, Any],
    rebuilt: dict[str, Any],
) -> list[dict[str, Any]]:
    """Compare one persisted and freshly rebuilt event."""

    issues: list[dict[str, Any]] = []

    event_id = str(persisted["event_id"])

    for field in TEMPORAL_FIELDS:
        persisted_value = persisted.get(field)

        rebuilt_value = rebuilt.get(field)

        if persisted_value != rebuilt_value:
            issues.append(
                {
                    "case_id": case_id,
                    "event_id": event_id,
                    "event_type": (persisted.get("event_type")),
                    "subject": (persisted.get("subject")),
                    "issue_type": (f"wrong_{field}"),
                    "field": field,
                    "persisted_value": (persisted_value),
                    "rebuilt_value": (rebuilt_value),
                }
            )

    for field in PROVENANCE_FIELDS:
        persisted_value = normalize_for_comparison(persisted.get(field))

        rebuilt_value = normalize_for_comparison(rebuilt.get(field))

        if persisted_value != rebuilt_value:
            issues.append(
                {
                    "case_id": case_id,
                    "event_id": event_id,
                    "event_type": (persisted.get("event_type")),
                    "subject": (persisted.get("subject")),
                    "issue_type": ("provenance_mismatch"),
                    "field": field,
                    "persisted_value": (persisted.get(field)),
                    "rebuilt_value": (rebuilt.get(field)),
                }
            )

    return issues


def main() -> int:
    """Run Step 8D.2 timestamp-normalization evaluation."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Investigation case root not found: {CASE_ROOT}")

    reports_scanned = 0

    persisted_event_count = 0
    rebuilt_event_count = 0

    matched_events = 0

    missing_after_rebuild: list[dict[str, Any]] = []

    unexpected_after_rebuild: list[dict[str, Any]] = []

    comparison_issues: list[dict[str, Any]] = []

    event_type_counts: Counter[str] = Counter()

    temporal_issue_counts: Counter[str] = Counter()

    timed_events = 0
    unknown_time_events = 0

    with tempfile.TemporaryDirectory(prefix="clinical_timeline_8d2_") as temporary_directory:
        temporary_root = Path(temporary_directory)

        for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
            persisted_path = case_dir / "canonical_timeline.json"

            report_path = case_dir / "final_investigation_report.json"

            if not persisted_path.exists() or not report_path.exists():
                continue

            reports_scanned += 1

            persisted_events = load_timeline(persisted_path)

            rebuilt_path = rebuild_case_timeline(
                case_dir,
                temporary_root,
            )

            rebuilt_events = load_timeline(rebuilt_path)

            persisted_event_count += len(persisted_events)

            rebuilt_event_count += len(rebuilt_events)

            persisted_index = event_index(persisted_events)

            rebuilt_index = event_index(rebuilt_events)

            persisted_ids = set(persisted_index)

            rebuilt_ids = set(rebuilt_index)

            for event_id in sorted(persisted_ids - rebuilt_ids):
                event = persisted_index[event_id]

                missing_after_rebuild.append(
                    {
                        "case_id": (case_dir.name),
                        "event_id": event_id,
                        "event_type": (event.get("event_type")),
                        "subject": (event.get("subject")),
                    }
                )

            for event_id in sorted(rebuilt_ids - persisted_ids):
                event = rebuilt_index[event_id]

                unexpected_after_rebuild.append(
                    {
                        "case_id": (case_dir.name),
                        "event_id": event_id,
                        "event_type": (event.get("event_type")),
                        "subject": (event.get("subject")),
                    }
                )

            common_ids = persisted_ids & rebuilt_ids

            matched_events += len(common_ids)

            for event_id in sorted(common_ids):
                persisted_event = persisted_index[event_id]

                rebuilt_event = rebuilt_index[event_id]

                event_type = str(
                    persisted_event.get(
                        "event_type",
                        "unknown",
                    )
                )

                event_type_counts[event_type] += 1

                if persisted_event.get("normalized_time") is None:
                    unknown_time_events += 1
                else:
                    timed_events += 1

                issues = compare_event(
                    case_id=case_dir.name,
                    persisted=persisted_event,
                    rebuilt=rebuilt_event,
                )

                comparison_issues.extend(issues)

                for issue in issues:
                    issue_type = str(issue["issue_type"])

                    temporal_issue_counts[issue_type] += 1

    wrong_normalized_time = temporal_issue_counts["wrong_normalized_time"]

    wrong_time_end = temporal_issue_counts["wrong_time_end"]

    wrong_time_precision = temporal_issue_counts["wrong_time_precision"]

    wrong_time_source = temporal_issue_counts["wrong_time_source"]

    provenance_mismatches = temporal_issue_counts["provenance_mismatch"]

    temporal_mismatch_count = sum(
        (
            wrong_normalized_time,
            wrong_time_end,
            wrong_time_precision,
            wrong_time_source,
        )
    )

    event_identity_issue_count = len(missing_after_rebuild) + len(unexpected_after_rebuild)

    total_issue_count = temporal_mismatch_count + provenance_mismatches + event_identity_issue_count

    reproducibility_rate = (
        (matched_events / persisted_event_count) if persisted_event_count else 1.0
    )

    temporal_field_comparisons = matched_events * len(TEMPORAL_FIELDS)

    correct_temporal_comparisons = temporal_field_comparisons - temporal_mismatch_count

    temporal_accuracy = (
        (correct_temporal_comparisons / temporal_field_comparisons)
        if temporal_field_comparisons
        else 1.0
    )

    status = "PASS" if total_issue_count == 0 else "FAIL"

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8D.2",
        "status": status,
        "evaluation_method": (
            "Freshly reconstruct each canonical "
            "timeline in an isolated temporary "
            "case copy using the production "
            "build_canonical_timeline function, "
            "then compare the persisted and "
            "freshly reconstructed timeline "
            "events. This evaluates the actual "
            "production timestamp precedence "
            "semantics rather than duplicating "
            "them in evaluation code."
        ),
        "reports_scanned": (reports_scanned),
        "persisted_events": (persisted_event_count),
        "rebuilt_events": (rebuilt_event_count),
        "matched_events": (matched_events),
        "timeline_event_reproducibility": {
            "missing_after_rebuild": len(missing_after_rebuild),
            "unexpected_after_rebuild": len(unexpected_after_rebuild),
            "matched_event_rate": (reproducibility_rate),
            "matched_event_percentage": (reproducibility_rate * 100.0),
        },
        "timestamp_population": {
            "timed_events": (timed_events),
            "unknown_time_events": (unknown_time_events),
        },
        "temporal_field_validation": {
            "matched_events": (matched_events),
            "fields_compared_per_event": (len(TEMPORAL_FIELDS)),
            "field_comparisons": (temporal_field_comparisons),
            "correct_field_comparisons": (correct_temporal_comparisons),
            "temporal_accuracy": (temporal_accuracy),
            "temporal_accuracy_percentage": (temporal_accuracy * 100.0),
            "wrong_normalized_time": (wrong_normalized_time),
            "wrong_time_end": (wrong_time_end),
            "wrong_time_precision": (wrong_time_precision),
            "wrong_time_source": (wrong_time_source),
        },
        "provenance_comparison": {
            "mismatches": (provenance_mismatches),
        },
        "event_type_counts": dict(sorted(event_type_counts.items())),
        "issue_counts": dict(sorted(temporal_issue_counts.items())),
        "total_issue_count": (total_issue_count),
        "issues": {
            "missing_after_rebuild": (missing_after_rebuild),
            "unexpected_after_rebuild": (unexpected_after_rebuild),
            "comparison_issues": (comparison_issues),
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
    print("STEP 8D.2 TIMESTAMP NORMALIZATION CORRECTNESS")
    print("=" * 72)

    print(f"Status:                         {status}")

    print(f"Reports scanned:                {reports_scanned}")

    print(f"Persisted timeline events:      {persisted_event_count}")

    print(f"Freshly rebuilt events:         {rebuilt_event_count}")

    print(f"Matched event IDs:              {matched_events}")

    print()
    print("Timeline reproducibility")
    print("-" * 72)

    print(f"Missing after rebuild:          {len(missing_after_rebuild)}")

    print(f"Unexpected after rebuild:       {len(unexpected_after_rebuild)}")

    print(f"Matched event rate:             {reproducibility_rate * 100.0:.1f}%")

    print()
    print("Timestamp population")
    print("-" * 72)

    print(f"Timed events:                   {timed_events}")

    print(f"Unknown-time events:            {unknown_time_events}")

    print()
    print("Temporal field comparison")
    print("-" * 72)

    print(f"Wrong normalized_time:          {wrong_normalized_time}")

    print(f"Wrong time_end:                 {wrong_time_end}")

    print(f"Wrong time_precision:           {wrong_time_precision}")

    print(f"Wrong time_source:              {wrong_time_source}")

    print(f"Temporal field accuracy:        {temporal_accuracy * 100.0:.1f}%")

    print()
    print("Provenance comparison")
    print("-" * 72)

    print(f"Provenance mismatches:          {provenance_mismatches}")

    print()
    print(f"Total issues:                   {total_issue_count}")

    print()
    print("Saved evaluation to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

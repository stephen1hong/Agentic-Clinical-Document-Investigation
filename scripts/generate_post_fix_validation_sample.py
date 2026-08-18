from __future__ import annotations

import json
import random
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "post_fix_validation_sample"

OUTPUT_PATH = OUTPUT_DIR / "finding_sample_manifest.json"


SAMPLE_SIZE = 80
MISSING_EVENT_TIME_SAMPLE_SIZE = 79

RANDOM_SEED = 2026081606

EXPECTED_TOTAL_POPULATION = 317
EXPECTED_DOSE_CONFLICT_COUNT = 1

MISSING_EVENT_TIME = "missing_event_time"
DOSE_CONFLICT = "dose_conflict"


def load_json(path: Path) -> Any:
    """Load JSON from disk."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def current_findings_from_report(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all current machine findings from one final report."""

    findings: list[dict[str, Any]] = []

    for field in (
        "high_priority_findings",
        "other_findings",
    ):
        value = report.get(field, [])

        if isinstance(value, list):
            findings.extend(finding for finding in value if isinstance(finding, dict))

    return findings


def finding_subtype(
    finding: dict[str, Any],
) -> str:
    """Return finding subtype."""

    value = finding.get("subtype")

    if isinstance(value, str):
        return value

    return ""


def finding_id(
    finding: dict[str, Any],
) -> str:
    """Return finding identifier."""

    value = finding.get("finding_id")

    if not isinstance(value, str) or not value:
        raise ValueError("Finding is missing a valid finding_id.")

    return value


def collect_population() -> list[dict[str, Any]]:
    """Collect authoritative findings from current final reports."""

    population: list[dict[str, Any]] = []

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        report_path = case_dir / "final_investigation_report.json"

        if not report_path.exists():
            continue

        report = load_json(report_path)

        if not isinstance(report, dict):
            raise ValueError(f"Expected JSON object: {report_path}")

        findings = current_findings_from_report(report)

        for finding in findings:
            record = {
                "case_id": case_dir.name,
                "source_report": str(report_path.relative_to(PROJECT_ROOT)),
                "finding_id": finding_id(finding),
                "finding_type": finding.get("finding_type"),
                "subtype": finding_subtype(finding),
                "severity": finding.get("severity"),
                "finding": finding,
            }

            population.append(record)

    return population


def validate_population(
    population: list[dict[str, Any]],
) -> None:
    """Ensure the sample is being drawn from the expected post-fix population."""

    if len(population) != EXPECTED_TOTAL_POPULATION:
        raise ValueError(
            "Unexpected current finding population. "
            f"Expected {EXPECTED_TOTAL_POPULATION}, "
            f"found {len(population)}."
        )

    finding_ids = [record["finding_id"] for record in population]

    duplicate_count = len(finding_ids) - len(set(finding_ids))

    if duplicate_count:
        raise ValueError(f"Current population contains duplicate finding IDs: {duplicate_count}")

    subtype_counts = Counter(record["subtype"] for record in population)

    dose_conflict_count = subtype_counts[DOSE_CONFLICT]

    if dose_conflict_count != EXPECTED_DOSE_CONFLICT_COUNT:
        raise ValueError(
            "Unexpected dose_conflict population. "
            f"Expected "
            f"{EXPECTED_DOSE_CONFLICT_COUNT}, "
            f"found {dose_conflict_count}."
        )

    missing_event_time_count = subtype_counts[MISSING_EVENT_TIME]

    if missing_event_time_count < MISSING_EVENT_TIME_SAMPLE_SIZE:
        raise ValueError("Not enough missing_event_time findings for requested sample.")

    unexpected_subtypes = {
        subtype: count
        for subtype, count in subtype_counts.items()
        if subtype
        not in {
            MISSING_EVENT_TIME,
            DOSE_CONFLICT,
        }
    }

    if unexpected_subtypes:
        raise ValueError(f"Unexpected current finding subtypes: {unexpected_subtypes}")


def build_sample(
    population: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build stratified fresh validation sample."""

    rng = random.Random(RANDOM_SEED)

    missing_event_time_records = [
        record for record in population if record["subtype"] == MISSING_EVENT_TIME
    ]

    dose_conflict_records = [record for record in population if record["subtype"] == DOSE_CONFLICT]

    sampled_missing = rng.sample(
        missing_event_time_records,
        MISSING_EVENT_TIME_SAMPLE_SIZE,
    )

    # Force-include the only remaining medication discrepancy.
    sample = sampled_missing + dose_conflict_records

    # Shuffle final ordering so the forced case is not
    # trivially identifiable by position.
    rng.shuffle(sample)

    if len(sample) != SAMPLE_SIZE:
        raise ValueError(
            f"Generated sample has unexpected size. Expected {SAMPLE_SIZE}, found {len(sample)}."
        )

    return sample


def main() -> int:
    """Generate fresh 8C.6 post-fix validation sample."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Investigation case root not found: {CASE_ROOT}")

    population = collect_population()

    validate_population(population)

    sample = build_sample(population)

    population_subtypes = Counter(record["subtype"] for record in population)

    population_types = Counter(str(record["finding_type"]) for record in population)

    sample_subtypes = Counter(record["subtype"] for record in sample)

    sample_types = Counter(str(record["finding_type"]) for record in sample)

    sample_records: list[dict[str, Any]] = []

    for index, record in enumerate(
        sample,
        start=1,
    ):
        sample_records.append(
            {
                "sample_index": index,
                **record,
            }
        )

    manifest = {
        "schema_version": "1.0",
        "evaluation_step": "8C.6",
        "generated_at": datetime.now(UTC).isoformat(),
        "sampling_method": (
            "Fresh post-fix stratified held-out "
            "validation sample. Randomly sampled "
            "79 missing_event_time findings and "
            "force-included the single remaining "
            "dose_conflict finding."
        ),
        "random_seed": RANDOM_SEED,
        "population": {
            "finding_count": len(population),
            "finding_type_counts": dict(sorted(population_types.items())),
            "subtype_counts": dict(sorted(population_subtypes.items())),
        },
        "sample": {
            "finding_count": len(sample),
            "finding_type_counts": dict(sorted(sample_types.items())),
            "subtype_counts": dict(sorted(sample_subtypes.items())),
        },
        "selection": {
            "missing_event_time": {
                "population_count": (population_subtypes[MISSING_EVENT_TIME]),
                "sample_count": (sample_subtypes[MISSING_EVENT_TIME]),
                "selection_method": ("seeded_random_sample"),
            },
            "dose_conflict": {
                "population_count": (population_subtypes[DOSE_CONFLICT]),
                "sample_count": (sample_subtypes[DOSE_CONFLICT]),
                "selection_method": ("forced_inclusion"),
            },
        },
        "records": sample_records,
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("STEP 8C.6 FRESH POST-FIX VALIDATION SAMPLE")
    print("=" * 72)

    print(f"Population findings:          {len(population)}")

    print(f"Sample findings:              {len(sample)}")

    print(f"Random seed:                  {RANDOM_SEED}")

    print()
    print("Population subtype distribution")
    print("-" * 72)

    for subtype, count in sorted(population_subtypes.items()):
        print(f"{subtype:<36}{count:>6}")

    print()
    print("Sample subtype distribution")
    print("-" * 72)

    for subtype, count in sorted(sample_subtypes.items()):
        print(f"{subtype:<36}{count:>6}")

    print()
    print("Saved sample manifest to:")
    print(OUTPUT_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FINAL_REPORT_FILENAME = "final_investigation_report.json"

DEFAULT_SAMPLE_SIZE = 80
DEFAULT_SEED = 20260815


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Generate a reproducible representative sample of current investigation findings."
        )
    )

    parser.add_argument(
        "--sample-size",
        type=int,
        default=DEFAULT_SAMPLE_SIZE,
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
    )

    return parser.parse_args()


def load_json(
    path: Path,
) -> dict[str, Any]:
    """Load a JSON object."""

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")

    return payload


def get_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all findings from a final investigation report."""

    findings: list[dict[str, Any]] = []

    for key in (
        "high_priority_findings",
        "other_findings",
    ):
        value = report.get(
            key,
            [],
        )

        if isinstance(value, list):
            findings.extend(finding for finding in value if isinstance(finding, dict))

    return findings


def collect_population(
    case_root: Path,
) -> list[dict[str, Any]]:
    """Collect current machine findings from all persisted reports."""

    population: list[dict[str, Any]] = []

    for case_dir in sorted(path for path in case_root.iterdir() if path.is_dir()):
        report_path = case_dir / FINAL_REPORT_FILENAME

        if not report_path.exists():
            continue

        report = load_json(report_path)

        for finding in get_findings(report):
            finding_id = str(
                finding.get(
                    "finding_id",
                    "",
                )
            )

            if not finding_id:
                continue

            population.append(
                {
                    "case_id": case_dir.name,
                    "finding_id": finding_id,
                    "finding_type": str(
                        finding.get(
                            "finding_type",
                            "unknown",
                        )
                    ),
                    "subtype": str(
                        finding.get(
                            "subtype",
                            "unknown",
                        )
                    ),
                    "severity": str(
                        finding.get(
                            "severity",
                            "unknown",
                        )
                    ),
                    "requires_human_review": bool(
                        finding.get(
                            "requires_human_review",
                            False,
                        )
                    ),
                    "evidence_ids": list(
                        finding.get(
                            "evidence_ids",
                            [],
                        )
                        or []
                    ),
                    "claim_ids": list(
                        finding.get(
                            "claim_ids",
                            [],
                        )
                        or []
                    ),
                }
            )

    return population


def allocate_proportionally(
    *,
    stratum_sizes: dict[str, int],
    sample_size: int,
) -> dict[str, int]:
    """Allocate sample slots proportionally by finding type."""

    population_size = sum(stratum_sizes.values())

    if population_size == 0:
        return {}

    if sample_size >= population_size:
        return dict(stratum_sizes)

    raw_allocations = {
        stratum: (sample_size * size / population_size) for stratum, size in stratum_sizes.items()
    }

    allocations = {
        stratum: min(
            size,
            int(raw_allocations[stratum]),
        )
        for stratum, size in stratum_sizes.items()
    }

    remaining = sample_size - sum(allocations.values())

    ranked = sorted(
        stratum_sizes,
        key=lambda stratum: (
            raw_allocations[stratum] - int(raw_allocations[stratum]),
            stratum_sizes[stratum],
            stratum,
        ),
        reverse=True,
    )

    while remaining > 0:
        changed = False

        for stratum in ranked:
            if remaining == 0:
                break

            if allocations[stratum] >= stratum_sizes[stratum]:
                continue

            allocations[stratum] += 1

            remaining -= 1
            changed = True

        if not changed:
            break

    return allocations


def distribution_by(
    records: list[dict[str, Any]],
    field_name: str,
) -> dict[str, int]:
    """Count records by a field."""

    counts = Counter(
        str(
            record.get(
                field_name,
                "unknown",
            )
        )
        for record in records
    )

    return dict(sorted(counts.items()))


def main() -> int:
    """Generate the representative finding sample."""

    args = parse_args()

    project_root = Path(__file__).resolve().parents[1]

    case_root = project_root / "data" / "investigation_cases"

    output_dir = project_root / "data" / "evaluation" / "representative_sample"

    output_path = output_dir / "finding_sample_manifest.json"

    population = collect_population(case_root)

    population_size = len(population)

    if population_size == 0:
        print("No machine findings found.")
        return 1

    sample_size = min(
        args.sample_size,
        population_size,
    )

    strata: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for record in population:
        strata[record["finding_type"]].append(record)

    stratum_sizes = {stratum: len(records) for stratum, records in strata.items()}

    allocations = allocate_proportionally(
        stratum_sizes=stratum_sizes,
        sample_size=sample_size,
    )

    rng = random.Random(args.seed)

    selected: list[dict[str, Any]] = []

    for stratum in sorted(strata):
        records = sorted(
            strata[stratum],
            key=lambda record: (
                record["case_id"],
                record["finding_id"],
            ),
        )

        allocation = allocations.get(
            stratum,
            0,
        )

        if allocation == 0:
            continue

        chosen = rng.sample(
            records,
            allocation,
        )

        population_count = len(records)

        sampling_probability = allocation / population_count

        sample_weight = population_count / allocation

        for record in chosen:
            selected.append(
                {
                    **record,
                    "stratum": stratum,
                    "stratum_population_size": (population_count),
                    "stratum_sample_size": (allocation),
                    "sampling_probability": (sampling_probability),
                    "sample_weight": (sample_weight),
                }
            )

    selected = sorted(
        selected,
        key=lambda record: (
            record["case_id"],
            record["finding_id"],
        ),
    )

    for index, record in enumerate(
        selected,
        start=1,
    ):
        record["sample_index"] = index

    manifest = {
        "schema_version": "1.0",
        "created_at": (datetime.now(UTC).isoformat()),
        "seed": args.seed,
        "population_size": (population_size),
        "requested_sample_size": (args.sample_size),
        "actual_sample_size": len(selected),
        "stratification_field": ("finding_type"),
        "population_distribution": {
            "finding_type": distribution_by(
                population,
                "finding_type",
            ),
            "subtype": distribution_by(
                population,
                "subtype",
            ),
            "severity": distribution_by(
                population,
                "severity",
            ),
        },
        "sample_distribution": {
            "finding_type": distribution_by(
                selected,
                "finding_type",
            ),
            "subtype": distribution_by(
                selected,
                "subtype",
            ),
            "severity": distribution_by(
                selected,
                "severity",
            ),
        },
        "stratum_allocations": {
            stratum: {
                "population": (stratum_sizes[stratum]),
                "sample": (allocations[stratum]),
            }
            for stratum in sorted(stratum_sizes)
        },
        "findings": selected,
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
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
    print("REPRESENTATIVE FINDING SAMPLE")
    print("=" * 72)

    print(f"Population size: {population_size}")

    print(f"Sample size: {len(selected)}")

    print(f"Random seed: {args.seed}")

    print()
    print("Allocation by finding type:")

    for stratum in sorted(stratum_sizes):
        print(f"  {stratum}: {allocations[stratum]}/{stratum_sizes[stratum]}")

    print()
    print("Sample subtype distribution:")

    for subtype, count in distribution_by(
        selected,
        "subtype",
    ).items():
        print(f"  {subtype}: {count}")

    print()
    print(f"Manifest: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

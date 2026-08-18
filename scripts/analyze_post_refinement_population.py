from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_PATH = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "representative_sample"
    / "post_refinement_population_analysis.json"
)

FINAL_REPORT_FILENAME = "final_investigation_report.json"


#
# Frozen pre-refinement population counts from the
# Step 8B.7.6 / workflow-audit baseline.
#
PRE_REFINEMENT_TYPE_COUNTS = {
    "temporal_uncertainty": 360,
    "medication_discrepancy": 129,
}

PRE_REFINEMENT_TOTAL = 489


def load_json(path: Path) -> dict[str, Any]:
    """Load one JSON object."""

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
    """Return current machine findings from a final report."""

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
            findings.extend(item for item in value if isinstance(item, dict))

    return findings


def percent(
    numerator: int,
    denominator: int,
) -> float:
    """Return a percentage."""

    if denominator == 0:
        return 0.0

    return numerator / denominator * 100.0


def main() -> int:
    """Analyze the post-refinement finding population."""

    if not CASE_ROOT.exists():
        print(f"Investigation case directory not found: {CASE_ROOT}")
        return 1

    type_counts: Counter[str] = Counter()
    subtype_counts: Counter[str] = Counter()

    subtype_by_type: dict[
        str,
        Counter[str],
    ] = defaultdict(Counter)

    severity_counts: Counter[str] = Counter()

    findings_by_case: Counter[str] = Counter()

    total_findings = 0
    reports_scanned = 0

    finding_ids: set[str] = set()

    duplicate_finding_ids: set[str] = set()

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        report_path = case_dir / FINAL_REPORT_FILENAME

        if not report_path.exists():
            continue

        report = load_json(report_path)

        reports_scanned += 1

        findings = get_findings(report)

        findings_by_case[case_dir.name] = len(findings)

        total_findings += len(findings)

        for finding in findings:
            finding_type = str(
                finding.get(
                    "finding_type",
                    "unknown",
                )
            )

            subtype = str(
                finding.get(
                    "subtype",
                    "unknown",
                )
            )

            severity = str(
                finding.get(
                    "severity",
                    "unknown",
                )
            )

            type_counts[finding_type] += 1

            subtype_counts[subtype] += 1

            subtype_by_type[finding_type][subtype] += 1

            severity_counts[severity] += 1

            finding_id = finding.get("finding_id")

            if isinstance(
                finding_id,
                str,
            ):
                if finding_id in finding_ids:
                    duplicate_finding_ids.add(finding_id)

                finding_ids.add(finding_id)

    if total_findings == 0:
        print("No current findings were found.")
        return 1

    #
    # Compare current counts with frozen
    # pre-refinement type counts.
    #
    type_comparison: dict[
        str,
        dict[str, Any],
    ] = {}

    all_types = set(PRE_REFINEMENT_TYPE_COUNTS) | set(type_counts)

    for finding_type in sorted(all_types):
        before = PRE_REFINEMENT_TYPE_COUNTS.get(
            finding_type,
            0,
        )

        after = type_counts.get(
            finding_type,
            0,
        )

        removed = before - after

        type_comparison[finding_type] = {
            "pre_refinement": before,
            "post_refinement": after,
            "net_change": after - before,
            "removed": removed,
            "reduction_percent": (
                percent(
                    removed,
                    before,
                )
                if before > 0
                else None
            ),
        }

    net_reduction = PRE_REFINEMENT_TOTAL - total_findings

    print("Post-Refinement Population Analysis")
    print("=" * 72)

    print(f"\nReports scanned:              {reports_scanned}")

    print(f"Pre-refinement findings:      {PRE_REFINEMENT_TOTAL}")

    print(f"Post-refinement findings:     {total_findings}")

    print(f"Net reduction:                {net_reduction}")

    print(f"Population reduction:         {percent(net_reduction, PRE_REFINEMENT_TOTAL):.1f}%")

    print(f"Unique current finding IDs:   {len(finding_ids)}")

    print(f"Duplicate finding IDs:        {len(duplicate_finding_ids)}")

    print("\nFinding-type comparison")
    print("-" * 72)

    for (
        finding_type,
        comparison,
    ) in type_comparison.items():
        reduction = comparison["reduction_percent"]

        reduction_text = f"{reduction:.1f}%" if reduction is not None else "N/A"

        print(
            f"{finding_type:<30}"
            f" before={comparison['pre_refinement']:<4}"
            f" after={comparison['post_refinement']:<4}"
            f" removed={comparison['removed']:<4}"
            f" reduction={reduction_text}"
        )

    print("\nCurrent subtype distribution")
    print("-" * 72)

    for subtype, count in subtype_counts.most_common():
        print(f"{subtype:<40}{count:<5}{percent(count, total_findings):6.1f}%")

    print("\nCurrent subtype distribution by finding type")
    print("-" * 72)

    for finding_type in sorted(subtype_by_type):
        print(f"\n{finding_type}")

        type_total = type_counts[finding_type]

        for subtype, count in subtype_by_type[finding_type].most_common():
            print(f"  {subtype:<38}{count:<5}{percent(count, type_total):6.1f}%")

    print("\nSeverity distribution")
    print("-" * 72)

    for severity, count in severity_counts.most_common():
        print(f"{severity:<20}{count:<5}{percent(count, total_findings):6.1f}%")

    print("\nFindings per case")
    print("-" * 72)

    case_counts = list(findings_by_case.values())

    if case_counts:
        print(f"Minimum:                     {min(case_counts)}")
        print(f"Maximum:                     {max(case_counts)}")
        print(f"Mean:                        {sum(case_counts) / len(case_counts):.1f}")

    output = {
        "schema_version": "1.0",
        "reports_scanned": reports_scanned,
        "pre_refinement": {
            "population_size": (PRE_REFINEMENT_TOTAL),
            "finding_type_counts": (PRE_REFINEMENT_TYPE_COUNTS),
        },
        "post_refinement": {
            "population_size": (total_findings),
            "finding_type_counts": dict(sorted(type_counts.items())),
            "subtype_counts": dict(subtype_counts.most_common()),
            "subtypes_by_finding_type": {
                finding_type: dict(counts.most_common())
                for (
                    finding_type,
                    counts,
                ) in sorted(subtype_by_type.items())
            },
            "severity_counts": dict(severity_counts.most_common()),
            "unique_finding_ids": len(finding_ids),
            "duplicate_finding_ids": sorted(duplicate_finding_ids),
        },
        "comparison": {
            "net_reduction": (net_reduction),
            "population_reduction_percent": (
                percent(
                    net_reduction,
                    PRE_REFINEMENT_TOTAL,
                )
            ),
            "by_finding_type": (type_comparison),
        },
        "findings_per_case": {
            "minimum": (min(case_counts) if case_counts else None),
            "maximum": (max(case_counts) if case_counts else None),
            "mean": (sum(case_counts) / len(case_counts) if case_counts else None),
            "counts": dict(sorted(findings_by_case.items())),
        },
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("\nSaved analysis to:")

    print(OUTPUT_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

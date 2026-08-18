from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

FINAL_REPORT_FILENAME = "final_investigation_report.json"


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""

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
            findings.extend(item for item in value if isinstance(item, dict))

    return findings


def main() -> int:
    """Count unsupported-claim findings across all investigation cases."""

    project_root = Path(__file__).resolve().parents[1]

    case_root = project_root / "data" / "investigation_cases"

    if not case_root.exists():
        print(f"Investigation case directory not found: {case_root}")
        return 1

    subtype_counts: Counter[str] = Counter()

    total_findings = 0
    unsupported_findings = 0
    reports_scanned = 0

    affected_cases: Counter[str] = Counter()

    for case_dir in sorted(path for path in case_root.iterdir() if path.is_dir()):
        report_path = case_dir / FINAL_REPORT_FILENAME

        if not report_path.exists():
            continue

        report = load_json(report_path)

        reports_scanned += 1

        findings = get_findings(report)

        total_findings += len(findings)

        for finding in findings:
            if finding.get("finding_type") != "unsupported_claim":
                continue

            unsupported_findings += 1

            subtype = str(
                finding.get(
                    "subtype",
                    "unknown",
                )
            )

            subtype_counts[subtype] += 1

            if subtype == "insufficient_evidence_support":
                affected_cases[case_dir.name] += 1

    print()
    print("=" * 72)
    print("UNSUPPORTED-CLAIM FINDING COUNTS")
    print("=" * 72)

    print(f"Reports scanned: {reports_scanned}")

    print(f"Total machine findings: {total_findings}")

    print(f"Unsupported-claim findings: {unsupported_findings}")

    print()
    print("By subtype:")

    if subtype_counts:
        for subtype, count in sorted(subtype_counts.items()):
            print(f"  {subtype}: {count}")
    else:
        print("  none")

    print()
    print("Cases with insufficient_evidence_support:")

    if affected_cases:
        for case_id, count in sorted(affected_cases.items()):
            print(f"  {case_id}: {count}")
    else:
        print("  none")

    print()
    print(f"Total insufficient_evidence_support: {subtype_counts['insufficient_evidence_support']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

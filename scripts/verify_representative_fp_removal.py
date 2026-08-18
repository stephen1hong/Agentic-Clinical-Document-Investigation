from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ANALYSIS_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "representative_sample" / "false_positive_analysis.json"
)

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

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


def collect_known_fp_ids() -> set[str]:
    """Load the known representative-sample FP finding IDs."""

    analysis = load_json(ANALYSIS_PATH)

    false_positives = analysis.get(
        "false_positives",
        [],
    )

    if not isinstance(false_positives, list):
        raise ValueError(
            "false_positive_analysis.json does not contain a valid 'false_positives' list."
        )

    return {
        str(item["finding_id"])
        for item in false_positives
        if (isinstance(item, dict) and item.get("finding_id"))
    }


def collect_current_finding_ids() -> tuple[
    set[str],
    int,
    int,
]:
    """Collect IDs from current final investigation reports."""

    finding_ids: set[str] = set()
    total_findings = 0
    reports_scanned = 0

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        report_path = case_dir / FINAL_REPORT_FILENAME

        if not report_path.exists():
            continue

        report = load_json(report_path)

        reports_scanned += 1

        findings = get_findings(report)

        total_findings += len(findings)

        for finding in findings:
            finding_id = finding.get("finding_id")

            if isinstance(
                finding_id,
                str,
            ):
                finding_ids.add(finding_id)

    return (
        finding_ids,
        total_findings,
        reports_scanned,
    )


def main() -> int:
    """Verify removal of known representative false positives."""

    if not CASE_ROOT.exists():
        print(f"Investigation case directory not found: {CASE_ROOT}")
        return 1

    target_ids = collect_known_fp_ids()

    (
        current_ids,
        total_findings,
        reports_scanned,
    ) = collect_current_finding_ids()

    remaining = target_ids & current_ids

    removed = target_ids - current_ids

    print("Representative FP Verification")
    print("=" * 40)

    print(f"Reports scanned:      {reports_scanned}")

    print(f"Current findings:     {total_findings}")

    print(f"Known FP findings:    {len(target_ids)}")

    print(f"Removed:              {len(removed)}")

    print(f"Still present:        {len(remaining)}")

    if remaining:
        print("\nStill-present finding IDs:")

        for finding_id in sorted(remaining):
            print(f"- {finding_id}")

    if removed:
        print("\nRemoved finding IDs:")

        for finding_id in sorted(removed):
            print(f"- {finding_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

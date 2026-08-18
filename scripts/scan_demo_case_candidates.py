from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from clinical_investigation.config import settings

FINAL_REPORT_FILENAME = "final_investigation_report.json"


def load_json(
    path: Path,
) -> dict[str, Any]:
    """Load one JSON object."""

    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(f"Expected JSON object: {path}")

    return payload


def extract_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract all findings from the persisted final report."""

    findings: list[dict[str, Any]] = []

    for field_name in (
        "high_priority_findings",
        "other_findings",
    ):
        value = report.get(
            field_name,
            [],
        )

        if not isinstance(
            value,
            list,
        ):
            continue

        findings.extend(
            finding
            for finding in value
            if isinstance(
                finding,
                dict,
            )
        )

    return findings


def finding_type(
    finding: dict[str, Any],
) -> str:
    """Resolve a finding type without assuming one exact field name."""

    for key in (
        "finding_type",
        "type",
        "category",
    ):
        value = finding.get(key)

        if (
            isinstance(
                value,
                str,
            )
            and value
        ):
            return value

    return "unknown"


def count_evidence_references(
    findings: list[dict[str, Any]],
) -> int:
    """Count explicit evidence references attached to findings."""

    total = 0

    for finding in findings:
        for key in (
            "evidence_ids",
            "supporting_evidence_ids",
            "evidence_references",
        ):
            value = finding.get(key)

            if isinstance(
                value,
                list,
            ):
                total += len(value)
                break

    return total


def main() -> int:
    """Print a compact candidate scan over persisted final reports."""

    case_root = settings.investigation_cases_dir

    rows: list[dict[str, Any]] = []

    for case_dir in sorted(path for path in case_root.iterdir() if path.is_dir()):
        report_path = case_dir / FINAL_REPORT_FILENAME

        if not report_path.is_file():
            continue

        report = load_json(report_path)

        findings = extract_findings(report)

        type_counts = Counter(finding_type(finding) for finding in findings)

        rows.append(
            {
                "case_id": case_dir.name,
                "finding_count": report.get(
                    "finding_count",
                    len(findings),
                ),
                "review_status": report.get(
                    "review_status",
                    "",
                ),
                "timeline": (
                    type_counts["timeline_conflict"] + type_counts["temporal_uncertainty"]
                ),
                "medication": type_counts["medication_discrepancy"],
                "contradiction": type_counts["contradiction"],
                "missing_follow_up": type_counts["missing_follow_up"],
                "unsupported_claim": type_counts["unsupported_claim"],
                "evidence_refs": (count_evidence_references(findings)),
            }
        )

    print()
    print("DEMO CASE CANDIDATE SCAN")

    print("=" * 132)

    header = (
        f"{'CASE ID':<78}"
        f"{'FIND':>6}"
        f"{'REVIEW':>14}"
        f"{'TIME':>7}"
        f"{'MED':>6}"
        f"{'CONTR':>7}"
        f"{'FOLLOW':>8}"
        f"{'UNSUP':>7}"
        f"{'EVID':>7}"
    )

    print(header)

    print("-" * 132)

    for row in rows:
        print(
            f"{row['case_id']:<78}"
            f"{str(row['finding_count']):>6}"
            f"{str(row['review_status']):>14}"
            f"{row['timeline']:>7}"
            f"{row['medication']:>6}"
            f"{row['contradiction']:>7}"
            f"{row['missing_follow_up']:>8}"
            f"{row['unsupported_claim']:>7}"
            f"{row['evidence_refs']:>7}"
        )

    print()
    print(f"Cases scanned: {len(rows)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

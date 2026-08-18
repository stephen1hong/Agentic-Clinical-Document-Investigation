from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from clinical_investigation.evaluation.annotation_context import (
    index_records,
    load_clinical_claims,
    load_evidence_items,
)

FINAL_REPORT_FILENAME = "final_investigation_report.json"


def project_root() -> Path:
    """Return repository root."""

    return Path(__file__).resolve().parents[1]


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
    """Return machine findings from a final report."""

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


def normalize_ids(
    value: Any,
) -> list[str]:
    """Normalize a provenance-ID field."""

    if not isinstance(value, list):
        return []

    return [str(item) for item in value if item]


def main() -> int:
    """Evaluate evidence-grounding provenance integrity."""

    root = project_root()

    case_root = root / "data" / "investigation_cases"

    output_dir = root / "data" / "evaluation" / "evidence_grounding"

    output_path = output_dir / "evidence_grounding_integrity.json"

    if not case_root.exists():
        print(f"Investigation case directory not found: {case_root}")
        return 1

    reports_scanned = 0
    total_findings = 0

    findings_with_any_reference = 0
    findings_without_any_reference = 0

    findings_with_evidence = 0
    findings_with_claims = 0

    findings_with_unresolved_evidence = 0
    findings_with_unresolved_claims = 0

    unresolved_evidence_ids = 0
    unresolved_claim_ids = 0

    type_counts: Counter[str] = Counter()
    subtype_counts: Counter[str] = Counter()

    missing_reference_by_type: Counter[str] = Counter()
    missing_reference_by_subtype: Counter[str] = Counter()

    unresolved_evidence_by_type: Counter[str] = Counter()
    unresolved_claim_by_type: Counter[str] = Counter()

    issues: list[dict[str, Any]] = []

    for case_dir in sorted(path for path in case_root.iterdir() if path.is_dir()):
        report_path = case_dir / FINAL_REPORT_FILENAME

        if not report_path.exists():
            continue

        report = load_json(report_path)

        evidence_items = load_evidence_items(case_dir)

        clinical_claims = load_clinical_claims(case_dir)

        evidence_by_id = index_records(
            evidence_items,
            id_field="evidence_id",
        )

        claims_by_id = index_records(
            clinical_claims,
            id_field="claim_id",
        )

        reports_scanned += 1

        for finding in get_findings(report):
            total_findings += 1

            finding_id = str(
                finding.get(
                    "finding_id",
                    "",
                )
            )

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

            type_counts[finding_type] += 1

            subtype_counts[subtype] += 1

            evidence_ids = normalize_ids(finding.get("evidence_ids", []))

            claim_ids = normalize_ids(finding.get("claim_ids", []))

            event_ids = normalize_ids(finding.get("event_ids", []))

            has_any_reference = bool(evidence_ids or claim_ids or event_ids)

            if has_any_reference:
                findings_with_any_reference += 1
            else:
                findings_without_any_reference += 1

                missing_reference_by_type[finding_type] += 1

                missing_reference_by_subtype[subtype] += 1

                issues.append(
                    {
                        "case_id": case_dir.name,
                        "finding_id": finding_id,
                        "finding_type": (finding_type),
                        "subtype": subtype,
                        "issue_type": ("no_provenance_reference"),
                    }
                )

            if evidence_ids:
                findings_with_evidence += 1

            if claim_ids:
                findings_with_claims += 1

            unresolved_evidence = [
                evidence_id for evidence_id in evidence_ids if evidence_id not in evidence_by_id
            ]

            unresolved_claims = [claim_id for claim_id in claim_ids if claim_id not in claims_by_id]

            if unresolved_evidence:
                findings_with_unresolved_evidence += 1

                unresolved_evidence_ids += len(unresolved_evidence)

                unresolved_evidence_by_type[finding_type] += 1

                issues.append(
                    {
                        "case_id": case_dir.name,
                        "finding_id": finding_id,
                        "finding_type": (finding_type),
                        "subtype": subtype,
                        "issue_type": ("unresolved_evidence_ids"),
                        "ids": (unresolved_evidence),
                    }
                )

            if unresolved_claims:
                findings_with_unresolved_claims += 1

                unresolved_claim_ids += len(unresolved_claims)

                unresolved_claim_by_type[finding_type] += 1

                issues.append(
                    {
                        "case_id": case_dir.name,
                        "finding_id": finding_id,
                        "finding_type": (finding_type),
                        "subtype": subtype,
                        "issue_type": ("unresolved_claim_ids"),
                        "ids": (unresolved_claims),
                    }
                )

    if total_findings == 0:
        print("No findings found.")
        return 1

    provenance_coverage = findings_with_any_reference / total_findings

    evidence_resolution_rate = 1.0 - (findings_with_unresolved_evidence / total_findings)

    claim_resolution_rate = 1.0 - (findings_with_unresolved_claims / total_findings)

    output = {
        "schema_version": "1.0",
        "reports_scanned": reports_scanned,
        "total_findings": (total_findings),
        "provenance": {
            "findings_with_any_reference": (findings_with_any_reference),
            "findings_without_any_reference": (findings_without_any_reference),
            "coverage_rate": (provenance_coverage),
        },
        "evidence": {
            "findings_with_evidence_ids": (findings_with_evidence),
            "findings_with_unresolved_evidence": (findings_with_unresolved_evidence),
            "unresolved_evidence_id_count": (unresolved_evidence_ids),
            "finding_resolution_rate": (evidence_resolution_rate),
        },
        "claims": {
            "findings_with_claim_ids": (findings_with_claims),
            "findings_with_unresolved_claims": (findings_with_unresolved_claims),
            "unresolved_claim_id_count": (unresolved_claim_ids),
            "finding_resolution_rate": (claim_resolution_rate),
        },
        "distribution": {
            "finding_type": dict(sorted(type_counts.items())),
            "subtype": dict(sorted(subtype_counts.items())),
        },
        "issues_by_type": {
            "missing_provenance": dict(sorted(missing_reference_by_type.items())),
            "unresolved_evidence": dict(sorted(unresolved_evidence_by_type.items())),
            "unresolved_claims": dict(sorted(unresolved_claim_by_type.items())),
        },
        "issues_by_subtype": {
            "missing_provenance": dict(sorted(missing_reference_by_subtype.items())),
        },
        "issues": issues,
    }

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
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
    print("STEP 8C.1 EVIDENCE-GROUNDING INTEGRITY")
    print("=" * 72)

    print(f"Reports scanned:                  {reports_scanned}")

    print(f"Total findings:                   {total_findings}")

    print()
    print("Provenance coverage")
    print("-" * 72)

    print(f"With provenance reference:        {findings_with_any_reference}")

    print(f"Without provenance reference:     {findings_without_any_reference}")

    print(f"Coverage rate:                    {provenance_coverage:.1%}")

    print()
    print("Evidence resolution")
    print("-" * 72)

    print(f"Findings with evidence IDs:       {findings_with_evidence}")

    print(f"Findings with unresolved evidence: {findings_with_unresolved_evidence}")

    print(f"Unresolved evidence IDs:          {unresolved_evidence_ids}")

    print(f"Finding resolution rate:          {evidence_resolution_rate:.1%}")

    print()
    print("Claim resolution")
    print("-" * 72)

    print(f"Findings with claim IDs:          {findings_with_claims}")

    print(f"Findings with unresolved claims:  {findings_with_unresolved_claims}")

    print(f"Unresolved claim IDs:             {unresolved_claim_ids}")

    print(f"Finding resolution rate:          {claim_resolution_rate:.1%}")

    print()
    print(f"Integrity issues:                 {len(issues)}")

    print()
    print("Saved audit to:")
    print(output_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

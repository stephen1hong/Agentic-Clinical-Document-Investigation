from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from clinical_investigation.evaluation.annotation_context import (
    index_records,
    load_clinical_claims,
    load_evidence_items,
)

FINAL_REPORT_FILENAME = "final_investigation_report.json"

NEGATIVE_ASSERTION_SUBTYPES = {
    "discharge_only_medication",
}


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
    """Normalize an ID list."""

    if not isinstance(value, list):
        return []

    return [str(item) for item in value if item]


def normalize_text(
    value: Any,
) -> str:
    """Normalize text for duplicate-support comparison."""

    if value is None:
        return ""

    return " ".join(str(value).lower().split())


def evidence_signature(
    evidence: dict[str, Any],
) -> tuple[str, str, str, str]:
    """
    Build a conservative semantic signature for evidence.

    Two evidence records are considered duplicate support only when
    document type, source table, source row, and normalized content match.
    """

    document_type = str(
        evidence.get(
            "document_type",
            "",
        )
    )

    source_table = str(
        evidence.get(
            "source_table",
            "",
        )
    )

    source_row = str(
        evidence.get(
            "source_row",
            "",
        )
    )

    content = normalize_text(
        evidence.get(
            "normalized_fact",
            evidence.get(
                "text_span",
                "",
            ),
        )
    )

    return (
        document_type,
        source_table,
        source_row,
        content,
    )


def main() -> int:
    """Analyze residual evidence-grounding risks."""

    root = project_root()

    case_root = root / "data" / "investigation_cases"

    output_dir = root / "data" / "evaluation" / "evidence_grounding"

    output_path = output_dir / "residual_grounding_risk_analysis.json"

    if not case_root.exists():
        print(f"Investigation case directory not found: {case_root}")
        return 1

    reports_scanned = 0
    total_findings = 0

    risk_counts: Counter[str] = Counter()

    risk_by_type: dict[
        str,
        Counter[str],
    ] = defaultdict(Counter)

    risk_by_subtype: dict[
        str,
        Counter[str],
    ] = defaultdict(Counter)

    findings_with_any_risk: set[str] = set()

    findings_with_multiple_risks: set[str] = set()

    risk_records: list[dict[str, Any]] = []

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

            evidence_ids = normalize_ids(
                finding.get(
                    "evidence_ids",
                    [],
                )
            )

            claim_ids = normalize_ids(
                finding.get(
                    "claim_ids",
                    [],
                )
            )

            event_ids = normalize_ids(
                finding.get(
                    "event_ids",
                    [],
                )
            )

            finding_risks: list[dict[str, Any]] = []

            #
            # Risk 1:
            # Negative assertions require exhaustive retrieval,
            # not merely positive evidence.
            #
            if subtype in NEGATIVE_ASSERTION_SUBTYPES:
                finding_risks.append(
                    {
                        "risk_type": ("negative_assertion"),
                        "detail": (
                            "Finding correctness depends partly "
                            "on confirming absence across other "
                            "documents or timeline sources."
                        ),
                    }
                )

            #
            # Risk 2:
            # Finding has provenance, but no direct evidence IDs.
            #
            if not evidence_ids and (claim_ids or event_ids):
                finding_risks.append(
                    {
                        "risk_type": ("no_direct_evidence"),
                        "detail": (
                            "Finding relies on claim/event "
                            "provenance without a direct "
                            "evidence_id reference."
                        ),
                    }
                )

            #
            # Resolve evidence.
            #
            resolved_evidence = [
                evidence_by_id[evidence_id]
                for evidence_id in evidence_ids
                if evidence_id in evidence_by_id
            ]

            #
            # Risk 3a:
            # Evidence belongs to another case.
            #
            mismatched_evidence = []

            for evidence in resolved_evidence:
                evidence_case_id = str(
                    evidence.get(
                        "case_id",
                        "",
                    )
                )

                if evidence_case_id and evidence_case_id != case_dir.name:
                    mismatched_evidence.append(
                        str(
                            evidence.get(
                                "evidence_id",
                                "",
                            )
                        )
                    )

            if mismatched_evidence:
                finding_risks.append(
                    {
                        "risk_type": ("evidence_case_mismatch"),
                        "detail": ("One or more evidence records belong to a different case."),
                        "ids": (mismatched_evidence),
                    }
                )

            #
            # Risk 3b:
            # Clinical claim belongs to another case.
            #
            resolved_claims = [
                claims_by_id[claim_id] for claim_id in claim_ids if claim_id in claims_by_id
            ]

            mismatched_claims = []

            for claim in resolved_claims:
                claim_case_id = str(
                    claim.get(
                        "case_id",
                        "",
                    )
                )

                if claim_case_id and claim_case_id != case_dir.name:
                    mismatched_claims.append(
                        str(
                            claim.get(
                                "claim_id",
                                "",
                            )
                        )
                    )

            if mismatched_claims:
                finding_risks.append(
                    {
                        "risk_type": ("claim_case_mismatch"),
                        "detail": ("One or more clinical claims belong to a different case."),
                        "ids": (mismatched_claims),
                    }
                )

            #
            # Risk 4:
            # Several evidence IDs may actually represent the
            # same underlying source fact.
            #
            signature_to_ids: dict[
                tuple[str, str, str, str],
                list[str],
            ] = defaultdict(list)

            for evidence in resolved_evidence:
                signature = evidence_signature(evidence)

                evidence_id = str(
                    evidence.get(
                        "evidence_id",
                        "",
                    )
                )

                if evidence_id:
                    signature_to_ids[signature].append(evidence_id)

            duplicate_groups = [ids for ids in (signature_to_ids.values()) if len(ids) > 1]

            if duplicate_groups:
                finding_risks.append(
                    {
                        "risk_type": ("duplicate_support"),
                        "detail": (
                            "Multiple evidence IDs represent the same underlying source fact."
                        ),
                        "duplicate_groups": (duplicate_groups),
                    }
                )

            #
            # Risk 5:
            # A referenced clinical claim has an evidence_ids
            # field but it is empty.
            #
            ungrounded_claim_ids = []

            for claim in resolved_claims:
                if "evidence_ids" not in claim:
                    continue

                claim_evidence_ids = normalize_ids(
                    claim.get(
                        "evidence_ids",
                        [],
                    )
                )

                if not claim_evidence_ids:
                    claim_id = str(
                        claim.get(
                            "claim_id",
                            "",
                        )
                    )

                    if claim_id:
                        ungrounded_claim_ids.append(claim_id)

            if ungrounded_claim_ids:
                finding_risks.append(
                    {
                        "risk_type": ("ungrounded_claim_chain"),
                        "detail": (
                            "Referenced clinical claim "
                            "contains an evidence_ids field "
                            "but has no linked evidence."
                        ),
                        "ids": (ungrounded_claim_ids),
                    }
                )

            if not finding_risks:
                continue

            findings_with_any_risk.add(finding_id)

            if len(finding_risks) > 1:
                findings_with_multiple_risks.add(finding_id)

            for risk in finding_risks:
                risk_type = str(risk["risk_type"])

                risk_counts[risk_type] += 1

                risk_by_type[finding_type][risk_type] += 1

                risk_by_subtype[subtype][risk_type] += 1

            risk_records.append(
                {
                    "case_id": (case_dir.name),
                    "finding_id": (finding_id),
                    "finding_type": (finding_type),
                    "subtype": (subtype),
                    "title": (
                        finding.get(
                            "title",
                            "",
                        )
                    ),
                    "summary": (
                        finding.get(
                            "summary",
                            "",
                        )
                    ),
                    "evidence_id_count": len(evidence_ids),
                    "claim_id_count": len(claim_ids),
                    "event_id_count": len(event_ids),
                    "risks": (finding_risks),
                }
            )

    if total_findings == 0:
        print("No findings found.")
        return 1

    findings_with_risk_count = len(findings_with_any_risk)

    risk_flag_rate = findings_with_risk_count / total_findings * 100.0

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8C.3",
        "reports_scanned": (reports_scanned),
        "total_findings": (total_findings),
        "interpretation": (
            "Residual-risk flags identify findings "
            "requiring stronger grounding assurance. "
            "A risk flag does not imply that the "
            "finding is incorrect."
        ),
        "summary": {
            "findings_with_any_risk": (findings_with_risk_count),
            "findings_with_multiple_risks": (len(findings_with_multiple_risks)),
            "risk_flag_rate_percent": (risk_flag_rate),
            "risk_counts": dict(sorted(risk_counts.items())),
        },
        "risk_by_finding_type": {
            finding_type: dict(sorted(counts.items()))
            for finding_type, counts in sorted(risk_by_type.items())
        },
        "risk_by_subtype": {
            subtype: dict(sorted(counts.items()))
            for subtype, counts in sorted(risk_by_subtype.items())
        },
        "risk_records": (risk_records),
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
    print("STEP 8C.3 RESIDUAL GROUNDING-RISK ANALYSIS")
    print("=" * 72)

    print(f"Reports scanned:              {reports_scanned}")

    print(f"Total findings:               {total_findings}")

    print(f"Findings with risk flags:     {findings_with_risk_count}")

    print(f"Risk-flag rate:               {risk_flag_rate:.1f}%")

    print(f"Findings with >1 risk:        {len(findings_with_multiple_risks)}")

    print()
    print("Residual risk categories")
    print("-" * 72)

    if risk_counts:
        for risk_type, count in sorted(risk_counts.items()):
            print(f"{risk_type:<35}{count}")
    else:
        print("none")

    print()
    print("Risk by finding type")
    print("-" * 72)

    if risk_by_type:
        for finding_type, counts in sorted(risk_by_type.items()):
            print(finding_type)

            for risk_type, count in sorted(counts.items()):
                print(f"  {risk_type:<33}{count}")
    else:
        print("none")

    print()
    print("Risk by subtype")
    print("-" * 72)

    if risk_by_subtype:
        for subtype, counts in sorted(risk_by_subtype.items()):
            print(subtype)

            for risk_type, count in sorted(counts.items()):
                print(f"  {risk_type:<33}{count}")
    else:
        print("none")

    print()
    print("Saved analysis to:")

    print(output_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clinical_investigation.evaluation.annotation_context import (
    index_records,
    load_clinical_claims,
    load_evidence_items,
    resolve_records,
)

MANIFEST_FILENAME = "finding_sample_manifest.json"
OUTPUT_FILENAME = "annotation_review.json"


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def get_report_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
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


def load_finding(
    *,
    case_dir: Path,
    finding_id: str,
) -> dict[str, Any]:
    report_path = case_dir / "final_investigation_report.json"

    report = load_json(report_path)

    for finding in get_report_findings(report):
        if (
            str(
                finding.get(
                    "finding_id",
                    "",
                )
            )
            == finding_id
        ):
            return finding

    raise ValueError(f"Finding {finding_id} not found in {report_path}")


def main() -> int:
    root = project_root()

    sample_dir = root / "data" / "evaluation" / "post_refinement_sample"

    manifest_path = sample_dir / MANIFEST_FILENAME

    output_path = sample_dir / OUTPUT_FILENAME

    investigation_root = root / "data" / "investigation_cases"

    manifest = load_json(manifest_path)

    findings = manifest.get(
        "findings",
        [],
    )

    review_records: list[dict[str, Any]] = []

    for sample_record in sorted(
        findings,
        key=lambda item: int(
            item.get(
                "sample_index",
                0,
            )
        ),
    ):
        sample_index = int(sample_record["sample_index"])

        case_id = str(sample_record["case_id"])

        finding_id = str(sample_record["finding_id"])

        case_dir = investigation_root / case_id

        finding = load_finding(
            case_dir=case_dir,
            finding_id=finding_id,
        )

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

        evidence_ids = [
            str(value)
            for value in (
                finding.get(
                    "evidence_ids",
                    [],
                )
                or []
            )
            if value
        ]

        claim_ids = [
            str(value)
            for value in (
                finding.get(
                    "claim_ids",
                    [],
                )
                or []
            )
            if value
        ]

        evidence_records = resolve_records(
            evidence_ids,
            index=evidence_by_id,
        )

        claim_records = resolve_records(
            claim_ids,
            index=claims_by_id,
        )

        review_records.append(
            {
                "sample_index": (sample_index),
                "case_id": case_id,
                "finding_id": (finding_id),
                "finding_type": (finding.get("finding_type")),
                "subtype": (finding.get("subtype")),
                "severity": (finding.get("severity")),
                "confidence": (finding.get("confidence")),
                "requires_human_review": bool(
                    finding.get(
                        "requires_human_review",
                        False,
                    )
                ),
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
                "evidence": (evidence_records),
                "clinical_claims": (claim_records),
                "sample_weight": (sample_record.get("sample_weight")),
                "sampling_probability": (sample_record.get("sampling_probability")),
                # Fields to be completed during review.
                "disposition": "",
                "evidence_support": "",
                "rationale": "",
            }
        )

    output = {
        "schema_version": "1.0",
        "evaluation_phase": ("post_refinement_held_out"),
        "population_size": (manifest.get("population_size")),
        "sample_size": len(review_records),
        "seed": manifest.get("seed"),
        "records": (review_records),
    }

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
    print("POST-REFINEMENT ANNOTATION REVIEW EXPORT")
    print("=" * 72)

    print(f"Findings exported: {len(review_records)}")

    print(f"Output: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

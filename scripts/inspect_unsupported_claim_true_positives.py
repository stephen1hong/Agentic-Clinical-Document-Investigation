from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clinical_investigation.agents.unsupported_claim import (
    build_unsupported_claim_id,
)

TARGET_SUBTYPE = "insufficient_evidence_support"


def load_json(path: Path) -> Any:
    """Load JSON from disk."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def extract_records(
    payload: Any,
    wrapper_key: str,
) -> list[dict[str, Any]]:
    """Extract records from list or wrapped-list JSON."""

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]

    if isinstance(payload, dict):
        value = payload.get(
            wrapper_key,
            [],
        )

        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    return []


def main() -> int:
    """Inspect gold-labeled unsupported-claim true positives."""

    project_root = Path(__file__).resolve().parents[1]

    gold_root = project_root / "data" / "evaluation" / "gold_labels"

    investigation_root = project_root / "data" / "investigation_cases"

    total = 0

    for gold_path in sorted(gold_root.glob("*/gold_labels.json")):
        gold = load_json(gold_path)

        case_id = str(
            gold.get(
                "case_id",
                gold_path.parent.name,
            )
        )

        target_labels = [
            label
            for label in gold.get("finding_labels", [])
            if (
                label.get("disposition") == "true_positive"
                and label.get("expected_finding_subtype") == TARGET_SUBTYPE
            )
        ]

        # Support templates may use expected_subtype
        # rather than expected_finding_subtype.
        if not target_labels:
            target_labels = [
                label
                for label in gold.get("finding_labels", [])
                if (
                    label.get("disposition") == "true_positive"
                    and label.get("expected_subtype") == TARGET_SUBTYPE
                )
            ]

        if not target_labels:
            continue

        case_dir = investigation_root / case_id

        claims_path = case_dir / "clinical_claims.json"

        evidence_path = case_dir / "evidence_items.json"

        if not claims_path.exists() or not evidence_path.exists():
            continue

        claims = extract_records(
            load_json(claims_path),
            "clinical_claims",
        )

        evidence_items = extract_records(
            load_json(evidence_path),
            "evidence_items",
        )

        evidence_index = {
            str(item.get("evidence_id")): item for item in evidence_items if item.get("evidence_id")
        }

        for label in target_labels:
            finding_id = str(
                label.get(
                    "finding_id",
                    "",
                )
            )

            matching_claim = None

            for claim in claims:
                claim_id = str(
                    claim.get(
                        "claim_id",
                        "",
                    )
                )

                candidate_id = build_unsupported_claim_id(
                    case_id=case_id,
                    claim_id=claim_id,
                    subtype=TARGET_SUBTYPE,
                )

                if candidate_id == finding_id:
                    matching_claim = claim
                    break

            if matching_claim is None:
                print()
                print(f"Could not resolve finding: {finding_id}")
                continue

            total += 1

            print()
            print("=" * 72)
            print(f"TRUE POSITIVE {total}")
            print("=" * 72)

            print(f"Case ID: {case_id}")

            print(f"Finding ID: {finding_id}")

            print(f"Claim type: {matching_claim.get('claim_type')}")

            print(f"Subject: {matching_claim.get('subject')}")

            print(f"Predicate: {matching_claim.get('predicate')}")

            print(f"Value: {matching_claim.get('value')}")

            print(f"Gold rationale: {label.get('rationale')}")

            print()
            print("SOURCE EVIDENCE")

            source_ids = (
                matching_claim.get(
                    "source_evidence_ids",
                    [],
                )
                or []
            )

            for evidence_id in source_ids:
                evidence = evidence_index.get(str(evidence_id))

                if evidence is None:
                    print(f"- Missing evidence: {evidence_id}")
                    continue

                print()
                print(f"Evidence ID: {evidence_id}")

                print(f"Document: {evidence.get('document_type')}")

                print(f"Section: {evidence.get('section')}")

                print(f"Normalized fact: {evidence.get('normalized_fact')}")

                print(f"Text span: {evidence.get('text_span')}")

    print()
    print("=" * 72)
    print(f"Total true positives inspected: {total}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

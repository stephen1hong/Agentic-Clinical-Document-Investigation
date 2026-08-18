from __future__ import annotations

import argparse
from typing import Any

from clinical_investigation.agents.workflow import investigation_graph


def print_evidence(
    evidence: dict[str, Any],
) -> None:
    print(f"evidence_id: {evidence.get('evidence_id')}")
    print(f"document_type: {evidence.get('document_type')}")
    print(f"section: {evidence.get('section')}")
    print(f"normalized_fact: {evidence.get('normalized_fact')}")
    print(f"text_span: {evidence.get('text_span')}")
    print(f"event_time: {evidence.get('event_time')}")
    print(f"document_date: {evidence.get('document_date')}")


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--case-id",
        required=True,
    )

    parser.add_argument(
        "--medication",
        required=True,
    )

    args = parser.parse_args()

    result = investigation_graph.invoke(
        {
            "case_id": args.case_id,
        }
    )

    medication_findings = result.get("medication_findings", [])

    print(f"Total medication findings: {len(medication_findings)}")

    conflicting_findings = [
        finding for finding in medication_findings if finding.subtype == "conflicting_status"
    ]

    print(f"Total conflicting_status findings: {len(conflicting_findings)}")

    print()
    print("Available conflicting medication keys:")

    for finding in conflicting_findings:
        print(f"- {finding.medication_key}")

    target = args.medication.strip().lower()

    matching_findings = [
        finding
        for finding in conflicting_findings
        if (finding.medication_key and finding.medication_key.lower() == target)
    ]

    print()
    print(f"Matches for '{target}': {len(matching_findings)}")

    if not matching_findings:
        print("No exact matching conflicting_status finding was found.")
        return 1

    finding = matching_findings[0]

    print()
    print("=== Finding ===")
    print(finding.model_dump_json(indent=2))

    evidence_index = {
        str(evidence.get("evidence_id")): evidence
        for evidence in result.get("evidence_items", [])
        if evidence.get("evidence_id")
    }

    print()
    print("=== Source Evidence ===")

    for evidence_id in finding.evidence_ids:
        print()
        print("----------------------------------------")

        evidence = evidence_index.get(evidence_id)

        if evidence is None:
            print(f"Evidence not found: {evidence_id}")
            continue

        print_evidence(evidence)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from collections import Counter

from clinical_investigation.agents.workflow import (
    investigation_graph,
)
from clinical_investigation.config import settings


def classify_validation_error(
    error: str,
) -> str:
    """Classify validator errors for audit reporting."""

    if "unknown claim_id" in error:
        return "unknown_claim_id"

    if "unknown evidence_id" in error:
        return "unknown_evidence_id"

    if "unknown event_id" in error:
        return "unknown_event_id"

    if "Duplicate finding_id" in error:
        return "duplicate_finding_id"

    if "at least two claims" in error:
        return "contradiction_missing_claims"

    if "at least two evidence items" in error:
        return "contradiction_missing_evidence"

    if "originating follow-up claim" in error:
        return "follow_up_missing_claim"

    if "source evidence for the requested follow-up" in error:
        return "follow_up_missing_evidence"

    if "must reference at least one claim" in error:
        return "unsupported_claim_missing_claim"

    if "insufficient_evidence_support" in error and "must reference evidence" in error:
        return "unsupported_claim_missing_evidence"

    if "missing_source_evidence" in error and "must preserve" in error:
        return "missing_source_evidence_ids"

    if "has no provenance references" in error:
        return "missing_provenance_references"

    if "has no supporting event, claim, or evidence references" in error:
        return "timeline_missing_provenance"

    if "but workflow case_id is" in error:
        return "case_id_mismatch"

    return "other"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Audit investigation validation against real cases.")
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help=("Maximum number of investigation cases to audit."),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    case_dirs = sorted(path for path in settings.investigation_cases_dir.iterdir() if path.is_dir())

    if not case_dirs:
        print("No investigation cases found.")
        return 1

    selected_cases = case_dirs[: args.limit]

    print("=== Investigation Validation Audit ===")

    print(f"Cases available: {len(case_dirs)}")

    print(f"Cases selected: {len(selected_cases)}")

    print()

    total_errors = 0

    error_type_counts: Counter[str] = Counter()

    cases_with_errors = 0
    cases_without_errors = 0
    cases_with_exceptions = 0

    for case_dir in selected_cases:
        case_id = case_dir.name

        print(f"--- Case: {case_id} ---")

        try:
            result = investigation_graph.invoke(
                {
                    "case_id": case_id,
                }
            )
        except Exception as exc:
            cases_with_exceptions += 1

            print("GRAPH EXECUTION ERROR:")

            print(f"{type(exc).__name__}: {exc}")

            print()

            continue

        validation_errors = result.get(
            "validation_errors",
            [],
        )

        investigation_findings = result.get(
            "investigation_findings",
            [],
        )

        print(f"Findings: {len(investigation_findings)}")

        print(f"Validation errors: {len(validation_errors)}")

        print(f"Requires human review: {result.get('requires_human_review')}")

        if not validation_errors:
            cases_without_errors += 1

            print("Validation status: PASS")

            print()

            continue

        cases_with_errors += 1

        total_errors += len(validation_errors)

        print("Validation status: REVIEW")

        for error in validation_errors:
            error_type = classify_validation_error(error)

            error_type_counts[error_type] += 1

            print(f"- [{error_type}] {error}")

        print()

    print("=== Audit Summary ===")

    print(f"Cases audited: {len(selected_cases)}")

    print(f"Cases passing validation: {cases_without_errors}")

    print(f"Cases with validation errors: {cases_with_errors}")

    print(f"Cases with graph exceptions: {cases_with_exceptions}")

    print(f"Total validation errors: {total_errors}")

    print()

    print("Validation error distribution:")

    if not error_type_counts:
        print("No validation errors detected.")
    else:
        for (
            error_type,
            count,
        ) in error_type_counts.most_common():
            print(f"- {error_type}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

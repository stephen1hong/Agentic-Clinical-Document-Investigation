from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from clinical_investigation.config import settings
from clinical_investigation.review.review_persistence import (
    load_human_review,
)

FINAL_REPORT_FILENAME = "final_investigation_report.json"
AUDIT_PASS = "PASS"
AUDIT_OUTSTANDING = "OUTSTANDING"
AUDIT_FAIL = "FAIL"


def load_final_report(
    case_dir: Path,
) -> dict[str, Any]:
    """Load the persisted final investigation report."""

    report_path = case_dir / FINAL_REPORT_FILENAME

    if not report_path.exists():
        raise FileNotFoundError(f"Final investigation report not found: {report_path}")

    payload = json.loads(
        report_path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(payload, dict):
        raise ValueError("Final investigation report must contain a JSON object.")

    return payload


def get_all_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all findings from the final report."""

    high_priority = list(
        report.get(
            "high_priority_findings",
            [],
        )
    )

    other = list(
        report.get(
            "other_findings",
            [],
        )
    )

    return high_priority + other


def get_required_finding_ids(
    report: dict[str, Any],
) -> list[str]:
    """Return finding IDs that require human review."""

    return [
        str(finding["finding_id"])
        for finding in get_all_findings(report)
        if bool(
            finding.get(
                "requires_human_review",
                False,
            )
        )
    ]


def audit_case(
    case_dir: Path,
) -> dict[str, Any]:
    """Audit one investigation case."""

    report = load_final_report(case_dir)

    required_ids = get_required_finding_ids(report)

    review = load_human_review(case_dir)

    machine_review_status = str(
        report.get(
            "review_status",
            "unknown",
        )
    )

    result: dict[str, Any] = {
        "case_id": str(
            report.get(
                "case_id",
                case_dir.name,
            )
        ),
        "machine_review_status": machine_review_status,
        "required_finding_count": len(required_ids),
        "human_review_exists": review is not None,
        "human_review_status": None,
        "decision_count": 0,
        "unique_decision_count": 0,
        "missing_decision_ids": [],
        "duplicate_decision_ids": [],
        "unexpected_decision_ids": [],
        "completed_at_present": False,
        "audit_status": AUDIT_PASS,
        "outstanding": False,
        "consistent": True,
        "issues": [],
    }

    issues: list[str] = []

    if review is None:
        if required_ids:
            result["outstanding"] = True
            result["audit_status"] = AUDIT_OUTSTANDING
            result["missing_decision_ids"] = sorted(required_ids)

            issues.append("human review has not yet been started")

        else:
            result["audit_status"] = AUDIT_PASS

        result["consistent"] = True
        result["issues"] = issues

        return result

    result["human_review_status"] = review.status.value
    result["decision_count"] = len(review.finding_reviews)
    result["completed_at_present"] = review.completed_at is not None

    reviewed_ids = [item.finding_id for item in review.finding_reviews]

    reviewed_id_counts = Counter(reviewed_ids)

    unique_reviewed_ids = set(reviewed_ids)

    required_id_set = set(required_ids)

    result["unique_decision_count"] = len(unique_reviewed_ids)

    missing_ids = sorted(required_id_set - unique_reviewed_ids)

    duplicate_ids = sorted(
        finding_id for finding_id, count in reviewed_id_counts.items() if count > 1
    )

    unexpected_ids = sorted(unique_reviewed_ids - required_id_set)

    result["missing_decision_ids"] = missing_ids

    result["duplicate_decision_ids"] = duplicate_ids

    result["unexpected_decision_ids"] = unexpected_ids

    if duplicate_ids:
        issues.append("duplicate finding decisions detected")

    if unexpected_ids:
        issues.append("decisions exist for findings that do not require review")

    if review.status.value == "completed":
        if missing_ids:
            issues.append("completed review is missing required decisions")

        if review.completed_at is None:
            issues.append("completed review is missing completed_at")

        if len(unique_reviewed_ids) != len(required_id_set):
            issues.append("completed review decision count does not match required finding count")

    elif review.status.value == "in_progress":
        if review.completed_at is not None:
            issues.append("in-progress review unexpectedly has completed_at")

        if missing_ids:
            result["outstanding"] = True

    elif review.status.value == "not_required":
        if required_ids:
            issues.append("review marked not_required despite required findings")

        if review.finding_reviews:
            issues.append("not_required review contains finding decisions")

    if issues:
        result["audit_status"] = AUDIT_FAIL
        result["consistent"] = False

    elif result["outstanding"]:
        result["audit_status"] = AUDIT_OUTSTANDING
        result["consistent"] = True

    else:
        result["audit_status"] = AUDIT_PASS
        result["consistent"] = True

    result["issues"] = issues

    return result


def print_case_result(
    result: dict[str, Any],
) -> None:
    """Print one case audit result."""

    print("-" * 72)
    print(f"Case: {result['case_id']}")
    print(f"Machine status: {result['machine_review_status']}")
    print(f"Human review exists: {result['human_review_exists']}")
    print(f"Human review status: {result['human_review_status']}")
    print(f"Required findings: {result['required_finding_count']}")
    print(f"Decisions: {result['decision_count']}")
    print(f"Unique decisions: {result['unique_decision_count']}")

    if result["missing_decision_ids"]:
        print(f"Missing decisions: {result['missing_decision_ids']}")

    if result["duplicate_decision_ids"]:
        print(f"Duplicate decisions: {result['duplicate_decision_ids']}")

    if result["unexpected_decision_ids"]:
        print(f"Unexpected decisions: {result['unexpected_decision_ids']}")

    print(f"Audit: {result['audit_status']}")

    if result["missing_decision_ids"]:
        print(f"Outstanding decisions: {len(result['missing_decision_ids'])}")

    for issue in result["issues"]:
        print(f"  - {issue}")


def main() -> int:
    """Audit human-review state across all investigation cases."""

    case_dirs = sorted(path for path in settings.investigation_cases_dir.iterdir() if path.is_dir())

    if not case_dirs:
        print("No investigation cases found.")
        return 1

    results: list[dict[str, Any]] = []
    errors = 0
    audit_failures = 0
    outstanding_cases = 0
    passed_cases = 0

    machine_status_counts: Counter[str] = Counter()

    human_status_counts: Counter[str] = Counter()

    total_required_findings = 0
    total_decisions = 0
    total_missing_decisions = 0
    total_duplicate_decisions = 0

    print()
    print("=" * 72)
    print("HUMAN REVIEW AUDIT")
    print("=" * 72)
    print()

    for case_dir in case_dirs:
        try:
            result = audit_case(case_dir)
        except Exception as exc:
            errors += 1

            print("-" * 72)
            print(f"Case: {case_dir.name}")
            print(f"Audit: ERROR - {type(exc).__name__}: {exc}")

            continue

        results.append(result)

        print_case_result(result)

        machine_status_counts[result["machine_review_status"]] += 1

        human_status = (
            result["human_review_status"]
            if result["human_review_status"] is not None
            else "missing"
        )

        human_status_counts[human_status] += 1

        total_required_findings += result["required_finding_count"]

        total_decisions += result["decision_count"]

        total_missing_decisions += len(result["missing_decision_ids"])

        total_duplicate_decisions += len(result["duplicate_decision_ids"])

        if result["audit_status"] == AUDIT_PASS:
            passed_cases += 1

        elif result["audit_status"] == AUDIT_OUTSTANDING:
            outstanding_cases += 1

        elif result["audit_status"] == AUDIT_FAIL:
            audit_failures += 1

    print()
    print("=" * 72)
    print("AUDIT SUMMARY")
    print("=" * 72)

    print(f"Cases total: {len(case_dirs)}")

    print(f"Cases audited: {len(results)}")

    print(f"Cases passed: {passed_cases}")

    print(f"Cases outstanding: {outstanding_cases}")

    print(f"Cases failed audit: {audit_failures}")

    print(f"Cases with audit errors: {errors}")

    print()
    print("Machine review statuses:")

    for status, count in sorted(machine_status_counts.items()):
        print(f"  {status}: {count}")

    print()
    print("Human review statuses:")

    for status, count in sorted(human_status_counts.items()):
        print(f"  {status}: {count}")

    print()
    print(f"Total required findings: {total_required_findings}")

    print(f"Total decisions: {total_decisions}")

    print(f"Missing required decisions: {total_missing_decisions}")

    print(f"Duplicate decisions: {total_duplicate_decisions}")

    return 0 if audit_failures == 0 and errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

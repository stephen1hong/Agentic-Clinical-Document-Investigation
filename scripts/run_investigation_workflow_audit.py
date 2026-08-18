from __future__ import annotations

from collections import Counter

from clinical_investigation.agents.workflow import (
    investigation_graph,
)
from clinical_investigation.config import settings


def main() -> int:
    case_dirs = sorted(path for path in settings.investigation_cases_dir.iterdir() if path.is_dir())

    if not case_dirs:
        print("No investigation cases found.")
        return 1

    total_cases = len(case_dirs)

    completed_cases = 0
    failed_cases = 0

    reports_verified = 0
    report_validation_failures = 0

    review_status_counts: Counter[str] = Counter()

    finding_type_counts: Counter[str] = Counter()

    total_findings = 0
    total_validation_errors = 0

    print("=== Full Investigation Workflow Audit ===")

    print(f"Cases: {total_cases}")

    print()

    for case_dir in case_dirs:
        case_id = case_dir.name

        print(f"Running: {case_id}")

        try:
            result = investigation_graph.invoke(
                {
                    "case_id": case_id,
                }
            )
        except Exception as exc:
            failed_cases += 1

            print(f"  ERROR: {type(exc).__name__}: {exc}")

            continue

        completed_cases += 1

        findings = result["investigation_findings"]

        validation_errors = result["validation_errors"]

        review_status = result["review_status"]

        final_report = result.get("final_report")

        report_errors: list[str] = []

        if not final_report:
            report_errors.append("final_report is missing or empty")
        else:
            if final_report.get("case_id") != case_id:
                report_errors.append("final_report.case_id mismatch")

            if final_report.get("finding_count") != len(findings):
                report_errors.append("final_report.finding_count mismatch")

            if final_report.get("review_status") != review_status:
                report_errors.append("final_report.review_status mismatch")

        if report_errors:
            report_validation_failures += 1

            for error in report_errors:
                print(f"  Report ERROR: {error}")
        else:
            reports_verified += 1

        total_findings += len(findings)

        total_validation_errors += len(validation_errors)

        review_status_counts[review_status] += 1

        for finding in findings:
            finding_type_counts[finding.finding_type.value] += 1

        print(f"  Findings: {len(findings)}")

        print(f"  Validation errors: {len(validation_errors)}")

        print(f"  Review status: {review_status}")

        print("  Final report: " + ("verified" if not report_errors else "FAILED"))

    print()
    print("=== Workflow Audit Summary ===")

    print(f"Cases total: {total_cases}")

    print(f"Cases completed: {completed_cases}")

    print(f"Cases failed: {failed_cases}")

    print(f"Total findings: {total_findings}")

    print(f"Total validation errors: {total_validation_errors}")

    print(f"Final reports verified: {reports_verified}")

    print(f"Final report validation failures: {report_validation_failures}")

    print()

    print("Review status distribution:")

    for (
        status,
        count,
    ) in review_status_counts.most_common():
        print(f"- {status}: {count}")

    print()

    print("Finding type distribution:")

    for (
        finding_type,
        count,
    ) in finding_type_counts.most_common():
        print(f"- {finding_type}: {count}")

    return 0 if (failed_cases == 0 and report_validation_failures == 0) else 1


if __name__ == "__main__":
    raise SystemExit(main())

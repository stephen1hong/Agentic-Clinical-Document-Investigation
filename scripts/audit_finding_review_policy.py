from __future__ import annotations

from collections import Counter

from clinical_investigation.agents.workflow import investigation_graph
from clinical_investigation.config import settings


def main() -> int:
    case_dirs = sorted(path for path in settings.investigation_cases_dir.iterdir() if path.is_dir())

    if not case_dirs:
        print("No investigation cases found.")
        return 1

    subtype_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    review_subtype_counts: Counter[str] = Counter()
    review_severity_counts: Counter[str] = Counter()

    subtype_severity_counts: Counter[tuple[str, str]] = Counter()

    subtype_review_counts: Counter[tuple[str, bool]] = Counter()

    total_findings = 0
    total_review_findings = 0

    print("=== Case-Level Review Audit ===")

    for case_dir in case_dirs:
        case_id = case_dir.name

        result = investigation_graph.invoke(
            {
                "case_id": case_id,
            }
        )

        findings = result.get(
            "investigation_findings",
            [],
        )

        validation_errors = result.get(
            "validation_errors",
            [],
        )

        review_status = result.get(
            "review_status",
            "",
        )

        review_findings = [finding for finding in findings if finding.requires_human_review]

        total_findings += len(findings)
        total_review_findings += len(review_findings)

        print(
            f"{case_id}: "
            f"findings={len(findings)}, "
            f"review_findings={len(review_findings)}, "
            f"validation_errors={len(validation_errors)}, "
            f"status={review_status}"
        )

        for finding in findings:
            subtype = finding.subtype
            severity = finding.severity.value
            requires_review = finding.requires_human_review

            subtype_counts[subtype] += 1
            severity_counts[severity] += 1

            subtype_severity_counts[
                (
                    subtype,
                    severity,
                )
            ] += 1

            subtype_review_counts[
                (
                    subtype,
                    requires_review,
                )
            ] += 1

            if requires_review:
                review_subtype_counts[subtype] += 1

                review_severity_counts[severity] += 1

    print()
    print("=== Summary ===")
    print(f"Cases: {len(case_dirs)}")
    print(f"Total findings: {total_findings}")
    print(f"Findings requiring review: {total_review_findings}")

    print()
    print("=== Findings by Subtype ===")

    for subtype, count in subtype_counts.most_common():
        print(f"{subtype}: {count}")

    print()
    print("=== Findings by Severity ===")

    for severity, count in severity_counts.most_common():
        print(f"{severity}: {count}")

    print()
    print("=== Review-Trigger Findings by Subtype ===")

    for subtype, count in review_subtype_counts.most_common():
        print(f"{subtype}: {count}")

    print()
    print("=== Review-Trigger Findings by Severity ===")

    for severity, count in review_severity_counts.most_common():
        print(f"{severity}: {count}")

    print()
    print("=== Subtype x Severity ===")

    for (
        subtype,
        severity,
    ), count in sorted(subtype_severity_counts.items()):
        print(f"{subtype} | {severity}: {count}")

    print()
    print("=== Subtype x Review Flag ===")

    for (
        subtype,
        requires_review,
    ), count in sorted(subtype_review_counts.items()):
        print(f"{subtype} | review={requires_review}: {count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

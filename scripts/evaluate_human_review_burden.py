from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "human_review_report_quality"

OUTPUT_PATH = OUTPUT_DIR / "human_review_burden.json"


FINAL_REPORT_FILENAME = "final_investigation_report.json"

REVIEWER_BUNDLE_FILENAME = "reviewer_bundle.json"


def load_json(
    path: Path,
) -> dict[str, Any]:
    """Load a JSON object."""

    raw = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(
        raw,
        dict,
    ):
        raise ValueError(f"{path} must contain a JSON object.")

    return raw


def as_findings(
    value: Any,
) -> list[dict[str, Any]]:
    """Normalize a finding-list field."""

    if not isinstance(
        value,
        list,
    ):
        return []

    return [
        item
        for item in value
        if isinstance(
            item,
            dict,
        )
    ]


def report_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all findings from a final report."""

    return as_findings(report.get("high_priority_findings")) + as_findings(
        report.get("other_findings")
    )


def bundle_review_findings(
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return findings routed for human review."""

    return as_findings(bundle.get("findings_requiring_review"))


def bundle_contextual_findings(
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return contextual reviewer findings."""

    return as_findings(bundle.get("contextual_findings"))


def finding_id_set(
    findings: list[dict[str, Any]],
) -> set[str]:
    """Return nonempty finding IDs."""

    return {str(finding["finding_id"]) for finding in findings if finding.get("finding_id")}


def duplicate_finding_ids(
    findings: list[dict[str, Any]],
) -> list[str]:
    """Return duplicate finding IDs."""

    counter: Counter[str] = Counter(
        str(finding["finding_id"]) for finding in findings if finding.get("finding_id")
    )

    return sorted(
        finding_id
        for (
            finding_id,
            count,
        ) in counter.items()
        if count > 1
    )


def percentile(
    values: list[int],
    probability: float,
) -> float:
    """Return linear-interpolated percentile."""

    if not values:
        return 0.0

    ordered = sorted(values)

    if len(ordered) == 1:
        return float(ordered[0])

    position = (len(ordered) - 1) * probability

    lower_index = math.floor(position)

    upper_index = math.ceil(position)

    if lower_index == upper_index:
        return float(ordered[lower_index])

    fraction = position - lower_index

    lower = ordered[lower_index]

    upper = ordered[upper_index]

    return lower + (upper - lower) * fraction


def percentage(
    numerator: int,
    denominator: int,
) -> float:
    """Return percentage safely."""

    if denominator == 0:
        return 0.0

    return numerator / denominator * 100.0


def main() -> int:
    """Run simplified Step 8D.1."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    cases_discovered = 0
    cases_scanned = 0

    total_findings = 0
    total_review_findings = 0
    total_contextual_findings = 0

    cases_with_findings = 0
    cases_requiring_review = 0
    cases_not_requiring_review = 0

    findings_per_case: list[int] = []
    review_findings_per_case: list[int] = []

    severity_counts: Counter[str] = Counter()

    review_severity_counts: Counter[str] = Counter()

    finding_type_counts: Counter[str] = Counter()

    review_finding_type_counts: Counter[str] = Counter()

    subtype_counts: Counter[str] = Counter()

    review_subtype_counts: Counter[str] = Counter()

    review_status_counts: Counter[str] = Counter()

    missing_artifacts: list[dict[str, Any]] = []

    case_id_mismatches: list[dict[str, Any]] = []

    count_mismatches: list[dict[str, Any]] = []

    review_status_mismatches: list[dict[str, Any]] = []

    finding_partition_mismatches: list[dict[str, Any]] = []

    review_flag_mismatches: list[dict[str, Any]] = []

    duplicate_ids: list[dict[str, Any]] = []

    case_summaries: list[dict[str, Any]] = []

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        cases_discovered += 1

        final_path = case_dir / FINAL_REPORT_FILENAME

        bundle_path = case_dir / REVIEWER_BUNDLE_FILENAME

        missing = []

        if not final_path.exists():
            missing.append(FINAL_REPORT_FILENAME)

        if not bundle_path.exists():
            missing.append(REVIEWER_BUNDLE_FILENAME)

        if missing:
            missing_artifacts.append(
                {
                    "case_id": (case_dir.name),
                    "missing_files": (missing),
                }
            )

            continue

        cases_scanned += 1

        case_id = case_dir.name

        report = load_json(final_path)

        bundle = load_json(bundle_path)

        findings = report_findings(report)

        review_findings = bundle_review_findings(bundle)

        contextual_findings = bundle_contextual_findings(bundle)

        expected_review_findings = [
            finding
            for finding in findings
            if bool(
                finding.get(
                    "requires_human_review",
                    False,
                )
            )
        ]

        expected_contextual_findings = [
            finding
            for finding in findings
            if not bool(
                finding.get(
                    "requires_human_review",
                    False,
                )
            )
        ]

        finding_count = len(findings)

        review_count = len(expected_review_findings)

        contextual_count = len(expected_contextual_findings)

        total_findings += finding_count

        total_review_findings += review_count

        total_contextual_findings += contextual_count

        findings_per_case.append(finding_count)

        review_findings_per_case.append(review_count)

        if finding_count > 0:
            cases_with_findings += 1

        if review_count > 0:
            cases_requiring_review += 1
        else:
            cases_not_requiring_review += 1

        report_case_id = report.get("case_id")

        bundle_case_id = bundle.get("case_id")

        if report_case_id != case_id:
            case_id_mismatches.append(
                {
                    "case_id": case_id,
                    "artifact": (FINAL_REPORT_FILENAME),
                    "record_case_id": (report_case_id),
                }
            )

        if bundle_case_id != case_id:
            case_id_mismatches.append(
                {
                    "case_id": case_id,
                    "artifact": (REVIEWER_BUNDLE_FILENAME),
                    "record_case_id": (bundle_case_id),
                }
            )

        report_declared_count = report.get("finding_count")

        if report_declared_count != finding_count:
            count_mismatches.append(
                {
                    "case_id": case_id,
                    "field": ("final_report.finding_count"),
                    "declared": (report_declared_count),
                    "actual": (finding_count),
                }
            )

        report_declared_review_count = report.get("review_finding_count")

        if report_declared_review_count != review_count:
            count_mismatches.append(
                {
                    "case_id": case_id,
                    "field": ("final_report.review_finding_count"),
                    "declared": (report_declared_review_count),
                    "actual": (review_count),
                }
            )

        bundle_declared_count = bundle.get("finding_count")

        if bundle_declared_count != finding_count:
            count_mismatches.append(
                {
                    "case_id": case_id,
                    "field": ("reviewer_bundle.finding_count"),
                    "declared": (bundle_declared_count),
                    "actual": (finding_count),
                }
            )

        bundle_declared_review_count = bundle.get("review_finding_count")

        if bundle_declared_review_count != review_count:
            count_mismatches.append(
                {
                    "case_id": case_id,
                    "field": ("reviewer_bundle.review_finding_count"),
                    "declared": (bundle_declared_review_count),
                    "actual": (review_count),
                }
            )

        report_review_status = str(
            report.get(
                "review_status",
                "",
            )
        )

        bundle_review_status = str(
            bundle.get(
                "review_status",
                "",
            )
        )

        review_status_counts[bundle_review_status] += 1

        if report_review_status != bundle_review_status:
            review_status_mismatches.append(
                {
                    "case_id": case_id,
                    "report_review_status": (report_review_status),
                    "bundle_review_status": (bundle_review_status),
                }
            )

        #
        # Do not force the application's review-status
        # vocabulary to our own wording unless needed.
        # We only require not_required when there is no
        # review workload.
        #
        if review_count == 0 and report_review_status != "not_required":
            review_status_mismatches.append(
                {
                    "case_id": case_id,
                    "issue": ("zero_review_findings_but_status_not_not_required"),
                    "review_status": (report_review_status),
                }
            )

        if review_count > 0 and report_review_status == "not_required":
            review_status_mismatches.append(
                {
                    "case_id": case_id,
                    "issue": ("review_findings_exist_but_status_not_required"),
                    "review_status": (report_review_status),
                    "review_finding_count": (review_count),
                }
            )

        final_ids = finding_id_set(findings)

        expected_review_ids = finding_id_set(expected_review_findings)

        expected_contextual_ids = finding_id_set(expected_contextual_findings)

        bundle_review_ids = finding_id_set(review_findings)

        bundle_contextual_ids = finding_id_set(contextual_findings)

        if expected_review_ids != bundle_review_ids:
            finding_partition_mismatches.append(
                {
                    "case_id": case_id,
                    "partition": ("findings_requiring_review"),
                    "missing_from_bundle": sorted(expected_review_ids - bundle_review_ids),
                    "unexpected_in_bundle": sorted(bundle_review_ids - expected_review_ids),
                }
            )

        if expected_contextual_ids != bundle_contextual_ids:
            finding_partition_mismatches.append(
                {
                    "case_id": case_id,
                    "partition": ("contextual_findings"),
                    "missing_from_bundle": sorted(expected_contextual_ids - bundle_contextual_ids),
                    "unexpected_in_bundle": sorted(bundle_contextual_ids - expected_contextual_ids),
                }
            )

        bundle_all_ids = bundle_review_ids | bundle_contextual_ids

        if final_ids != bundle_all_ids:
            finding_partition_mismatches.append(
                {
                    "case_id": case_id,
                    "partition": ("all_reviewer_findings"),
                    "missing_from_bundle": sorted(final_ids - bundle_all_ids),
                    "unexpected_in_bundle": sorted(bundle_all_ids - final_ids),
                }
            )

        for finding in review_findings:
            if not bool(
                finding.get(
                    "requires_human_review",
                    False,
                )
            ):
                review_flag_mismatches.append(
                    {
                        "case_id": case_id,
                        "finding_id": (finding.get("finding_id")),
                        "location": ("findings_requiring_review"),
                        "requires_human_review": (finding.get("requires_human_review")),
                    }
                )

        for finding in contextual_findings:
            if bool(
                finding.get(
                    "requires_human_review",
                    False,
                )
            ):
                review_flag_mismatches.append(
                    {
                        "case_id": case_id,
                        "finding_id": (finding.get("finding_id")),
                        "location": ("contextual_findings"),
                        "requires_human_review": (finding.get("requires_human_review")),
                    }
                )

        for (
            artifact_name,
            artifact_findings,
        ) in (
            (
                "final_report",
                findings,
            ),
            (
                "reviewer_bundle",
                (review_findings + contextual_findings),
            ),
        ):
            duplicates = duplicate_finding_ids(artifact_findings)

            if duplicates:
                duplicate_ids.append(
                    {
                        "case_id": (case_id),
                        "artifact": (artifact_name),
                        "finding_ids": (duplicates),
                    }
                )

        for finding in findings:
            severity = str(
                finding.get(
                    "severity",
                    "unknown",
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

            severity_counts[severity] += 1

            finding_type_counts[finding_type] += 1

            subtype_counts[subtype] += 1

            if bool(
                finding.get(
                    "requires_human_review",
                    False,
                )
            ):
                review_severity_counts[severity] += 1

                review_finding_type_counts[finding_type] += 1

                review_subtype_counts[subtype] += 1

        case_summaries.append(
            {
                "case_id": case_id,
                "finding_count": (finding_count),
                "review_finding_count": (review_count),
                "contextual_finding_count": (contextual_count),
                "review_status": (report_review_status),
                "requires_human_review": (review_count > 0),
                "review_rate_percentage": (
                    percentage(
                        review_count,
                        finding_count,
                    )
                ),
            }
        )

    integrity_issue_count = sum(
        (
            len(missing_artifacts),
            len(case_id_mismatches),
            len(count_mismatches),
            len(review_status_mismatches),
            len(finding_partition_mismatches),
            len(review_flag_mismatches),
            len(duplicate_ids),
        )
    )

    status = "PASS" if integrity_issue_count == 0 else "FAIL"

    overall_review_rate = percentage(
        total_review_findings,
        total_findings,
    )

    case_review_rate = percentage(
        cases_requiring_review,
        cases_scanned,
    )

    mean_findings = mean(findings_per_case) if findings_per_case else 0.0

    median_findings = median(findings_per_case) if findings_per_case else 0.0

    mean_review_findings = mean(review_findings_per_case) if review_findings_per_case else 0.0

    median_review_findings = median(review_findings_per_case) if review_findings_per_case else 0.0

    max_review_findings = max(review_findings_per_case) if review_findings_per_case else 0

    p95_review_findings = percentile(
        review_findings_per_case,
        0.95,
    )

    cases_ranked_by_review_burden = sorted(
        case_summaries,
        key=lambda item: (
            int(item["review_finding_count"]),
            int(item["finding_count"]),
        ),
        reverse=True,
    )

    output = {
        "schema_version": "1.0",
        "evaluation_step": ("simplified_8D.1"),
        "title": ("Human Review Burden"),
        "status": status,
        "evaluation_method": (
            "Full-population audit of current "
            "final investigation reports and "
            "derived reviewer bundles."
        ),
        "population": {
            "cases_discovered": (cases_discovered),
            "cases_scanned": (cases_scanned),
            "cases_with_findings": (cases_with_findings),
            "total_findings": (total_findings),
            "total_review_findings": (total_review_findings),
            "total_contextual_findings": (total_contextual_findings),
        },
        "review_burden": {
            "cases_requiring_review": (cases_requiring_review),
            "cases_not_requiring_review": (cases_not_requiring_review),
            "case_review_rate_percentage": (case_review_rate),
            "finding_review_rate_percentage": (overall_review_rate),
            "mean_findings_per_case": (mean_findings),
            "median_findings_per_case": (median_findings),
            "mean_review_findings_per_case": (mean_review_findings),
            "median_review_findings_per_case": (median_review_findings),
            "p95_review_findings_per_case": (p95_review_findings),
            "max_review_findings_per_case": (max_review_findings),
        },
        "severity_distribution": {
            "all_findings": dict(sorted(severity_counts.items())),
            "review_findings": dict(sorted(review_severity_counts.items())),
        },
        "finding_type_distribution": {
            "all_findings": dict(sorted(finding_type_counts.items())),
            "review_findings": dict(sorted(review_finding_type_counts.items())),
        },
        "subtype_distribution": {
            "all_findings": dict(sorted(subtype_counts.items())),
            "review_findings": dict(sorted(review_subtype_counts.items())),
        },
        "review_status_distribution": dict(sorted(review_status_counts.items())),
        "integrity": {
            "missing_artifacts": len(missing_artifacts),
            "case_id_mismatches": len(case_id_mismatches),
            "count_mismatches": len(count_mismatches),
            "review_status_mismatches": len(review_status_mismatches),
            "finding_partition_mismatches": len(finding_partition_mismatches),
            "review_flag_mismatches": len(review_flag_mismatches),
            "duplicate_finding_id_issues": len(duplicate_ids),
            "total_integrity_issues": (integrity_issue_count),
        },
        "cases_ranked_by_review_burden": (cases_ranked_by_review_burden),
        "issues": {
            "missing_artifacts": (missing_artifacts),
            "case_id_mismatches": (case_id_mismatches),
            "count_mismatches": (count_mismatches),
            "review_status_mismatches": (review_status_mismatches),
            "finding_partition_mismatches": (finding_partition_mismatches),
            "review_flag_mismatches": (review_flag_mismatches),
            "duplicate_finding_ids": (duplicate_ids),
        },
        "interpretation": {
            "note": (
                "This step measures observed reviewer "
                "workload. It does not impose an "
                "arbitrary acceptable-review-rate "
                "threshold. Burden acceptability is "
                "interpreted together with finding "
                "severity and report quality in "
                "simplified Step 8D."
            ),
        },
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
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
    print("SIMPLIFIED STEP 8D.1 HUMAN-REVIEW BURDEN")
    print("=" * 72)

    print(f"Status:                          {status}")

    print()
    print("Population")
    print("-" * 72)

    print(f"Cases scanned:                   {cases_scanned}")

    print(f"Total findings:                  {total_findings}")

    print(f"Review-required findings:        {total_review_findings}")

    print(f"Contextual findings:             {total_contextual_findings}")

    print()
    print("Human-review burden")
    print("-" * 72)

    print(f"Cases requiring review:          {cases_requiring_review}")

    print(f"Case review rate:                {case_review_rate:.1f}%")

    print(f"Finding review rate:             {overall_review_rate:.1f}%")

    print(f"Mean findings / case:            {mean_findings:.2f}")

    print(f"Median findings / case:          {median_findings:.2f}")

    print(f"Mean review findings / case:     {mean_review_findings:.2f}")

    print(f"Median review findings / case:   {median_review_findings:.2f}")

    print(f"P95 review findings / case:      {p95_review_findings:.2f}")

    print(f"Maximum review findings / case:  {max_review_findings}")

    print()
    print("Review findings by severity")
    print("-" * 72)

    if review_severity_counts:
        for (
            severity,
            count,
        ) in sorted(review_severity_counts.items()):
            print(f"{severity:<32}{count:>8}")
    else:
        print("No findings require review.")

    print()
    print("Review findings by type")
    print("-" * 72)

    if review_finding_type_counts:
        for (
            finding_type,
            count,
        ) in sorted(review_finding_type_counts.items()):
            print(f"{finding_type:<32}{count:>8}")
    else:
        print("No findings require review.")

    print()
    print("Artifact consistency")
    print("-" * 72)

    print(f"Missing artifacts:               {len(missing_artifacts)}")

    print(f"Case-ID mismatches:              {len(case_id_mismatches)}")

    print(f"Count mismatches:                {len(count_mismatches)}")

    print(f"Review-status mismatches:        {len(review_status_mismatches)}")

    print(f"Finding partition mismatches:    {len(finding_partition_mismatches)}")

    print(f"Review-flag mismatches:          {len(review_flag_mismatches)}")

    print(f"Duplicate-ID issues:             {len(duplicate_ids)}")

    print()
    print(f"Total integrity issues:          {integrity_issue_count}")

    print()
    print("Saved evaluation to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

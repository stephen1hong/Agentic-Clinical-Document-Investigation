from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluate_end_to_end_regression import (
    get_report_findings,
    load_json,
    sha256_file,
    validate_one_case,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

STEP_9A_PATH = PROJECT_ROOT / "data" / "evaluation" / "step_9a" / "end_to_end_regression.json"

STEP_9B_FINAL_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "step_9b_final" / "step_9b_robustness_summary.json"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "step_9c"

OUTPUT_PATH = OUTPUT_DIR / "final_report_human_review_acceptance.json"


#
# Frozen Step-8 / Step-9A population contract.
#
EXPECTED_CASE_COUNT = 20
EXPECTED_FINDING_COUNT = 317
EXPECTED_REVIEW_FINDING_COUNT = 1
EXPECTED_CONTEXTUAL_FINDING_COUNT = 316
EXPECTED_REVIEW_CASE_COUNT = 1


REQUIRED_CASE_ARTIFACTS = (
    "final_investigation_report.json",
    "reviewer_bundle.json",
    "reviewer_report.md",
)


def write_json(
    path: Path,
    payload: Any,
) -> None:
    """Write formatted UTF-8 JSON."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def artifact_status(
    payload: dict[str, Any],
) -> str | None:
    """Return normalized evaluation status."""

    for field in (
        "status",
        "overall_status",
    ):
        value = payload.get(field)

        if isinstance(
            value,
            str,
        ):
            return value

    return None


def load_required_pass(
    path: Path,
    name: str,
) -> dict[str, Any]:
    """Load one required PASS evaluation artifact."""

    if not path.exists():
        raise FileNotFoundError(f"{name} artifact not found: {path}")

    payload = load_json(path)

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(f"{name} artifact must contain a JSON object.")

    status = artifact_status(payload)

    if status != "PASS":
        raise RuntimeError(f"{name} must be PASS; found {status!r}.")

    return payload


def case_dirs() -> list[Path]:
    """Return persisted investigation-case directories."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Investigation case root not found: {CASE_ROOT}")

    return sorted(path for path in CASE_ROOT.iterdir() if path.is_dir())


def finding_id(
    finding: dict[str, Any],
) -> str:
    """Return normalized finding ID."""

    return str(
        finding.get(
            "finding_id",
            "",
        )
    )


def finding_ids(
    findings: list[dict[str, Any]],
) -> list[str]:
    """Return non-empty finding IDs."""

    return [value for finding in findings if (value := finding_id(finding))]


def bundle_findings(
    bundle: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Return review-required and contextual reviewer findings."""

    review_value = bundle.get(
        "findings_requiring_review",
        [],
    )

    contextual_value = bundle.get(
        "contextual_findings",
        [],
    )

    review_findings = (
        [
            item
            for item in review_value
            if isinstance(
                item,
                dict,
            )
        ]
        if isinstance(
            review_value,
            list,
        )
        else []
    )

    contextual_findings = (
        [
            item
            for item in contextual_value
            if isinstance(
                item,
                dict,
            )
        ]
        if isinstance(
            contextual_value,
            list,
        )
        else []
    )

    return (
        review_findings,
        contextual_findings,
    )


def expected_review_partition(
    report_findings: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """Partition machine findings by review requirement."""

    review_findings = [
        finding for finding in report_findings if finding.get("requires_human_review") is True
    ]

    contextual_findings = [
        finding for finding in report_findings if finding.get("requires_human_review") is not True
    ]

    return (
        review_findings,
        contextual_findings,
    )


def append_issue(
    issues: list[dict[str, Any]],
    *,
    case_id: str,
    category: str,
    detail: str,
) -> None:
    """Append normalized acceptance issue."""

    issues.append(
        {
            "case_id": case_id,
            "category": category,
            "detail": detail,
        }
    )


def validate_markdown(
    *,
    case_id: str,
    markdown: str,
    finding_count: int,
    review_count: int,
    issues: list[dict[str, Any]],
) -> None:
    """Validate reviewer-facing Markdown projection."""

    if not markdown.strip():
        append_issue(
            issues,
            case_id=case_id,
            category=("empty_reviewer_report"),
            detail=("reviewer_report.md is empty."),
        )

        return

    required_fragments = (
        "# Clinical Investigation Review",
        "**Case ID:**",
        "**Review status:**",
        "**Findings requiring review:**",
        "**Total findings:**",
        "## Findings Requiring Review",
        "## Contextual Findings",
    )

    for fragment in required_fragments:
        if fragment not in markdown:
            append_issue(
                issues,
                case_id=case_id,
                category=("reviewer_markdown_structure_mismatch"),
                detail=(f"Missing reviewer Markdown fragment: {fragment!r}."),
            )

    if case_id not in markdown:
        append_issue(
            issues,
            case_id=case_id,
            category=("reviewer_markdown_case_id_mismatch"),
            detail=("Reviewer Markdown does not contain the case ID."),
        )

    review_count_fragment = f"**Findings requiring review:** {review_count}"

    if review_count_fragment not in markdown:
        append_issue(
            issues,
            case_id=case_id,
            category=("reviewer_markdown_count_mismatch"),
            detail=(f"Reviewer Markdown review count does not equal {review_count}."),
        )

    total_fragment = f"**Total findings:** {finding_count}"

    if total_fragment not in markdown:
        append_issue(
            issues,
            case_id=case_id,
            category=("reviewer_markdown_count_mismatch"),
            detail=(f"Reviewer Markdown total finding count does not equal {finding_count}."),
        )

    expected_status = "pending" if review_count > 0 else "not_required"

    status_fragment = f"**Review status:** `{expected_status}`"

    if status_fragment not in markdown:
        append_issue(
            issues,
            case_id=case_id,
            category=("reviewer_markdown_status_mismatch"),
            detail=(f"Reviewer Markdown review status should be {expected_status!r}."),
        )


def validate_one_acceptance_case(
    case_dir: Path,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
]:
    """Validate final report and human-review projection for one case."""

    case_id = case_dir.name

    issues: list[dict[str, Any]] = []

    #
    # First reuse the established Step-9A
    # integrity/provenance validator.
    #
    try:
        (
            regression_summary,
            regression_issues,
        ) = validate_one_case(case_dir)
    except Exception as exc:
        append_issue(
            issues,
            case_id=case_id,
            category=("acceptance_validator_exception"),
            detail=(f"{type(exc).__name__}: {exc}"),
        )

        return (
            {
                "case_id": case_id,
                "status": "FAIL",
            },
            issues,
        )

    issues.extend(regression_issues)

    #
    # Required output artifacts.
    #
    for filename in REQUIRED_CASE_ARTIFACTS:
        if not (case_dir / filename).exists():
            append_issue(
                issues,
                case_id=case_id,
                category=("missing_acceptance_artifact"),
                detail=(f"Missing required acceptance artifact: {filename}."),
            )

    report_path = case_dir / "final_investigation_report.json"

    bundle_path = case_dir / "reviewer_bundle.json"

    markdown_path = case_dir / "reviewer_report.md"

    if not (report_path.exists() and bundle_path.exists() and markdown_path.exists()):
        return (
            {
                "case_id": case_id,
                "status": "FAIL",
                "regression_status": (regression_summary.get("status")),
            },
            issues,
        )

    report = load_json(report_path)

    bundle = load_json(bundle_path)

    if not isinstance(
        report,
        dict,
    ):
        append_issue(
            issues,
            case_id=case_id,
            category=("invalid_final_report_schema"),
            detail=("Final report must contain a JSON object."),
        )

        return (
            {
                "case_id": case_id,
                "status": "FAIL",
            },
            issues,
        )

    if not isinstance(
        bundle,
        dict,
    ):
        append_issue(
            issues,
            case_id=case_id,
            category=("invalid_reviewer_bundle_schema"),
            detail=("Reviewer bundle must contain a JSON object."),
        )

        return (
            {
                "case_id": case_id,
                "status": "FAIL",
            },
            issues,
        )

    report_findings = get_report_findings(report)

    (
        expected_review_findings,
        expected_contextual_findings,
    ) = expected_review_partition(report_findings)

    (
        bundle_review_findings,
        bundle_contextual_findings,
    ) = bundle_findings(bundle)

    report_ids = finding_ids(report_findings)

    expected_review_ids = finding_ids(expected_review_findings)

    expected_contextual_ids = finding_ids(expected_contextual_findings)

    bundle_review_ids = finding_ids(bundle_review_findings)

    bundle_contextual_ids = finding_ids(bundle_contextual_findings)

    #
    # Final-report case identity.
    #
    report_case_id = str(
        report.get(
            "case_id",
            "",
        )
    )

    if report_case_id and report_case_id != case_id:
        append_issue(
            issues,
            case_id=case_id,
            category=("final_report_case_id_mismatch"),
            detail=(f"Final report case_id is {report_case_id!r}."),
        )

    #
    # Reviewer bundle case identity.
    #
    bundle_case_id = str(
        bundle.get(
            "case_id",
            "",
        )
    )

    if bundle_case_id and bundle_case_id != case_id:
        append_issue(
            issues,
            case_id=case_id,
            category=("reviewer_bundle_case_id_mismatch"),
            detail=(f"Reviewer bundle case_id is {bundle_case_id!r}."),
        )

    #
    # Finding IDs must remain unique.
    #
    if len(report_ids) != len(set(report_ids)):
        append_issue(
            issues,
            case_id=case_id,
            category=("duplicate_final_finding_id"),
            detail=("Final report contains duplicate finding IDs."),
        )

    #
    # Reviewer partition must be an exact
    # projection of machine findings.
    #
    if sorted(expected_review_ids) != sorted(bundle_review_ids):
        append_issue(
            issues,
            case_id=case_id,
            category=("review_required_projection_mismatch"),
            detail=(
                "Reviewer bundle review-required "
                "findings do not exactly match "
                "machine findings marked "
                "requires_human_review=true."
            ),
        )

    if sorted(expected_contextual_ids) != sorted(bundle_contextual_ids):
        append_issue(
            issues,
            case_id=case_id,
            category=("contextual_projection_mismatch"),
            detail=(
                "Reviewer bundle contextual "
                "findings do not exactly match "
                "the non-review-required machine "
                "findings."
            ),
        )

    #
    # Nothing may appear in both reviewer sections.
    #
    overlap = set(bundle_review_ids) & set(bundle_contextual_ids)

    if overlap:
        append_issue(
            issues,
            case_id=case_id,
            category=("reviewer_partition_overlap"),
            detail=(
                "Findings appear in both "
                "review-required and contextual "
                f"sections: {sorted(overlap)}."
            ),
        )

    #
    # Reviewer union must equal complete
    # machine finding population.
    #
    bundle_union = bundle_review_ids + bundle_contextual_ids

    if sorted(bundle_union) != sorted(report_ids):
        append_issue(
            issues,
            case_id=case_id,
            category=("reviewer_population_projection_mismatch"),
            detail=(
                "Reviewer bundle finding population does not exactly equal final report findings."
            ),
        )

    #
    # Persisted counts.
    #
    actual_finding_count = len(report_findings)

    actual_review_count = len(expected_review_findings)

    actual_contextual_count = len(expected_contextual_findings)

    if bundle.get("finding_count") != actual_finding_count:
        append_issue(
            issues,
            case_id=case_id,
            category=("reviewer_finding_count_mismatch"),
            detail=(
                f"Reviewer bundle finding_count="
                f"{bundle.get('finding_count')}; "
                f"actual={actual_finding_count}."
            ),
        )

    if bundle.get("review_finding_count") != actual_review_count:
        append_issue(
            issues,
            case_id=case_id,
            category=("reviewer_review_count_mismatch"),
            detail=(
                f"Reviewer bundle "
                f"review_finding_count="
                f"{bundle.get('review_finding_count')}; "
                f"actual={actual_review_count}."
            ),
        )

    #
    # If the bundle persists a review_status,
    # require it to agree with the machine
    # review routing decision.
    #
    bundle_status = bundle.get("review_status")

    expected_status = "pending" if actual_review_count > 0 else "not_required"

    if bundle_status is not None and bundle_status != expected_status:
        append_issue(
            issues,
            case_id=case_id,
            category=("reviewer_status_mismatch"),
            detail=(f"Reviewer bundle status is {bundle_status!r}; expected {expected_status!r}."),
        )

    #
    # Reviewer Markdown.
    #
    markdown = markdown_path.read_text(encoding="utf-8")

    validate_markdown(
        case_id=case_id,
        markdown=markdown,
        finding_count=(actual_finding_count),
        review_count=(actual_review_count),
        issues=issues,
    )

    #
    # Reviewer finding content must preserve
    # the machine finding identity and
    # core classification.
    #
    report_by_id = {
        finding_id(finding): finding for finding in report_findings if finding_id(finding)
    }

    for reviewer_finding in bundle_review_findings + bundle_contextual_findings:
        reviewer_id = finding_id(reviewer_finding)

        machine_finding = report_by_id.get(reviewer_id)

        if machine_finding is None:
            continue

        for field in (
            "finding_type",
            "subtype",
            "severity",
            "title",
            "summary",
            "requires_human_review",
        ):
            if field in reviewer_finding and reviewer_finding.get(field) != machine_finding.get(
                field
            ):
                append_issue(
                    issues,
                    case_id=case_id,
                    category=("reviewer_finding_content_mismatch"),
                    detail=(
                        f"Finding {reviewer_id} "
                        f"field {field!r} differs "
                        "between machine report "
                        "and reviewer bundle."
                    ),
                )

    case_summary = {
        "case_id": case_id,
        "status": ("PASS" if not issues else "FAIL"),
        "regression_status": (regression_summary.get("status")),
        "finding_count": (actual_finding_count),
        "review_required_findings": (actual_review_count),
        "contextual_findings": (actual_contextual_count),
        "requires_human_review": (actual_review_count > 0),
        "review_status": (expected_status),
        "issue_count": len(issues),
        "artifact_hashes": {
            "final_investigation_report.json": (sha256_file(report_path)),
            "reviewer_bundle.json": (sha256_file(bundle_path)),
            "reviewer_report.md": (sha256_file(markdown_path)),
        },
    }

    return (
        case_summary,
        issues,
    )


def all_production_hashes() -> dict[
    str,
    dict[str, str],
]:
    """Hash all acceptance artifacts before/after audit."""

    hashes: dict[
        str,
        dict[str, str],
    ] = {}

    for case_dir in case_dirs():
        case_hashes: dict[
            str,
            str,
        ] = {}

        for filename in REQUIRED_CASE_ARTIFACTS:
            path = case_dir / filename

            if path.exists():
                case_hashes[filename] = sha256_file(path)

        hashes[case_dir.name] = case_hashes

    return hashes


def main() -> int:
    """Run Step 9C acceptance audit."""

    load_required_pass(
        STEP_9A_PATH,
        "Step 9A",
    )

    load_required_pass(
        STEP_9B_FINAL_PATH,
        "Step 9B freeze",
    )

    hashes_before = all_production_hashes()

    cases = case_dirs()

    case_results: list[dict[str, Any]] = []

    issues: list[dict[str, Any]] = []

    for case_dir in cases:
        (
            case_summary,
            case_issues,
        ) = validate_one_acceptance_case(case_dir)

        case_results.append(case_summary)

        issues.extend(case_issues)

    hashes_after = all_production_hashes()

    production_outputs_unchanged = hashes_before == hashes_after

    cases_passed = sum(1 for result in case_results if result.get("status") == "PASS")

    cases_failed = len(case_results) - cases_passed

    total_findings = sum(
        int(
            result.get(
                "finding_count",
                0,
            )
        )
        for result in case_results
    )

    total_review_findings = sum(
        int(
            result.get(
                "review_required_findings",
                0,
            )
        )
        for result in case_results
    )

    total_contextual_findings = sum(
        int(
            result.get(
                "contextual_findings",
                0,
            )
        )
        for result in case_results
    )

    review_cases = sum(1 for result in case_results if result.get("requires_human_review") is True)

    no_review_cases = len(case_results) - review_cases

    #
    # Population-level frozen contract.
    #
    population_checks = {
        "case_count": (len(case_results) == EXPECTED_CASE_COUNT),
        "finding_count": (total_findings == EXPECTED_FINDING_COUNT),
        "review_finding_count": (total_review_findings == EXPECTED_REVIEW_FINDING_COUNT),
        "contextual_finding_count": (
            total_contextual_findings == EXPECTED_CONTEXTUAL_FINDING_COUNT
        ),
        "review_case_count": (review_cases == EXPECTED_REVIEW_CASE_COUNT),
    }

    for (
        field,
        passed,
    ) in population_checks.items():
        if passed:
            continue

        observed_values = {
            "case_count": (len(case_results)),
            "finding_count": (total_findings),
            "review_finding_count": (total_review_findings),
            "contextual_finding_count": (total_contextual_findings),
            "review_case_count": (review_cases),
        }

        expected_values = {
            "case_count": (EXPECTED_CASE_COUNT),
            "finding_count": (EXPECTED_FINDING_COUNT),
            "review_finding_count": (EXPECTED_REVIEW_FINDING_COUNT),
            "contextual_finding_count": (EXPECTED_CONTEXTUAL_FINDING_COUNT),
            "review_case_count": (EXPECTED_REVIEW_CASE_COUNT),
        }

        issues.append(
            {
                "case_id": None,
                "category": ("acceptance_population_regression"),
                "detail": (
                    f"{field}: expected "
                    f"{expected_values[field]}; "
                    f"observed "
                    f"{observed_values[field]}."
                ),
            }
        )

    if not production_outputs_unchanged:
        issues.append(
            {
                "case_id": None,
                "category": ("production_output_mutation"),
                "detail": (
                    "Step 9C changed one or more production-facing report/reviewer artifacts."
                ),
            }
        )

    issue_categories: Counter[str] = Counter(
        str(
            issue.get(
                "category",
                "",
            )
        )
        for issue in issues
        if issue.get("category")
    )

    #
    # Special release conditions:
    #
    # - all cases structurally valid
    # - exact machine→review projection
    # - exactly one review-required finding
    # - exactly one case routed to review
    # - all remaining findings contextual
    # - no output mutation caused by the audit
    #
    overall_pass = all(
        (
            len(case_results) == EXPECTED_CASE_COUNT,
            cases_failed == 0,
            total_findings == EXPECTED_FINDING_COUNT,
            total_review_findings == EXPECTED_REVIEW_FINDING_COUNT,
            total_contextual_findings == EXPECTED_CONTEXTUAL_FINDING_COUNT,
            review_cases == EXPECTED_REVIEW_CASE_COUNT,
            production_outputs_unchanged,
            len(issues) == 0,
        )
    )

    status = "PASS" if overall_pass else "FAIL"

    output = {
        "schema_version": ("1.0"),
        "acceptance_step": ("9C"),
        "acceptance_name": ("Final Report + Human-Review Acceptance"),
        "status": (status),
        "evaluated_at": (datetime.now(UTC).isoformat()),
        "prerequisites": {
            "9A": "PASS",
            "9B": "PASS",
        },
        "frozen_population_contract": {
            "expected_cases": (EXPECTED_CASE_COUNT),
            "expected_findings": (EXPECTED_FINDING_COUNT),
            "expected_review_required_findings": (EXPECTED_REVIEW_FINDING_COUNT),
            "expected_contextual_findings": (EXPECTED_CONTEXTUAL_FINDING_COUNT),
            "expected_review_cases": (EXPECTED_REVIEW_CASE_COUNT),
        },
        "population_results": {
            "cases": (len(case_results)),
            "cases_passed": (cases_passed),
            "cases_failed": (cases_failed),
            "findings": (total_findings),
            "review_required_findings": (total_review_findings),
            "contextual_findings": (total_contextual_findings),
            "cases_requiring_review": (review_cases),
            "cases_not_requiring_review": (no_review_cases),
        },
        "population_checks": (population_checks),
        "acceptance_criteria": {
            "all_cases_pass": (cases_failed == 0),
            "final_report_integrity_pass": all(
                result.get("regression_status") == "PASS" for result in case_results
            ),
            "machine_to_reviewer_projection_exact": (
                not any(
                    issue.get("category")
                    in {
                        "review_required_projection_mismatch",
                        "contextual_projection_mismatch",
                        "reviewer_population_projection_mismatch",
                        "reviewer_partition_overlap",
                    }
                    for issue in issues
                )
            ),
            "review_counts_consistent": (
                not any(
                    issue.get("category")
                    in {
                        "reviewer_finding_count_mismatch",
                        "reviewer_review_count_mismatch",
                        "reviewer_markdown_count_mismatch",
                    }
                    for issue in issues
                )
            ),
            "review_status_routing_consistent": (
                not any(
                    issue.get("category")
                    in {
                        "reviewer_status_mismatch",
                        "reviewer_markdown_status_mismatch",
                    }
                    for issue in issues
                )
            ),
            "reviewer_markdown_acceptable": (
                not any(
                    str(
                        issue.get(
                            "category",
                            "",
                        )
                    ).startswith("reviewer_markdown")
                    or issue.get("category") == "empty_reviewer_report"
                    for issue in issues
                )
            ),
            "frozen_population_preserved": (all(population_checks.values())),
            "machine_outputs_immutable": (production_outputs_unchanged),
            "zero_acceptance_issues": (len(issues) == 0),
        },
        "issue_summary": {
            "issue_count": (len(issues)),
            "categories": dict(sorted(issue_categories.items())),
        },
        "case_results": (case_results),
        "issues": (issues),
        "ready_for_9d": (overall_pass),
        "methodological_notes": [
            ("Step 9C is a read-only release acceptance audit."),
            (
                "The machine-generated final "
                "investigation report remains "
                "the immutable source report."
            ),
            (
                "Reviewer artifacts are validated "
                "as projections of machine findings "
                "rather than replacements for the "
                "machine report."
            ),
            (
                "A finding belongs in "
                "findings_requiring_review exactly "
                "when requires_human_review=true."
            ),
            ("All remaining findings must appear exactly once in the contextual reviewer section."),
            (
                "Reviewer Markdown must preserve "
                "case identity, total finding count, "
                "review-required count, and review "
                "routing status."
            ),
            (
                "The current release contract "
                "preserves the frozen population "
                "of 20 cases, 317 findings, "
                "1 review-required finding, and "
                "316 contextual findings."
            ),
            (
                "Acceptance of this deterministic "
                "test population does not establish "
                "universal clinical validity."
            ),
        ],
    }

    write_json(
        OUTPUT_PATH,
        output,
    )

    print()
    print("=" * 72)
    print("STEP 9C — FINAL REPORT + HUMAN-REVIEW ACCEPTANCE")
    print("=" * 72)

    print(f"Overall status:                   {status}")

    print()
    print("Prerequisites")
    print("-" * 72)

    print("Step 9A status:                   PASS")

    print("Step 9B status:                   PASS")

    print()
    print("Case acceptance")
    print("-" * 72)

    print(f"Cases evaluated:                  {len(case_results)}")

    print(f"Cases passed:                     {cases_passed}")

    print(f"Cases failed:                     {cases_failed}")

    print()
    print("Finding population")
    print("-" * 72)

    print(f"Total findings:                   {total_findings} / {EXPECTED_FINDING_COUNT}")

    print(
        "Review-required findings:         "
        f"{total_review_findings}"
        f" / {EXPECTED_REVIEW_FINDING_COUNT}"
    )

    print(
        "Contextual findings:              "
        f"{total_contextual_findings}"
        f" / {EXPECTED_CONTEXTUAL_FINDING_COUNT}"
    )

    print(f"Cases requiring review:           {review_cases} / {EXPECTED_REVIEW_CASE_COUNT}")

    print()
    print("Integrity")
    print("-" * 72)

    print(f"Machine outputs unchanged:        {production_outputs_unchanged}")

    print(f"Acceptance issues:                {len(issues)}")

    print()
    print(f"Ready for Step 9D:                {overall_pass}")

    print()
    print("Saved Step-9C result to:")

    print(OUTPUT_PATH)

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())

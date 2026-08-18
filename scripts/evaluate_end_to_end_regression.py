from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

STEP_8_FREEZE_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "step_8_final" / "step_8_final_summary.json"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "step_9a"

OUTPUT_PATH = OUTPUT_DIR / "end_to_end_regression.json"


REQUIRED_JSON_ARTIFACTS = (
    "evidence_items.json",
    "clinical_claims.json",
    "canonical_timeline.json",
    "medication_mentions.json",
    "medication_profiles.json",
    "medication_discrepancies.json",
    "medication_reconciliation_manifest.json",
    "final_investigation_report.json",
    "reviewer_bundle.json",
)

REQUIRED_TEXT_ARTIFACTS = ("reviewer_report.md",)


def load_json(
    path: Path,
) -> Any:
    """Load one JSON artifact."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def sha256_file(
    path: Path,
) -> str:
    """Return SHA-256 digest for one file."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def as_dict_list(
    value: Any,
) -> list[dict[str, Any]]:
    """Return dictionary records from a JSON list."""

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


def get_report_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all findings from one final report."""

    findings: list[dict[str, Any]] = []

    findings.extend(
        as_dict_list(
            report.get(
                "high_priority_findings",
                [],
            )
        )
    )

    findings.extend(
        as_dict_list(
            report.get(
                "other_findings",
                [],
            )
        )
    )

    return findings


def get_bundle_findings(
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all projected findings from reviewer bundle."""

    findings: list[dict[str, Any]] = []

    for key in (
        "findings_requiring_review",
        "contextual_findings",
    ):
        findings.extend(
            as_dict_list(
                bundle.get(
                    key,
                    [],
                )
            )
        )

    return findings


def get_id_set(
    records: list[dict[str, Any]],
    key: str,
) -> set[str]:
    """Extract non-empty IDs from records."""

    return {
        str(
            record.get(
                key,
                "",
            )
        )
        for record in records
        if record.get(key)
    }


def append_issue(
    issues: list[dict[str, Any]],
    *,
    case_id: str,
    category: str,
    detail: str,
) -> None:
    """Append one regression issue."""

    issues.append(
        {
            "case_id": case_id,
            "category": category,
            "detail": detail,
        }
    )


def validate_case_id_records(
    *,
    case_id: str,
    artifact_name: str,
    records: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    """Validate case IDs inside an artifact."""

    for index, record in enumerate(records):
        record_case_id = str(
            record.get(
                "case_id",
                "",
            )
        )

        if record_case_id and record_case_id != case_id:
            append_issue(
                issues,
                case_id=case_id,
                category=("case_id_mismatch"),
                detail=(f"{artifact_name}[{index}] has case_id {record_case_id!r}."),
            )


def validate_finding_provenance(
    *,
    case_id: str,
    findings: list[dict[str, Any]],
    evidence_ids: set[str],
    claim_ids: set[str],
    event_ids: set[str],
    issues: list[dict[str, Any]],
) -> None:
    """Validate finding provenance references."""

    for finding in findings:
        finding_id = str(
            finding.get(
                "finding_id",
                "",
            )
        )

        for evidence_id in (
            finding.get(
                "evidence_ids",
                [],
            )
            or []
        ):
            value = str(evidence_id)

            if value and value not in evidence_ids:
                append_issue(
                    issues,
                    case_id=case_id,
                    category=("unresolved_evidence_reference"),
                    detail=(f"Finding {finding_id} references missing evidence {value}."),
                )

        for claim_id in (
            finding.get(
                "claim_ids",
                [],
            )
            or []
        ):
            value = str(claim_id)

            if value and value not in claim_ids:
                append_issue(
                    issues,
                    case_id=case_id,
                    category=("unresolved_claim_reference"),
                    detail=(f"Finding {finding_id} references missing claim {value}."),
                )

        for event_id in (
            finding.get(
                "event_ids",
                [],
            )
            or []
        ):
            value = str(event_id)

            if value and value not in event_ids:
                append_issue(
                    issues,
                    case_id=case_id,
                    category=("unresolved_timeline_reference"),
                    detail=(f"Finding {finding_id} references missing timeline event {value}."),
                )


def validate_reviewer_projection(
    *,
    case_id: str,
    report_findings: list[dict[str, Any]],
    bundle_findings: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    """Validate reviewer bundle against final report."""

    report_by_id = {
        str(
            finding.get(
                "finding_id",
                "",
            )
        ): finding
        for finding in report_findings
        if finding.get("finding_id")
    }

    bundle_by_id = {
        str(
            finding.get(
                "finding_id",
                "",
            )
        ): finding
        for finding in bundle_findings
        if finding.get("finding_id")
    }

    if set(report_by_id) != set(bundle_by_id):
        missing_from_bundle = sorted(set(report_by_id) - set(bundle_by_id))

        extra_in_bundle = sorted(set(bundle_by_id) - set(report_by_id))

        append_issue(
            issues,
            case_id=case_id,
            category=("reviewer_projection_mismatch"),
            detail=(
                "Final report and reviewer "
                "bundle finding IDs differ. "
                f"Missing from bundle="
                f"{missing_from_bundle}; "
                f"extra in bundle="
                f"{extra_in_bundle}."
            ),
        )


def validate_one_case(
    case_dir: Path,
) -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
]:
    """Run end-to-end acceptance checks for one case."""

    case_id = case_dir.name

    issues: list[dict[str, Any]] = []

    artifact_hashes: dict[
        str,
        str,
    ] = {}

    loaded: dict[
        str,
        Any,
    ] = {}

    #
    # Required JSON artifacts.
    #
    for filename in REQUIRED_JSON_ARTIFACTS:
        path = case_dir / filename

        if not path.exists():
            append_issue(
                issues,
                case_id=case_id,
                category=("missing_artifact"),
                detail=(f"Missing required artifact: {filename}"),
            )
            continue

        artifact_hashes[filename] = sha256_file(path)

        try:
            loaded[filename] = load_json(path)
        except (
            OSError,
            json.JSONDecodeError,
        ) as exc:
            append_issue(
                issues,
                case_id=case_id,
                category=("invalid_json"),
                detail=(f"{filename}: {exc}"),
            )

    #
    # Required text artifacts.
    #
    for filename in REQUIRED_TEXT_ARTIFACTS:
        path = case_dir / filename

        if not path.exists():
            append_issue(
                issues,
                case_id=case_id,
                category=("missing_artifact"),
                detail=(f"Missing required artifact: {filename}"),
            )
            continue

        artifact_hashes[filename] = sha256_file(path)

        try:
            text = path.read_text(
                encoding="utf-8",
            )
        except OSError as exc:
            append_issue(
                issues,
                case_id=case_id,
                category=("unreadable_artifact"),
                detail=(f"{filename}: {exc}"),
            )
            continue

        if not text.strip():
            append_issue(
                issues,
                case_id=case_id,
                category=("empty_artifact"),
                detail=(f"{filename} is empty."),
            )

    evidence_items = as_dict_list(loaded.get("evidence_items.json"))

    clinical_claims = as_dict_list(loaded.get("clinical_claims.json"))

    timeline = as_dict_list(loaded.get("canonical_timeline.json"))

    medication_mentions = as_dict_list(loaded.get("medication_mentions.json"))

    medication_profiles = as_dict_list(loaded.get("medication_profiles.json"))

    medication_discrepancies = as_dict_list(loaded.get("medication_discrepancies.json"))

    #
    # Case-ID consistency.
    #
    for (
        artifact_name,
        records,
    ) in (
        (
            "evidence_items.json",
            evidence_items,
        ),
        (
            "clinical_claims.json",
            clinical_claims,
        ),
        (
            "canonical_timeline.json",
            timeline,
        ),
        (
            "medication_mentions.json",
            medication_mentions,
        ),
        (
            "medication_profiles.json",
            medication_profiles,
        ),
        (
            "medication_discrepancies.json",
            medication_discrepancies,
        ),
    ):
        validate_case_id_records(
            case_id=case_id,
            artifact_name=(artifact_name),
            records=records,
            issues=issues,
        )

    evidence_ids = get_id_set(
        evidence_items,
        "evidence_id",
    )

    claim_ids = get_id_set(
        clinical_claims,
        "claim_id",
    )

    event_ids = get_id_set(
        timeline,
        "event_id",
    )

    #
    # Final report.
    #
    report_value = loaded.get("final_investigation_report.json")

    if isinstance(
        report_value,
        dict,
    ):
        report = report_value
    else:
        report = {}

        if report_value is not None:
            append_issue(
                issues,
                case_id=case_id,
                category=("invalid_report_schema"),
                detail=("final_investigation_report.json must contain a JSON object."),
            )

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
            category=("case_id_mismatch"),
            detail=(f"Final report case_id is {report_case_id!r}."),
        )

    report_findings = get_report_findings(report)

    finding_ids = [
        str(
            finding.get(
                "finding_id",
                "",
            )
        )
        for finding in report_findings
        if finding.get("finding_id")
    ]

    if len(finding_ids) != len(set(finding_ids)):
        append_issue(
            issues,
            case_id=case_id,
            category=("duplicate_finding_id"),
            detail=("Final report contains duplicate finding IDs."),
        )

    persisted_finding_count = report.get("finding_count")

    if persisted_finding_count != len(report_findings):
        append_issue(
            issues,
            case_id=case_id,
            category=("finding_count_mismatch"),
            detail=(f"finding_count={persisted_finding_count}; actual={len(report_findings)}."),
        )

    review_findings = [
        finding
        for finding in report_findings
        if bool(
            finding.get(
                "requires_human_review",
                False,
            )
        )
    ]

    persisted_review_count = report.get("review_finding_count")

    if persisted_review_count != len(review_findings):
        append_issue(
            issues,
            case_id=case_id,
            category=("review_count_mismatch"),
            detail=(
                f"review_finding_count={persisted_review_count}; actual={len(review_findings)}."
            ),
        )

    validation_errors = (
        report.get(
            "validation_errors",
            [],
        )
        or []
    )

    if validation_errors:
        append_issue(
            issues,
            case_id=case_id,
            category=("validation_error"),
            detail=(f"Final report contains validation errors: {validation_errors}"),
        )

    validate_finding_provenance(
        case_id=case_id,
        findings=(report_findings),
        evidence_ids=(evidence_ids),
        claim_ids=(claim_ids),
        event_ids=(event_ids),
        issues=issues,
    )

    #
    # Reviewer bundle.
    #
    bundle_value = loaded.get("reviewer_bundle.json")

    if isinstance(
        bundle_value,
        dict,
    ):
        bundle = bundle_value
    else:
        bundle = {}

        if bundle_value is not None:
            append_issue(
                issues,
                case_id=case_id,
                category=("invalid_reviewer_schema"),
                detail=("reviewer_bundle.json must contain a JSON object."),
            )

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
            category=("case_id_mismatch"),
            detail=(f"Reviewer bundle case_id is {bundle_case_id!r}."),
        )

    bundle_findings = get_bundle_findings(bundle)

    validate_reviewer_projection(
        case_id=case_id,
        report_findings=(report_findings),
        bundle_findings=(bundle_findings),
        issues=issues,
    )

    #
    # Medication manifest.
    #
    medication_manifest_value = loaded.get("medication_reconciliation_manifest.json")

    if isinstance(
        medication_manifest_value,
        dict,
    ):
        medication_manifest = medication_manifest_value

        manifest_case_id = str(
            medication_manifest.get(
                "case_id",
                "",
            )
        )

        if manifest_case_id and manifest_case_id != case_id:
            append_issue(
                issues,
                case_id=case_id,
                category=("case_id_mismatch"),
                detail=(f"Medication manifest case_id is {manifest_case_id!r}."),
            )

        expected_counts = {
            "medication_mention_count": (len(medication_mentions)),
            "medication_profile_count": (len(medication_profiles)),
            "discrepancy_count": (len(medication_discrepancies)),
        }

        for (
            field,
            actual_count,
        ) in expected_counts.items():
            persisted_count = medication_manifest.get(field)

            if persisted_count != actual_count:
                append_issue(
                    issues,
                    case_id=case_id,
                    category=("medication_manifest_count_mismatch"),
                    detail=(f"{field}={persisted_count}; actual={actual_count}."),
                )

    case_summary = {
        "case_id": case_id,
        "status": ("PASS" if not issues else "FAIL"),
        "evidence_items": (len(evidence_items)),
        "clinical_claims": (len(clinical_claims)),
        "timeline_events": (len(timeline)),
        "medication_mentions": (len(medication_mentions)),
        "medication_profiles": (len(medication_profiles)),
        "medication_discrepancies": (len(medication_discrepancies)),
        "findings": (len(report_findings)),
        "review_required_findings": (len(review_findings)),
        "artifact_hashes": (artifact_hashes),
        "issue_count": (len(issues)),
    }

    return (
        case_summary,
        issues,
    )


def main() -> int:
    """Run simplified Step 9A regression."""

    if not (STEP_8_FREEZE_PATH.exists()):
        raise FileNotFoundError(f"Step-8 final freeze not found: {STEP_8_FREEZE_PATH}")

    step_8 = load_json(STEP_8_FREEZE_PATH)

    if not isinstance(
        step_8,
        dict,
    ):
        raise ValueError("Step-8 final summary must be a JSON object.")

    step_8_status = step_8.get("overall_status") or step_8.get("status")

    final_population = step_8.get(
        "final_population",
        {},
    )

    if not isinstance(
        final_population,
        dict,
    ):
        final_population = {}

    expected_cases = final_population.get("cases")

    expected_findings = final_population.get("findings")

    expected_review_required = final_population.get("review_required_findings")

    expected_contextual = final_population.get("contextual_findings")

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    case_dirs = sorted(path for path in (CASE_ROOT.iterdir()) if path.is_dir())

    case_results: list[dict[str, Any]] = []

    issues: list[dict[str, Any]] = []

    for case_dir in case_dirs:
        try:
            (
                case_result,
                case_issues,
            ) = validate_one_case(case_dir)
        except Exception as exc:
            case_result = {
                "case_id": (case_dir.name),
                "status": "FAIL",
                "issue_count": 1,
            }

            case_issues = [
                {
                    "case_id": (case_dir.name),
                    "category": ("unhandled_case_exception"),
                    "detail": (f"{type(exc).__name__}: {exc}"),
                }
            ]

        case_results.append(case_result)

        issues.extend(case_issues)

    total_cases = len(case_results)

    total_findings = sum(
        int(
            item.get(
                "findings",
                0,
            )
            or 0
        )
        for item in case_results
    )

    total_review_required = sum(
        int(
            item.get(
                "review_required_findings",
                0,
            )
            or 0
        )
        for item in case_results
    )

    total_contextual = total_findings - total_review_required

    passed_cases = sum(1 for item in case_results if item.get("status") == "PASS")

    failed_cases = total_cases - passed_cases

    issue_counts = Counter(
        str(
            issue.get(
                "category",
                "unknown",
            )
        )
        for issue in issues
    )

    population_regressions: list[dict[str, Any]] = []

    for (
        metric,
        expected,
        actual,
    ) in (
        (
            "cases",
            expected_cases,
            total_cases,
        ),
        (
            "findings",
            expected_findings,
            total_findings,
        ),
        (
            "review_required_findings",
            expected_review_required,
            total_review_required,
        ),
        (
            "contextual_findings",
            expected_contextual,
            total_contextual,
        ),
    ):
        if expected is not None and expected != actual:
            population_regressions.append(
                {
                    "metric": metric,
                    "expected": expected,
                    "actual": actual,
                }
            )

    overall_pass = all(
        (
            step_8_status == "PASS",
            failed_cases == 0,
            len(issues) == 0,
            len(population_regressions) == 0,
            (expected_cases is None or total_cases == expected_cases),
        )
    )

    status = "PASS" if overall_pass else "FAIL"

    output = {
        "schema_version": "1.0",
        "acceptance_step": "9A",
        "acceptance_name": ("Full End-to-End Regression"),
        "status": status,
        "evaluated_at": (datetime.now(UTC).isoformat()),
        "step_8_release_gate": {
            "path": str(STEP_8_FREEZE_PATH.relative_to(PROJECT_ROOT)),
            "status": (step_8_status),
            "sha256": sha256_file(STEP_8_FREEZE_PATH),
        },
        "expected_population": {
            "cases": (expected_cases),
            "findings": (expected_findings),
            "review_required_findings": (expected_review_required),
            "contextual_findings": (expected_contextual),
        },
        "observed_population": {
            "cases": (total_cases),
            "passed_cases": (passed_cases),
            "failed_cases": (failed_cases),
            "findings": (total_findings),
            "review_required_findings": (total_review_required),
            "contextual_findings": (total_contextual),
        },
        "regression_summary": {
            "population_regression_count": (len(population_regressions)),
            "artifact_or_integrity_issue_count": (len(issues)),
            "issue_counts_by_category": (dict(sorted(issue_counts.items()))),
        },
        "population_regressions": (population_regressions),
        "issues": (issues),
        "case_results": (case_results),
        "acceptance_gate": {
            "all_cases_complete": (failed_cases == 0),
            "population_matches_step_8": (not population_regressions),
            "artifact_integrity_pass": (not issues),
            "ready_for_9B": (overall_pass),
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
    print("STEP 9A — FULL END-TO-END REGRESSION")
    print("=" * 72)

    print(f"Overall status:                   {status}")

    print()
    print("Release baseline")
    print("-" * 72)

    print(f"Step-8 freeze:                    {step_8_status}")

    print()
    print("Case execution / artifact state")
    print("-" * 72)

    print(f"Cases evaluated:                  {total_cases}")

    print(f"Cases passed:                     {passed_cases}")

    print(f"Cases failed:                     {failed_cases}")

    print()
    print("Population regression")
    print("-" * 72)

    print(f"Findings expected / observed:     {expected_findings} / {total_findings}")

    print(
        f"Review-required expected / observed: {expected_review_required} / {total_review_required}"
    )

    print(f"Contextual expected / observed:   {expected_contextual} / {total_contextual}")

    print()
    print("Integrity")
    print("-" * 72)

    print(f"Population regressions:           {len(population_regressions)}")

    print(f"Artifact/integrity issues:        {len(issues)}")

    print()
    print(f"Ready for Step 9B:                {overall_pass}")

    print()
    print("Saved Step-9A result to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

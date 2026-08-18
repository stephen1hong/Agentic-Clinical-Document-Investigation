from __future__ import annotations

import json
import shutil
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

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "step_9b1"

WORKSPACE_DIR = OUTPUT_DIR / "workspace"

OUTPUT_PATH = OUTPUT_DIR / "missing_partial_artifact_robustness.json"


MISSING_ARTIFACT_MUTATIONS = (
    (
        "missing_evidence_items",
        "evidence_items.json",
        "missing_artifact",
    ),
    (
        "missing_clinical_claims",
        "clinical_claims.json",
        "missing_artifact",
    ),
    (
        "missing_canonical_timeline",
        "canonical_timeline.json",
        "missing_artifact",
    ),
    (
        "missing_medication_mentions",
        "medication_mentions.json",
        "missing_artifact",
    ),
    (
        "missing_medication_profiles",
        "medication_profiles.json",
        "missing_artifact",
    ),
    (
        "missing_medication_discrepancies",
        "medication_discrepancies.json",
        "missing_artifact",
    ),
    (
        "missing_medication_manifest",
        "medication_reconciliation_manifest.json",
        "missing_artifact",
    ),
    (
        "missing_final_report",
        "final_investigation_report.json",
        "missing_artifact",
    ),
    (
        "missing_reviewer_bundle",
        "reviewer_bundle.json",
        "missing_artifact",
    ),
    (
        "missing_reviewer_report",
        "reviewer_report.md",
        "missing_artifact",
    ),
)


def write_json(
    path: Path,
    payload: Any,
) -> None:
    """Persist deterministic formatted JSON."""

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
    artifact: dict[str, Any],
) -> str | None:
    """Read status from current or legacy artifact schemas."""

    status = artifact.get("status")

    if isinstance(
        status,
        str,
    ):
        return status

    overall_status = artifact.get("overall_status")

    if isinstance(
        overall_status,
        str,
    ):
        return overall_status

    return None


def choose_reference_case() -> Path:
    """Choose a complete case with the largest finding population."""

    candidates: list[tuple[int, str, Path]] = []

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        report_path = case_dir / "final_investigation_report.json"

        bundle_path = case_dir / "reviewer_bundle.json"

        reviewer_report_path = case_dir / "reviewer_report.md"

        if not (report_path.exists() and bundle_path.exists() and reviewer_report_path.exists()):
            continue

        report = load_json(report_path)

        if not isinstance(
            report,
            dict,
        ):
            continue

        finding_count = len(get_report_findings(report))

        candidates.append(
            (
                finding_count,
                case_dir.name,
                case_dir,
            )
        )

    if not candidates:
        raise RuntimeError("No complete investigation case is available for Step 9B.1.")

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    return candidates[0][2]


def copy_case_for_mutation(
    *,
    source_case: Path,
    mutation_name: str,
) -> Path:
    """Copy one production case into an isolated mutation workspace."""

    mutation_root = WORKSPACE_DIR / mutation_name

    mutation_case = mutation_root / source_case.name

    if mutation_root.exists():
        shutil.rmtree(mutation_root)

    mutation_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copytree(
        source_case,
        mutation_case,
    )

    return mutation_case


def issue_categories(
    issues: list[dict[str, Any]],
) -> set[str]:
    """Return unique issue categories."""

    return {
        str(
            issue.get(
                "category",
                "",
            )
        )
        for issue in issues
        if issue.get("category")
    }


def run_missing_artifact_mutation(
    *,
    source_case: Path,
    mutation_name: str,
    filename: str,
    expected_category: str,
) -> dict[str, Any]:
    """Delete one artifact and verify fail-closed behavior."""

    mutation_case = copy_case_for_mutation(
        source_case=source_case,
        mutation_name=mutation_name,
    )

    target_path = mutation_case / filename

    if not target_path.exists():
        return {
            "mutation": mutation_name,
            "status": "FAIL",
            "reason": (f"Reference case does not contain {filename}."),
            "expected_category": (expected_category),
            "detected_categories": [],
        }

    target_path.unlink()

    case_result, issues = validate_one_case(mutation_case)

    categories = issue_categories(issues)

    expected_detected = expected_category in categories

    failed_closed = case_result.get("status") == "FAIL"

    passed = expected_detected and failed_closed

    return {
        "mutation": mutation_name,
        "mutation_type": ("missing_artifact"),
        "artifact": filename,
        "expected_category": (expected_category),
        "validator_status": (case_result.get("status")),
        "issue_count": len(issues),
        "detected_categories": (sorted(categories)),
        "expected_category_detected": (expected_detected),
        "failed_closed": (failed_closed),
        "status": ("PASS" if passed else "FAIL"),
        "issues": issues,
    }


def run_empty_reviewer_report_mutation(
    *,
    source_case: Path,
) -> dict[str, Any]:
    """Verify an empty reviewer report is rejected."""

    mutation_name = "empty_reviewer_report"

    mutation_case = copy_case_for_mutation(
        source_case=source_case,
        mutation_name=mutation_name,
    )

    target_path = mutation_case / "reviewer_report.md"

    target_path.write_text(
        "",
        encoding="utf-8",
    )

    case_result, issues = validate_one_case(mutation_case)

    categories = issue_categories(issues)

    expected_category = "empty_artifact"

    expected_detected = expected_category in categories

    failed_closed = case_result.get("status") == "FAIL"

    passed = expected_detected and failed_closed

    return {
        "mutation": mutation_name,
        "mutation_type": ("partial_artifact"),
        "artifact": ("reviewer_report.md"),
        "expected_category": (expected_category),
        "validator_status": (case_result.get("status")),
        "issue_count": len(issues),
        "detected_categories": (sorted(categories)),
        "expected_category_detected": (expected_detected),
        "failed_closed": (failed_closed),
        "status": ("PASS" if passed else "FAIL"),
        "issues": issues,
    }


def get_bundle_findings(
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all findings from the actual reviewer-bundle schema."""

    findings: list[dict[str, Any]] = []

    for key in (
        "findings_requiring_review",
        "contextual_findings",
    ):
        value = bundle.get(
            key,
            [],
        )

        if isinstance(
            value,
            list,
        ):
            findings.extend(
                item
                for item in value
                if isinstance(
                    item,
                    dict,
                )
            )

    return findings


def run_partial_reviewer_bundle_mutation(
    *,
    source_case: Path,
) -> dict[str, Any]:
    """Remove one finding from reviewer projection."""

    mutation_name = "partial_reviewer_bundle"

    mutation_case = copy_case_for_mutation(
        source_case=source_case,
        mutation_name=mutation_name,
    )

    bundle_path = mutation_case / "reviewer_bundle.json"

    bundle = load_json(bundle_path)

    if not isinstance(
        bundle,
        dict,
    ):
        return {
            "mutation": mutation_name,
            "status": "FAIL",
            "reason": ("Reviewer bundle is not a JSON object."),
        }

    review_findings = bundle.get(
        "findings_requiring_review",
        [],
    )

    contextual_findings = bundle.get(
        "contextual_findings",
        [],
    )

    removed_finding_id: str | None = None

    if (
        isinstance(
            contextual_findings,
            list,
        )
        and contextual_findings
    ):
        removed = contextual_findings.pop()

        if isinstance(
            removed,
            dict,
        ):
            removed_finding_id = str(
                removed.get(
                    "finding_id",
                    "",
                )
            )

    elif (
        isinstance(
            review_findings,
            list,
        )
        and review_findings
    ):
        removed = review_findings.pop()

        if isinstance(
            removed,
            dict,
        ):
            removed_finding_id = str(
                removed.get(
                    "finding_id",
                    "",
                )
            )

    else:
        return {
            "mutation": mutation_name,
            "status": "FAIL",
            "reason": ("Reference reviewer bundle contains no findings to remove."),
        }

    write_json(
        bundle_path,
        bundle,
    )

    case_result, issues = validate_one_case(mutation_case)

    categories = issue_categories(issues)

    expected_category = "reviewer_projection_mismatch"

    expected_detected = expected_category in categories

    failed_closed = case_result.get("status") == "FAIL"

    passed = expected_detected and failed_closed

    return {
        "mutation": mutation_name,
        "mutation_type": ("partial_artifact"),
        "artifact": ("reviewer_bundle.json"),
        "removed_finding_id": (removed_finding_id),
        "remaining_bundle_findings": (len(get_bundle_findings(bundle))),
        "expected_category": (expected_category),
        "validator_status": (case_result.get("status")),
        "issue_count": len(issues),
        "detected_categories": (sorted(categories)),
        "expected_category_detected": (expected_detected),
        "failed_closed": (failed_closed),
        "status": ("PASS" if passed else "FAIL"),
        "issues": issues,
    }


def main() -> int:
    """Run Step 9B.1 missing/partial artifact robustness tests."""

    if not (STEP_9A_PATH.exists()):
        raise FileNotFoundError(f"Step 9A result not found: {STEP_9A_PATH}")

    step_9a = load_json(STEP_9A_PATH)

    if not isinstance(
        step_9a,
        dict,
    ):
        raise ValueError("Step 9A result must contain a JSON object.")

    step_9a_status = artifact_status(step_9a)

    if step_9a_status != "PASS":
        raise RuntimeError("Step 9B.1 requires a PASS Step 9A baseline.")

    reference_case = choose_reference_case()

    baseline_hashes = {
        path.name: (sha256_file(path)) for path in (reference_case.iterdir()) if path.is_file()
    }

    if WORKSPACE_DIR.exists():
        shutil.rmtree(WORKSPACE_DIR)

    WORKSPACE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    mutation_results: list[dict[str, Any]] = []

    for (
        mutation_name,
        filename,
        expected_category,
    ) in MISSING_ARTIFACT_MUTATIONS:
        mutation_results.append(
            run_missing_artifact_mutation(
                source_case=(reference_case),
                mutation_name=(mutation_name),
                filename=filename,
                expected_category=(expected_category),
            )
        )

    mutation_results.append(run_empty_reviewer_report_mutation(source_case=(reference_case)))

    mutation_results.append(run_partial_reviewer_bundle_mutation(source_case=(reference_case)))

    post_test_hashes = {
        path.name: (sha256_file(path)) for path in (reference_case.iterdir()) if path.is_file()
    }

    production_case_unchanged = baseline_hashes == post_test_hashes

    passed_mutations = sum(1 for result in mutation_results if result.get("status") == "PASS")

    failed_mutations = len(mutation_results) - passed_mutations

    category_counts = Counter()

    for result in mutation_results:
        for category in (
            result.get(
                "detected_categories",
                [],
            )
            or []
        ):
            category_counts[str(category)] += 1

    overall_pass = all(
        (
            step_9a_status == "PASS",
            production_case_unchanged,
            failed_mutations == 0,
            len(mutation_results) == (len(MISSING_ARTIFACT_MUTATIONS) + 2),
        )
    )

    status = "PASS" if overall_pass else "FAIL"

    output = {
        "schema_version": "1.0",
        "acceptance_step": "9B.1",
        "acceptance_name": ("Missing and Partial Artifact Robustness"),
        "status": status,
        "evaluated_at": (datetime.now(UTC).isoformat()),
        "baseline": {
            "step_9a_path": str(STEP_9A_PATH.relative_to(PROJECT_ROOT)),
            "step_9a_status": (step_9a_status),
            "reference_case": (reference_case.name),
            "reference_case_file_count": (len(baseline_hashes)),
        },
        "mutation_summary": {
            "mutations": (len(mutation_results)),
            "passed": (passed_mutations),
            "failed": (failed_mutations),
            "production_case_unchanged": (production_case_unchanged),
            "detected_issue_categories": dict(sorted(category_counts.items())),
        },
        "acceptance_criteria": {
            "all_mutations_fail_closed": (failed_mutations == 0),
            "expected_issue_detected": (
                all(
                    bool(
                        result.get(
                            "expected_category_detected",
                            False,
                        )
                    )
                    for result in mutation_results
                )
            ),
            "production_artifacts_immutable": (production_case_unchanged),
        },
        "mutation_results": (mutation_results),
        "ready_for_9b2": (overall_pass),
        "methodological_notes": [
            (
                "All mutations are performed "
                "on isolated copies under the "
                "Step 9B.1 evaluation workspace."
            ),
            (
                "No file under the production "
                "data/investigation_cases tree "
                "is intentionally modified."
            ),
            (
                "This substep tests fail-closed "
                "detection of missing and partial "
                "persisted artifacts. It does not "
                "yet test malformed JSON or "
                "schema-invalid content; those "
                "belong to Step 9B.2."
            ),
        ],
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
    print("STEP 9B.1 — MISSING / PARTIAL ARTIFACT ROBUSTNESS")
    print("=" * 72)

    print(f"Overall status:                   {status}")

    print()
    print("Baseline")
    print("-" * 72)

    print(f"Step 9A status:                   {step_9a_status}")

    print(f"Reference case:                   {reference_case.name}")

    print()
    print("Mutation results")
    print("-" * 72)

    print(f"Mutations executed:               {len(mutation_results)}")

    print(f"Mutations passed:                 {passed_mutations}")

    print(f"Mutations failed:                 {failed_mutations}")

    print()
    print("Safety")
    print("-" * 72)

    print(f"Production case unchanged:        {production_case_unchanged}")

    print()
    print(f"Ready for Step 9B.2:              {overall_pass}")

    print()
    print("Saved Step-9B.1 result to:")

    print(OUTPUT_PATH)

    #
    # Remove mutation copies after the
    # result artifact has been persisted.
    #
    if WORKSPACE_DIR.exists():
        shutil.rmtree(WORKSPACE_DIR)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

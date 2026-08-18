from __future__ import annotations

import json
import shutil
from collections import Counter
from collections.abc import Callable
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

STEP_9B1_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "step_9b1" / "missing_partial_artifact_robustness.json"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "step_9b2"

WORKSPACE_DIR = OUTPUT_DIR / "workspace"

OUTPUT_PATH = OUTPUT_DIR / "malformed_schema_robustness.json"


MutationFunction = Callable[
    [Path],
    None,
]


def write_json(
    path: Path,
    payload: Any,
) -> None:
    """Write deterministic JSON."""

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
    """Read PASS/FAIL status across evaluation schemas."""

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
    """Choose a complete case with many findings."""

    candidates: list[tuple[int, str, Path]] = []

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        required_paths = (
            case_dir / "evidence_items.json",
            case_dir / "clinical_claims.json",
            case_dir / "canonical_timeline.json",
            case_dir / "medication_mentions.json",
            case_dir / "medication_profiles.json",
            case_dir / "medication_discrepancies.json",
            case_dir / "medication_reconciliation_manifest.json",
            case_dir / "final_investigation_report.json",
            case_dir / "reviewer_bundle.json",
            case_dir / "reviewer_report.md",
        )

        if not all(path.exists() for path in required_paths):
            continue

        report = load_json(case_dir / "final_investigation_report.json")

        if not isinstance(
            report,
            dict,
        ):
            continue

        candidates.append(
            (
                len(get_report_findings(report)),
                case_dir.name,
                case_dir,
            )
        )

    if not candidates:
        raise RuntimeError("No complete investigation case is available.")

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    return candidates[0][2]


def copy_case(
    *,
    source_case: Path,
    mutation_name: str,
) -> Path:
    """Create isolated case copy."""

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
    """Return detected issue categories."""

    return {str(issue.get("category")) for issue in issues if issue.get("category")}


#
# ------------------------------------------------------------
# Mutation functions
# ------------------------------------------------------------
#


def malformed_evidence_json(
    case_dir: Path,
) -> None:
    """Corrupt evidence JSON syntax."""

    (case_dir / "evidence_items.json").write_text(
        '{"broken": ',
        encoding="utf-8",
    )


def malformed_final_report_json(
    case_dir: Path,
) -> None:
    """Corrupt final report JSON syntax."""

    (case_dir / "final_investigation_report.json").write_text(
        '{"case_id": ',
        encoding="utf-8",
    )


def malformed_reviewer_bundle_json(
    case_dir: Path,
) -> None:
    """Corrupt reviewer bundle JSON syntax."""

    (case_dir / "reviewer_bundle.json").write_text(
        '{"contextual_findings": ',
        encoding="utf-8",
    )


def evidence_wrong_top_level_type(
    case_dir: Path,
) -> None:
    """Replace evidence list with object."""

    write_json(
        case_dir / "evidence_items.json",
        {"unexpected": ("object_instead_of_list")},
    )


def final_report_wrong_top_level_type(
    case_dir: Path,
) -> None:
    """Replace final report object with list."""

    write_json(
        case_dir / "final_investigation_report.json",
        [],
    )


def reviewer_bundle_wrong_top_level_type(
    case_dir: Path,
) -> None:
    """Replace reviewer bundle object with list."""

    write_json(
        case_dir / "reviewer_bundle.json",
        [],
    )


def remove_finding_count(
    case_dir: Path,
) -> None:
    """Remove required finding count."""

    path = case_dir / "final_investigation_report.json"

    report = load_json(path)

    if not isinstance(
        report,
        dict,
    ):
        raise ValueError("Expected final report object.")

    report.pop(
        "finding_count",
        None,
    )

    write_json(
        path,
        report,
    )


def corrupt_finding_count(
    case_dir: Path,
) -> None:
    """Corrupt report finding count."""

    path = case_dir / "final_investigation_report.json"

    report = load_json(path)

    if not isinstance(
        report,
        dict,
    ):
        raise ValueError("Expected final report object.")

    report["finding_count"] = "nineteen"

    write_json(
        path,
        report,
    )


def corrupt_review_finding_count(
    case_dir: Path,
) -> None:
    """Corrupt review finding count."""

    path = case_dir / "final_investigation_report.json"

    report = load_json(path)

    if not isinstance(
        report,
        dict,
    ):
        raise ValueError("Expected final report object.")

    current = report.get(
        "review_finding_count",
        0,
    )

    if isinstance(
        current,
        int,
    ):
        report["review_finding_count"] = current + 100
    else:
        report["review_finding_count"] = 100

    write_json(
        path,
        report,
    )


def corrupt_reviewer_findings_type(
    case_dir: Path,
) -> None:
    """Replace contextual finding list with object."""

    path = case_dir / "reviewer_bundle.json"

    bundle = load_json(path)

    if not isinstance(
        bundle,
        dict,
    ):
        raise ValueError("Expected reviewer bundle object.")

    bundle["contextual_findings"] = {"invalid": ("expected_list")}

    write_json(
        path,
        bundle,
    )


def corrupt_medication_manifest_count(
    case_dir: Path,
) -> None:
    """Corrupt medication mention count."""

    path = case_dir / "medication_reconciliation_manifest.json"

    manifest = load_json(path)

    if not isinstance(
        manifest,
        dict,
    ):
        raise ValueError("Expected medication manifest object.")

    actual = manifest.get("medication_mention_count")

    if isinstance(
        actual,
        int,
    ):
        manifest["medication_mention_count"] = actual + 100
    else:
        manifest["medication_mention_count"] = 999999

    write_json(
        path,
        manifest,
    )


def corrupt_report_case_id(
    case_dir: Path,
) -> None:
    """Create cross-case identity mismatch."""

    path = case_dir / "final_investigation_report.json"

    report = load_json(path)

    if not isinstance(
        report,
        dict,
    ):
        raise ValueError("Expected final report object.")

    report["case_id"] = "corrupted-case-id"

    write_json(
        path,
        report,
    )


MUTATIONS: tuple[
    tuple[
        str,
        MutationFunction,
        str,
    ],
    ...,
] = (
    (
        "malformed_evidence_json",
        malformed_evidence_json,
        "invalid_json",
    ),
    (
        "malformed_final_report_json",
        malformed_final_report_json,
        "invalid_json",
    ),
    (
        "malformed_reviewer_bundle_json",
        malformed_reviewer_bundle_json,
        "invalid_json",
    ),
    (
        "evidence_wrong_top_level_type",
        evidence_wrong_top_level_type,
        ("unresolved_evidence_reference"),
    ),
    (
        "final_report_wrong_top_level_type",
        final_report_wrong_top_level_type,
        "invalid_report_schema",
    ),
    (
        "reviewer_bundle_wrong_top_level_type",
        reviewer_bundle_wrong_top_level_type,
        "invalid_reviewer_schema",
    ),
    (
        "missing_finding_count",
        remove_finding_count,
        "finding_count_mismatch",
    ),
    (
        "corrupt_finding_count",
        corrupt_finding_count,
        "finding_count_mismatch",
    ),
    (
        "corrupt_review_finding_count",
        corrupt_review_finding_count,
        "review_count_mismatch",
    ),
    (
        "corrupt_reviewer_findings_type",
        corrupt_reviewer_findings_type,
        ("reviewer_projection_mismatch"),
    ),
    (
        "corrupt_medication_manifest_count",
        corrupt_medication_manifest_count,
        ("medication_manifest_count_mismatch"),
    ),
    (
        "corrupt_report_case_id",
        corrupt_report_case_id,
        "case_id_mismatch",
    ),
)


def run_mutation(
    *,
    source_case: Path,
    mutation_name: str,
    mutation_function: MutationFunction,
    expected_category: str,
) -> dict[str, Any]:
    """Execute one schema robustness mutation."""

    mutation_case = copy_case(
        source_case=source_case,
        mutation_name=mutation_name,
    )

    try:
        mutation_function(mutation_case)
    except Exception as exc:
        return {
            "mutation": mutation_name,
            "status": "FAIL",
            "mutation_setup_error": (f"{type(exc).__name__}: {exc}"),
            "expected_category": (expected_category),
            "expected_category_detected": (False),
            "failed_closed": False,
            "detected_categories": [],
            "issues": [],
        }

    try:
        (
            case_result,
            issues,
        ) = validate_one_case(mutation_case)
    except Exception as exc:
        return {
            "mutation": mutation_name,
            "status": "FAIL",
            "validator_exception": (f"{type(exc).__name__}: {exc}"),
            "expected_category": (expected_category),
            "expected_category_detected": (False),
            "failed_closed": False,
            "detected_categories": [],
            "issues": [],
        }

    categories = issue_categories(issues)

    expected_detected = expected_category in categories

    failed_closed = case_result.get("status") == "FAIL"

    passed = failed_closed and expected_detected

    return {
        "mutation": mutation_name,
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
    """Run Step 9B.2 robustness evaluation."""

    for prerequisite in (
        STEP_9A_PATH,
        STEP_9B1_PATH,
    ):
        if not prerequisite.exists():
            raise FileNotFoundError(f"Required evaluation artifact missing: {prerequisite}")

    step_9a = load_json(STEP_9A_PATH)

    step_9b1 = load_json(STEP_9B1_PATH)

    if not isinstance(
        step_9a,
        dict,
    ):
        raise ValueError("Step 9A artifact must be a JSON object.")

    if not isinstance(
        step_9b1,
        dict,
    ):
        raise ValueError("Step 9B.1 artifact must be a JSON object.")

    step_9a_status = artifact_status(step_9a)

    step_9b1_status = artifact_status(step_9b1)

    if step_9a_status != "PASS":
        raise RuntimeError("Step 9B.2 requires PASS Step 9A.")

    if step_9b1_status != "PASS":
        raise RuntimeError("Step 9B.2 requires PASS Step 9B.1.")

    reference_case = choose_reference_case()

    baseline_hashes = {
        path.name: sha256_file(path) for path in (reference_case.iterdir()) if path.is_file()
    }

    if WORKSPACE_DIR.exists():
        shutil.rmtree(WORKSPACE_DIR)

    WORKSPACE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[dict[str, Any]] = []

    for (
        mutation_name,
        mutation_function,
        expected_category,
    ) in MUTATIONS:
        results.append(
            run_mutation(
                source_case=(reference_case),
                mutation_name=(mutation_name),
                mutation_function=(mutation_function),
                expected_category=(expected_category),
            )
        )

    post_test_hashes = {
        path.name: sha256_file(path) for path in (reference_case.iterdir()) if path.is_file()
    }

    production_case_unchanged = baseline_hashes == post_test_hashes

    passed = sum(1 for result in results if result.get("status") == "PASS")

    failed = len(results) - passed

    category_counts: Counter[str] = Counter()

    for result in results:
        for category in (
            result.get(
                "detected_categories",
                [],
            )
            or []
        ):
            category_counts[str(category)] += 1

    all_failed_closed = all(
        bool(
            result.get(
                "failed_closed",
                False,
            )
        )
        for result in results
    )

    all_expected_detected = all(
        bool(
            result.get(
                "expected_category_detected",
                False,
            )
        )
        for result in results
    )

    overall_pass = all(
        (
            step_9a_status == "PASS",
            step_9b1_status == "PASS",
            len(results) == len(MUTATIONS),
            failed == 0,
            all_failed_closed,
            all_expected_detected,
            production_case_unchanged,
        )
    )

    status = "PASS" if overall_pass else "FAIL"

    output = {
        "schema_version": "1.0",
        "acceptance_step": "9B.2",
        "acceptance_name": ("Malformed and Schema-Invalid Input Handling"),
        "status": status,
        "evaluated_at": (datetime.now(UTC).isoformat()),
        "baseline": {
            "step_9a_status": (step_9a_status),
            "step_9b1_status": (step_9b1_status),
            "reference_case": (reference_case.name),
            "reference_case_file_count": (len(baseline_hashes)),
        },
        "mutation_summary": {
            "mutations": len(results),
            "passed": passed,
            "failed": failed,
            "all_failed_closed": (all_failed_closed),
            "all_expected_categories_detected": (all_expected_detected),
            "production_case_unchanged": (production_case_unchanged),
            "detected_issue_categories": dict(sorted(category_counts.items())),
        },
        "acceptance_criteria": {
            "malformed_json_rejected": all(
                result.get("status") == "PASS"
                for result in results
                if str(result.get("mutation", "")).startswith("malformed_")
            ),
            "wrong_top_level_types_rejected": all(
                result.get("status") == "PASS"
                for result in results
                if ("wrong_top_level_type" in str(result.get("mutation", "")))
            ),
            "invalid_report_fields_rejected": all(
                result.get("status") == "PASS"
                for result in results
                if result.get("mutation")
                in {
                    "missing_finding_count",
                    "corrupt_finding_count",
                    ("corrupt_review_finding_count"),
                }
            ),
            "cross_artifact_corruption_rejected": all(
                result.get("status") == "PASS"
                for result in results
                if result.get("mutation")
                in {
                    ("corrupt_reviewer_findings_type"),
                    ("corrupt_medication_manifest_count"),
                    ("corrupt_report_case_id"),
                }
            ),
            "production_artifacts_immutable": (production_case_unchanged),
        },
        "mutation_results": (results),
        "ready_for_9b3": (overall_pass),
        "methodological_notes": [
            ("All malformed and schema-invalid mutations are applied only to workspace copies."),
            ("Malformed JSON tests validate serialization-level failure detection."),
            (
                "Wrong top-level type and "
                "field corruption tests "
                "validate structural "
                "acceptance behavior."
            ),
            (
                "This step tests the "
                "persisted end-to-end "
                "acceptance boundary. "
                "Deliberate dangling "
                "provenance mutations are "
                "reserved for Step 9B.3."
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
    print("STEP 9B.2 — MALFORMED / SCHEMA-INVALID INPUT HANDLING")
    print("=" * 72)

    print(f"Overall status:                   {status}")

    print()
    print("Baseline")
    print("-" * 72)

    print(f"Step 9A status:                   {step_9a_status}")

    print(f"Step 9B.1 status:                 {step_9b1_status}")

    print(f"Reference case:                   {reference_case.name}")

    print()
    print("Mutation results")
    print("-" * 72)

    print(f"Mutations executed:               {len(results)}")

    print(f"Mutations passed:                 {passed}")

    print(f"Mutations failed:                 {failed}")

    print(f"All failed closed:                {all_failed_closed}")

    print(f"Expected categories detected:    {all_expected_detected}")

    print()
    print("Safety")
    print("-" * 72)

    print(f"Production case unchanged:        {production_case_unchanged}")

    print()
    print(f"Ready for Step 9B.3:              {overall_pass}")

    print()
    print("Saved Step-9B.2 result to:")

    print(OUTPUT_PATH)

    if WORKSPACE_DIR.exists():
        shutil.rmtree(WORKSPACE_DIR)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

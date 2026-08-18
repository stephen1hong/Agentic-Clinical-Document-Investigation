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
from evaluate_medication_timeline_perturbation_robustness import (
    semantic_issues,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

STEP_9A_PATH = PROJECT_ROOT / "data" / "evaluation" / "step_9a" / "end_to_end_regression.json"

STEP_9B1_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "step_9b1" / "missing_partial_artifact_robustness.json"
)

STEP_9B2_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "step_9b2" / "malformed_schema_robustness.json"
)

STEP_9B3_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "step_9b3" / "provenance_breakage_robustness.json"
)

STEP_9B4_PATH = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "step_9b4"
    / "medication_timeline_perturbation_robustness.json"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "step_9b5"

WORKSPACE_DIR = OUTPUT_DIR / "workspace"

OUTPUT_PATH = OUTPUT_DIR / "deterministic_failure_recovery.json"


MutationFunction = Callable[
    [Path],
    dict[str, Any],
]


def write_json(
    path: Path,
    payload: Any,
) -> None:
    """Write deterministic formatted JSON."""

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
    """Read evaluation status."""

    for key in (
        "status",
        "overall_status",
    ):
        value = payload.get(key)

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
    """Require one prerequisite evaluation to be PASS."""

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


def as_dict_list(
    value: Any,
) -> list[dict[str, Any]]:
    """Return JSON-object records from a list."""

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


def case_dirs() -> list[Path]:
    """Return production investigation cases."""

    return sorted(path for path in CASE_ROOT.iterdir() if path.is_dir())


def required_case_files() -> tuple[str, ...]:
    """Return artifacts needed by Step 9B.5."""

    return (
        "evidence_items.json",
        "clinical_claims.json",
        "canonical_timeline.json",
        "medication_mentions.json",
        "medication_profiles.json",
        "medication_discrepancies.json",
        "medication_reconciliation_manifest.json",
        "final_investigation_report.json",
        "reviewer_bundle.json",
        "reviewer_report.md",
    )


def complete_case(
    case_dir: Path,
) -> bool:
    """Return whether required artifacts exist."""

    return all((case_dir / filename).exists() for filename in required_case_files())


def choose_reference_case() -> Path:
    """Choose a complete case suitable for all five scenarios."""

    candidates: list[tuple[int, int, str, Path]] = []

    for case_dir in case_dirs():
        if not complete_case(case_dir):
            continue

        report = load_json(case_dir / "final_investigation_report.json")

        timeline = as_dict_list(load_json(case_dir / "canonical_timeline.json"))

        mentions = as_dict_list(load_json(case_dir / "medication_mentions.json"))

        if not isinstance(
            report,
            dict,
        ):
            continue

        findings = get_report_findings(report)

        has_evidence_reference = any(
            bool(
                finding.get(
                    "evidence_ids",
                    [],
                )
            )
            for finding in findings
        )

        if not (findings and timeline and mentions and has_evidence_reference):
            continue

        candidates.append(
            (
                len(mentions),
                len(findings),
                case_dir.name,
                case_dir,
            )
        )

    if not candidates:
        raise RuntimeError("No complete case satisfies Step 9B.5 reference requirements.")

    candidates.sort(reverse=True)

    return candidates[0][3]


def case_hashes(
    case_dir: Path,
) -> dict[str, str]:
    """Hash production case files."""

    return {path.name: sha256_file(path) for path in case_dir.iterdir() if path.is_file()}


def copy_case(
    *,
    source_case: Path,
    scenario_name: str,
    run_name: str,
) -> Path:
    """Create isolated workspace copy."""

    run_root = WORKSPACE_DIR / scenario_name / run_name

    mutation_case = run_root / source_case.name

    if run_root.exists():
        shutil.rmtree(run_root)

    run_root.mkdir(
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
) -> list[str]:
    """Return sorted unique issue categories."""

    return sorted(
        {
            str(
                issue.get(
                    "category",
                    "",
                )
            )
            for issue in issues
            if issue.get("category")
        }
    )


def combined_validate(
    case_dir: Path,
) -> dict[str, Any]:
    """Run structural and semantic acceptance validation."""

    try:
        (
            case_result,
            acceptance_issues,
        ) = validate_one_case(case_dir)
    except Exception as exc:
        return {
            "status": "FAIL",
            "validator_exception": (f"{type(exc).__name__}: {exc}"),
            "acceptance_issues": [],
            "semantic_issues": [],
            "categories": ["validator_exception"],
        }

    semantic_validation_issues: list[dict[str, Any]] = []

    #
    # Semantic regeneration requires valid
    # JSON and the relevant persisted files.
    # If structural validation has already
    # identified serialization/missing-file
    # corruption, it is not necessary to
    # invoke semantic regeneration.
    #
    acceptance_categories = set(issue_categories(acceptance_issues))

    semantic_blockers = {
        "invalid_json",
        "missing_artifact",
        "invalid_report_schema",
        "invalid_reviewer_schema",
    }

    if not (acceptance_categories & semantic_blockers):
        try:
            semantic_validation_issues = semantic_issues(case_dir)
        except Exception as exc:
            semantic_validation_issues = [
                {
                    "category": ("semantic_validator_exception"),
                    "detail": (f"{type(exc).__name__}: {exc}"),
                }
            ]

    all_issues = [
        *acceptance_issues,
        *semantic_validation_issues,
    ]

    categories = issue_categories(all_issues)

    passed = case_result.get("status") == "PASS" and not all_issues

    return {
        "status": ("PASS" if passed else "FAIL"),
        "acceptance_status": (case_result.get("status")),
        "acceptance_issues": (acceptance_issues),
        "semantic_issues": (semantic_validation_issues),
        "categories": (categories),
    }


def validate_clean_case(
    case_dir: Path,
) -> None:
    """Require clean reference case."""

    result = combined_validate(case_dir)

    if result.get("status") != "PASS":
        raise RuntimeError(f"Reference case does not pass combined Step 9B.5 validation: {result}")


#
# ------------------------------------------------------------
# Mutation scenarios
# ------------------------------------------------------------
#


def mutate_missing_reviewer_bundle(
    case_dir: Path,
) -> dict[str, Any]:
    """Remove required reviewer bundle."""

    path = case_dir / "reviewer_bundle.json"

    path.unlink()

    return {
        "artifact": ("reviewer_bundle.json"),
        "mutation_type": ("missing_artifact"),
    }


def mutate_malformed_final_report(
    case_dir: Path,
) -> dict[str, Any]:
    """Corrupt final report JSON."""

    path = case_dir / "final_investigation_report.json"

    path.write_text(
        '{"case_id": ',
        encoding="utf-8",
    )

    return {
        "artifact": ("final_investigation_report.json"),
        "mutation_type": ("malformed_json"),
    }


def mutate_dangling_evidence_reference(
    case_dir: Path,
) -> dict[str, Any]:
    """Add one unresolved evidence ID to a real finding."""

    path = case_dir / "final_investigation_report.json"

    report = load_json(path)

    if not isinstance(
        report,
        dict,
    ):
        raise ValueError("Final report must contain a JSON object.")

    target: (
        dict[
            str,
            Any,
        ]
        | None
    ) = None

    for finding in get_report_findings(report):
        if finding.get("evidence_ids"):
            target = finding
            break

    if target is None:
        raise RuntimeError("No finding with an evidence reference found.")

    evidence_ids = list(
        target.get(
            "evidence_ids",
            [],
        )
        or []
    )

    dangling_id = "9b5-dangling-evidence-id"

    evidence_ids.append(dangling_id)

    target["evidence_ids"] = evidence_ids

    write_json(
        path,
        report,
    )

    return {
        "artifact": ("final_investigation_report.json"),
        "mutation_type": ("dangling_provenance"),
        "finding_id": (target.get("finding_id")),
        "injected_id": (dangling_id),
    }


def mutate_timeline_subject(
    case_dir: Path,
) -> dict[str, Any]:
    """Perturb one canonical timeline event."""

    path = case_dir / "canonical_timeline.json"

    timeline = as_dict_list(load_json(path))

    if not timeline:
        raise RuntimeError("Canonical timeline is empty.")

    target = timeline[0]

    original = str(
        target.get(
            "subject",
            "",
        )
    )

    target["subject"] = original + " [9B5 PERTURBED]"

    write_json(
        path,
        timeline,
    )

    return {
        "artifact": ("canonical_timeline.json"),
        "mutation_type": ("timeline_perturbation"),
        "event_id": (target.get("event_id")),
        "original_value": (original),
        "mutated_value": (target["subject"]),
    }


def mutate_medication_dose(
    case_dir: Path,
) -> dict[str, Any]:
    """Perturb one persisted medication mention dose."""

    path = case_dir / "medication_mentions.json"

    mentions = as_dict_list(load_json(path))

    if not mentions:
        raise RuntimeError("Medication mention artifact is empty.")

    target = next(
        (mention for mention in mentions if mention.get("dose")),
        mentions[0],
    )

    original = target.get("dose")

    target["dose"] = "999 MG"

    write_json(
        path,
        mentions,
    )

    return {
        "artifact": ("medication_mentions.json"),
        "mutation_type": ("medication_perturbation"),
        "mention_id": (target.get("mention_id")),
        "original_value": (original),
        "mutated_value": ("999 MG"),
    }


SCENARIOS: tuple[
    tuple[
        str,
        MutationFunction,
        set[str],
    ],
    ...,
] = (
    (
        "missing_reviewer_bundle",
        mutate_missing_reviewer_bundle,
        {
            "missing_artifact",
        },
    ),
    (
        "malformed_final_report",
        mutate_malformed_final_report,
        {
            "invalid_json",
        },
    ),
    (
        "dangling_evidence_reference",
        mutate_dangling_evidence_reference,
        {
            "unresolved_evidence_reference",
        },
    ),
    (
        "timeline_subject_perturbation",
        mutate_timeline_subject,
        {
            "timeline_reconstruction_mismatch",
        },
    ),
    (
        "medication_dose_perturbation",
        mutate_medication_dose,
        {
            "medication_reconciliation_mismatch",
        },
    ),
)


def save_original_artifact(
    *,
    case_dir: Path,
    artifact_name: str,
) -> bytes:
    """Read artifact bytes before mutation."""

    path = case_dir / artifact_name

    if not path.exists():
        raise FileNotFoundError(f"Recovery artifact not found: {path}")

    return path.read_bytes()


def restore_artifact(
    *,
    case_dir: Path,
    artifact_name: str,
    original_bytes: bytes,
) -> None:
    """Restore original artifact exactly."""

    path = case_dir / artifact_name

    path.write_bytes(original_bytes)


def execute_once(
    *,
    source_case: Path,
    scenario_name: str,
    run_name: str,
    mutation_function: MutationFunction,
    expected_categories: set[str],
) -> dict[str, Any]:
    """Execute one deterministic failure/recovery cycle."""

    mutation_case = copy_case(
        source_case=source_case,
        scenario_name=scenario_name,
        run_name=run_name,
    )

    #
    # We need the mutation metadata first to know
    # the affected artifact. Since restoration must
    # use pristine bytes, take a complete pre-mutation
    # file snapshot.
    #
    original_files = {
        path.name: path.read_bytes() for path in mutation_case.iterdir() if path.is_file()
    }

    original_hashes = {
        filename: sha256_file(mutation_case / filename) for filename in original_files
    }

    try:
        mutation_metadata = mutation_function(mutation_case)
    except Exception as exc:
        return {
            "scenario": (scenario_name),
            "run": run_name,
            "status": "FAIL",
            "setup_error": (f"{type(exc).__name__}: {exc}"),
            "failure_detected": False,
            "expected_categories_detected": (False),
            "recovery_passed": False,
        }

    artifact_name = str(
        mutation_metadata.get(
            "artifact",
            "",
        )
    )

    if not artifact_name or artifact_name not in original_files:
        return {
            "scenario": (scenario_name),
            "run": run_name,
            "status": "FAIL",
            "setup_error": ("Mutation did not identify a restorable artifact."),
            "failure_detected": False,
            "expected_categories_detected": (False),
            "recovery_passed": False,
            **mutation_metadata,
        }

    failure_result = combined_validate(mutation_case)

    detected_categories = set(
        failure_result.get(
            "categories",
            [],
        )
        or []
    )

    failure_detected = failure_result.get("status") == "FAIL"

    expected_detected = expected_categories <= detected_categories

    #
    # Restore exactly the artifact mutated
    # by the scenario.
    #
    restore_artifact(
        case_dir=mutation_case,
        artifact_name=artifact_name,
        original_bytes=(original_files[artifact_name]),
    )

    restored_hash = sha256_file(mutation_case / artifact_name)

    original_hash = original_hashes[artifact_name]

    byte_exact_recovery = restored_hash == original_hash

    recovery_result = combined_validate(mutation_case)

    recovery_passed = recovery_result.get("status") == "PASS" and byte_exact_recovery

    passed = all(
        (
            failure_detected,
            expected_detected,
            recovery_passed,
            byte_exact_recovery,
        )
    )

    return {
        "scenario": (scenario_name),
        "run": run_name,
        "status": ("PASS" if passed else "FAIL"),
        "expected_categories": (sorted(expected_categories)),
        "failure_status": (failure_result.get("status")),
        "failure_categories": (sorted(detected_categories)),
        "failure_detected": (failure_detected),
        "expected_categories_detected": (expected_detected),
        "recovery_status": (recovery_result.get("status")),
        "byte_exact_recovery": (byte_exact_recovery),
        "recovery_passed": (recovery_passed),
        "original_artifact_hash": (original_hash),
        "restored_artifact_hash": (restored_hash),
        "failure_validation": (failure_result),
        "recovery_validation": (recovery_result),
        **mutation_metadata,
    }


def evaluate_scenario(
    *,
    source_case: Path,
    scenario_name: str,
    mutation_function: MutationFunction,
    expected_categories: set[str],
) -> dict[str, Any]:
    """Run identical scenario twice and compare behavior."""

    first = execute_once(
        source_case=source_case,
        scenario_name=scenario_name,
        run_name="run_1",
        mutation_function=mutation_function,
        expected_categories=expected_categories,
    )

    second = execute_once(
        source_case=source_case,
        scenario_name=scenario_name,
        run_name="run_2",
        mutation_function=mutation_function,
        expected_categories=expected_categories,
    )

    same_failure_status = first.get("failure_status") == second.get("failure_status")

    same_failure_categories = first.get("failure_categories") == second.get("failure_categories")

    same_expected_detection = first.get("expected_categories_detected") == second.get(
        "expected_categories_detected"
    )

    both_recovered = all(
        (
            first.get("recovery_passed") is True,
            second.get("recovery_passed") is True,
        )
    )

    both_runs_passed = all(
        (
            first.get("status") == "PASS",
            second.get("status") == "PASS",
        )
    )

    deterministic = all(
        (
            same_failure_status,
            same_failure_categories,
            same_expected_detection,
        )
    )

    passed = all(
        (
            deterministic,
            both_recovered,
            both_runs_passed,
        )
    )

    return {
        "scenario": (scenario_name),
        "status": ("PASS" if passed else "FAIL"),
        "deterministic_failure_behavior": (deterministic),
        "same_failure_status": (same_failure_status),
        "same_failure_categories": (same_failure_categories),
        "same_expected_detection": (same_expected_detection),
        "both_runs_recovered": (both_recovered),
        "run_1": first,
        "run_2": second,
    }


def main() -> int:
    """Run Step 9B.5."""

    load_required_pass(
        STEP_9A_PATH,
        "Step 9A",
    )

    load_required_pass(
        STEP_9B1_PATH,
        "Step 9B.1",
    )

    load_required_pass(
        STEP_9B2_PATH,
        "Step 9B.2",
    )

    load_required_pass(
        STEP_9B3_PATH,
        "Step 9B.3",
    )

    load_required_pass(
        STEP_9B4_PATH,
        "Step 9B.4",
    )

    reference_case = choose_reference_case()

    validate_clean_case(reference_case)

    production_hashes_before = case_hashes(reference_case)

    if WORKSPACE_DIR.exists():
        shutil.rmtree(WORKSPACE_DIR)

    WORKSPACE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[dict[str, Any]] = []

    for (
        scenario_name,
        mutation_function,
        expected_categories,
    ) in SCENARIOS:
        results.append(
            evaluate_scenario(
                source_case=(reference_case),
                scenario_name=(scenario_name),
                mutation_function=(mutation_function),
                expected_categories=(expected_categories),
            )
        )

    production_hashes_after = case_hashes(reference_case)

    production_case_unchanged = production_hashes_before == production_hashes_after

    scenarios_passed = sum(1 for result in results if result.get("status") == "PASS")

    scenarios_failed = len(results) - scenarios_passed

    deterministic_scenarios = sum(
        1 for result in results if result.get("deterministic_failure_behavior") is True
    )

    recovery_scenarios = sum(1 for result in results if result.get("both_runs_recovered") is True)

    total_failure_runs = len(results) * 2

    successful_failure_runs = sum(
        1
        for result in results
        for run_key in (
            "run_1",
            "run_2",
        )
        if result.get(
            run_key,
            {},
        ).get("failure_detected")
        is True
    )

    successful_recoveries = sum(
        1
        for result in results
        for run_key in (
            "run_1",
            "run_2",
        )
        if result.get(
            run_key,
            {},
        ).get("recovery_passed")
        is True
    )

    category_counts: Counter[str] = Counter()

    for result in results:
        for run_key in (
            "run_1",
            "run_2",
        ):
            for category in (
                result.get(
                    run_key,
                    {},
                ).get(
                    "failure_categories",
                    [],
                )
                or []
            ):
                category_counts[str(category)] += 1

    overall_pass = all(
        (
            len(results) == len(SCENARIOS),
            scenarios_failed == 0,
            deterministic_scenarios == len(SCENARIOS),
            recovery_scenarios == len(SCENARIOS),
            successful_failure_runs == total_failure_runs,
            successful_recoveries == total_failure_runs,
            production_case_unchanged,
        )
    )

    status = "PASS" if overall_pass else "FAIL"

    output = {
        "schema_version": "1.0",
        "acceptance_step": "9B.5",
        "acceptance_name": ("Deterministic Failure Behavior and Recovery"),
        "status": status,
        "evaluated_at": (datetime.now(UTC).isoformat()),
        "prerequisites": {
            "9A": "PASS",
            "9B.1": "PASS",
            "9B.2": "PASS",
            "9B.3": "PASS",
            "9B.4": "PASS",
        },
        "reference_case": (reference_case.name),
        "scenario_summary": {
            "scenarios": (len(results)),
            "scenarios_passed": (scenarios_passed),
            "scenarios_failed": (scenarios_failed),
            "repeat_runs_per_scenario": 2,
            "total_failure_runs": (total_failure_runs),
            "failure_runs_detected": (successful_failure_runs),
            "successful_recoveries": (successful_recoveries),
            "deterministic_scenarios": (deterministic_scenarios),
            "recovery_scenarios": (recovery_scenarios),
            "production_case_unchanged": (production_case_unchanged),
            "detected_issue_categories": dict(sorted(category_counts.items())),
        },
        "acceptance_criteria": {
            "same_mutation_same_failure_status": all(
                result.get("same_failure_status") is True for result in results
            ),
            "same_mutation_same_failure_categories": all(
                result.get("same_failure_categories") is True for result in results
            ),
            "all_failures_detected": (successful_failure_runs == total_failure_runs),
            "all_recoveries_pass": (successful_recoveries == total_failure_runs),
            "all_restorations_byte_exact": all(
                result.get(
                    run_key,
                    {},
                ).get("byte_exact_recovery")
                is True
                for result in results
                for run_key in (
                    "run_1",
                    "run_2",
                )
            ),
            "production_artifacts_immutable": (production_case_unchanged),
        },
        "scenario_results": (results),
        "ready_for_9b6": (overall_pass),
        "methodological_notes": [
            ("Each failure scenario is executed twice in independently copied workspaces."),
            (
                "Determinism is defined as "
                "identical failure status and "
                "identical normalized issue-category "
                "sets across repeated executions."
            ),
            (
                "Raw issue-detail strings are not "
                "required to be byte-identical because "
                "workspace-specific paths may appear "
                "in diagnostic messages."
            ),
            (
                "Recovery restores the mutated "
                "artifact from its exact pre-mutation "
                "bytes and verifies the restored "
                "SHA-256 hash."
            ),
            (
                "A recovered case must pass both "
                "the Step 9A acceptance validator "
                "and Step 9B.4 deterministic semantic "
                "regeneration checks."
            ),
            (
                "No mutation is intentionally "
                "performed inside the production "
                "data/investigation_cases tree."
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
    print("STEP 9B.5 — DETERMINISTIC FAILURE BEHAVIOR / RECOVERY")
    print("=" * 72)

    print(f"Overall status:                   {status}")

    print()
    print("Prerequisites")
    print("-" * 72)

    print("Step 9A status:                   PASS")
    print("Step 9B.1 status:                 PASS")
    print("Step 9B.2 status:                 PASS")
    print("Step 9B.3 status:                 PASS")
    print("Step 9B.4 status:                 PASS")

    print()
    print("Determinism")
    print("-" * 72)

    print(f"Scenarios executed:               {len(results)}")

    print(f"Scenarios passed:                 {scenarios_passed}")

    print(f"Scenarios failed:                 {scenarios_failed}")

    print(f"Deterministic scenarios:          {deterministic_scenarios} / {len(results)}")

    print(f"Failure runs detected:            {successful_failure_runs} / {total_failure_runs}")

    print()
    print("Recovery")
    print("-" * 72)

    print(f"Recovery scenarios passed:        {recovery_scenarios} / {len(results)}")

    print(f"Successful recoveries:            {successful_recoveries} / {total_failure_runs}")

    print()
    print("Safety")
    print("-" * 72)

    print(f"Production case unchanged:        {production_case_unchanged}")

    print()
    print(f"Ready for Step 9B.6:              {overall_pass}")

    print()
    print("Saved Step-9B.5 result to:")
    print(OUTPUT_PATH)

    if WORKSPACE_DIR.exists():
        shutil.rmtree(WORKSPACE_DIR)

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())

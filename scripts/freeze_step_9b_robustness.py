from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EVALUATION_ROOT = PROJECT_ROOT / "data" / "evaluation"

STEP_9A_PATH = EVALUATION_ROOT / "step_9a" / "end_to_end_regression.json"

STEP_9B1_PATH = EVALUATION_ROOT / "step_9b1" / "missing_partial_artifact_robustness.json"

STEP_9B2_PATH = EVALUATION_ROOT / "step_9b2" / "malformed_schema_robustness.json"

STEP_9B3_PATH = EVALUATION_ROOT / "step_9b3" / "provenance_breakage_robustness.json"

STEP_9B4_PATH = EVALUATION_ROOT / "step_9b4" / "medication_timeline_perturbation_robustness.json"

STEP_9B5_PATH = EVALUATION_ROOT / "step_9b5" / "deterministic_failure_recovery.json"

OUTPUT_DIR = EVALUATION_ROOT / "step_9b_final"

OUTPUT_PATH = OUTPUT_DIR / "step_9b_robustness_summary.json"


SUBSTEPS = {
    "9B.1": {
        "name": ("Missing / Partial Artifact Robustness"),
        "path": STEP_9B1_PATH,
    },
    "9B.2": {
        "name": ("Malformed / Schema-Invalid Input Handling"),
        "path": STEP_9B2_PATH,
    },
    "9B.3": {
        "name": ("Provenance Breakage / Dangling-Reference Detection"),
        "path": STEP_9B3_PATH,
    },
    "9B.4": {
        "name": ("Medication / Timeline Perturbation Robustness"),
        "path": STEP_9B4_PATH,
    },
    "9B.5": {
        "name": ("Deterministic Failure Behavior and Recovery"),
        "path": STEP_9B5_PATH,
    },
}


EXPECTED_COVERAGE = {
    "9B.1": {
        "mutations": 12,
    },
    "9B.2": {
        "mutations": 12,
    },
    "9B.3": {
        "mutations": 12,
    },
    "9B.4": {
        "mutations": 13,
    },
    "9B.5": {
        "scenarios": 5,
        "total_failure_runs": 10,
        "successful_recoveries": 10,
    },
}


def load_json(
    path: Path,
) -> Any:
    """Load JSON artifact."""

    return json.loads(path.read_text(encoding="utf-8"))


def artifact_status(
    payload: dict[str, Any],
) -> str | None:
    """Read status across evaluation artifact schemas."""

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


def sha256_file(
    path: Path,
) -> str:
    """Return SHA-256 hash."""

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def get_nested(
    payload: dict[str, Any],
    *keys: str,
) -> Any:
    """Read nested dictionary value."""

    current: Any = payload

    for key in keys:
        if not isinstance(
            current,
            dict,
        ):
            return None

        current = current.get(key)

    return current


def validate_step_9a(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate Step 9A baseline gate."""

    issues: list[dict[str, Any]] = []

    if artifact_status(payload) != "PASS":
        issues.append(
            {
                "category": ("non_pass_prerequisite"),
                "artifact": "9A",
                "detail": ("Step 9A is not PASS."),
            }
        )

    ready = payload.get("ready_for_step_9b")

    #
    # Some versions may not persist the
    # readiness flag. Only fail if it is
    # explicitly False.
    #
    if ready is False:
        issues.append(
            {
                "category": ("baseline_not_ready"),
                "artifact": "9A",
                "detail": ("Step 9A explicitly reports not ready for Step 9B."),
            }
        )

    return issues


def validate_9b1(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate 9B.1 freeze criteria."""

    issues: list[dict[str, Any]] = []

    summary = payload.get(
        "mutation_summary",
        {},
    )

    mutations = summary.get("mutations")

    passed = summary.get("passed")

    failed = summary.get("failed")

    unchanged = summary.get("production_case_unchanged")

    if mutations != 12:
        issues.append(
            {
                "category": ("coverage_mismatch"),
                "artifact": "9B.1",
                "detail": (f"Expected 12 mutations; found {mutations}."),
            }
        )

    if passed != 12:
        issues.append(
            {
                "category": ("pass_count_mismatch"),
                "artifact": "9B.1",
                "detail": (f"Expected 12 passed; found {passed}."),
            }
        )

    if failed != 0:
        issues.append(
            {
                "category": ("failure_count_nonzero"),
                "artifact": "9B.1",
                "detail": (f"Expected 0 failed; found {failed}."),
            }
        )

    if unchanged is not True:
        issues.append(
            {
                "category": ("production_immutability_failed"),
                "artifact": "9B.1",
                "detail": ("Production case immutability was not confirmed."),
            }
        )

    return issues


def validate_9b2(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate 9B.2 freeze criteria."""

    issues: list[dict[str, Any]] = []

    summary = payload.get(
        "mutation_summary",
        {},
    )

    if summary.get("mutations") != 12:
        issues.append(
            {
                "category": ("coverage_mismatch"),
                "artifact": "9B.2",
                "detail": ("Expected 12 mutations."),
            }
        )

    if summary.get("passed") != 12:
        issues.append(
            {
                "category": ("pass_count_mismatch"),
                "artifact": "9B.2",
                "detail": ("Expected all 12 mutations to pass."),
            }
        )

    if summary.get("failed") != 0:
        issues.append(
            {
                "category": ("failure_count_nonzero"),
                "artifact": "9B.2",
                "detail": ("Expected zero failed mutations."),
            }
        )

    if summary.get("all_failed_closed") is not True:
        issues.append(
            {
                "category": ("fail_closed_not_confirmed"),
                "artifact": "9B.2",
                "detail": ("Fail-closed behavior was not confirmed."),
            }
        )

    if summary.get("all_expected_categories_detected") is not True:
        issues.append(
            {
                "category": ("expected_detection_failed"),
                "artifact": "9B.2",
                "detail": ("Expected issue categories were not all detected."),
            }
        )

    if summary.get("production_case_unchanged") is not True:
        issues.append(
            {
                "category": ("production_immutability_failed"),
                "artifact": "9B.2",
                "detail": ("Production case immutability was not confirmed."),
            }
        )

    return issues


def validate_9b3(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate 9B.3 freeze criteria."""

    issues: list[dict[str, Any]] = []

    summary = payload.get(
        "mutation_summary",
        {},
    )

    if summary.get("mutations") != 12:
        issues.append(
            {
                "category": ("coverage_mismatch"),
                "artifact": "9B.3",
                "detail": ("Expected 12 provenance mutations."),
            }
        )

    if summary.get("passed") != 12:
        issues.append(
            {
                "category": ("pass_count_mismatch"),
                "artifact": "9B.3",
                "detail": ("Expected all 12 provenance mutations to pass."),
            }
        )

    if summary.get("failed") != 0:
        issues.append(
            {
                "category": ("failure_count_nonzero"),
                "artifact": "9B.3",
                "detail": ("Expected zero failed provenance mutations."),
            }
        )

    if summary.get("all_failed_closed") is not True:
        issues.append(
            {
                "category": ("fail_closed_not_confirmed"),
                "artifact": "9B.3",
                "detail": ("Provenance corruption did not consistently fail closed."),
            }
        )

    if summary.get("all_expected_categories_detected") is not True:
        issues.append(
            {
                "category": ("expected_detection_failed"),
                "artifact": "9B.3",
                "detail": ("Not all expected provenance failures were detected."),
            }
        )

    if summary.get("production_cases_unchanged") is not True:
        issues.append(
            {
                "category": ("production_immutability_failed"),
                "artifact": "9B.3",
                "detail": ("Production case immutability was not confirmed."),
            }
        )

    provenance_summary = payload.get(
        "provenance_summary",
        {},
    )

    for provenance_type in (
        "evidence",
        "claim",
        "event",
    ):
        scoped = provenance_summary.get(
            provenance_type,
            {},
        )

        if scoped.get("mutations") != 4:
            issues.append(
                {
                    "category": ("provenance_coverage_mismatch"),
                    "artifact": "9B.3",
                    "detail": (f"{provenance_type} expected 4 mutations."),
                }
            )

        if scoped.get("passed") != 4:
            issues.append(
                {
                    "category": ("provenance_pass_mismatch"),
                    "artifact": "9B.3",
                    "detail": (f"{provenance_type} expected 4 passed."),
                }
            )

    return issues


def validate_9b4(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate 9B.4 freeze criteria."""

    issues: list[dict[str, Any]] = []

    summary = payload.get(
        "mutation_summary",
        {},
    )

    if summary.get("mutations") != 13:
        issues.append(
            {
                "category": ("coverage_mismatch"),
                "artifact": "9B.4",
                "detail": ("Expected 13 perturbations."),
            }
        )

    if summary.get("passed") != 13:
        issues.append(
            {
                "category": ("pass_count_mismatch"),
                "artifact": "9B.4",
                "detail": ("Expected all 13 perturbations to pass."),
            }
        )

    if summary.get("failed") != 0:
        issues.append(
            {
                "category": ("failure_count_nonzero"),
                "artifact": "9B.4",
                "detail": ("Expected zero failed perturbations."),
            }
        )

    if summary.get("all_failed_closed") is not True:
        issues.append(
            {
                "category": ("fail_closed_not_confirmed"),
                "artifact": "9B.4",
                "detail": ("Perturbations did not consistently fail closed."),
            }
        )

    if summary.get("all_expected_categories_detected") is not True:
        issues.append(
            {
                "category": ("expected_detection_failed"),
                "artifact": "9B.4",
                "detail": ("Expected perturbation categories were not all detected."),
            }
        )

    if summary.get("production_cases_unchanged") is not True:
        issues.append(
            {
                "category": ("production_immutability_failed"),
                "artifact": "9B.4",
                "detail": ("Production case immutability was not confirmed."),
            }
        )

    domain = payload.get(
        "domain_summary",
        {},
    )

    timeline = domain.get(
        "timeline",
        {},
    )

    medication = domain.get(
        "medication",
        {},
    )

    if timeline.get("mutations") != 5 or timeline.get("passed") != 5:
        issues.append(
            {
                "category": ("timeline_coverage_mismatch"),
                "artifact": "9B.4",
                "detail": ("Expected timeline coverage 5/5."),
            }
        )

    if medication.get("mutations") != 8 or medication.get("passed") != 8:
        issues.append(
            {
                "category": ("medication_coverage_mismatch"),
                "artifact": "9B.4",
                "detail": ("Expected medication coverage 8/8."),
            }
        )

    return issues


def validate_9b5(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Validate 9B.5 freeze criteria."""

    issues: list[dict[str, Any]] = []

    summary = payload.get(
        "scenario_summary",
        {},
    )

    expected_values = {
        "scenarios": 5,
        "scenarios_passed": 5,
        "scenarios_failed": 0,
        "repeat_runs_per_scenario": 2,
        "total_failure_runs": 10,
        "failure_runs_detected": 10,
        "successful_recoveries": 10,
        "deterministic_scenarios": 5,
        "recovery_scenarios": 5,
    }

    for (
        field,
        expected,
    ) in expected_values.items():
        actual = summary.get(field)

        if actual != expected:
            issues.append(
                {
                    "category": ("recovery_coverage_mismatch"),
                    "artifact": "9B.5",
                    "detail": (f"{field}: expected {expected}; found {actual}."),
                }
            )

    if summary.get("production_case_unchanged") is not True:
        issues.append(
            {
                "category": ("production_immutability_failed"),
                "artifact": "9B.5",
                "detail": ("Production case immutability was not confirmed."),
            }
        )

    criteria = payload.get(
        "acceptance_criteria",
        {},
    )

    required_true = (
        "same_mutation_same_failure_status",
        "same_mutation_same_failure_categories",
        "all_failures_detected",
        "all_recoveries_pass",
        "all_restorations_byte_exact",
        "production_artifacts_immutable",
    )

    for field in required_true:
        if criteria.get(field) is not True:
            issues.append(
                {
                    "category": ("recovery_acceptance_failed"),
                    "artifact": "9B.5",
                    "detail": (f"{field} is not True."),
                }
            )

    return issues


VALIDATORS = {
    "9B.1": validate_9b1,
    "9B.2": validate_9b2,
    "9B.3": validate_9b3,
    "9B.4": validate_9b4,
    "9B.5": validate_9b5,
}


def main() -> int:
    """Freeze Step 9B robustness evaluation."""

    issues: list[dict[str, Any]] = []

    frozen_artifacts: list[dict[str, Any]] = []

    #
    # Step 9A remains the release baseline.
    #
    if not STEP_9A_PATH.exists():
        issues.append(
            {
                "category": ("missing_prerequisite"),
                "artifact": "9A",
                "detail": (f"Missing artifact: {STEP_9A_PATH}"),
            }
        )

        step_9a_payload: dict[
            str,
            Any,
        ] = {}
    else:
        raw_9a = load_json(STEP_9A_PATH)

        if not isinstance(
            raw_9a,
            dict,
        ):
            issues.append(
                {
                    "category": ("invalid_prerequisite"),
                    "artifact": "9A",
                    "detail": ("Step 9A artifact is not a JSON object."),
                }
            )

            step_9a_payload = {}
        else:
            step_9a_payload = raw_9a

            issues.extend(validate_step_9a(step_9a_payload))

            frozen_artifacts.append(
                {
                    "step": "9A",
                    "path": str(STEP_9A_PATH.relative_to(PROJECT_ROOT)),
                    "sha256": (sha256_file(STEP_9A_PATH)),
                    "status": (artifact_status(step_9a_payload)),
                }
            )

    substep_results: dict[
        str,
        dict[str, Any],
    ] = {}

    for (
        step,
        config,
    ) in SUBSTEPS.items():
        path = config["path"]

        name = str(config["name"])

        if not path.exists():
            issues.append(
                {
                    "category": ("missing_substep_artifact"),
                    "artifact": step,
                    "detail": (f"Missing artifact: {path}"),
                }
            )

            substep_results[step] = {
                "name": name,
                "status": None,
                "path": str(path.relative_to(PROJECT_ROOT)),
                "sha256": None,
                "issues": ["artifact_missing"],
            }

            continue

        raw = load_json(path)

        if not isinstance(
            raw,
            dict,
        ):
            issues.append(
                {
                    "category": ("invalid_substep_artifact"),
                    "artifact": step,
                    "detail": ("Artifact is not a JSON object."),
                }
            )

            substep_results[step] = {
                "name": name,
                "status": None,
                "path": str(path.relative_to(PROJECT_ROOT)),
                "sha256": (sha256_file(path)),
                "issues": ["invalid_json_object"],
            }

            continue

        status = artifact_status(raw)

        if status != "PASS":
            issues.append(
                {
                    "category": ("non_pass_substep"),
                    "artifact": step,
                    "detail": (f"{step} status is {status!r}."),
                }
            )

        validator = VALIDATORS[step]

        substep_issues = validator(raw)

        issues.extend(substep_issues)

        artifact_hash = sha256_file(path)

        frozen_artifacts.append(
            {
                "step": step,
                "path": str(path.relative_to(PROJECT_ROOT)),
                "sha256": (artifact_hash),
                "status": (status),
            }
        )

        substep_results[step] = {
            "name": name,
            "status": status,
            "path": str(path.relative_to(PROJECT_ROOT)),
            "sha256": artifact_hash,
            "validation_issue_count": (len(substep_issues)),
        }

    #
    # Consolidated coverage.
    #
    total_mutations = 0

    for step in (
        "9B.1",
        "9B.2",
        "9B.3",
        "9B.4",
    ):
        path = SUBSTEPS[step]["path"]

        if not path.exists():
            continue

        payload = load_json(path)

        if not isinstance(
            payload,
            dict,
        ):
            continue

        mutation_count = get_nested(
            payload,
            "mutation_summary",
            "mutations",
        )

        if isinstance(
            mutation_count,
            int,
        ):
            total_mutations += mutation_count

    step_9b5_payload: dict[
        str,
        Any,
    ] = {}

    if STEP_9B5_PATH.exists():
        raw_9b5 = load_json(STEP_9B5_PATH)

        if isinstance(
            raw_9b5,
            dict,
        ):
            step_9b5_payload = raw_9b5

    total_failure_runs = get_nested(
        step_9b5_payload,
        "scenario_summary",
        "total_failure_runs",
    )

    successful_recoveries = get_nested(
        step_9b5_payload,
        "scenario_summary",
        "successful_recoveries",
    )

    expected_total_mutations = 12 + 12 + 12 + 13

    if total_mutations != expected_total_mutations:
        issues.append(
            {
                "category": ("total_mutation_coverage_mismatch"),
                "artifact": "9B",
                "detail": (
                    f"Expected "
                    f"{expected_total_mutations} "
                    f"robustness mutations; "
                    f"found {total_mutations}."
                ),
            }
        )

    if total_failure_runs != 10:
        issues.append(
            {
                "category": ("failure_run_coverage_mismatch"),
                "artifact": "9B",
                "detail": ("Expected 10 repeated failure runs in 9B.5."),
            }
        )

    if successful_recoveries != 10:
        issues.append(
            {
                "category": ("recovery_coverage_mismatch"),
                "artifact": "9B",
                "detail": ("Expected 10 successful recoveries in 9B.5."),
            }
        )

    all_substeps_pass = all(
        substep_results.get(
            step,
            {},
        ).get("status")
        == "PASS"
        for step in SUBSTEPS
    )

    all_substeps_validated = all(
        substep_results.get(
            step,
            {},
        ).get(
            "validation_issue_count",
            1,
        )
        == 0
        for step in SUBSTEPS
    )

    production_immutability_confirmed = all(
        (
            (
                get_nested(
                    load_json(SUBSTEPS[step]["path"]),
                    "mutation_summary",
                    (
                        "production_cases_unchanged"
                        if step
                        in {
                            "9B.3",
                            "9B.4",
                        }
                        else ("production_case_unchanged")
                    ),
                )
                is True
            )
            if step
            in {
                "9B.1",
                "9B.2",
                "9B.3",
                "9B.4",
            }
            else (
                get_nested(
                    load_json(STEP_9B5_PATH),
                    "scenario_summary",
                    "production_case_unchanged",
                )
                is True
            )
        )
        for step in SUBSTEPS
        if SUBSTEPS[step]["path"].exists()
    )

    overall_pass = all(
        (
            artifact_status(step_9a_payload) == "PASS",
            all_substeps_pass,
            all_substeps_validated,
            total_mutations == expected_total_mutations,
            total_failure_runs == 10,
            successful_recoveries == 10,
            production_immutability_confirmed,
            len(issues) == 0,
        )
    )

    status = "PASS" if overall_pass else "FAIL"

    output = {
        "schema_version": ("1.0"),
        "acceptance_step": ("9B.6"),
        "acceptance_name": ("Consolidated Robustness Summary / Step 9B Freeze"),
        "status": (status),
        "evaluated_at": (datetime.now(UTC).isoformat()),
        "release_baseline": {
            "step_9a_status": (artifact_status(step_9a_payload)),
            "step_9a_path": str(STEP_9A_PATH.relative_to(PROJECT_ROOT)),
        },
        "substeps": (substep_results),
        "coverage": {
            "robustness_substeps": 5,
            "robustness_substeps_passed": sum(
                1 for value in substep_results.values() if value.get("status") == "PASS"
            ),
            "mutation_tests_9b1_to_9b4": (total_mutations),
            "expected_mutation_tests_9b1_to_9b4": (expected_total_mutations),
            "deterministic_failure_scenarios": (
                get_nested(
                    step_9b5_payload,
                    "scenario_summary",
                    "scenarios",
                )
            ),
            "repeated_failure_runs": (total_failure_runs),
            "successful_recoveries": (successful_recoveries),
        },
        "robustness_domains": {
            "missing_partial_artifacts": (
                substep_results.get(
                    "9B.1",
                    {},
                ).get("status")
            ),
            "malformed_schema_invalid_inputs": (
                substep_results.get(
                    "9B.2",
                    {},
                ).get("status")
            ),
            "provenance_integrity": (
                substep_results.get(
                    "9B.3",
                    {},
                ).get("status")
            ),
            "timeline_medication_semantics": (
                substep_results.get(
                    "9B.4",
                    {},
                ).get("status")
            ),
            "determinism_and_recovery": (
                substep_results.get(
                    "9B.5",
                    {},
                ).get("status")
            ),
        },
        "acceptance_criteria": {
            "step_9a_baseline_pass": (artifact_status(step_9a_payload) == "PASS"),
            "all_9b_substeps_pass": (all_substeps_pass),
            "all_9b_substeps_validated": (all_substeps_validated),
            "expected_mutation_coverage_complete": (total_mutations == expected_total_mutations),
            "deterministic_failure_runs_complete": (total_failure_runs == 10),
            "all_recovery_runs_pass": (successful_recoveries == 10),
            "production_immutability_confirmed": (production_immutability_confirmed),
            "freeze_has_no_validation_issues": (len(issues) == 0),
        },
        "validation_issue_count": (len(issues)),
        "validation_issues": (issues),
        "frozen_artifact_count": (len(frozen_artifacts)),
        "frozen_artifacts": (frozen_artifacts),
        "ready_for_9c": (overall_pass),
        "methodological_notes": [
            ("Step 9B.6 is a read-only consolidation and freeze gate."),
            (
                "It does not rerun robustness "
                "mutations or intentionally modify "
                "investigation-case artifacts."
            ),
            ("Step 9B.1 through 9B.4 contribute 49 mutation tests in total."),
            (
                "Step 9B.5 contributes five "
                "failure/recovery scenarios executed "
                "twice, for ten repeated failure "
                "runs and ten recovery checks."
            ),
            (
                "Production-artifact immutability "
                "must be confirmed independently "
                "by every robustness substep."
            ),
            (
                "SHA-256 hashes freeze the "
                "authoritative Step 9A and "
                "Step 9B.1 through 9B.5 "
                "evaluation artifacts."
            ),
            (
                "A PASS establishes robustness "
                "against the tested failure modes; "
                "it does not imply universal "
                "clinical correctness or exhaustive "
                "coverage of all possible malformed "
                "inputs."
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
    print("STEP 9B.6 — CONSOLIDATED ROBUSTNESS SUMMARY / 9B FREEZE")
    print("=" * 72)

    print(f"Overall Step 9B status:           {status}")

    print()
    print("Release baseline")
    print("-" * 72)

    print(f"Step 9A:                         {artifact_status(step_9a_payload)}")

    print()
    print("Robustness substeps")
    print("-" * 72)

    for step in (
        "9B.1",
        "9B.2",
        "9B.3",
        "9B.4",
        "9B.5",
    ):
        result = substep_results.get(
            step,
            {},
        )

        print(f"{step:<6}                           {result.get('status')}")

    print()
    print("Coverage")
    print("-" * 72)

    print(f"Mutation tests 9B.1–9B.4:         {total_mutations} / {expected_total_mutations}")

    print(f"9B.5 failure runs:                {total_failure_runs} / 10")

    print(f"9B.5 successful recoveries:       {successful_recoveries} / 10")

    print()
    print("Integrity")
    print("-" * 72)

    print(f"Production immutability:          {production_immutability_confirmed}")

    print(f"Validation issues:                {len(issues)}")

    print(f"Frozen artifacts:                 {len(frozen_artifacts)}")

    print()
    print(f"Ready for Step 9C:                {overall_pass}")

    print()
    print("Saved Step-9B freeze to:")

    print(OUTPUT_PATH)

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())

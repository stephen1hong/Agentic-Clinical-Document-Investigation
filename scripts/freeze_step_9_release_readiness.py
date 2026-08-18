from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EVALUATION_ROOT = PROJECT_ROOT / "data" / "evaluation"

STEP_9A_PATH = EVALUATION_ROOT / "step_9a" / "end_to_end_regression.json"

STEP_9B_PATH = EVALUATION_ROOT / "step_9b_final" / "step_9b_robustness_summary.json"

STEP_9C_PATH = EVALUATION_ROOT / "step_9c" / "final_report_human_review_acceptance.json"

OUTPUT_DIR = EVALUATION_ROOT / "step_9_final"

OUTPUT_PATH = OUTPUT_DIR / "step_9_release_readiness_summary.json"


EXPECTED_CASE_COUNT = 20
EXPECTED_FINDING_COUNT = 317
EXPECTED_REVIEW_FINDING_COUNT = 1
EXPECTED_CONTEXTUAL_FINDING_COUNT = 316
EXPECTED_REVIEW_CASE_COUNT = 1

EXPECTED_9B_MUTATIONS = 49
EXPECTED_9B_FAILURE_RUNS = 10
EXPECTED_9B_RECOVERIES = 10


def load_json(
    path: Path,
) -> Any:
    """Load JSON artifact."""

    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(
    path: Path,
) -> str:
    """Return SHA-256 digest for one file."""

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def artifact_status(
    payload: dict[str, Any],
) -> str | None:
    """Return normalized artifact status."""

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


def get_nested(
    payload: dict[str, Any],
    *keys: str,
) -> Any:
    """Safely read a nested dictionary field."""

    current: Any = payload

    for key in keys:
        if not isinstance(
            current,
            dict,
        ):
            return None

        current = current.get(key)

    return current


def append_issue(
    issues: list[dict[str, Any]],
    *,
    artifact: str,
    category: str,
    detail: str,
) -> None:
    """Append normalized release-readiness issue."""

    issues.append(
        {
            "artifact": artifact,
            "category": category,
            "detail": detail,
        }
    )


def load_required_artifact(
    *,
    path: Path,
    step: str,
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    """Load one required evaluation artifact."""

    if not path.exists():
        append_issue(
            issues,
            artifact=step,
            category=("missing_release_artifact"),
            detail=(f"Required artifact does not exist: {path}"),
        )

        return {}

    try:
        payload = load_json(path)
    except Exception as exc:
        append_issue(
            issues,
            artifact=step,
            category=("invalid_release_artifact"),
            detail=(f"{type(exc).__name__}: {exc}"),
        )

        return {}

    if not isinstance(
        payload,
        dict,
    ):
        append_issue(
            issues,
            artifact=step,
            category=("invalid_release_artifact"),
            detail=("Release artifact must contain a JSON object."),
        )

        return {}

    return payload


def validate_pass_status(
    *,
    payload: dict[str, Any],
    step: str,
    issues: list[dict[str, Any]],
) -> None:
    """Require one release artifact to be PASS."""

    status = artifact_status(payload)

    if status != "PASS":
        append_issue(
            issues,
            artifact=step,
            category=("non_pass_release_gate"),
            detail=(f"{step} status is {status!r}; expected 'PASS'."),
        )


def validate_step_9b(
    *,
    payload: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    """Validate frozen Step 9B release contract."""

    if payload.get("ready_for_9c") is not True:
        append_issue(
            issues,
            artifact="9B",
            category=("step_9b_not_ready"),
            detail=("Step 9B does not report ready_for_9c=true."),
        )

    validation_issue_count = payload.get("validation_issue_count")

    if validation_issue_count != 0:
        append_issue(
            issues,
            artifact="9B",
            category=("step_9b_validation_issues"),
            detail=(f"Step 9B validation issue count is {validation_issue_count}; expected 0."),
        )

    mutation_count = get_nested(
        payload,
        "coverage",
        "mutation_tests_9b1_to_9b4",
    )

    if mutation_count != EXPECTED_9B_MUTATIONS:
        append_issue(
            issues,
            artifact="9B",
            category=("step_9b_mutation_coverage_mismatch"),
            detail=(
                f"Expected {EXPECTED_9B_MUTATIONS} 9B.1–9B.4 mutations; found {mutation_count}."
            ),
        )

    failure_runs = get_nested(
        payload,
        "coverage",
        "repeated_failure_runs",
    )

    if failure_runs != EXPECTED_9B_FAILURE_RUNS:
        append_issue(
            issues,
            artifact="9B",
            category=("step_9b_failure_run_mismatch"),
            detail=(f"Expected {EXPECTED_9B_FAILURE_RUNS} failure runs; found {failure_runs}."),
        )

    recoveries = get_nested(
        payload,
        "coverage",
        "successful_recoveries",
    )

    if recoveries != EXPECTED_9B_RECOVERIES:
        append_issue(
            issues,
            artifact="9B",
            category=("step_9b_recovery_mismatch"),
            detail=(
                f"Expected {EXPECTED_9B_RECOVERIES} successful recoveries; found {recoveries}."
            ),
        )

    immutability = get_nested(
        payload,
        "acceptance_criteria",
        "production_immutability_confirmed",
    )

    if immutability is not True:
        append_issue(
            issues,
            artifact="9B",
            category=("production_immutability_not_confirmed"),
            detail=("Step 9B does not confirm production-artifact immutability."),
        )


def validate_step_9c(
    *,
    payload: dict[str, Any],
    issues: list[dict[str, Any]],
) -> None:
    """Validate Step 9C release contract."""

    if payload.get("ready_for_9d") is not True:
        append_issue(
            issues,
            artifact="9C",
            category=("step_9c_not_ready"),
            detail=("Step 9C does not report ready_for_9d=true."),
        )

    population = payload.get(
        "population_results",
        {},
    )

    expected_population = {
        "cases": (EXPECTED_CASE_COUNT),
        "cases_passed": (EXPECTED_CASE_COUNT),
        "cases_failed": 0,
        "findings": (EXPECTED_FINDING_COUNT),
        "review_required_findings": (EXPECTED_REVIEW_FINDING_COUNT),
        "contextual_findings": (EXPECTED_CONTEXTUAL_FINDING_COUNT),
        "cases_requiring_review": (EXPECTED_REVIEW_CASE_COUNT),
    }

    for (
        field,
        expected,
    ) in expected_population.items():
        actual = (
            population.get(field)
            if isinstance(
                population,
                dict,
            )
            else None
        )

        if actual != expected:
            append_issue(
                issues,
                artifact="9C",
                category=("step_9c_population_mismatch"),
                detail=(f"{field}: expected {expected}; found {actual}."),
            )

    issue_count = get_nested(
        payload,
        "issue_summary",
        "issue_count",
    )

    if issue_count != 0:
        append_issue(
            issues,
            artifact="9C",
            category=("step_9c_acceptance_issues"),
            detail=(f"Step 9C reports {issue_count} acceptance issues."),
        )

    criteria = payload.get(
        "acceptance_criteria",
        {},
    )

    required_true = (
        "all_cases_pass",
        "final_report_integrity_pass",
        "machine_to_reviewer_projection_exact",
        "review_counts_consistent",
        "review_status_routing_consistent",
        "reviewer_markdown_acceptable",
        "frozen_population_preserved",
        "machine_outputs_immutable",
        "zero_acceptance_issues",
    )

    for field in required_true:
        actual = (
            criteria.get(field)
            if isinstance(
                criteria,
                dict,
            )
            else None
        )

        if actual is not True:
            append_issue(
                issues,
                artifact="9C",
                category=("step_9c_acceptance_criterion_failed"),
                detail=(f"{field} is not True."),
            )


def build_frozen_artifact(
    *,
    step: str,
    path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Build frozen-artifact hash record."""

    return {
        "step": step,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "status": (artifact_status(payload)),
        "sha256": (sha256_file(path) if path.exists() else None),
    }


def main() -> int:
    """Freeze final Step 9 release-readiness state."""

    issues: list[dict[str, Any]] = []

    step_9a = load_required_artifact(
        path=STEP_9A_PATH,
        step="9A",
        issues=issues,
    )

    step_9b = load_required_artifact(
        path=STEP_9B_PATH,
        step="9B",
        issues=issues,
    )

    step_9c = load_required_artifact(
        path=STEP_9C_PATH,
        step="9C",
        issues=issues,
    )

    if step_9a:
        validate_pass_status(
            payload=step_9a,
            step="9A",
            issues=issues,
        )

    if step_9b:
        validate_pass_status(
            payload=step_9b,
            step="9B",
            issues=issues,
        )

        validate_step_9b(
            payload=step_9b,
            issues=issues,
        )

    if step_9c:
        validate_pass_status(
            payload=step_9c,
            step="9C",
            issues=issues,
        )

        validate_step_9c(
            payload=step_9c,
            issues=issues,
        )

    all_gates_pass = all(
        (
            artifact_status(step_9a) == "PASS",
            artifact_status(step_9b) == "PASS",
            artifact_status(step_9c) == "PASS",
        )
    )

    step_9b_ready = step_9b.get("ready_for_9c") is True

    step_9c_ready = step_9c.get("ready_for_9d") is True

    zero_release_issues = len(issues) == 0

    overall_pass = all(
        (
            all_gates_pass,
            step_9b_ready,
            step_9c_ready,
            zero_release_issues,
        )
    )

    status = "PASS" if overall_pass else "FAIL"

    frozen_artifacts: list[dict[str, Any]] = []

    for (
        step,
        path,
        payload,
    ) in (
        (
            "9A",
            STEP_9A_PATH,
            step_9a,
        ),
        (
            "9B",
            STEP_9B_PATH,
            step_9b,
        ),
        (
            "9C",
            STEP_9C_PATH,
            step_9c,
        ),
    ):
        if not path.exists():
            continue

        frozen_artifacts.append(
            build_frozen_artifact(
                step=step,
                path=path,
                payload=payload,
            )
        )

    output = {
        "schema_version": ("1.0"),
        "acceptance_step": ("9D"),
        "acceptance_name": ("Release-Readiness Freeze"),
        "status": (status),
        "frozen_at": (datetime.now(UTC).isoformat()),
        "release_gates": {
            "9A": {
                "status": (artifact_status(step_9a)),
                "purpose": ("Full end-to-end persisted-output regression"),
            },
            "9B": {
                "status": (artifact_status(step_9b)),
                "purpose": ("Robustness and failure-mode acceptance"),
                "ready_for_9c": (step_9b.get("ready_for_9c")),
            },
            "9C": {
                "status": (artifact_status(step_9c)),
                "purpose": ("Final report and human-review acceptance"),
                "ready_for_9d": (step_9c.get("ready_for_9d")),
            },
        },
        "release_population": {
            "cases": (
                get_nested(
                    step_9c,
                    "population_results",
                    "cases",
                )
            ),
            "findings": (
                get_nested(
                    step_9c,
                    "population_results",
                    "findings",
                )
            ),
            "review_required_findings": (
                get_nested(
                    step_9c,
                    "population_results",
                    "review_required_findings",
                )
            ),
            "contextual_findings": (
                get_nested(
                    step_9c,
                    "population_results",
                    "contextual_findings",
                )
            ),
            "cases_requiring_review": (
                get_nested(
                    step_9c,
                    "population_results",
                    "cases_requiring_review",
                )
            ),
        },
        "robustness_coverage": {
            "mutation_tests_9b1_to_9b4": (
                get_nested(
                    step_9b,
                    "coverage",
                    "mutation_tests_9b1_to_9b4",
                )
            ),
            "repeated_failure_runs": (
                get_nested(
                    step_9b,
                    "coverage",
                    "repeated_failure_runs",
                )
            ),
            "successful_recoveries": (
                get_nested(
                    step_9b,
                    "coverage",
                    "successful_recoveries",
                )
            ),
        },
        "release_acceptance": {
            "all_release_gates_pass": (all_gates_pass),
            "step_9b_ready_for_9c": (step_9b_ready),
            "step_9c_ready_for_9d": (step_9c_ready),
            "final_report_integrity": (
                get_nested(
                    step_9c,
                    "acceptance_criteria",
                    "final_report_integrity_pass",
                )
            ),
            "human_review_projection_exact": (
                get_nested(
                    step_9c,
                    "acceptance_criteria",
                    "machine_to_reviewer_projection_exact",
                )
            ),
            "human_review_routing_consistent": (
                get_nested(
                    step_9c,
                    "acceptance_criteria",
                    "review_status_routing_consistent",
                )
            ),
            "production_immutability_confirmed": all(
                (
                    get_nested(
                        step_9b,
                        "acceptance_criteria",
                        "production_immutability_confirmed",
                    )
                    is True,
                    get_nested(
                        step_9c,
                        "acceptance_criteria",
                        "machine_outputs_immutable",
                    )
                    is True,
                )
            ),
            "zero_release_validation_issues": (zero_release_issues),
        },
        "validation_issue_count": (len(issues)),
        "validation_issues": (issues),
        "frozen_artifact_count": (len(frozen_artifacts)),
        "frozen_artifacts": (frozen_artifacts),
        "step_9_complete": (overall_pass),
        "release_ready": (overall_pass),
        "methodological_notes": [
            ("Step 9D is a read-only release-readiness freeze."),
            (
                "It does not rerun production "
                "investigation workflows, "
                "regenerate reviewer artifacts, "
                "or intentionally modify "
                "investigation-case outputs."
            ),
            ("Step 9A establishes the persisted-output regression baseline."),
            (
                "Step 9B establishes robustness "
                "against the tested missing-artifact, "
                "schema-invalid, provenance, "
                "timeline, medication, deterministic "
                "failure, and recovery scenarios."
            ),
            (
                "Step 9C establishes release "
                "acceptance of final investigation "
                "reports and human-review projections."
            ),
            ("SHA-256 hashes freeze the authoritative Step 9A, 9B, and 9C evaluation artifacts."),
            (
                "A PASS means the current tested "
                "release satisfies the defined "
                "Step 9 acceptance criteria."
            ),
            (
                "It does not imply universal "
                "clinical correctness, exhaustive "
                "failure-mode coverage, or external "
                "regulatory validation."
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
    print("STEP 9D — RELEASE-READINESS FREEZE")
    print("=" * 72)

    print(f"Overall Step 9 status:            {status}")

    print()
    print("Release gates")
    print("-" * 72)

    print(f"9A — End-to-end regression:       {artifact_status(step_9a)}")

    print(f"9B — Robustness:                  {artifact_status(step_9b)}")

    print(f"9C — Report / human review:       {artifact_status(step_9c)}")

    print()
    print("Release population")
    print("-" * 72)

    print(
        "Cases:                           "
        f"{get_nested(step_9c, 'population_results', 'cases')}"
        f" / {EXPECTED_CASE_COUNT}"
    )

    print(
        "Findings:                        "
        f"{get_nested(step_9c, 'population_results', 'findings')}"
        f" / {EXPECTED_FINDING_COUNT}"
    )

    print(
        "Review-required findings:        "
        f"{get_nested(step_9c, 'population_results', 'review_required_findings')}"
        f" / {EXPECTED_REVIEW_FINDING_COUNT}"
    )

    print(
        "Contextual findings:             "
        f"{get_nested(step_9c, 'population_results', 'contextual_findings')}"
        f" / {EXPECTED_CONTEXTUAL_FINDING_COUNT}"
    )

    print(
        "Cases requiring review:          "
        f"{get_nested(step_9c, 'population_results', 'cases_requiring_review')}"
        f" / {EXPECTED_REVIEW_CASE_COUNT}"
    )

    print()
    print("Robustness")
    print("-" * 72)

    print(
        "9B mutations:                    "
        f"{get_nested(step_9b, 'coverage', 'mutation_tests_9b1_to_9b4')}"
        f" / {EXPECTED_9B_MUTATIONS}"
    )

    print(
        "Repeated failure runs:           "
        f"{get_nested(step_9b, 'coverage', 'repeated_failure_runs')}"
        f" / {EXPECTED_9B_FAILURE_RUNS}"
    )

    print(
        "Successful recoveries:           "
        f"{get_nested(step_9b, 'coverage', 'successful_recoveries')}"
        f" / {EXPECTED_9B_RECOVERIES}"
    )

    print()
    print("Integrity")
    print("-" * 72)

    print(f"Release validation issues:       {len(issues)}")

    print(f"Frozen artifacts:                {len(frozen_artifacts)}")

    print()
    print(f"Step 9 complete:                  {overall_pass}")

    print(f"Release ready:                    {overall_pass}")

    print()
    print("Saved Step-9 release freeze to:")

    print(OUTPUT_PATH)

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())

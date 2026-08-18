from __future__ import annotations

import importlib.util
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

PACKAGE_ROOT = PROJECT_ROOT / "src" / "clinical_investigation"

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

STEP_9_RELEASE_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "step_9_final" / "step_9_release_readiness_summary.json"
)

REQUIRED_IMPORTS = (
    "clinical_investigation",
    "langgraph",
    "pydantic",
)

MINIMUM_PYTHON = (
    3,
    12,
)


@dataclass(frozen=True)
class CheckResult:
    """One release-environment check."""

    name: str
    status: str
    detail: str


def check(
    *,
    condition: bool,
    name: str,
    success_detail: str,
    failure_detail: str,
) -> CheckResult:
    """Build a normalized PASS/FAIL check."""

    return CheckResult(
        name=name,
        status=("PASS" if condition else "FAIL"),
        detail=(success_detail if condition else failure_detail),
    )


def load_json(
    path: Path,
) -> Any:
    """Load JSON from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def check_python_version() -> CheckResult:
    """Validate the supported Python baseline."""

    actual = (
        sys.version_info.major,
        sys.version_info.minor,
    )

    condition = actual >= MINIMUM_PYTHON

    return check(
        condition=condition,
        name="python_version",
        success_detail=(f"Python {platform.python_version()} meets the release baseline."),
        failure_detail=(
            "Python "
            f"{platform.python_version()} "
            "is below the required "
            f"{MINIMUM_PYTHON[0]}."
            f"{MINIMUM_PYTHON[1]} baseline."
        ),
    )


def check_required_path(
    *,
    name: str,
    path: Path,
    expect_directory: bool,
) -> CheckResult:
    """Validate one required release path."""

    exists = path.exists()

    correct_type = path.is_dir() if expect_directory else path.is_file()

    condition = exists and correct_type

    expected_type = "directory" if expect_directory else "file"

    return check(
        condition=condition,
        name=name,
        success_detail=(f"Required {expected_type} exists: {path}"),
        failure_detail=(f"Required {expected_type} is missing or invalid: {path}"),
    )


def check_required_import(
    module_name: str,
) -> CheckResult:
    """Validate one required Python import."""

    try:
        spec = importlib.util.find_spec(module_name)
    except (
        ImportError,
        ModuleNotFoundError,
        ValueError,
    ) as exc:
        return CheckResult(
            name=(f"import:{module_name}"),
            status="FAIL",
            detail=(f"{type(exc).__name__}: {exc}"),
        )

    return check(
        condition=(spec is not None),
        name=(f"import:{module_name}"),
        success_detail=(f"Python module {module_name!r} is available."),
        failure_detail=(f"Python module {module_name!r} cannot be resolved."),
    )


def check_release_artifact() -> list[CheckResult]:
    """Validate the frozen Step 9 release artifact."""

    results: list[CheckResult] = []

    if not STEP_9_RELEASE_PATH.is_file():
        results.append(
            CheckResult(
                name=("step_9_release_artifact"),
                status="FAIL",
                detail=(f"Frozen Step 9 release artifact is missing: {STEP_9_RELEASE_PATH}"),
            )
        )

        return results

    results.append(
        CheckResult(
            name=("step_9_release_artifact"),
            status="PASS",
            detail=("Frozen Step 9 release artifact exists."),
        )
    )

    try:
        payload = load_json(STEP_9_RELEASE_PATH)
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        results.append(
            CheckResult(
                name=("step_9_release_parse"),
                status="FAIL",
                detail=(f"{type(exc).__name__}: {exc}"),
            )
        )

        return results

    if not isinstance(
        payload,
        dict,
    ):
        results.append(
            CheckResult(
                name=("step_9_release_schema"),
                status="FAIL",
                detail=("Step 9 release artifact must contain a JSON object."),
            )
        )

        return results

    results.append(
        check(
            condition=(payload.get("status") == "PASS"),
            name=("step_9_status"),
            success_detail=("Step 9 release status is PASS."),
            failure_detail=(
                f"Step 9 release status is {payload.get('status')!r}; expected 'PASS'."
            ),
        )
    )

    results.append(
        check(
            condition=(payload.get("step_9_complete") is True),
            name=("step_9_complete"),
            success_detail=("Step 9 is marked complete."),
            failure_detail=("Step 9 is not marked complete."),
        )
    )

    results.append(
        check(
            condition=(payload.get("release_ready") is True),
            name=("release_ready"),
            success_detail=("Frozen release is marked release-ready."),
            failure_detail=("Frozen release is not marked release-ready."),
        )
    )

    results.append(
        check(
            condition=(payload.get("validation_issue_count") == 0),
            name=("release_validation_issues"),
            success_detail=("Frozen release has zero validation issues."),
            failure_detail=(
                "Frozen release reports "
                f"{payload.get('validation_issue_count')!r} "
                "validation issues."
            ),
        )
    )

    return results


def count_cases() -> tuple[
    int,
    CheckResult,
]:
    """Count currently available investigation cases."""

    if not CASE_ROOT.is_dir():
        return (
            0,
            CheckResult(
                name="investigation_cases",
                status="FAIL",
                detail=("Investigation case directory is unavailable."),
            ),
        )

    case_count = sum(1 for path in CASE_ROOT.iterdir() if path.is_dir())

    return (
        case_count,
        check(
            condition=(case_count > 0),
            name="investigation_cases",
            success_detail=(f"{case_count} investigation case(s) are available."),
            failure_detail=("No investigation cases are available."),
        ),
    )


def main() -> int:
    """Run release-environment checks."""

    results: list[CheckResult] = []

    results.append(check_python_version())

    results.append(
        check_required_path(
            name="pyproject",
            path=PYPROJECT_PATH,
            expect_directory=False,
        )
    )

    results.append(
        check_required_path(
            name="clinical_package",
            path=PACKAGE_ROOT,
            expect_directory=True,
        )
    )

    for module_name in REQUIRED_IMPORTS:
        results.append(check_required_import(module_name))

    case_count, case_result = count_cases()

    results.append(case_result)

    results.extend(check_release_artifact())

    failed = [result for result in results if result.status != "PASS"]

    overall_status = "PASS" if not failed else "FAIL"

    print()
    print("=" * 72)

    print("STEP 10A.6 — RELEASE ENVIRONMENT / REPRODUCIBILITY CHECK")

    print("=" * 72)

    print(f"Overall status:                   {overall_status}")

    print()
    print("Environment")

    print("-" * 72)

    print(f"Python:                          {platform.python_version()}")

    print(f"Executable:                      {sys.executable}")

    print(f"Platform:                        {platform.platform()}")

    print(f"Investigation cases:             {case_count}")

    print()
    print("Checks")

    print("-" * 72)

    for result in results:
        print(f"{result.status:<4} {result.name}")

    print()
    print("Failures")

    print("-" * 72)

    if failed:
        for result in failed:
            print(f"- {result.name}: {result.detail}")
    else:
        print("None")

    print()
    print(f"Reproducible execution ready:    {not failed}")

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

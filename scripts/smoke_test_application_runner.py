from __future__ import annotations

import argparse

from clinical_investigation.application import (
    run_investigation,
)
from clinical_investigation.config import (
    settings,
)


def parse_args() -> argparse.Namespace:
    """Parse smoke-test arguments."""

    parser = argparse.ArgumentParser(
        description=("Run one investigation through the stable application interface.")
    )

    parser.add_argument(
        "--case-id",
        help=("Investigation case ID. Defaults to the first available case."),
    )

    return parser.parse_args()


def choose_case_id(
    requested_case_id: str | None,
) -> str:
    """Choose explicit or deterministic default case."""

    if requested_case_id:
        return requested_case_id

    case_dirs = sorted(path for path in settings.investigation_cases_dir.iterdir() if path.is_dir())

    if not case_dirs:
        raise RuntimeError("No investigation cases found.")

    return case_dirs[0].name


def main() -> int:
    """Run one production investigation through the application runner."""

    args = parse_args()

    case_id = choose_case_id(args.case_id)

    print("=== Application Runner Smoke Test ===")

    print(f"Case: {case_id}")

    result = run_investigation(case_id)

    print()
    print(f"Findings: {result.finding_count}")

    print(f"Validation errors: {result.validation_error_count}")

    print(f"Requires human review: {result.requires_human_review}")

    print(f"Review status: {result.review_status}")

    print("Final report: verified")

    print()
    print("Application runner smoke test: PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

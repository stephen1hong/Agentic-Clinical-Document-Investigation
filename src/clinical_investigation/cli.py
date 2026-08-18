from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from clinical_investigation.application import run_investigation
from clinical_investigation.application.demo_cases import (
    DEMO_CASES,
    get_demo_case,
)
from clinical_investigation.config import settings


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""

    parser = argparse.ArgumentParser(
        prog="clinical-investigation",
        description="Clinical document investigation command-line interface.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    investigate_parser = subparsers.add_parser(
        "investigate",
        help="Run the investigation workflow for one persisted case.",
    )

    investigate_parser.add_argument(
        "--case-id",
        required=True,
        help="Investigation case identifier.",
    )

    investigate_parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable JSON summary.",
    )

    list_parser = subparsers.add_parser(
        "list-cases",
        help="List available investigation cases.",
    )

    list_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of case identifiers to print.",
    )

    demo_parser = subparsers.add_parser(
        "demo",
        help="Run one frozen demonstration case.",
    )

    demo_parser.add_argument(
        "demo_id",
        choices=sorted(DEMO_CASES),
        help="Frozen demonstration case identifier.",
    )

    demo_parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable JSON summary.",
    )

    return parser


def list_case_ids() -> list[str]:
    """Return persisted investigation case IDs."""

    root = settings.investigation_cases_dir

    if not root.exists():
        return []

    return [path.name for path in sorted(root.iterdir()) if path.is_dir()]


def build_investigation_payload(
    *,
    case_id: str,
) -> dict[str, Any]:
    """Run one investigation and build its release summary."""

    result = run_investigation(case_id)

    return {
        "case_id": result.case_id,
        "case_dir": str(result.case_dir),
        "finding_count": result.finding_count,
        "validation_error_count": result.validation_error_count,
        "requires_human_review": result.requires_human_review,
        "review_status": result.review_status,
        "final_report_path": str(Path(result.case_dir) / "final_investigation_report.json"),
    }


def print_json_payload(
    payload: dict[str, Any],
) -> None:
    """Print one machine-readable CLI payload."""

    print(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
    )

def print_json_error(
    exc: Exception,
) -> None:
    """Print one machine-readable CLI error."""

    payload = {
        "status": "error",
        "error_type": type(exc).__name__,
        "message": str(exc),
    }

    print(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )

def run_investigate_command(
    *,
    case_id: str,
    as_json: bool,
) -> int:
    """Execute one investigation command."""

    payload = build_investigation_payload(
        case_id=case_id,
    )

    if as_json:
        print_json_payload(payload)
        return 0

    print()
    print("Clinical Investigation")
    print("=" * 40)
    print(f"Case: {payload['case_id']}")
    print(f"Findings: {payload['finding_count']}")
    print(f"Validation errors: {payload['validation_error_count']}")
    print(f"Requires human review: {payload['requires_human_review']}")
    print(f"Review status: {payload['review_status']}")
    print(f"Final report: {payload['final_report_path']}")

    return 0


def run_demo_command(
    *,
    demo_id: str,
    as_json: bool,
) -> int:
    """Execute one frozen demonstration case."""

    demo_case = get_demo_case(demo_id)

    payload = build_investigation_payload(
        case_id=demo_case.case_id,
    )

    if payload["finding_count"] != demo_case.expected_finding_count:
        raise RuntimeError(
            "Demo finding count changed: "
            f"{demo_case.demo_id} expected "
            f"{demo_case.expected_finding_count}, "
            f"received {payload['finding_count']}."
        )

    if payload["review_status"] != demo_case.expected_review_status:
        raise RuntimeError(
            "Demo review status changed: "
            f"{demo_case.demo_id} expected "
            f"{demo_case.expected_review_status!r}, "
            f"received {payload['review_status']!r}."
        )

    if payload["requires_human_review"] != demo_case.expected_requires_human_review:
        raise RuntimeError(
            "Demo human-review requirement changed: "
            f"{demo_case.demo_id} expected "
            f"{demo_case.expected_requires_human_review}, "
            f"received {payload['requires_human_review']}."
        )

    demo_payload: dict[str, Any] = {
        "demo_id": demo_case.demo_id,
        "demo_title": demo_case.title,
        **payload,
    }

    if as_json:
        print_json_payload(demo_payload)
        return 0

    print()
    print("Clinical Investigation Demo")
    print("=" * 40)
    print(f"Demo: {demo_case.demo_id}")
    print(f"Title: {demo_case.title}")
    print(f"Case: {payload['case_id']}")
    print(f"Findings: {payload['finding_count']}")
    print(f"Validation errors: {payload['validation_error_count']}")
    print(f"Requires human review: {payload['requires_human_review']}")
    print(f"Review status: {payload['review_status']}")
    print(f"Final report: {payload['final_report_path']}")

    return 0


def run_list_cases_command(
    *,
    limit: int | None,
) -> int:
    """List persisted investigation cases."""

    case_ids = list_case_ids()

    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be greater than 0.")

        case_ids = case_ids[:limit]

    if not case_ids:
        print("No investigation cases found.")
        return 1

    for case_id in case_ids:
        print(case_id)

    return 0


def main() -> int:
    """CLI entrypoint."""

    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "investigate":
            return run_investigate_command(
                case_id=args.case_id,
                as_json=args.json,
            )

        if args.command == "list-cases":
            return run_list_cases_command(
                limit=args.limit,
            )

        if args.command == "demo":
            return run_demo_command(
                demo_id=args.demo_id,
                as_json=args.json,
            )

    except (
        FileNotFoundError,
        NotADirectoryError,
        RuntimeError,
        ValueError,
    ) as exc:
        if getattr(args, "json", False):
            print_json_error(exc)
        else:
            print(f"ERROR: {exc}", file=sys.stderr)

        return 1

    parser.error(f"Unsupported command: {args.command}")

    return 2


if __name__ == "__main__":
    raise SystemExit(main())

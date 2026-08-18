from __future__ import annotations

import argparse

# import json
from pathlib import Path
from typing import Any

from clinical_investigation.config import settings
from clinical_investigation.review.models import (
    FindingReviewDecision,
)
from clinical_investigation.review.service import (
    complete_case_review,
    get_report_findings,
    load_final_report,
    record_finding_decision,
    start_case_review,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=("Interactively review one clinical investigation case.")
    )

    parser.add_argument(
        "--case-id",
        required=True,
        help="Investigation case ID.",
    )

    parser.add_argument(
        "--reviewer",
        required=True,
        help="Reviewer name or identifier.",
    )

    return parser.parse_args()


def get_case_dir(
    case_id: str,
) -> Path:
    """Resolve and validate one investigation case directory."""

    case_dir = settings.investigation_cases_dir / case_id

    if not case_dir.exists():
        raise FileNotFoundError(f"Investigation case not found: {case_dir}")

    return case_dir


def get_required_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return only findings requiring human review."""

    return [
        finding
        for finding in get_report_findings(report)
        if bool(
            finding.get(
                "requires_human_review",
                False,
            )
        )
    ]


def print_case_header(
    *,
    report: dict[str, Any],
    required_findings: list[dict[str, Any]],
) -> None:
    """Print reviewer-facing case summary."""

    print()
    print("=" * 72)
    print("CLINICAL INVESTIGATION HUMAN REVIEW")
    print("=" * 72)

    print()
    print(f"Case ID: {report.get('case_id', '')}")

    print(f"Review status: {report.get('review_status', 'unknown')}")

    print(f"Findings requiring review: {len(required_findings)}")

    print(f"Total findings: {report.get('finding_count', 0)}")

    print()
    print("Investigation question:")
    print(
        report.get(
            "investigation_question",
            "",
        )
    )

    print()
    print("Executive summary:")
    print(
        report.get(
            "executive_summary",
            "",
        )
    )


def print_finding(
    *,
    finding: dict[str, Any],
    index: int,
    total: int,
) -> None:
    """Print one finding requiring review."""

    print()
    print("-" * 72)
    print(f"Finding {index} of {total}")
    print("-" * 72)

    print(f"Finding ID: {finding.get('finding_id', '')}")

    print(f"Type: {finding.get('finding_type', '')}")

    print(f"Subtype: {finding.get('subtype', '')}")

    print(f"Severity: {finding.get('severity', '')}")

    print(f"Confidence: {finding.get('confidence', '')}")

    print()
    print("Title:")
    print(
        finding.get(
            "title",
            "",
        )
    )

    print()
    print("Summary:")
    print(
        finding.get(
            "summary",
            "",
        )
    )

    evidence_ids = list(
        finding.get(
            "evidence_ids",
            [],
        )
    )

    if evidence_ids:
        print()
        print("Evidence IDs:")

        for evidence_id in evidence_ids:
            print(f"  - {evidence_id}")


def prompt_decision() -> FindingReviewDecision:
    """Prompt until the reviewer enters a valid decision."""

    print()
    print("Decision:")
    print("  1 = accepted")
    print("  2 = dismissed")
    print("  3 = needs_follow_up")

    mapping = {
        "1": FindingReviewDecision.ACCEPTED,
        "2": FindingReviewDecision.DISMISSED,
        "3": FindingReviewDecision.NEEDS_FOLLOW_UP,
        "accepted": FindingReviewDecision.ACCEPTED,
        "dismissed": FindingReviewDecision.DISMISSED,
        "needs_follow_up": (FindingReviewDecision.NEEDS_FOLLOW_UP),
    }

    while True:
        value = input("> ").strip().lower()

        decision = mapping.get(value)

        if decision is not None:
            return decision

        print("Invalid decision. Enter 1, 2, 3, accepted, dismissed, or needs_follow_up.")


def prompt_rationale() -> str:
    """Prompt for reviewer rationale."""

    print()
    print("Rationale:")

    return input("> ").strip()


def review_required_findings(
    *,
    case_dir: Path,
    report: dict[str, Any],
    reviewer: str,
) -> None:
    """Interactively review all required findings."""

    required_findings = get_required_findings(report)

    if not required_findings:
        print()
        print("No findings require human review.")
        return

    total = len(required_findings)

    for index, finding in enumerate(
        required_findings,
        start=1,
    ):
        print_finding(
            finding=finding,
            index=index,
            total=total,
        )

        decision = prompt_decision()

        rationale = prompt_rationale()

        record_finding_decision(
            case_dir=case_dir,
            finding_id=str(finding["finding_id"]),
            decision=decision,
            rationale=rationale,
            reviewer=reviewer,
        )

        print()
        print("Decision saved.")


def prompt_case_notes() -> str:
    """Prompt for optional case-level notes."""

    print()
    print("Case notes (optional):")

    return input("> ").strip()


def main() -> int:
    """Run the interactive human-review CLI."""

    args = parse_args()

    try:
        case_dir = get_case_dir(args.case_id)

        report = load_final_report(case_dir)

        required_findings = get_required_findings(report)

        print_case_header(
            report=report,
            required_findings=required_findings,
        )

        start_case_review(
            case_dir=case_dir,
            reviewer=args.reviewer,
        )

        if not required_findings:
            print()
            print("This case does not require human review.")
            return 0

        review_required_findings(
            case_dir=case_dir,
            report=report,
            reviewer=args.reviewer,
        )

        case_notes = prompt_case_notes()

        completed = complete_case_review(
            case_dir=case_dir,
            reviewer=args.reviewer,
            case_notes=case_notes,
        )

        print()
        print("=" * 72)
        print("REVIEW COMPLETED")
        print("=" * 72)

        print(f"Status: {completed.status.value}")

        print(f"Decisions recorded: {len(completed.finding_reviews)}")

        print(f"Review record: {case_dir / 'human_review.json'}")

        return 0

    except Exception as exc:
        print()
        print(f"ERROR: {type(exc).__name__}: {exc}")

        return 1


if __name__ == "__main__":
    raise SystemExit(main())

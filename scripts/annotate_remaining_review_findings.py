from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

FINAL_REPORT_FILENAME = "final_investigation_report.json"
GOLD_LABEL_FILENAME = "gold_labels.json"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=("Sequentially annotate all remaining findings that require human review.")
    )

    parser.add_argument(
        "--evaluator",
        required=True,
        help="Evaluator name or identifier.",
    )

    return parser.parse_args()


def find_project_root() -> Path:
    """Return the project root."""

    return Path(__file__).resolve().parents[1]


def load_json(
    path: Path,
) -> dict[str, Any]:
    """Load a JSON object."""

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")

    return payload


def get_required_finding_ids(
    report: dict[str, Any],
) -> set[str]:
    """Return finding IDs requiring human review."""

    findings = list(
        report.get(
            "high_priority_findings",
            [],
        )
    ) + list(
        report.get(
            "other_findings",
            [],
        )
    )

    return {
        str(finding["finding_id"])
        for finding in findings
        if bool(
            finding.get(
                "requires_human_review",
                False,
            )
        )
    }


def get_remaining_required_ids(
    *,
    report_path: Path,
    gold_path: Path,
) -> list[str]:
    """Return required findings that remain unevaluated."""

    report = load_json(report_path)

    gold = load_json(gold_path)

    required_ids = get_required_finding_ids(report)

    remaining_ids = [
        str(label["finding_id"])
        for label in gold.get(
            "finding_labels",
            [],
        )
        if (
            str(
                label.get(
                    "finding_id",
                    "",
                )
            )
            in required_ids
            and label.get("disposition") == "not_evaluated"
        )
    ]

    return sorted(remaining_ids)


def main() -> int:
    """Run annotation sessions for all remaining review cases."""

    args = parse_args()

    project_root = find_project_root()

    investigation_root = project_root / "data" / "investigation_cases"

    gold_root = project_root / "data" / "evaluation" / "gold_labels"

    annotation_script = project_root / "scripts" / "annotate_gold_findings.py"

    queue: list[tuple[str, int]] = []

    for case_dir in sorted(path for path in investigation_root.iterdir() if path.is_dir()):
        case_id = case_dir.name

        report_path = case_dir / FINAL_REPORT_FILENAME

        gold_path = gold_root / case_id / GOLD_LABEL_FILENAME

        if not report_path.exists() or not gold_path.exists():
            continue

        remaining_ids = get_remaining_required_ids(
            report_path=report_path,
            gold_path=gold_path,
        )

        if remaining_ids:
            queue.append(
                (
                    case_id,
                    len(remaining_ids),
                )
            )

    total_remaining = sum(count for _, count in queue)

    print()
    print("=" * 72)
    print("REVIEW-REQUIRED GOLD ANNOTATION QUEUE")
    print("=" * 72)

    print(f"Cases remaining: {len(queue)}")

    print(f"Findings remaining: {total_remaining}")

    if not queue:
        print()
        print("All review-required findings are already evaluated.")
        return 0

    print()

    for case_id, count in queue:
        print(f"{case_id}: {count} remaining")

    for index, (case_id, count) in enumerate(
        queue,
        start=1,
    ):
        print()
        print("=" * 72)
        print(f"CASE {index} OF {len(queue)}")
        print("=" * 72)

        print(f"Case ID: {case_id}")

        print(f"Remaining findings: {count}")

        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(annotation_script),
                    "--case-id",
                    case_id,
                    "--evaluator",
                    args.evaluator,
                ],
                check=False,
            )
        except KeyboardInterrupt:
            print()
            print("Annotation queue interrupted.")
            print("All previously saved labels remain persisted.")

            return 130

        if completed.returncode != 0:
            print()
            print(f"Annotation failed for case: {case_id}")

            return completed.returncode

    print()
    print("=" * 72)
    print("QUEUE COMPLETE")
    print("=" * 72)

    remaining_after = 0

    for case_dir in sorted(path for path in investigation_root.iterdir() if path.is_dir()):
        report_path = case_dir / FINAL_REPORT_FILENAME

        gold_path = gold_root / case_dir.name / GOLD_LABEL_FILENAME

        if not report_path.exists() or not gold_path.exists():
            continue

        remaining_after += len(
            get_remaining_required_ids(
                report_path=report_path,
                gold_path=gold_path,
            )
        )

    print(f"Review-required findings remaining: {remaining_after}")

    return 0 if remaining_after == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

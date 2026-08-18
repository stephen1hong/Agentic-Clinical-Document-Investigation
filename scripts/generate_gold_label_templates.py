from __future__ import annotations

from pathlib import Path

from clinical_investigation.evaluation.persistence import (
    persist_gold_labels,
)
from clinical_investigation.evaluation.template import (
    build_gold_label_template,
)


def find_project_root() -> Path:
    """Return the project root."""

    return Path(__file__).resolve().parents[1]


def main() -> int:
    """Generate gold-label templates for all investigation cases."""

    project_root = find_project_root()

    investigation_root = project_root / "data" / "investigation_cases"

    gold_root = project_root / "data" / "evaluation" / "gold_labels"

    if not investigation_root.exists():
        print(f"Investigation directory not found: {investigation_root}")
        return 1

    case_dirs = sorted(path for path in investigation_root.iterdir() if path.is_dir())

    if not case_dirs:
        print("No investigation cases found.")
        return 1

    total = len(case_dirs)
    completed = 0
    failed = 0

    print()
    print("=== Gold-Label Template Generation ===")
    print(f"Cases found: {total}")
    print()

    for case_dir in case_dirs:
        case_id = case_dir.name

        try:
            gold = build_gold_label_template(case_dir)

            output_dir = gold_root / case_id

            output_path = persist_gold_labels(
                output_dir=output_dir,
                gold_labels=gold,
            )

        except Exception as exc:
            failed += 1

            print(f"FAIL {case_id}: {type(exc).__name__}: {exc}")

            continue

        completed += 1

        print(
            f"PASS {case_id}: "
            f"{len(gold.finding_labels)} findings, "
            f"{len(gold.timeline_labels)} timeline events, "
            f"{len(gold.medication_labels)} medications"
        )

        print(f"  {output_path}")

    print()
    print("=== Summary ===")
    print(f"Cases total: {total}")
    print(f"Completed: {completed}")
    print(f"Failed: {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

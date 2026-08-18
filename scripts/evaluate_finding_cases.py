from __future__ import annotations

from pathlib import Path

from clinical_investigation.evaluation.finding_evaluation import (
    evaluate_case_findings,
)


def find_project_root() -> Path:
    """Return the project root."""

    return Path(__file__).resolve().parents[1]


def main() -> int:
    """Evaluate all cases that have gold-label artifacts."""

    project_root = find_project_root()

    investigation_dir = project_root / "data" / "investigation_cases"

    gold_root = project_root / "data" / "evaluation" / "gold_labels"

    results_root = project_root / "data" / "evaluation" / "results"

    if not gold_root.exists():
        print(f"Gold-label directory not found: {gold_root}")
        return 1

    gold_case_dirs = sorted(path for path in gold_root.iterdir() if path.is_dir())

    if not gold_case_dirs:
        print("No gold-label case directories found.")
        return 1

    total = 0
    completed = 0
    skipped = 0
    failed = 0

    for gold_case_dir in gold_case_dirs:
        case_id = gold_case_dir.name

        gold_path = gold_case_dir / "gold_labels.json"

        if not gold_path.exists():
            continue

        total += 1

        case_dir = investigation_dir / case_id

        if not case_dir.exists():
            skipped += 1
            print(f"SKIP {case_id}: investigation case not found")
            continue

        output_dir = results_root / case_id

        try:
            result = evaluate_case_findings(
                case_dir=case_dir,
                gold_label_dir=gold_case_dir,
                output_dir=output_dir,
            )
        except Exception as exc:
            failed += 1
            print(f"FAIL {case_id}: {type(exc).__name__}: {exc}")
            continue

        completed += 1

        print(
            f"PASS {case_id}: "
            f"{result.overall.evaluated_findings}/"
            f"{result.overall.total_findings} evaluated"
        )

    print()
    print("=== Finding Evaluation Summary ===")
    print(f"Gold-label cases: {total}")
    print(f"Completed: {completed}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

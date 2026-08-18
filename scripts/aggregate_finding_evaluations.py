from __future__ import annotations

from pathlib import Path

from clinical_investigation.evaluation.aggregate_persistence import (
    persist_aggregate_finding_evaluation,
)
from clinical_investigation.evaluation.finding_aggregate import (
    aggregate_finding_evaluations,
)
from clinical_investigation.evaluation.finding_persistence import (
    FINDING_EVALUATION_FILENAME,
    load_finding_evaluation,
)


def find_project_root() -> Path:
    """Return the project root from this script location."""

    return Path(__file__).resolve().parents[1]


def main() -> int:
    """Aggregate all persisted finding evaluation results."""

    project_root = find_project_root()

    results_dir = project_root / "data" / "evaluation" / "results"

    if not results_dir.exists():
        print(f"Evaluation results directory not found: {results_dir}")
        return 1

    result_paths = sorted(
        path for path in results_dir.glob(f"*/{FINDING_EVALUATION_FILENAME}") if path.is_file()
    )

    if not result_paths:
        print("No case-level finding evaluation results found.")
        return 1

    results = [load_finding_evaluation(path) for path in result_paths]

    aggregate = aggregate_finding_evaluations(results)

    output_path = persist_aggregate_finding_evaluation(
        output_dir=results_dir,
        result=aggregate,
    )

    print("Aggregate finding evaluation complete.")

    print(f"Cases evaluated: {aggregate.case_count}")

    print(f"Total findings: {aggregate.overall.total_findings}")

    print(f"Evaluated findings: {aggregate.overall.evaluated_findings}")

    print(f"Evaluation coverage: {aggregate.overall.evaluation_coverage:.3f}")

    if aggregate.overall.precision is None:
        print("Precision: not available")
    else:
        print(f"Precision: {aggregate.overall.precision:.3f}")

    print(f"Output: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

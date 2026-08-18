from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from clinical_investigation.evaluation.finding_metrics import (
    FindingOutcome,
    FindingScore,
)
from clinical_investigation.evaluation.finding_persistence import (
    FINDING_EVALUATION_FILENAME,
    load_finding_evaluation,
)


def find_project_root() -> Path:
    """Return project root."""

    return Path(__file__).resolve().parents[1]


def main() -> int:
    """Analyze evaluated findings and false-positive patterns."""

    project_root = find_project_root()

    results_root = project_root / "data" / "evaluation" / "results"

    result_paths = sorted(
        path for path in results_root.glob(f"*/{FINDING_EVALUATION_FILENAME}") if path.is_file()
    )

    if not result_paths:
        print("No case-level finding evaluation files found.")
        return 1

    all_scores: list[FindingScore] = []

    for result_path in result_paths:
        result = load_finding_evaluation(result_path)

        all_scores.extend(result.scores)

    evaluated = [score for score in all_scores if score.outcome != FindingOutcome.NOT_EVALUATED]

    false_positives = [
        score for score in evaluated if score.outcome == FindingOutcome.FALSE_POSITIVE
    ]

    partials = [score for score in evaluated if score.outcome == FindingOutcome.PARTIALLY_CORRECT]

    true_positives = [score for score in evaluated if score.outcome == FindingOutcome.TRUE_POSITIVE]

    print()
    print("=" * 72)
    print("FINDING EVALUATION ANALYSIS")
    print("=" * 72)

    print()
    print(f"Total machine findings: {len(all_scores)}")

    print(f"Evaluated findings: {len(evaluated)}")

    print(f"True positives: {len(true_positives)}")

    print(f"False positives: {len(false_positives)}")

    print(f"Partially correct: {len(partials)}")

    if evaluated:
        precision = len(true_positives) / len(evaluated)

        false_positive_rate = len(false_positives) / len(evaluated)

        partial_rate = len(partials) / len(evaluated)

        print()
        print(f"Precision: {precision:.3f}")

        print(f"False-positive rate: {false_positive_rate:.3f}")

        print(f"Partial-correct rate: {partial_rate:.3f}")

    subtype_counts = Counter(score.subtype for score in false_positives)

    type_counts = Counter(score.finding_type for score in false_positives)

    severity_counts = Counter(score.severity for score in false_positives)

    review_counts = Counter(score.requires_human_review for score in false_positives)

    print()
    print("=" * 72)
    print("FALSE POSITIVES BY SUBTYPE")
    print("=" * 72)

    if not subtype_counts:
        print("No false positives in evaluated findings.")
    else:
        for subtype, count in subtype_counts.most_common():
            print(f"{subtype}: {count}")

    print()
    print("False positives by finding type:")

    for finding_type, count in type_counts.most_common():
        print(f"  {finding_type}: {count}")

    print()
    print("False positives by severity:")

    for severity, count in severity_counts.most_common():
        print(f"  {severity}: {count}")

    print()
    print("False positives by review requirement:")

    for requires_review, count in review_counts.most_common():
        print(f"  {requires_review}: {count}")

    subtype_evaluation: dict[
        str,
        list[FindingScore],
    ] = defaultdict(list)

    for score in evaluated:
        subtype_evaluation[score.subtype].append(score)

    print()
    print("=" * 72)
    print("SUBTYPE QUALITY")
    print("=" * 72)

    for subtype in sorted(subtype_evaluation):
        scores = subtype_evaluation[subtype]

        tp = sum(score.outcome == FindingOutcome.TRUE_POSITIVE for score in scores)

        fp = sum(score.outcome == FindingOutcome.FALSE_POSITIVE for score in scores)

        partial = sum(score.outcome == FindingOutcome.PARTIALLY_CORRECT for score in scores)

        total = len(scores)

        precision = tp / total

        print()
        print(f"Subtype: {subtype}")

        print(f"  Evaluated: {total}")

        print(f"  TP: {tp}")

        print(f"  FP: {fp}")

        print(f"  Partial: {partial}")

        print(f"  Precision: {precision:.3f}")

    if false_positives:
        print()
        print("=" * 72)
        print("FALSE-POSITIVE FINDINGS")
        print("=" * 72)

        for score in false_positives:
            print()
            print(f"Finding ID: {score.finding_id}")

            print(f"Type: {score.finding_type}")

            print(f"Subtype: {score.subtype}")

            print(f"Severity: {score.severity}")

            print(f"Requires review: {score.requires_human_review}")

            print(f"Evidence support: {score.evidence_support}")

            if score.rationale:
                print(f"Rationale: {score.rationale}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

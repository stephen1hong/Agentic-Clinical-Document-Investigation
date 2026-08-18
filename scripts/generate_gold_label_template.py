from __future__ import annotations

import argparse

from clinical_investigation.config import settings
from clinical_investigation.evaluation.persistence import (
    persist_gold_labels,
)
from clinical_investigation.evaluation.template import (
    build_gold_label_template,
)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=("Generate an unevaluated gold-label template for one investigation case.")
    )

    parser.add_argument(
        "--case-id",
        required=True,
        help="Investigation case ID.",
    )

    return parser.parse_args()


def main() -> int:
    """Generate one gold-label template."""

    args = parse_args()

    case_dir = settings.investigation_cases_dir / args.case_id

    if not case_dir.exists():
        raise FileNotFoundError(f"Case not found: {case_dir}")

    gold = build_gold_label_template(case_dir)

    output_dir = settings.data_dir / "evaluation" / "gold_labels" / args.case_id

    output_path = persist_gold_labels(
        output_dir=output_dir,
        gold_labels=gold,
    )

    print(f"Gold-label template: {output_path}")

    print(f"Finding labels: {len(gold.finding_labels)}")

    print(f"Timeline labels: {len(gold.timeline_labels)}")

    print(f"Medication labels: {len(gold.medication_labels)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

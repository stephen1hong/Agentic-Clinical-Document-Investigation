from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from clinical_investigation.evaluation.annotation_context import (
    format_clinical_claim,
    format_evidence_item,
    index_records,
    load_clinical_claims,
    load_evidence_items,
    resolve_records,
)
from clinical_investigation.evaluation.models import (
    EvidenceSupportLabel,
    GoldCaseLabel,
    GoldFindingDisposition,
    GoldFindingLabel,
)
from clinical_investigation.evaluation.persistence import (
    load_gold_labels,
    persist_gold_labels,
)

FINAL_REPORT_FILENAME = "final_investigation_report.json"
GOLD_LABEL_FILENAME = "gold_labels.json"


def utc_now_iso() -> str:
    """Return the current UTC time in ISO-8601 format."""

    return datetime.now(UTC).isoformat()


def find_project_root() -> Path:
    """Return the project root."""

    return Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description=("Interactively annotate machine findings with gold-standard labels.")
    )

    parser.add_argument(
        "--case-id",
        required=True,
        help="Investigation case ID.",
    )

    parser.add_argument(
        "--evaluator",
        required=True,
        help="Evaluator name or identifier.",
    )

    parser.add_argument(
        "--all-findings",
        action="store_true",
        help=("Annotate all findings instead of only findings requiring human review."),
    )

    return parser.parse_args()


def load_final_report(
    case_dir: Path,
) -> dict[str, Any]:
    """Load one final investigation report."""

    path = case_dir / FINAL_REPORT_FILENAME

    if not path.exists():
        raise FileNotFoundError(f"Final investigation report not found: {path}")

    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(payload, dict):
        raise ValueError("Final investigation report must contain a JSON object.")

    return payload


def get_report_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all findings from the machine report."""

    return list(
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


def get_annotation_findings(
    *,
    report: dict[str, Any],
    all_findings: bool,
) -> list[dict[str, Any]]:
    """Return findings eligible for this annotation session."""

    findings = get_report_findings(report)

    if all_findings:
        return findings

    return [
        finding
        for finding in findings
        if bool(
            finding.get(
                "requires_human_review",
                False,
            )
        )
    ]


def print_case_header(
    *,
    case_id: str,
    findings: list[dict[str, Any]],
    all_findings: bool,
) -> None:
    """Print annotation-session information."""

    print()
    print("=" * 72)
    print("GOLD-LABEL FINDING ANNOTATION")
    print("=" * 72)

    print()
    print(f"Case ID: {case_id}")

    if all_findings:
        print("Scope: all findings")
    else:
        print("Scope: findings requiring human review")

    print(f"Findings in scope: {len(findings)}")


def print_finding(
    *,
    finding: dict[str, Any],
    index: int,
    total: int,
    evidence_index: dict[str, dict[str, Any]],
    claim_index: dict[str, dict[str, Any]],
) -> None:
    """Display one finding with resolved evidence and claim context."""

    print()
    print("-" * 72)
    print(f"Finding {index} of {total}")
    print("-" * 72)

    print(f"Finding ID: {finding.get('finding_id', '')}")

    print(f"Type: {finding.get('finding_type', '')}")

    print(f"Subtype: {finding.get('subtype', '')}")

    print(f"Severity: {finding.get('severity', '')}")

    print(f"Requires human review: {finding.get('requires_human_review', False)}")

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

    evidence_ids = [
        str(value)
        for value in finding.get(
            "evidence_ids",
            [],
        )
    ]

    print()
    print("Supporting Evidence")
    print("=" * 72)

    if not evidence_ids:
        print("No evidence IDs are attached to this finding.")
    else:
        resolved_evidence = resolve_records(
            evidence_ids,
            index=evidence_index,
        )

        resolved_ids = {
            str(
                evidence.get(
                    "evidence_id",
                    "",
                )
            )
            for evidence in resolved_evidence
        }

        for evidence_number, evidence in enumerate(
            resolved_evidence,
            start=1,
        ):
            print()
            print(f"[Evidence {evidence_number}]")

            print(format_evidence_item(evidence))

        unresolved_ids = [
            evidence_id for evidence_id in evidence_ids if evidence_id not in resolved_ids
        ]

        if unresolved_ids:
            print()
            print("Unresolved evidence IDs:")

            for evidence_id in unresolved_ids:
                print(f"  - {evidence_id}")

    claim_ids = [
        str(value)
        for value in finding.get(
            "claim_ids",
            [],
        )
    ]

    print()
    print("Related Clinical Claims")
    print("=" * 72)

    if not claim_ids:
        print("No claim IDs are attached to this finding.")
    else:
        resolved_claims = resolve_records(
            claim_ids,
            index=claim_index,
        )

        resolved_ids = {
            str(
                claim.get(
                    "claim_id",
                    "",
                )
            )
            for claim in resolved_claims
        }

        for claim_number, claim in enumerate(
            resolved_claims,
            start=1,
        ):
            print()
            print(f"[Claim {claim_number}]")

            print(format_clinical_claim(claim))

        unresolved_ids = [claim_id for claim_id in claim_ids if claim_id not in resolved_ids]

        if unresolved_ids:
            print()
            print("Unresolved claim IDs:")

            for claim_id in unresolved_ids:
                print(f"  - {claim_id}")


def prompt_disposition() -> GoldFindingDisposition | None:
    """Prompt for a gold finding disposition."""

    print()
    print("Gold disposition:")
    print("  1 = true_positive")
    print("  2 = false_positive")
    print("  3 = partially_correct")
    print("  4 = leave not_evaluated / skip")

    mapping = {
        "1": GoldFindingDisposition.TRUE_POSITIVE,
        "2": GoldFindingDisposition.FALSE_POSITIVE,
        "3": GoldFindingDisposition.PARTIALLY_CORRECT,
        "true_positive": (GoldFindingDisposition.TRUE_POSITIVE),
        "false_positive": (GoldFindingDisposition.FALSE_POSITIVE),
        "partially_correct": (GoldFindingDisposition.PARTIALLY_CORRECT),
    }

    while True:
        entered = input("> ").strip().lower()

        if entered == "4":
            return None

        disposition = mapping.get(entered)

        if disposition is not None:
            return disposition

        print("Invalid selection. Enter 1, 2, 3, or 4.")


def prompt_evidence_support() -> EvidenceSupportLabel:
    """Prompt for the evidence-support judgment."""

    print()
    print("Evidence support:")
    print("  1 = supported")
    print("  2 = partially_supported")
    print("  3 = unsupported")
    print("  4 = not_evaluated")

    mapping = {
        "1": EvidenceSupportLabel.SUPPORTED,
        "2": EvidenceSupportLabel.PARTIALLY_SUPPORTED,
        "3": EvidenceSupportLabel.UNSUPPORTED,
        "4": EvidenceSupportLabel.NOT_EVALUATED,
    }

    while True:
        entered = input("> ").strip()

        label = mapping.get(entered)

        if label is not None:
            return label

        print("Invalid selection. Enter 1, 2, 3, or 4.")


def prompt_rationale() -> str:
    """Prompt for evaluator rationale."""

    print()
    print("Rationale:")

    return input("> ").strip()


def find_gold_label(
    *,
    gold: GoldCaseLabel,
    finding_id: str,
) -> GoldFindingLabel:
    """Find the gold-label record for one machine finding."""

    for label in gold.finding_labels:
        if label.finding_id == finding_id:
            return label

    raise ValueError(f"Gold-label template does not contain finding: {finding_id}")


def replace_gold_label(
    *,
    gold: GoldCaseLabel,
    updated_label: GoldFindingLabel,
    evaluator: str,
) -> GoldCaseLabel:
    """Replace one finding label in the case gold artifact."""

    updated_labels = [
        (updated_label if label.finding_id == updated_label.finding_id else label)
        for label in gold.finding_labels
    ]

    return gold.model_copy(
        update={
            "evaluator": evaluator,
            "evaluated_at": utc_now_iso(),
            "finding_labels": updated_labels,
        }
    )


def annotate_case(
    *,
    case_dir: Path,
    gold_dir: Path,
    evaluator: str,
    all_findings: bool,
) -> GoldCaseLabel:
    """Interactively annotate findings for one case."""

    report = load_final_report(case_dir)

    gold_path = gold_dir / GOLD_LABEL_FILENAME

    if not gold_path.exists():
        raise FileNotFoundError(f"Gold labels not found: {gold_path}")

    gold = load_gold_labels(gold_path)

    report_case_id = str(
        report.get(
            "case_id",
            "",
        )
    )

    if gold.case_id != report_case_id:
        raise ValueError("Case ID mismatch between final report and gold-label artifact.")

    evidence_items = load_evidence_items(case_dir)

    clinical_claims = load_clinical_claims(case_dir)

    evidence_index = index_records(
        evidence_items,
        id_field="evidence_id",
    )

    claim_index = index_records(
        clinical_claims,
        id_field="claim_id",
    )

    findings = get_annotation_findings(
        report=report,
        all_findings=all_findings,
    )

    print_case_header(
        case_id=report_case_id,
        findings=findings,
        all_findings=all_findings,
    )

    pending_findings = []

    for finding in findings:
        finding_id = str(finding["finding_id"])

        gold_label = find_gold_label(
            gold=gold,
            finding_id=finding_id,
        )

        if gold_label.disposition == GoldFindingDisposition.NOT_EVALUATED:
            pending_findings.append(finding)

    print(f"Already evaluated: {len(findings) - len(pending_findings)}")

    print(f"Remaining: {len(pending_findings)}")

    if not pending_findings:
        print()
        print("No unevaluated findings remain in this scope.")
        return gold

    total = len(pending_findings)

    for index, finding in enumerate(
        pending_findings,
        start=1,
    ):
        print_finding(
            finding=finding,
            index=index,
            total=total,
            evidence_index=evidence_index,
            claim_index=claim_index,
        )

        disposition = prompt_disposition()

        if disposition is None:
            print("Finding left as not_evaluated.")
            continue

        evidence_support = prompt_evidence_support()

        rationale = prompt_rationale()

        finding_id = str(finding["finding_id"])

        existing = find_gold_label(
            gold=gold,
            finding_id=finding_id,
        )

        updated_label = existing.model_copy(
            update={
                "disposition": disposition,
                "reviewer": evaluator,
                "rationale": rationale,
                "evidence_support": evidence_support,
            }
        )

        gold = replace_gold_label(
            gold=gold,
            updated_label=updated_label,
            evaluator=evaluator,
        )

        persist_gold_labels(
            output_dir=gold_dir,
            gold_labels=gold,
        )

        print()
        print("Gold label saved.")

    return gold


def main() -> int:
    """Run the interactive annotation CLI."""

    args = parse_args()

    project_root = find_project_root()

    case_dir = project_root / "data" / "investigation_cases" / args.case_id

    gold_dir = project_root / "data" / "evaluation" / "gold_labels" / args.case_id

    if not case_dir.exists():
        print(f"ERROR: case not found: {case_dir}")
        return 1

    try:
        gold = annotate_case(
            case_dir=case_dir,
            gold_dir=gold_dir,
            evaluator=args.evaluator,
            all_findings=args.all_findings,
        )
    except Exception as exc:
        print()
        print(f"ERROR: {type(exc).__name__}: {exc}")
        return 1

    evaluated = sum(
        label.disposition != GoldFindingDisposition.NOT_EVALUATED for label in gold.finding_labels
    )

    print()
    print("=" * 72)
    print("ANNOTATION SESSION COMPLETE")
    print("=" * 72)

    print(f"Case: {gold.case_id}")

    print(f"Evaluated findings in full case: {evaluated}/{len(gold.finding_labels)}")

    print(f"Gold-label artifact: {gold_dir / GOLD_LABEL_FILENAME}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

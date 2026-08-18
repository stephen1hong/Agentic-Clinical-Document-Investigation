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

MANIFEST_FILENAME = "finding_sample_manifest.json"
ANNOTATION_FILENAME = "finding_sample_annotations.json"


VALID_DISPOSITIONS = {
    "1": "true_positive",
    "2": "false_positive",
    "3": "partially_correct",
    "4": "not_evaluated",
}


VALID_EVIDENCE_SUPPORT = {
    "1": "supported",
    "2": "partially_supported",
    "3": "unsupported",
    "4": "not_evaluated",
}


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Annotate the post-refinement held-out finding sample with evidence-aware context."
        )
    )

    parser.add_argument(
        "--evaluator",
        required=True,
        help="Evaluator name or identifier.",
    )

    parser.add_argument(
        "--start-index",
        type=int,
        default=1,
        help=(
            "Optional 1-based sample index to start from. "
            "Previously evaluated findings are skipped automatically."
        ),
    )

    return parser.parse_args()


def project_root() -> Path:
    """Return repository root."""

    return Path(__file__).resolve().parents[1]


def load_json(
    path: Path,
) -> Any:
    """Load JSON from disk."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def persist_json(
    path: Path,
    payload: Any,
) -> None:
    """Persist JSON to disk."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def load_manifest(
    path: Path,
) -> dict[str, Any]:
    """Load and validate the representative sample manifest."""

    payload = load_json(path)

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(f"Expected manifest JSON object: {path}")

    findings = payload.get("findings")

    if not isinstance(
        findings,
        list,
    ):
        raise ValueError("Manifest must contain a findings list.")

    return payload


def new_annotation_payload(
    *,
    manifest: dict[str, Any],
    evaluator: str,
) -> dict[str, Any]:
    """Create a new annotation artifact."""

    return {
        "schema_version": "1.0",
        "created_at": (datetime.now(UTC).isoformat()),
        "updated_at": (datetime.now(UTC).isoformat()),
        "evaluator": evaluator,
        "sample_manifest": (MANIFEST_FILENAME),
        "sample_seed": manifest.get("seed"),
        "population_size": manifest.get("population_size"),
        "sample_size": manifest.get("actual_sample_size"),
        "annotations": [],
    }


def load_or_create_annotations(
    *,
    path: Path,
    manifest: dict[str, Any],
    evaluator: str,
) -> dict[str, Any]:
    """Load existing annotations or create a new artifact."""

    if not path.exists():
        return new_annotation_payload(
            manifest=manifest,
            evaluator=evaluator,
        )

    payload = load_json(path)

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(f"Expected annotation JSON object: {path}")

    annotations = payload.get("annotations")

    if not isinstance(
        annotations,
        list,
    ):
        raise ValueError("Annotation artifact must contain an annotations list.")

    existing_evaluator = str(
        payload.get(
            "evaluator",
            "",
        )
    )

    if existing_evaluator and existing_evaluator != evaluator:
        raise ValueError(
            f"Existing annotations belong to evaluator {existing_evaluator!r}, not {evaluator!r}."
        )

    payload["evaluator"] = evaluator

    return payload


def annotation_index(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Index saved annotations by finding ID."""

    return {
        str(
            annotation.get(
                "finding_id",
                "",
            )
        ): annotation
        for annotation in payload.get("annotations", [])
        if annotation.get("finding_id")
    }


def get_report_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all findings from a final report."""

    findings: list[dict[str, Any]] = []

    for key in (
        "high_priority_findings",
        "other_findings",
    ):
        value = report.get(
            key,
            [],
        )

        if isinstance(
            value,
            list,
        ):
            findings.extend(
                finding
                for finding in value
                if isinstance(
                    finding,
                    dict,
                )
            )

    return findings


def load_finding(
    *,
    case_dir: Path,
    finding_id: str,
) -> dict[str, Any]:
    """Load one finding from the persisted final report."""

    report_path = case_dir / "final_investigation_report.json"

    if not report_path.exists():
        raise FileNotFoundError(f"Missing final report: {report_path}")

    report = load_json(report_path)

    if not isinstance(
        report,
        dict,
    ):
        raise ValueError(f"Expected report JSON object: {report_path}")

    for finding in get_report_findings(report):
        if (
            str(
                finding.get(
                    "finding_id",
                    "",
                )
            )
            == finding_id
        ):
            return finding

    raise ValueError(f"Finding {finding_id} not found in {report_path}")


def print_finding_header(
    *,
    finding: dict[str, Any],
    sample_record: dict[str, Any],
    position: int,
    total: int,
) -> None:
    """Render finding-level metadata."""

    print()
    print("-" * 72)
    print(f"Finding {position} of {total}")
    print("-" * 72)

    print(f"Sample index: {sample_record.get('sample_index')}")

    print(f"Finding ID: {finding.get('finding_id')}")

    print(f"Type: {finding.get('finding_type')}")

    print(f"Subtype: {finding.get('subtype')}")

    print(f"Severity: {finding.get('severity')}")

    print(f"Requires human review: {finding.get('requires_human_review')}")

    print(f"Confidence: {finding.get('confidence')}")

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


def print_evidence_context(
    *,
    case_dir: Path,
    finding: dict[str, Any],
) -> None:
    """Render linked evidence and claim context."""

    evidence_items = load_evidence_items(case_dir)

    clinical_claims = load_clinical_claims(case_dir)

    evidence_by_id = index_records(
        evidence_items,
        id_field="evidence_id",
    )

    claims_by_id = index_records(
        clinical_claims,
        id_field="claim_id",
    )

    evidence_ids = [
        str(evidence_id)
        for evidence_id in (
            finding.get(
                "evidence_ids",
                [],
            )
            or []
        )
        if evidence_id
    ]

    claim_ids = [
        str(claim_id)
        for claim_id in (
            finding.get(
                "claim_ids",
                [],
            )
            or []
        )
        if claim_id
    ]

    evidence_records = resolve_records(
        evidence_ids,
        index=evidence_by_id,
    )

    claim_records = resolve_records(
        claim_ids,
        index=claims_by_id,
    )

    print()
    print("Supporting Evidence")
    print("=" * 72)

    if not evidence_records:
        print("(No linked evidence records resolved.)")

    for index, evidence in enumerate(
        evidence_records,
        start=1,
    ):
        print()
        print(f"[Evidence {index}]")
        print(format_evidence_item(evidence))

    print()
    print("Related Clinical Claims")
    print("=" * 72)

    if not claim_records:
        print("(No linked clinical claims resolved.)")

    for index, claim in enumerate(
        claim_records,
        start=1,
    ):
        print()
        print(f"[Claim {index}]")
        print(format_clinical_claim(claim))


def prompt_choice(
    *,
    heading: str,
    choices: dict[str, str],
) -> str:
    """Prompt until a valid choice is entered."""

    print()
    print(f"{heading}:")

    for key, value in choices.items():
        print(f"  {key} = {value}")

    while True:
        value = input("> ").strip()

        if value in choices:
            return choices[value]

        print(f"Invalid choice. Enter one of: {', '.join(choices)}")


def prompt_rationale() -> str:
    """Prompt for a short rationale."""

    print()
    print("Rationale (recommended for all evaluated findings):")

    return input("> ").strip()


def build_annotation(
    *,
    sample_record: dict[str, Any],
    finding: dict[str, Any],
    evaluator: str,
    disposition: str,
    evidence_support: str,
    rationale: str,
) -> dict[str, Any]:
    """Build one persisted annotation record."""

    now = datetime.now(UTC).isoformat()

    return {
        "sample_index": (sample_record.get("sample_index")),
        "case_id": (sample_record.get("case_id")),
        "finding_id": (sample_record.get("finding_id")),
        "finding_type": (finding.get("finding_type")),
        "subtype": (finding.get("subtype")),
        "severity": (finding.get("severity")),
        "requires_human_review": bool(
            finding.get(
                "requires_human_review",
                False,
            )
        ),
        "disposition": disposition,
        "evidence_support": (evidence_support),
        "rationale": rationale,
        "evaluator": evaluator,
        "annotated_at": now,
        "sample_weight": (sample_record.get("sample_weight")),
        "sampling_probability": (sample_record.get("sampling_probability")),
    }


def upsert_annotation(
    *,
    payload: dict[str, Any],
    annotation: dict[str, Any],
) -> None:
    """Insert or replace an annotation by finding ID."""

    finding_id = str(annotation["finding_id"])

    annotations = payload["annotations"]

    for index, existing in enumerate(annotations):
        if (
            str(
                existing.get(
                    "finding_id",
                    "",
                )
            )
            == finding_id
        ):
            annotations[index] = annotation
            break
    else:
        annotations.append(annotation)

    annotations.sort(
        key=lambda item: int(
            item.get(
                "sample_index",
                0,
            )
        )
    )

    payload["updated_at"] = datetime.now(UTC).isoformat()


def count_evaluated(
    payload: dict[str, Any],
) -> int:
    """Count annotations with a non-skip disposition."""

    return sum(
        1
        for annotation in payload.get("annotations", [])
        if annotation.get("disposition") != "not_evaluated"
    )


def main() -> int:
    """Run post-refinement held-out sample annotation."""

    args = parse_args()

    root = project_root()

    sample_dir = root / "data" / "evaluation" / "post_refinement_sample"

    manifest_path = sample_dir / MANIFEST_FILENAME

    annotation_path = sample_dir / ANNOTATION_FILENAME

    investigation_root = root / "data" / "investigation_cases"

    if not manifest_path.exists():
        print(f"Sample manifest not found: {manifest_path}")
        return 1

    manifest = load_manifest(manifest_path)

    annotation_payload = load_or_create_annotations(
        path=annotation_path,
        manifest=manifest,
        evaluator=args.evaluator,
    )

    saved_by_id = annotation_index(annotation_payload)

    sample_records = sorted(
        (
            record
            for record in manifest["findings"]
            if isinstance(
                record,
                dict,
            )
        ),
        key=lambda record: int(
            record.get(
                "sample_index",
                0,
            )
        ),
    )

    total = len(sample_records)

    already_evaluated = sum(
        1
        for record in sample_records
        if (
            str(
                record.get(
                    "finding_id",
                    "",
                )
            )
            in saved_by_id
            and saved_by_id[
                str(
                    record.get(
                        "finding_id",
                        "",
                    )
                )
            ].get("disposition")
            != "not_evaluated"
        )
    )

    print()
    print("=" * 72)
    print("POST-REFINEMENT HELD-OUT FINDING ANNOTATION")
    print("=" * 72)

    print(f"Sample size: {total}")

    print(f"Already evaluated: {already_evaluated}")

    print(f"Remaining: {total - already_evaluated}")

    print(f"Evaluator: {args.evaluator}")

    print(f"Artifact: {annotation_path}")

    try:
        for sample_record in sample_records:
            sample_index = int(
                sample_record.get(
                    "sample_index",
                    0,
                )
            )

            if sample_index < args.start_index:
                continue

            finding_id = str(
                sample_record.get(
                    "finding_id",
                    "",
                )
            )

            if not finding_id:
                continue

            existing = saved_by_id.get(finding_id)

            if existing and existing.get("disposition") != "not_evaluated":
                continue

            case_id = str(
                sample_record.get(
                    "case_id",
                    "",
                )
            )

            case_dir = investigation_root / case_id

            finding = load_finding(
                case_dir=case_dir,
                finding_id=finding_id,
            )

            print_finding_header(
                finding=finding,
                sample_record=sample_record,
                position=sample_index,
                total=total,
            )

            print_evidence_context(
                case_dir=case_dir,
                finding=finding,
            )

            disposition = prompt_choice(
                heading="Gold disposition",
                choices=VALID_DISPOSITIONS,
            )

            if disposition == "not_evaluated":
                evidence_support = "not_evaluated"
            else:
                evidence_support = prompt_choice(
                    heading=("Evidence support"),
                    choices=(VALID_EVIDENCE_SUPPORT),
                )

            rationale = prompt_rationale()

            annotation = build_annotation(
                sample_record=sample_record,
                finding=finding,
                evaluator=args.evaluator,
                disposition=disposition,
                evidence_support=evidence_support,
                rationale=rationale,
            )

            upsert_annotation(
                payload=annotation_payload,
                annotation=annotation,
            )

            persist_json(
                annotation_path,
                annotation_payload,
            )

            saved_by_id[finding_id] = annotation

            print()
            print("Saved.")

    except KeyboardInterrupt:
        print()
        print()
        print("Annotation interrupted.")

        print("All previously completed annotations have already been saved.")

        return 130

    evaluated = count_evaluated(annotation_payload)

    remaining = total - evaluated

    print()
    print("=" * 72)
    print("ANNOTATION SESSION COMPLETE")
    print("=" * 72)

    print(f"Evaluated findings: {evaluated}/{total}")

    print(f"Remaining: {remaining}")

    print(f"Annotation artifact: {annotation_path}")

    return 0 if remaining == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

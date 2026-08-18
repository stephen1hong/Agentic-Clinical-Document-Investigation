from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from clinical_investigation.review.models import ReviewerBundle
from clinical_investigation.review.renderer import render_reviewer_report

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "human_review_report_quality"

OUTPUT_PATH = OUTPUT_DIR / "report_reviewer_quality.json"


FINAL_REPORT_FILENAME = "final_investigation_report.json"
REVIEWER_BUNDLE_FILENAME = "reviewer_bundle.json"
REVIEWER_REPORT_FILENAME = "reviewer_report.md"

EVIDENCE_FILENAME = "evidence_items.json"
CLAIMS_FILENAME = "clinical_claims.json"
TIMELINE_FILENAME = "canonical_timeline.json"


REQUIRED_FINDING_FIELDS = (
    "finding_id",
    "finding_type",
    "subtype",
    "severity",
    "title",
    "summary",
    "confidence",
    "requires_human_review",
)


REVIEWER_FINDING_FIELDS = (
    "finding_id",
    "finding_type",
    "subtype",
    "severity",
    "title",
    "summary",
    "confidence",
    "requires_human_review",
    "evidence_ids",
    "claim_ids",
    "event_ids",
)


def load_json(
    path: Path,
) -> Any:
    """Load JSON."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def load_json_object(
    path: Path,
) -> dict[str, Any]:
    """Load JSON that must contain an object."""

    raw = load_json(path)

    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object.")

    return raw


def load_json_records(
    path: Path,
    possible_keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Load records from a list or common wrapper."""

    raw = load_json(path)

    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]

    if isinstance(raw, dict):
        for key in possible_keys:
            value = raw.get(key)

            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    return []


def findings_from_report(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all machine-report findings."""

    high_priority = report.get(
        "high_priority_findings",
        [],
    )

    other = report.get(
        "other_findings",
        [],
    )

    if not isinstance(high_priority, list):
        high_priority = []

    if not isinstance(other, list):
        other = []

    return [finding for finding in (high_priority + other) if isinstance(finding, dict)]


def findings_from_bundle(
    bundle: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all reviewer-bundle findings."""

    review = bundle.get(
        "findings_requiring_review",
        [],
    )

    contextual = bundle.get(
        "contextual_findings",
        [],
    )

    if not isinstance(review, list):
        review = []

    if not isinstance(contextual, list):
        contextual = []

    return [finding for finding in (review + contextual) if isinstance(finding, dict)]


def nonempty_string(
    value: Any,
) -> bool:
    """Return whether a value is a nonempty string."""

    return isinstance(value, str) and bool(value.strip())


def string_ids(
    value: Any,
) -> list[str]:
    """Normalize ID fields."""

    if isinstance(value, str):
        return [value] if value else []

    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]

    return []


def build_id_set(
    records: list[dict[str, Any]],
    field: str,
) -> set[str]:
    """Build ID lookup."""

    return {str(record[field]) for record in records if nonempty_string(record.get(field))}


def normalized_markdown(
    text: str,
) -> str:
    """Normalize markdown for deterministic comparison."""

    return text.rstrip() + "\n"


def main() -> int:
    """Run simplified Step 8D.2."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    cases_scanned = 0
    findings_scanned = 0
    reviewer_findings_scanned = 0

    missing_artifacts: list[dict[str, Any]] = []

    case_id_mismatches: list[dict[str, Any]] = []

    missing_required_fields: list[dict[str, Any]] = []

    empty_text_fields: list[dict[str, Any]] = []

    invalid_confidence_values: list[dict[str, Any]] = []

    missing_provenance: list[dict[str, Any]] = []

    unresolved_provenance: list[dict[str, Any]] = []

    reviewer_projection_mismatches: list[dict[str, Any]] = []

    markdown_mismatches: list[dict[str, Any]] = []

    executive_summary_issues: list[dict[str, Any]] = []

    finding_count_issues: list[dict[str, Any]] = []

    review_count_issues: list[dict[str, Any]] = []

    high_priority_partition_issues: list[dict[str, Any]] = []

    finding_type_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()

    case_summaries: list[dict[str, Any]] = []

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        required_paths = {
            FINAL_REPORT_FILENAME: (case_dir / FINAL_REPORT_FILENAME),
            REVIEWER_BUNDLE_FILENAME: (case_dir / REVIEWER_BUNDLE_FILENAME),
            REVIEWER_REPORT_FILENAME: (case_dir / REVIEWER_REPORT_FILENAME),
            EVIDENCE_FILENAME: (case_dir / EVIDENCE_FILENAME),
            CLAIMS_FILENAME: (case_dir / CLAIMS_FILENAME),
            TIMELINE_FILENAME: (case_dir / TIMELINE_FILENAME),
        }

        missing = [name for name, path in required_paths.items() if not path.exists()]

        if missing:
            missing_artifacts.append(
                {
                    "case_id": case_dir.name,
                    "missing_files": missing,
                }
            )

            continue

        cases_scanned += 1
        case_id = case_dir.name

        report = load_json_object(required_paths[FINAL_REPORT_FILENAME])

        bundle = load_json_object(required_paths[REVIEWER_BUNDLE_FILENAME])

        reviewer_markdown = required_paths[REVIEWER_REPORT_FILENAME].read_text(
            encoding="utf-8",
        )

        evidence = load_json_records(
            required_paths[EVIDENCE_FILENAME],
            (
                "evidence_items",
                "items",
                "records",
            ),
        )

        claims = load_json_records(
            required_paths[CLAIMS_FILENAME],
            (
                "clinical_claims",
                "claims",
                "records",
            ),
        )

        timeline = load_json_records(
            required_paths[TIMELINE_FILENAME],
            (
                "events",
                "timeline",
                "records",
            ),
        )

        findings = findings_from_report(report)

        reviewer_findings = findings_from_bundle(bundle)

        findings_scanned += len(findings)

        reviewer_findings_scanned += len(reviewer_findings)

        evidence_ids = build_id_set(
            evidence,
            "evidence_id",
        )

        claim_ids = build_id_set(
            claims,
            "claim_id",
        )

        event_ids = build_id_set(
            timeline,
            "event_id",
        )

        if report.get("case_id") != case_id:
            case_id_mismatches.append(
                {
                    "case_id": case_id,
                    "artifact": (FINAL_REPORT_FILENAME),
                    "record_case_id": (report.get("case_id")),
                }
            )

        if bundle.get("case_id") != case_id:
            case_id_mismatches.append(
                {
                    "case_id": case_id,
                    "artifact": (REVIEWER_BUNDLE_FILENAME),
                    "record_case_id": (bundle.get("case_id")),
                }
            )

        if not nonempty_string(report.get("investigation_question")):
            empty_text_fields.append(
                {
                    "case_id": case_id,
                    "artifact": ("final_report"),
                    "field": ("investigation_question"),
                }
            )

        if not nonempty_string(report.get("executive_summary")):
            executive_summary_issues.append(
                {
                    "case_id": case_id,
                    "issue": ("missing_executive_summary"),
                }
            )

        expected_finding_count = len(findings)

        expected_review_count = sum(
            bool(
                finding.get(
                    "requires_human_review",
                    False,
                )
            )
            for finding in findings
        )

        if report.get("finding_count") != expected_finding_count:
            finding_count_issues.append(
                {
                    "case_id": case_id,
                    "artifact": ("final_report"),
                    "declared": (report.get("finding_count")),
                    "actual": (expected_finding_count),
                }
            )

        if bundle.get("finding_count") != expected_finding_count:
            finding_count_issues.append(
                {
                    "case_id": case_id,
                    "artifact": ("reviewer_bundle"),
                    "declared": (bundle.get("finding_count")),
                    "actual": (expected_finding_count),
                }
            )

        if report.get("review_finding_count") != expected_review_count:
            review_count_issues.append(
                {
                    "case_id": case_id,
                    "artifact": ("final_report"),
                    "declared": (report.get("review_finding_count")),
                    "actual": (expected_review_count),
                }
            )

        if bundle.get("review_finding_count") != expected_review_count:
            review_count_issues.append(
                {
                    "case_id": case_id,
                    "artifact": ("reviewer_bundle"),
                    "declared": (bundle.get("review_finding_count")),
                    "actual": (expected_review_count),
                }
            )

        high_priority = report.get(
            "high_priority_findings",
            [],
        )

        if isinstance(
            high_priority,
            list,
        ):
            for finding in high_priority:
                if not isinstance(
                    finding,
                    dict,
                ):
                    continue

                if finding.get("severity") != "high":
                    high_priority_partition_issues.append(
                        {
                            "case_id": case_id,
                            "finding_id": (finding.get("finding_id")),
                            "severity": (finding.get("severity")),
                        }
                    )

        report_by_id = {
            str(finding["finding_id"]): finding for finding in findings if finding.get("finding_id")
        }

        reviewer_by_id = {
            str(finding["finding_id"]): finding
            for finding in reviewer_findings
            if finding.get("finding_id")
        }

        for finding in findings:
            finding_id = str(
                finding.get(
                    "finding_id",
                    "",
                )
            )

            finding_type_counts[
                str(
                    finding.get(
                        "finding_type",
                        "unknown",
                    )
                )
            ] += 1

            severity_counts[
                str(
                    finding.get(
                        "severity",
                        "unknown",
                    )
                )
            ] += 1

            for field in REQUIRED_FINDING_FIELDS:
                if field not in finding:
                    missing_required_fields.append(
                        {
                            "case_id": case_id,
                            "finding_id": (finding_id),
                            "field": field,
                        }
                    )

            for field in (
                "finding_id",
                "finding_type",
                "subtype",
                "severity",
                "title",
                "summary",
            ):
                if not nonempty_string(finding.get(field)):
                    empty_text_fields.append(
                        {
                            "case_id": (case_id),
                            "finding_id": (finding_id),
                            "field": field,
                        }
                    )

            confidence = finding.get("confidence")

            if (
                not isinstance(
                    confidence,
                    (int, float),
                )
                or isinstance(
                    confidence,
                    bool,
                )
                or not (0.0 <= float(confidence) <= 1.0)
            ):
                invalid_confidence_values.append(
                    {
                        "case_id": case_id,
                        "finding_id": (finding_id),
                        "confidence": (confidence),
                    }
                )

            finding_evidence_ids = string_ids(finding.get("evidence_ids"))

            finding_claim_ids = string_ids(finding.get("claim_ids"))

            finding_event_ids = string_ids(finding.get("event_ids"))

            if not (finding_evidence_ids or finding_claim_ids or finding_event_ids):
                missing_provenance.append(
                    {
                        "case_id": case_id,
                        "finding_id": (finding_id),
                    }
                )

            for evidence_id in finding_evidence_ids:
                if evidence_id not in evidence_ids:
                    unresolved_provenance.append(
                        {
                            "case_id": (case_id),
                            "finding_id": (finding_id),
                            "reference_type": ("evidence_id"),
                            "reference_id": (evidence_id),
                        }
                    )

            for claim_id in finding_claim_ids:
                if claim_id not in claim_ids:
                    unresolved_provenance.append(
                        {
                            "case_id": (case_id),
                            "finding_id": (finding_id),
                            "reference_type": ("claim_id"),
                            "reference_id": (claim_id),
                        }
                    )

            for event_id in finding_event_ids:
                if event_id not in event_ids:
                    unresolved_provenance.append(
                        {
                            "case_id": (case_id),
                            "finding_id": (finding_id),
                            "reference_type": ("event_id"),
                            "reference_id": (event_id),
                        }
                    )

        if set(report_by_id) != set(reviewer_by_id):
            reviewer_projection_mismatches.append(
                {
                    "case_id": case_id,
                    "issue": ("finding_id_set_mismatch"),
                    "missing_from_bundle": sorted(set(report_by_id) - set(reviewer_by_id)),
                    "unexpected_in_bundle": sorted(set(reviewer_by_id) - set(report_by_id)),
                }
            )

        shared_ids = set(report_by_id) & set(reviewer_by_id)

        for finding_id in sorted(shared_ids):
            source = report_by_id[finding_id]

            reviewer = reviewer_by_id[finding_id]

            for field in REVIEWER_FINDING_FIELDS:
                source_value = (
                    source.get(
                        field,
                        [],
                    )
                    if field
                    in (
                        "evidence_ids",
                        "claim_ids",
                        "event_ids",
                    )
                    else source.get(field)
                )

                reviewer_value = (
                    reviewer.get(
                        field,
                        [],
                    )
                    if field
                    in (
                        "evidence_ids",
                        "claim_ids",
                        "event_ids",
                    )
                    else reviewer.get(field)
                )

                if source_value != reviewer_value:
                    reviewer_projection_mismatches.append(
                        {
                            "case_id": (case_id),
                            "finding_id": (finding_id),
                            "field": field,
                            "report_value": (source_value),
                            "reviewer_value": (reviewer_value),
                        }
                    )

        #
        # The persisted markdown should be the exact
        # deterministic rendering of the current bundle.
        #
        validated_bundle = ReviewerBundle.model_validate(bundle)

        expected_markdown = render_reviewer_report(validated_bundle)

        if normalized_markdown(reviewer_markdown) != normalized_markdown(expected_markdown):
            markdown_mismatches.append(
                {
                    "case_id": case_id,
                    "issue": ("persisted_markdown_does_not_match_bundle"),
                }
            )

        case_summaries.append(
            {
                "case_id": case_id,
                "finding_count": (expected_finding_count),
                "review_finding_count": (expected_review_count),
                "review_status": (report.get("review_status")),
                "markdown_matches_bundle": (
                    normalized_markdown(reviewer_markdown) == normalized_markdown(expected_markdown)
                ),
            }
        )

    structural_issue_count = sum(
        (
            len(missing_artifacts),
            len(case_id_mismatches),
            len(missing_required_fields),
            len(empty_text_fields),
            len(invalid_confidence_values),
            len(missing_provenance),
            len(unresolved_provenance),
            len(reviewer_projection_mismatches),
            len(markdown_mismatches),
            len(executive_summary_issues),
            len(finding_count_issues),
            len(review_count_issues),
            len(high_priority_partition_issues),
        )
    )

    status = "PASS" if structural_issue_count == 0 else "FAIL"

    output = {
        "schema_version": "1.0",
        "evaluation_step": ("simplified_8D.2"),
        "title": ("Final Report and Reviewer Artifact Quality"),
        "status": status,
        "evaluation_method": (
            "Full-population structural, provenance, "
            "projection, and deterministic-rendering "
            "audit of final investigation reports and "
            "reviewer-facing artifacts."
        ),
        "population": {
            "cases_scanned": (cases_scanned),
            "machine_findings": (findings_scanned),
            "reviewer_findings": (reviewer_findings_scanned),
        },
        "quality_checks": {
            "required_field_issues": (len(missing_required_fields)),
            "empty_text_field_issues": (len(empty_text_fields)),
            "invalid_confidence_values": (len(invalid_confidence_values)),
            "findings_without_provenance": (len(missing_provenance)),
            "unresolved_provenance_references": (len(unresolved_provenance)),
            "reviewer_projection_mismatches": (len(reviewer_projection_mismatches)),
            "markdown_render_mismatches": (len(markdown_mismatches)),
            "executive_summary_issues": (len(executive_summary_issues)),
            "finding_count_issues": (len(finding_count_issues)),
            "review_count_issues": (len(review_count_issues)),
            "high_priority_partition_issues": (len(high_priority_partition_issues)),
        },
        "artifact_integrity": {
            "missing_artifacts": (len(missing_artifacts)),
            "case_id_mismatches": (len(case_id_mismatches)),
            "total_issues": (structural_issue_count),
        },
        "finding_type_distribution": dict(sorted(finding_type_counts.items())),
        "severity_distribution": dict(sorted(severity_counts.items())),
        "case_summaries": (case_summaries),
        "issues": {
            "missing_artifacts": (missing_artifacts),
            "case_id_mismatches": (case_id_mismatches),
            "missing_required_fields": (missing_required_fields),
            "empty_text_fields": (empty_text_fields),
            "invalid_confidence_values": (invalid_confidence_values),
            "missing_provenance": (missing_provenance),
            "unresolved_provenance": (unresolved_provenance),
            "reviewer_projection_mismatches": (reviewer_projection_mismatches),
            "markdown_mismatches": (markdown_mismatches),
            "executive_summary_issues": (executive_summary_issues),
            "finding_count_issues": (finding_count_issues),
            "review_count_issues": (review_count_issues),
            "high_priority_partition_issues": (high_priority_partition_issues),
        },
        "interpretation": {
            "scope_note": (
                "This evaluation establishes structural "
                "report quality, evidence visibility, "
                "reviewer projection consistency, and "
                "deterministic rendering. It does not "
                "claim that machine-generated prose has "
                "been independently clinically rated."
            ),
        },
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("SIMPLIFIED STEP 8D.2 FINAL-REPORT / REVIEWER QUALITY")
    print("=" * 72)

    print(f"Status:                          {status}")

    print()
    print("Population")
    print("-" * 72)

    print(f"Cases scanned:                   {cases_scanned}")

    print(f"Machine findings:                {findings_scanned}")

    print(f"Reviewer findings:               {reviewer_findings_scanned}")

    print()
    print("Report quality")
    print("-" * 72)

    print(f"Missing required fields:         {len(missing_required_fields)}")

    print(f"Empty text fields:               {len(empty_text_fields)}")

    print(f"Invalid confidence values:       {len(invalid_confidence_values)}")

    print(f"Findings without provenance:     {len(missing_provenance)}")

    print(f"Unresolved provenance refs:      {len(unresolved_provenance)}")

    print()
    print("Reviewer consistency")
    print("-" * 72)

    print(f"Reviewer projection mismatch:    {len(reviewer_projection_mismatches)}")

    print(f"Markdown render mismatch:        {len(markdown_mismatches)}")

    print(f"Finding-count issues:            {len(finding_count_issues)}")

    print(f"Review-count issues:             {len(review_count_issues)}")

    print(f"High-priority partition issues:  {len(high_priority_partition_issues)}")

    print()
    print("Artifact integrity")
    print("-" * 72)

    print(f"Missing artifacts:               {len(missing_artifacts)}")

    print(f"Case-ID mismatches:              {len(case_id_mismatches)}")

    print()
    print(f"Total quality issues:            {structural_issue_count}")

    print()
    print("Saved evaluation to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "step_8_refinement"

OUTPUT_PATH = OUTPUT_DIR / "step_8_refinement_summary.json"


SOURCE_ARTIFACTS = {
    # Simplified 8B:
    # old detailed Step 8C evidence/finding freeze.
    "8B_finding_evidence_quality": (
        PROJECT_ROOT / "data" / "evaluation" / "step_8c_final" / "step_8c_final_summary.json"
    ),
    # Simplified 8C.1:
    # old detailed Step 8D timeline freeze.
    "8C.1_timeline_validation": (
        PROJECT_ROOT / "data" / "evaluation" / "step_8d_final" / "step_8d_final_summary.json"
    ),
    # Simplified 8C.2.
    "8C.2_medication_validation": (
        PROJECT_ROOT
        / "data"
        / "evaluation"
        / "step_8c2_final"
        / "step_8c2_medication_validation_summary.json"
    ),
    # Simplified 8D.
    "8D_review_report_quality": (
        PROJECT_ROOT
        / "data"
        / "evaluation"
        / "step_8d_final"
        / "step_8d_review_quality_summary.json"
    ),
}


SUPPORTING_ARTIFACTS = {
    "post_fix_population": (
        PROJECT_ROOT
        / "data"
        / "evaluation"
        / "representative_sample"
        / "post_refinement_population_analysis.json"
    ),
    "post_fix_validation": (
        PROJECT_ROOT
        / "data"
        / "evaluation"
        / "post_fix_validation_sample"
        / "post_fix_validation_metrics.json"
    ),
    "medication_integrity": (
        PROJECT_ROOT / "data" / "evaluation" / "medication" / "medication_integrity.json"
    ),
    "medication_reconciliation": (
        PROJECT_ROOT
        / "data"
        / "evaluation"
        / "medication"
        / "medication_reconciliation_correctness.json"
    ),
    "medication_detection": (
        PROJECT_ROOT
        / "data"
        / "evaluation"
        / "medication"
        / "medication_discrepancy_detection_quality.json"
    ),
    "human_review_burden": (
        PROJECT_ROOT
        / "data"
        / "evaluation"
        / "human_review_report_quality"
        / "human_review_burden.json"
    ),
    "report_reviewer_quality": (
        PROJECT_ROOT
        / "data"
        / "evaluation"
        / "human_review_report_quality"
        / "report_reviewer_quality.json"
    ),
}


def load_json(
    path: Path,
) -> dict[str, Any]:
    """Load a JSON object."""

    raw = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object.")

    return raw


def sha256_file(
    path: Path,
) -> str:
    """Return SHA-256 hash."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def artifact_record(
    *,
    name: str,
    path: Path,
    artifact: dict[str, Any],
) -> dict[str, Any]:
    """Build source-artifact metadata."""

    return {
        "name": name,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "sha256": sha256_file(path),
        "status": artifact.get("status"),
    }


def nested_get(
    value: dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    """Safely read nested dictionaries."""

    current: Any = value

    for key in keys:
        if not isinstance(
            current,
            dict,
        ):
            return default

        current = current.get(
            key,
            default,
        )

    return current


def artifact_pass_status(
    artifact: dict[str, Any],
) -> str | None:
    """Return status across current and legacy evaluation schemas."""

    status = artifact.get("status")

    if isinstance(status, str):
        return status

    overall_status = artifact.get("overall_status")

    if isinstance(overall_status, str):
        return overall_status

    return None


def main() -> int:
    """Run simplified Step 8E."""

    loaded_sources: dict[
        str,
        dict[str, Any],
    ] = {}

    loaded_supporting: dict[
        str,
        dict[str, Any],
    ] = {}

    source_records: list[dict[str, Any]] = []

    supporting_records: list[dict[str, Any]] = []

    missing_artifacts: list[str] = []

    #
    # Load required frozen simplified-step artifacts.
    #
    for (
        name,
        path,
    ) in SOURCE_ARTIFACTS.items():
        if not path.exists():
            missing_artifacts.append(str(path.relative_to(PROJECT_ROOT)))
            continue

        artifact = load_json(path)

        loaded_sources[name] = artifact

        source_records.append(
            {
                "name": name,
                "path": str(path.relative_to(PROJECT_ROOT)),
                "sha256": sha256_file(path),
                "status": artifact_pass_status(artifact),
            }
        )
    #
    # Load supporting evaluation artifacts.
    #
    for (
        name,
        path,
    ) in SUPPORTING_ARTIFACTS.items():
        if not path.exists():
            missing_artifacts.append(str(path.relative_to(PROJECT_ROOT)))
            continue

        artifact = load_json(path)

        loaded_supporting[name] = artifact

        supporting_records.append(
            artifact_record(
                name=name,
                path=path,
                artifact=artifact,
            )
        )

    required_source_names = set(SOURCE_ARTIFACTS)

    source_set_complete = set(loaded_sources) == required_source_names

    #
    # All current simplified evaluation components
    # after baseline/refinement must be PASS.
    #
    non_pass_sources = [
        {
            "name": name,
            "status": artifact_pass_status(artifact),
        }
        for name, artifact in loaded_sources.items()
        if artifact_pass_status(artifact) != "PASS"
    ]

    medication_integrity = loaded_supporting.get(
        "medication_integrity",
        {},
    )

    medication_reconciliation = loaded_supporting.get(
        "medication_reconciliation",
        {},
    )

    medication_detection = loaded_supporting.get(
        "medication_detection",
        {},
    )

    human_review = loaded_supporting.get(
        "human_review_burden",
        {},
    )

    report_quality = loaded_supporting.get(
        "report_reviewer_quality",
        {},
    )

    medication_integrity_issues = nested_get(
        medication_integrity,
        "integrity",
        "total_issues",
        default=None,
    )

    medication_reconciliation_issues = medication_reconciliation.get("total_issues")

    medication_false_positives = nested_get(
        medication_detection,
        "overall_metrics",
        "false_positives",
        default=None,
    )

    medication_false_negatives = nested_get(
        medication_detection,
        "overall_metrics",
        "false_negatives",
        default=None,
    )

    review_integrity_issues = nested_get(
        human_review,
        "integrity",
        "total_integrity_issues",
        default=None,
    )

    report_quality_issues = nested_get(
        report_quality,
        "artifact_integrity",
        "total_issues",
        default=None,
    )

    #
    # Historical error register.
    #
    error_register = [
        {
            "error_id": "E8-001",
            "category": ("structural_text_extraction"),
            "description": (
                "Structural, table-header, metadata, "
                "or explanatory text could be promoted "
                "into clinical claims/findings."
            ),
            "root_cause": (
                "Evidence-to-claim filtering was not "
                "sufficiently strict for non-clinical "
                "structural text."
            ),
            "refinement": (
                "Strengthened claim-creation filtering "
                "to reject known structural and "
                "non-clinical explanatory text."
            ),
            "validation_evidence": [
                ("Simplified 8B finding/evidence quality freeze passed."),
                (
                    "Fresh post-fix finding validation "
                    "showed 80/80 observed true-positive "
                    "and evidence-supported findings."
                ),
            ],
            "current_status": "RESOLVED",
            "production_change": True,
        },
        {
            "error_id": "E8-002",
            "category": ("medication_identity_normalization"),
            "description": (
                "Generated discharge-event wrapper "
                "text contaminated medication identity "
                "and produced false "
                "discharge-only discrepancies."
            ),
            "root_cause": (
                "Synthetic discharge wrapper prefixes "
                "and generated datetime suffixes were "
                "not removed before medication "
                "normalization."
            ),
            "refinement": (
                "Added deterministic stripping of "
                "synthetic discharge medication "
                "wrapper text before canonical "
                "medication-name normalization."
            ),
            "validation_evidence": [
                ("Medication discrepancy population reduced from historical 129 to current 1."),
                ("1697 medication mentions and 176 profiles passed reconciliation integrity."),
                (
                    "144 raw wrapper-bearing mentions "
                    "produced zero normalized wrapper "
                    "or datetime leakage."
                ),
                ("Independent discrepancy reconstruction produced 1 TP, 0 FP, and 0 FN."),
            ],
            "current_status": "RESOLVED",
            "production_change": True,
        },
        {
            "error_id": "E8-003",
            "category": ("timeline_evaluator_semantics"),
            "description": (
                "An intermediate evaluation appeared "
                "to report hundreds of medication "
                "stop-before-start timeline errors."
            ),
            "root_cause": (
                "The evaluator initially compared "
                "medication events too broadly and "
                "did not reproduce production episode "
                "matching semantics."
            ),
            "refinement": (
                "Corrected the evaluator to honor production same-episode provenance semantics."
            ),
            "validation_evidence": [
                (
                    "Corrected timeline conflict "
                    "evaluation matched the production "
                    "population with 316 TP, 0 FP, "
                    "and 0 FN."
                ),
                ("Simplified 8C.1 timeline validation is frozen PASS."),
            ],
            "current_status": "RESOLVED",
            "production_change": False,
        },
        {
            "error_id": "E8-004",
            "category": ("derived_reviewer_artifact_staleness"),
            "description": (
                "Reviewer bundle and reviewer Markdown "
                "still contained pre-refinement "
                "findings after the machine final "
                "reports had been regenerated."
            ),
            "root_cause": (
                "Derived reviewer-facing artifacts "
                "were not regenerated after upstream "
                "finding/refinement changes."
            ),
            "refinement": (
                "Regenerated reviewer artifacts from "
                "the current persisted final reports "
                "using the production reviewer "
                "generation pipeline."
            ),
            "validation_evidence": [
                ("317 machine findings exactly match 317 reviewer findings."),
                ("Reviewer projection mismatches: 0."),
                ("Markdown rendering mismatches: 0."),
                ("Finding-count and review-count mismatches: 0."),
            ],
            "current_status": "RESOLVED",
            "production_change": False,
        },
    ]

    unresolved_errors = [item for item in error_register if item["current_status"] != "RESOLVED"]

    #
    # Current residual systematic checks.
    #
    residual_checks = {
        "frozen_source_set_complete": (source_set_complete),
        "all_required_frozen_sources_pass": (not non_pass_sources),
        "medication_integrity_issues": (medication_integrity_issues),
        "medication_reconciliation_issues": (medication_reconciliation_issues),
        "medication_false_positives": (medication_false_positives),
        "medication_false_negatives": (medication_false_negatives),
        "human_review_integrity_issues": (review_integrity_issues),
        "report_quality_issues": (report_quality_issues),
        "unresolved_error_register_items": (len(unresolved_errors)),
    }

    numeric_residuals = (
        medication_integrity_issues,
        medication_reconciliation_issues,
        medication_false_positives,
        medication_false_negatives,
        review_integrity_issues,
        report_quality_issues,
    )

    numeric_residuals_available = all(value is not None for value in numeric_residuals)

    numeric_residuals_zero = numeric_residuals_available and all(
        int(value) == 0 for value in numeric_residuals
    )

    #
    # No new production code was changed during
    # 8D/8E after the already-validated medication
    # and claim refinements. Reviewer regeneration
    # refreshed derived artifacts only.
    #
    new_production_change_required = False

    fresh_validation_required = new_production_change_required

    overall_pass = all(
        (
            not missing_artifacts,
            source_set_complete,
            not non_pass_sources,
            numeric_residuals_zero,
            len(unresolved_errors) == 0,
        )
    )

    status = "PASS" if overall_pass else "FAIL"

    output = {
        "schema_version": "1.0",
        "evaluation_step": ("simplified_8E"),
        "title": ("Consolidated Error Analysis and Refinement"),
        "status": status,
        "generated_at": (datetime.now(UTC).isoformat()),
        "objective": (
            "Consolidate Step 8 defects, "
            "refinements, validation evidence, "
            "and residual-risk decisions before "
            "the final Step 8 freeze."
        ),
        "error_register": (error_register),
        "summary": {
            "historical_errors_registered": (len(error_register)),
            "resolved_errors": (
                sum(item["current_status"] == "RESOLVED" for item in error_register)
            ),
            "unresolved_errors": (len(unresolved_errors)),
            "historical_production_refinements": (
                sum(bool(item["production_change"]) for item in error_register)
            ),
        },
        "residual_checks": (residual_checks),
        "current_decision": {
            "unresolved_systematic_defects": (len(unresolved_errors)),
            "new_production_change_required": (new_production_change_required),
            "fresh_validation_required": (fresh_validation_required),
            "reason": (
                "All current frozen evaluation "
                "components pass and no unresolved "
                "systematic defect remains. The "
                "reviewer-artifact repair refreshed "
                "derived outputs but did not change "
                "production investigation logic."
            ),
        },
        "fresh_validation_policy": {
            "required_now": (fresh_validation_required),
            "trigger": (
                "Run new targeted validation only "
                "if production investigation logic "
                "changes after the currently frozen "
                "finding, timeline, or medication "
                "evaluations."
            ),
        },
        "missing_artifacts": (missing_artifacts),
        "non_pass_sources": (non_pass_sources),
        "unresolved_errors": (unresolved_errors),
        "frozen_source_artifacts": (source_records),
        "supporting_artifacts": (supporting_records),
        "conclusion": {
            "error_analysis": ("PASS" if len(unresolved_errors) == 0 else "FAIL"),
            "residual_systematic_risk": (
                "NO_KNOWN_SYSTEMATIC_DEFECT" if overall_pass else "REQUIRES_REVIEW"
            ),
            "additional_refinement_required": (new_production_change_required),
            "additional_fresh_validation_required": (fresh_validation_required),
            "overall_step_8e": (status),
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
    print("SIMPLIFIED STEP 8E CONSOLIDATED ERROR ANALYSIS / REFINEMENT")
    print("=" * 72)

    print(f"Overall status:                   {status}")

    print()
    print("Historical defect register")
    print("-" * 72)

    print(f"Registered defects:               {len(error_register)}")

    print(f"Resolved defects:                 {len(error_register) - len(unresolved_errors)}")

    print(f"Unresolved defects:               {len(unresolved_errors)}")

    print()
    print("Current residual checks")
    print("-" * 72)

    print(f"Frozen source set complete:       {source_set_complete}")

    print(f"Non-PASS frozen sources:          {len(non_pass_sources)}")

    print(f"Medication integrity issues:      {medication_integrity_issues}")

    print(f"Medication reconciliation issues: {medication_reconciliation_issues}")

    print(
        f"Medication FP / FN:               "
        f"{medication_false_positives} / "
        f"{medication_false_negatives}"
    )

    print(f"Review integrity issues:          {review_integrity_issues}")

    print(f"Report quality issues:            {report_quality_issues}")

    print()
    print("Refinement decision")
    print("-" * 72)

    print(f"New production change required:   {new_production_change_required}")

    print(f"Fresh validation required:        {fresh_validation_required}")

    print()
    print(f"Frozen evaluation sources:        {len(source_records)}")

    print(f"Supporting artifacts:             {len(supporting_records)}")

    print()
    print("Saved Step 8E summary to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

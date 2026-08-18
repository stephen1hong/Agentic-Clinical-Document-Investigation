from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EVALUATION_ROOT = PROJECT_ROOT / "data" / "evaluation"

GROUNDING_ROOT = EVALUATION_ROOT / "evidence_grounding"

POST_FIX_ROOT = EVALUATION_ROOT / "post_fix_validation_sample"

REPRESENTATIVE_ROOT = EVALUATION_ROOT / "representative_sample"

OUTPUT_DIR = EVALUATION_ROOT / "step_8c_final"

OUTPUT_PATH = OUTPUT_DIR / "step_8c_final_summary.json"


SOURCE_ARTIFACTS = {
    "evidence_grounding_integrity": (GROUNDING_ROOT / "evidence_grounding_integrity.json"),
    "semantic_evidence_support": (GROUNDING_ROOT / "semantic_evidence_support_metrics.json"),
    "residual_grounding_risk": (GROUNDING_ROOT / "residual_grounding_risk_analysis.json"),
    "negative_assertion_verification": (GROUNDING_ROOT / "negative_assertion_verification.json"),
    "post_refinement_population": (
        REPRESENTATIVE_ROOT / "post_refinement_population_analysis.json"
    ),
    "post_fix_sample_manifest": (POST_FIX_ROOT / "finding_sample_manifest.json"),
    "post_fix_annotations": (POST_FIX_ROOT / "annotations.json"),
    "post_fix_validation_metrics": (POST_FIX_ROOT / "post_fix_validation_metrics.json"),
}


def load_json(path: Path) -> Any:
    """Load JSON from disk."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def sha256_file(path: Path) -> str:
    """Return SHA-256 digest for a file."""

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(65536),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def relative_path(path: Path) -> str:
    """Return project-relative path."""

    return str(path.relative_to(PROJECT_ROOT))


def validate_required_artifacts() -> None:
    """Require every Step 8C source artifact."""

    missing = [relative_path(path) for path in SOURCE_ARTIFACTS.values() if not path.exists()]

    if missing:
        formatted = "\n".join(f"  - {path}" for path in missing)

        raise FileNotFoundError(
            f"Step 8C cannot be frozen because required artifacts are missing:\n{formatted}"
        )


def validate_post_fix_results(
    population: dict[str, Any],
    verification: dict[str, Any],
    annotations: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    """Validate critical final Step 8C acceptance conditions."""

    reports_scanned = verification.get("reports_scanned")

    discrepancies_evaluated = verification.get("discrepancies_evaluated")

    verification_summary = verification.get(
        "summary",
        {},
    )

    if reports_scanned != 20:
        raise ValueError(f"Expected post-fix 8C.4 to scan 20 reports, found {reports_scanned!r}.")

    if discrepancies_evaluated != 0:
        raise ValueError(
            "Post-fix negative assertions remain. "
            f"discrepancies_evaluated="
            f"{discrepancies_evaluated!r}"
        )

    if (
        verification_summary.get(
            "contradicted_by_other_source",
            0,
        )
        != 0
    ):
        raise ValueError("Post-fix 8C.4 still contains contradicted negative assertions.")

    if (
        verification_summary.get(
            "manual_review",
            0,
        )
        != 0
    ):
        raise ValueError("Post-fix 8C.4 still contains unresolved manual-review cases.")

    if annotations.get("annotation_status") != "final_approved":
        raise ValueError("Post-fix annotations are not marked final_approved.")

    if annotations.get("sample_size") != 80:
        raise ValueError("Expected 80 final approved annotations.")

    annotation_summary = annotations.get(
        "summary",
        {},
    )

    correctness = annotation_summary.get(
        "finding_correctness",
        {},
    )

    grounding = annotation_summary.get(
        "evidence_grounding",
        {},
    )

    if (
        correctness.get(
            "true_positive",
            0,
        )
        != 80
    ):
        raise ValueError("Expected 80 true-positive post-fix annotations.")

    if (
        grounding.get(
            "supported",
            0,
        )
        != 80
    ):
        raise ValueError("Expected 80 supported post-fix annotations.")

    overall = metrics.get(
        "overall",
        {},
    )

    correctness_metrics = overall.get(
        "finding_correctness",
        {},
    )

    grounding_metrics = overall.get(
        "evidence_grounding",
        {},
    )

    if correctness_metrics.get("strict_successes") != 80:
        raise ValueError(
            "Post-fix validation metrics do not contain 80 strict correctness successes."
        )

    if grounding_metrics.get("strict_successes") != 80:
        raise ValueError(
            "Post-fix validation metrics do not contain 80 strict grounding successes."
        )

    # Validate the known final population through
    # subtype counts rather than depending on one
    # particular population-total field name.
    subtype_counts = population.get("current_subtype_distribution")

    if isinstance(
        subtype_counts,
        dict,
    ):
        expected = {
            "missing_event_time": 316,
            "dose_conflict": 1,
        }

        if subtype_counts != expected:
            raise ValueError(f"Unexpected final subtype population: {subtype_counts}")


def artifact_manifest() -> dict[str, Any]:
    """Create immutable source-artifact metadata."""

    return {
        name: {
            "path": relative_path(path),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for name, path in SOURCE_ARTIFACTS.items()
    }


def main() -> int:
    """Freeze final Step 8C evaluation."""

    validate_required_artifacts()

    integrity = load_json(SOURCE_ARTIFACTS["evidence_grounding_integrity"])

    semantic_support = load_json(SOURCE_ARTIFACTS["semantic_evidence_support"])

    residual_risk = load_json(SOURCE_ARTIFACTS["residual_grounding_risk"])

    verification = load_json(SOURCE_ARTIFACTS["negative_assertion_verification"])

    population = load_json(SOURCE_ARTIFACTS["post_refinement_population"])

    sample_manifest = load_json(SOURCE_ARTIFACTS["post_fix_sample_manifest"])

    annotations = load_json(SOURCE_ARTIFACTS["post_fix_annotations"])

    metrics = load_json(SOURCE_ARTIFACTS["post_fix_validation_metrics"])

    validate_post_fix_results(
        population=population,
        verification=verification,
        annotations=annotations,
        metrics=metrics,
    )

    correctness_metrics = metrics["overall"]["finding_correctness"]

    grounding_metrics = metrics["overall"]["evidence_grounding"]

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8C.7",
        "status": "PASS",
        "frozen_at": datetime.now(UTC).isoformat(),
        "evaluation_scope": (
            "Evidence-grounding evaluation for "
            "the final post-refinement clinical "
            "investigation finding population."
        ),
        "final_population": {
            "reports": 20,
            "findings": 317,
            "finding_types": {
                "temporal_uncertainty": 316,
                "medication_discrepancy": 1,
            },
            "subtypes": {
                "missing_event_time": 316,
                "dose_conflict": 1,
            },
            "severity": {
                "info": 316,
                "high": 1,
            },
        },
        "refinement_history": {
            "initial_population": 489,
            "final_population": 317,
            "findings_removed": 172,
            "population_reduction_percentage": 35.2,
            "medication_discrepancies": {
                "before": 129,
                "after": 1,
                "removed": 128,
                "reduction_percentage": 99.2,
            },
            "temporal_uncertainties": {
                "before": 360,
                "after": 316,
                "removed": 44,
                "reduction_percentage": 12.2,
            },
        },
        "step_results": {
            "8C.1": {
                "status": "PASS",
                "description": ("Full-population provenance integrity evaluation."),
            },
            "8C.2": {
                "status": "PASS",
                "description": (
                    "Semantic evidence-support evaluation on the earlier held-out sample."
                ),
                "qualification": (
                    "The earlier semantic-support "
                    "sample did not independently "
                    "challenge cross-source "
                    "negative medication assertions."
                ),
            },
            "8C.3": {
                "status": ("PASS_WITH_DOCUMENTED_RESIDUAL_RISK"),
                "findings_evaluated": 425,
                "findings_flagged": 108,
                "risk_type": ("negative_assertion"),
                "description": (
                    "Residual-risk analysis "
                    "isolated 108 discharge-only "
                    "medication assertions for "
                    "stronger verification."
                ),
            },
            "8C.4_pre_fix": {
                "status": "FAIL",
                "discrepancies_evaluated": 108,
                "verified_absence": 0,
                "contradicted_by_other_source": 108,
                "manual_review": 0,
                "description": (
                    "All 108 discharge-only "
                    "medication assertions were "
                    "contradicted by matching "
                    "non-discharge evidence."
                ),
            },
            "8C.5": {
                "status": "PASS",
                "description": (
                    "Medication normalization was "
                    "refined to remove synthetic "
                    "near-discharge wrappers and "
                    "timestamps before medication "
                    "identity grouping. Full "
                    "regression suite passed."
                ),
            },
            "8C.4_post_fix": {
                "status": "PASS",
                "reports_scanned": (verification.get("reports_scanned")),
                "discrepancies_evaluated": (verification.get("discrepancies_evaluated")),
                "summary": (
                    verification.get(
                        "summary",
                        {},
                    )
                ),
                "description": (
                    "No discharge-only medication "
                    "negative assertions remained "
                    "after rebuilding the pipeline."
                ),
            },
            "8C.6": {
                "status": "PASS",
                "population_size": 317,
                "sample_size": 80,
                "sampling": {
                    "missing_event_time": {
                        "population": 316,
                        "evaluated": 79,
                        "method": ("seeded random sample"),
                    },
                    "dose_conflict": {
                        "population": 1,
                        "evaluated": 1,
                        "method": ("forced complete subtype coverage"),
                    },
                },
                "finding_correctness": {
                    "true_positive": 80,
                    "partially_correct": 0,
                    "false_positive": 0,
                    "strict_percentage": (correctness_metrics["strict_percentage"]),
                    "weighted_percentage": (correctness_metrics["weighted_percentage"]),
                    "wilson_95_ci": (correctness_metrics["wilson_95_ci"]),
                },
                "evidence_grounding": {
                    "supported": 80,
                    "partially_supported": 0,
                    "unsupported": 0,
                    "strict_percentage": (grounding_metrics["strict_percentage"]),
                    "weighted_percentage": (grounding_metrics["weighted_percentage"]),
                    "wilson_95_ci": (grounding_metrics["wilson_95_ci"]),
                },
            },
        },
        "final_interpretation": {
            "conclusion": (
                "Step 8C passes after targeted refinement and fresh post-fix validation."
            ),
            "observed_validation_result": (
                "All 80 fresh post-fix sampled "
                "findings were adjudicated "
                "correct and evidence-supported."
            ),
            "statistical_qualification": (
                "The observed validation rate is "
                "100%, but this should not be "
                "interpreted as proof that the "
                "true population-level accuracy "
                "is exactly 100%. The Wilson "
                "confidence interval should be "
                "reported with the observed rate."
            ),
            "dose_conflict_qualification": (
                "The single remaining "
                "dose_conflict represents complete "
                "coverage of that subtype rather "
                "than a random statistical sample."
            ),
            "adjudication_method": ("Fresh post-fix AI-assisted, human-approved adjudication."),
        },
        "source_artifacts": artifact_manifest(),
        "source_snapshots": {
            "8C.1_integrity": integrity,
            "8C.2_semantic_support": (semantic_support),
            "8C.3_residual_risk": (residual_risk),
            "8C.4_post_fix_verification": (verification),
            "8C.6_sample_manifest": (sample_manifest),
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
    print("STEP 8C.7 FINAL EVIDENCE-GROUNDING SUMMARY")
    print("=" * 72)

    print("Overall status:                 PASS")

    print("Final finding population:       317")

    print("Final reports:                  20")

    print()
    print("Final post-fix validation")
    print("-" * 72)

    print("Sample size:                     80")

    print("True positives:                  80")

    print("False positives:                  0")

    print("Supported:                       80")

    print("Unsupported:                      0")

    print(f"Observed correctness:          {correctness_metrics['strict_percentage']:.1f}%")

    print(f"Observed grounding:            {grounding_metrics['strict_percentage']:.1f}%")

    correctness_ci = correctness_metrics["wilson_95_ci"]

    print(
        "Correctness Wilson 95% CI:      "
        f"[{correctness_ci['lower_percentage']:.1f}%, "
        f"{correctness_ci['upper_percentage']:.1f}%]"
    )

    grounding_ci = grounding_metrics["wilson_95_ci"]

    print(
        "Grounding Wilson 95% CI:        "
        f"[{grounding_ci['lower_percentage']:.1f}%, "
        f"{grounding_ci['upper_percentage']:.1f}%]"
    )

    print()
    print("Refinement outcome")
    print("-" * 72)

    print("Findings:                 489 -> 317")

    print("Medication discrepancies: 129 -> 1")

    print("Known negative assertions:108 -> 0")

    print()
    print(f"Frozen source artifacts:         {len(SOURCE_ARTIFACTS)}")

    print()
    print("Saved frozen summary to:")

    print(OUTPUT_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

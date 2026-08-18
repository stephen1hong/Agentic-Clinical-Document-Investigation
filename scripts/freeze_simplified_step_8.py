from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EVALUATION_ROOT = PROJECT_ROOT / "data" / "evaluation"

OUTPUT_DIR = EVALUATION_ROOT / "step_8_final"

OUTPUT_PATH = OUTPUT_DIR / "step_8_final_summary.json"


STEP_8A_BASELINE_ARTIFACTS = {
    "finding_sample_manifest": (
        EVALUATION_ROOT / "representative_sample" / "finding_sample_manifest.json"
    ),
    "finding_sample_annotations": (
        EVALUATION_ROOT / "representative_sample" / "finding_sample_annotations.json"
    ),
    "finding_sample_metrics": (
        EVALUATION_ROOT / "representative_sample" / "finding_sample_metrics.json"
    ),
    "false_positive_analysis": (
        EVALUATION_ROOT / "representative_sample" / "false_positive_analysis.json"
    ),
}


STEP_SUMMARIES = {
    "8B": {
        "name": ("Finding quality and evidence grounding"),
        "path": (EVALUATION_ROOT / "step_8c_final" / "step_8c_final_summary.json"),
    },
    "8C.1": {
        "name": ("Timeline validation"),
        "path": (EVALUATION_ROOT / "step_8d_final" / "step_8d_final_summary.json"),
    },
    "8C.2": {
        "name": ("Medication validation"),
        "path": (
            EVALUATION_ROOT / "step_8c2_final" / "step_8c2_medication_validation_summary.json"
        ),
    },
    "8D": {
        "name": ("Human-review burden and report quality"),
        "path": (EVALUATION_ROOT / "step_8d_final" / "step_8d_review_quality_summary.json"),
    },
    "8E": {
        "name": ("Consolidated error analysis and refinement"),
        "path": (EVALUATION_ROOT / "step_8_refinement" / "step_8_refinement_summary.json"),
    },
}


def load_json(
    path: Path,
) -> dict[str, Any]:
    """Load one JSON object."""

    raw = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(
        raw,
        dict,
    ):
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


def artifact_status(
    artifact: dict[str, Any],
) -> str | None:
    """Read status from simplified and legacy schemas."""

    status = artifact.get("status")

    if isinstance(
        status,
        str,
    ):
        return status

    overall_status = artifact.get("overall_status")

    if isinstance(
        overall_status,
        str,
    ):
        return overall_status

    return None


def frozen_record(
    *,
    name: str,
    path: Path,
    status: str | None = None,
) -> dict[str, Any]:
    """Create immutable artifact metadata."""

    return {
        "name": name,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "size_bytes": (path.stat().st_size),
        "sha256": sha256_file(path),
        "status": status,
    }


def main() -> int:
    """Freeze simplified Step 8."""

    missing_artifacts: list[str] = []

    #
    # ------------------------------------------------
    # Simplified 8A
    # ------------------------------------------------
    #
    baseline_records: list[dict[str, Any]] = []

    for (
        name,
        path,
    ) in STEP_8A_BASELINE_ARTIFACTS.items():
        if not path.exists():
            missing_artifacts.append(str(path.relative_to(PROJECT_ROOT)))
            continue

        baseline_records.append(
            frozen_record(
                name=name,
                path=path,
                status="COMPLETE",
            )
        )

    step_8a_complete = len(baseline_records) == len(STEP_8A_BASELINE_ARTIFACTS)

    #
    # ------------------------------------------------
    # Simplified 8B through 8E
    # ------------------------------------------------
    #
    loaded_steps: dict[
        str,
        dict[str, Any],
    ] = {}

    step_records: list[dict[str, Any]] = []

    non_pass_steps: list[dict[str, Any]] = []

    for (
        step,
        definition,
    ) in STEP_SUMMARIES.items():
        path = definition["path"]

        if not path.exists():
            missing_artifacts.append(str(path.relative_to(PROJECT_ROOT)))
            continue

        artifact = load_json(path)

        loaded_steps[step] = artifact

        status = artifact_status(artifact)

        step_records.append(
            frozen_record(
                name=(f"{step} {definition['name']}"),
                path=path,
                status=status,
            )
        )

        if status != "PASS":
            non_pass_steps.append(
                {
                    "step": step,
                    "name": (definition["name"]),
                    "status": status,
                }
            )

    required_step_set = set(STEP_SUMMARIES)

    loaded_step_set = set(loaded_steps)

    all_step_summaries_present = loaded_step_set == required_step_set

    #
    # ------------------------------------------------
    # Extract key final metrics
    # ------------------------------------------------
    #
    medication = loaded_steps.get(
        "8C.2",
        {},
    )

    review = loaded_steps.get(
        "8D",
        {},
    )

    refinement = loaded_steps.get(
        "8E",
        {},
    )

    medication_scope = (
        medication.get(
            "scope",
            {},
        )
        if isinstance(
            medication,
            dict,
        )
        else {}
    )

    medication_components = (
        medication.get(
            "component_results",
            {},
        )
        if isinstance(
            medication,
            dict,
        )
        else {}
    )

    medication_detection = (
        medication_components.get(
            "8C.2c",
            {},
        )
        if isinstance(
            medication_components,
            dict,
        )
        else {}
    )

    review_scope = (
        review.get(
            "scope",
            {},
        )
        if isinstance(
            review,
            dict,
        )
        else {}
    )

    review_components = (
        review.get(
            "component_results",
            {},
        )
        if isinstance(
            review,
            dict,
        )
        else {}
    )

    review_burden = (
        review_components.get(
            "8D.1",
            {},
        )
        if isinstance(
            review_components,
            dict,
        )
        else {}
    )

    refinement_summary = (
        refinement.get(
            "summary",
            {},
        )
        if isinstance(
            refinement,
            dict,
        )
        else {}
    )

    refinement_decision = (
        refinement.get(
            "current_decision",
            {},
        )
        if isinstance(
            refinement,
            dict,
        )
        else {}
    )

    #
    # ------------------------------------------------
    # Final Step-8 decision
    # ------------------------------------------------
    #
    overall_pass = all(
        (
            not missing_artifacts,
            step_8a_complete,
            all_step_summaries_present,
            not non_pass_steps,
            len(loaded_steps) == len(STEP_SUMMARIES),
        )
    )

    status = "PASS" if overall_pass else "FAIL"

    output = {
        "schema_version": "1.0",
        "evaluation_step": ("simplified_8F"),
        "evaluation_name": ("Final Simplified Step 8 Freeze"),
        "overall_status": status,
        "frozen_at": (datetime.now(UTC).isoformat()),
        "step_results": {
            "8A": {
                "name": ("Evaluation framework and baseline"),
                "status": ("COMPLETE" if step_8a_complete else "INCOMPLETE"),
                "frozen_artifact_count": (len(baseline_records)),
            },
            "8B": {
                "name": ("Finding quality and evidence grounding"),
                "status": artifact_status(
                    loaded_steps.get(
                        "8B",
                        {},
                    )
                ),
            },
            "8C": {
                "name": ("Timeline and medication validation"),
                "status": (
                    "PASS"
                    if (
                        artifact_status(
                            loaded_steps.get(
                                "8C.1",
                                {},
                            )
                        )
                        == "PASS"
                        and artifact_status(
                            loaded_steps.get(
                                "8C.2",
                                {},
                            )
                        )
                        == "PASS"
                    )
                    else "FAIL"
                ),
                "components": {
                    "8C.1": {
                        "name": ("Timeline validation"),
                        "status": artifact_status(
                            loaded_steps.get(
                                "8C.1",
                                {},
                            )
                        ),
                    },
                    "8C.2": {
                        "name": ("Medication validation"),
                        "status": artifact_status(
                            loaded_steps.get(
                                "8C.2",
                                {},
                            )
                        ),
                    },
                },
            },
            "8D": {
                "name": ("Human-review burden and report quality"),
                "status": artifact_status(
                    loaded_steps.get(
                        "8D",
                        {},
                    )
                ),
            },
            "8E": {
                "name": ("Consolidated error analysis and refinement"),
                "status": artifact_status(
                    loaded_steps.get(
                        "8E",
                        {},
                    )
                ),
            },
            "8F": {
                "name": ("Final Step-8 freeze"),
                "status": status,
            },
        },
        "final_population": {
            "cases": (review_scope.get("cases")),
            "findings": (review_scope.get("total_findings")),
            "review_required_findings": (review_scope.get("review_required_findings")),
            "contextual_findings": (review_scope.get("contextual_findings")),
            "medication_mentions": (medication_scope.get("medication_mentions")),
            "medication_profiles": (medication_scope.get("medication_profiles")),
            "medication_discrepancies": (medication_scope.get("medication_discrepancies")),
        },
        "final_quality_metrics": {
            "medication_detection": {
                "true_positives": (medication_detection.get("true_positives")),
                "false_positives": (medication_detection.get("false_positives")),
                "false_negatives": (medication_detection.get("false_negatives")),
                "precision": (medication_detection.get("precision")),
                "recall": (medication_detection.get("recall")),
                "f1": (medication_detection.get("f1")),
            },
            "human_review": {
                "cases_requiring_review": (review_burden.get("cases_requiring_review")),
                "case_review_rate_percentage": (review_burden.get("case_review_rate_percentage")),
                "finding_review_rate_percentage": (
                    review_burden.get("finding_review_rate_percentage")
                ),
                "max_review_findings_per_case": (review_burden.get("max_review_findings_per_case")),
            },
            "refinement": {
                "historical_errors_registered": (
                    refinement_summary.get("historical_errors_registered")
                ),
                "resolved_errors": (refinement_summary.get("resolved_errors")),
                "unresolved_errors": (refinement_summary.get("unresolved_errors")),
                "new_production_change_required": (
                    refinement_decision.get("new_production_change_required")
                ),
                "fresh_validation_required": (refinement_decision.get("fresh_validation_required")),
            },
        },
        "release_gate": {
            "step_8_complete": (overall_pass),
            "ready_for_step_9": (overall_pass),
            "next_step": (
                "Step 9 — End-to-End Acceptance Testing"
                if overall_pass
                else ("Resolve Step-8 freeze failures before Step 9.")
            ),
        },
        "missing_artifacts": (missing_artifacts),
        "non_pass_steps": (non_pass_steps),
        "frozen_artifacts": {
            "8A_baseline": (baseline_records),
            "8B_through_8E": (step_records),
        },
        "frozen_artifact_count": (len(baseline_records) + len(step_records)),
        "methodological_notes": [
            (
                "Simplified Step 8A is frozen as "
                "the original representative baseline "
                "package rather than as a synthetic "
                "summary artifact created after the fact."
            ),
            ("Legacy detailed Step 8C maps to simplified Step 8B."),
            ("Legacy detailed Step 8D timeline evaluation maps to simplified Step 8C.1."),
            (
                "Observed 100% values apply to the "
                "evaluated deterministic datasets and "
                "must not be interpreted as proof of "
                "universal clinical accuracy."
            ),
            (
                "Step 8 evaluation is considered "
                "frozen after this artifact is created. "
                "Any later production-logic change "
                "requires rerunning the affected "
                "validation before release."
            ),
        ],
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
    print("SIMPLIFIED STEP 8 — FINAL EVALUATION / REFINEMENT FREEZE")
    print("=" * 72)

    print(f"Overall Step 8 status:            {status}")

    print()
    print("Step results")
    print("-" * 72)

    print(f"8A Evaluation framework/baseline: {'COMPLETE' if step_8a_complete else 'INCOMPLETE'}")

    for step in (
        "8B",
        "8C.1",
        "8C.2",
        "8D",
        "8E",
    ):
        print(f"{step:<35}{artifact_status(loaded_steps.get(step, {}))}")

    print(f"{'8F Final Step-8 freeze':<35}{status}")

    print()
    print("Final population")
    print("-" * 72)

    print(f"Cases:                            {review_scope.get('cases')}")

    print(f"Final findings:                   {review_scope.get('total_findings')}")

    print(f"Review-required findings:         {review_scope.get('review_required_findings')}")

    print(f"Contextual findings:              {review_scope.get('contextual_findings')}")

    print()
    print("Final refinement state")
    print("-" * 72)

    print(
        f"Historical defects:               "
        f"{refinement_summary.get('historical_errors_registered')}"
    )

    print(f"Resolved defects:                 {refinement_summary.get('resolved_errors')}")

    print(f"Unresolved defects:               {refinement_summary.get('unresolved_errors')}")

    print(
        f"New production change required:   "
        f"{refinement_decision.get('new_production_change_required')}"
    )

    print(
        f"Fresh validation required:        {refinement_decision.get('fresh_validation_required')}"
    )

    print()
    print(f"Missing artifacts:                {len(missing_artifacts)}")

    print(f"Non-PASS step summaries:          {len(non_pass_steps)}")

    print(f"Frozen artifacts:                 {len(baseline_records) + len(step_records)}")

    print()
    print(f"Ready for Step 9:                 {overall_pass}")

    print()
    print("Saved final Step-8 freeze to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

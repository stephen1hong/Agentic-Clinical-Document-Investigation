from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EVALUATION_ROOT = PROJECT_ROOT / "data" / "evaluation"

OUTPUT_DIR = EVALUATION_ROOT / "step_8_simplified"

OUTPUT_PATH = OUTPUT_DIR / "step_8_simplified_status.json"


ARTIFACTS = {
    "evidence_grounding_final": (EVALUATION_ROOT / "step_8c_final" / "step_8c_final_summary.json"),
    "timeline_final": (EVALUATION_ROOT / "step_8d_final" / "step_8d_final_summary.json"),
    "baseline_sample": (EVALUATION_ROOT / "representative_sample" / "finding_sample_manifest.json"),
    "baseline_annotations": (
        EVALUATION_ROOT / "representative_sample" / "finding_sample_annotations.json"
    ),
    "baseline_fp_analysis": (
        EVALUATION_ROOT / "representative_sample" / "false_positive_analysis.json"
    ),
    "post_fix_validation": (
        EVALUATION_ROOT / "post_fix_validation_sample" / "post_fix_validation_metrics.json"
    ),
}


def load_json(
    path: Path,
) -> dict[str, Any] | None:
    """Load JSON when the artifact exists."""

    if not path.exists():
        return None

    raw = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(
        raw,
        dict,
    ):
        raise ValueError(f"Expected JSON object: {path}")

    return raw


def artifact_record(
    path: Path,
) -> dict[str, Any]:
    """Describe an existing or pending artifact."""

    return {
        "path": str(path.relative_to(PROJECT_ROOT)),
        "exists": (path.exists()),
    }


def final_status(
    data: dict[str, Any] | None,
) -> str | None:
    """Read common final-status fields."""

    if data is None:
        return None

    for field in (
        "overall_status",
        "status",
    ):
        value = data.get(field)

        if isinstance(
            value,
            str,
        ):
            return value

    return None


def main() -> int:
    """Build simplified Step 8 roadmap/status."""

    evidence_summary = load_json(ARTIFACTS["evidence_grounding_final"])

    timeline_summary = load_json(ARTIFACTS["timeline_final"])

    evidence_status = final_status(evidence_summary)

    timeline_status = final_status(timeline_summary)

    phase_8a_complete = all(
        ARTIFACTS[name].exists()
        for name in (
            "baseline_sample",
            "baseline_annotations",
            "baseline_fp_analysis",
        )
    )

    phase_8b_complete = evidence_status == "PASS"

    timeline_complete = timeline_status == "PASS"

    #
    # Medication validation has not yet been
    # completed under the simplified structure.
    #
    medication_complete = False

    phase_8c_complete = timeline_complete and medication_complete

    #
    # These phases intentionally remain pending.
    #
    phase_8d_complete = False
    phase_8e_complete = False
    phase_8f_complete = False

    output = {
        "schema_version": "1.0",
        "roadmap": ("simplified_step_8"),
        "step": "8",
        "name": ("Evaluation & Refinement"),
        "mapping_policy": {
            "preserve_existing_artifacts": True,
            "rename_existing_artifacts": False,
            "description": (
                "Detailed historical Step 8 "
                "artifacts remain unchanged. "
                "The simplified structure is a "
                "documentation and execution layer "
                "that groups those detailed results "
                "into six major phases."
            ),
        },
        "phases": {
            "8A": {
                "name": ("Evaluation framework and baseline"),
                "status": ("COMPLETE" if phase_8a_complete else "INCOMPLETE"),
                "mapped_work": [
                    "Original Step 8A",
                    "Original Step 8B",
                ],
                "scope": [
                    ("Evaluation schema and gold-label framework"),
                    ("Representative baseline finding sample"),
                    ("Baseline precision and false-positive analysis"),
                    ("Initial error characterization"),
                ],
            },
            "8B": {
                "name": ("Finding quality and evidence grounding"),
                "status": ("COMPLETE" if phase_8b_complete else "INCOMPLETE"),
                "mapped_work": [
                    "Original Step 8C",
                ],
                "final_status": (evidence_status),
                "scope": [
                    ("Evidence provenance integrity"),
                    ("Semantic evidence support"),
                    ("Residual grounding risk"),
                    ("Negative-assertion verification"),
                    ("Post-refinement fresh validation"),
                ],
            },
            "8C": {
                "name": ("Timeline and medication validation"),
                "status": ("COMPLETE" if phase_8c_complete else "IN_PROGRESS"),
                "subphases": {
                    "8C.1": {
                        "name": ("Timeline validation"),
                        "status": ("COMPLETE" if timeline_complete else "INCOMPLETE"),
                        "mapped_work": [
                            "Original Step 8D",
                        ],
                        "final_status": (timeline_status),
                    },
                    "8C.2": {
                        "name": ("Medication validation"),
                        "status": ("COMPLETE" if medication_complete else "NEXT"),
                    },
                },
            },
            "8D": {
                "name": ("Human-review burden and report quality"),
                "status": ("COMPLETE" if phase_8d_complete else "PENDING"),
            },
            "8E": {
                "name": ("Error analysis, refinement, and fresh validation"),
                "status": ("COMPLETE" if phase_8e_complete else "PENDING"),
                "historical_work_already_done": [
                    ("Unsupported-claim false-positive analysis"),
                    ("Structural-text claim suppression refinement"),
                    ("Medication normalization refinement"),
                    ("Fresh post-fix finding validation"),
                ],
                "remaining_scope": [
                    ("Consolidated residual error analysis"),
                    ("Apply any remaining cross-subsystem fixes"),
                    ("Fresh validation only if new production changes are introduced"),
                ],
            },
            "8F": {
                "name": ("Final Step 8 freeze"),
                "status": ("COMPLETE" if phase_8f_complete else "PENDING"),
                "scope": [
                    ("Validate simplified 8A-8E completion"),
                    ("Freeze final source artifacts"),
                    ("Create consolidated Step 8 summary"),
                ],
            },
        },
        "existing_artifacts": {name: artifact_record(path) for name, path in ARTIFACTS.items()},
        "next_action": {
            "phase": "8C.2",
            "name": ("Medication validation"),
        },
        "future_steps": {
            "9": ("End-to-End Acceptance Testing"),
            "10": ("Documentation & Release Packaging"),
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
    print("SIMPLIFIED STEP 8 STATUS")
    print("=" * 72)

    print(f"8A Evaluation framework/baseline:      {output['phases']['8A']['status']}")

    print(f"8B Finding/evidence quality:           {output['phases']['8B']['status']}")

    print(f"8C Timeline + medication validation:   {output['phases']['8C']['status']}")

    print(
        "  8C.1 Timeline validation:            "
        f"{output['phases']['8C']['subphases']['8C.1']['status']}"
    )

    print(
        "  8C.2 Medication validation:          "
        f"{output['phases']['8C']['subphases']['8C.2']['status']}"
    )

    print(f"8D Human review/report quality:        {output['phases']['8D']['status']}")

    print(f"8E Error analysis/refinement:          {output['phases']['8E']['status']}")

    print(f"8F Final Step 8 freeze:                {output['phases']['8F']['status']}")

    print()
    print("Next action: 8C.2 — Medication Validation")

    print()
    print("Saved simplified status to:")

    print(OUTPUT_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

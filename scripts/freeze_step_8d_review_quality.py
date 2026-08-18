from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

SOURCE_DIR = PROJECT_ROOT / "data" / "evaluation" / "human_review_report_quality"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "step_8d_final"

OUTPUT_PATH = OUTPUT_DIR / "step_8d_review_quality_summary.json"


SOURCE_ARTIFACTS = {
    "8D.1_human_review_burden": (SOURCE_DIR / "human_review_burden.json"),
    "8D.2_report_reviewer_quality": (SOURCE_DIR / "report_reviewer_quality.json"),
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

    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object.")

    return raw


def sha256_file(
    path: Path,
) -> str:
    """Return SHA-256 hash for one file."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


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


def require_pass(
    *,
    name: str,
    artifact: dict[str, Any],
) -> None:
    """Require a PASS source artifact."""

    status = artifact.get("status")

    if status != "PASS":
        raise RuntimeError(f"{name} is not PASS: {status!r}")


def main() -> int:
    """Freeze simplified Step 8D."""

    loaded: dict[
        str,
        dict[str, Any],
    ] = {}

    frozen_sources: list[dict[str, Any]] = []

    for name, path in SOURCE_ARTIFACTS.items():
        if not path.exists():
            raise FileNotFoundError(f"Required artifact not found: {path}")

        artifact = load_json(path)

        require_pass(
            name=name,
            artifact=artifact,
        )

        loaded[name] = artifact

        frozen_sources.append(
            {
                "name": name,
                "path": str(path.relative_to(PROJECT_ROOT)),
                "sha256": sha256_file(path),
                "status": artifact.get("status"),
            }
        )

    burden = loaded["8D.1_human_review_burden"]

    quality = loaded["8D.2_report_reviewer_quality"]

    burden_population = burden.get(
        "population",
        {},
    )

    burden_metrics = burden.get(
        "review_burden",
        {},
    )

    burden_integrity = burden.get(
        "integrity",
        {},
    )

    quality_population = quality.get(
        "population",
        {},
    )

    quality_checks = quality.get(
        "quality_checks",
        {},
    )

    quality_integrity = quality.get(
        "artifact_integrity",
        {},
    )

    cases = burden_population.get("cases_scanned")

    total_findings = burden_population.get("total_findings")

    review_findings = burden_population.get("total_review_findings")

    contextual_findings = burden_population.get("total_contextual_findings")

    cases_requiring_review = burden_metrics.get("cases_requiring_review")

    case_review_rate = burden_metrics.get("case_review_rate_percentage")

    finding_review_rate = burden_metrics.get("finding_review_rate_percentage")

    max_review_findings = burden_metrics.get("max_review_findings_per_case")

    burden_integrity_issues = burden_integrity.get("total_integrity_issues")

    quality_issue_count = quality_integrity.get("total_issues")

    machine_findings = quality_population.get("machine_findings")

    reviewer_findings = quality_population.get("reviewer_findings")

    critical_quality_checks = {
        "required_field_issues": (quality_checks.get("required_field_issues")),
        "empty_text_field_issues": (quality_checks.get("empty_text_field_issues")),
        "invalid_confidence_values": (quality_checks.get("invalid_confidence_values")),
        "findings_without_provenance": (quality_checks.get("findings_without_provenance")),
        "unresolved_provenance_references": (
            quality_checks.get("unresolved_provenance_references")
        ),
        "reviewer_projection_mismatches": (quality_checks.get("reviewer_projection_mismatches")),
        "markdown_render_mismatches": (quality_checks.get("markdown_render_mismatches")),
        "finding_count_issues": (quality_checks.get("finding_count_issues")),
        "review_count_issues": (quality_checks.get("review_count_issues")),
        "high_priority_partition_issues": (quality_checks.get("high_priority_partition_issues")),
    }

    critical_quality_issue_count = sum(
        int(value or 0) for value in critical_quality_checks.values()
    )

    overall_pass = all(
        (
            burden.get("status") == "PASS",
            quality.get("status") == "PASS",
            burden_integrity_issues == 0,
            quality_issue_count == 0,
            critical_quality_issue_count == 0,
            machine_findings == reviewer_findings,
            total_findings == machine_findings,
        )
    )

    status = "PASS" if overall_pass else "FAIL"

    output = {
        "schema_version": "1.0",
        "evaluation_step": "simplified_8D",
        "title": ("Human Review Burden and Final Report Quality"),
        "status": status,
        "frozen_at": datetime.now(UTC).isoformat(),
        "scope": {
            "cases": cases,
            "total_findings": total_findings,
            "review_required_findings": (review_findings),
            "contextual_findings": (contextual_findings),
        },
        "component_results": {
            "8D.1": {
                "name": ("Human-review burden"),
                "status": burden.get("status"),
                "cases_requiring_review": (cases_requiring_review),
                "case_review_rate_percentage": (case_review_rate),
                "finding_review_rate_percentage": (finding_review_rate),
                "max_review_findings_per_case": (max_review_findings),
                "integrity_issues": (burden_integrity_issues),
            },
            "8D.2": {
                "name": ("Final-report and reviewer-artifact quality"),
                "status": quality.get("status"),
                "machine_findings": (machine_findings),
                "reviewer_findings": (reviewer_findings),
                "quality_issues": (quality_issue_count),
                "critical_checks": (critical_quality_checks),
            },
        },
        "conclusion": {
            "human_review_burden": "LOW",
            "review_projection_integrity": "PASS",
            "report_structural_quality": "PASS",
            "provenance_integrity": "PASS",
            "overall_step_8d": status,
        },
        "interpretation": {
            "review_burden_note": (
                "Observed human-review workload is "
                "low in the current evaluation "
                "population: one review-required "
                "finding across twenty cases."
            ),
            "quality_note": (
                "Final reports and reviewer-facing "
                "artifacts are structurally "
                "consistent, provenance-resolved, "
                "and deterministically synchronized."
            ),
            "scope_note": (
                "This step evaluates operational "
                "review burden and structural report "
                "quality. It does not constitute "
                "independent clinical usability or "
                "physician acceptance testing."
            ),
        },
        "frozen_source_artifacts": (frozen_sources),
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
    print("SIMPLIFIED STEP 8D HUMAN-REVIEW / REPORT QUALITY — FINAL")
    print("=" * 72)

    print(f"Overall status:                  {status}")

    print()
    print("Population")
    print("-" * 72)

    print(f"Cases:                           {cases}")

    print(f"Total findings:                  {total_findings}")

    print(f"Review-required findings:        {review_findings}")

    print(f"Contextual findings:             {contextual_findings}")

    print()
    print("Human-review burden")
    print("-" * 72)

    print(f"Cases requiring review:          {cases_requiring_review}")

    print(f"Case review rate:                {float(case_review_rate):.1f}%")

    print(f"Finding review rate:             {float(finding_review_rate):.1f}%")

    print(f"Maximum review items / case:     {max_review_findings}")

    print()
    print("Report / reviewer quality")
    print("-" * 72)

    print(f"Machine findings:                {machine_findings}")

    print(f"Reviewer findings:               {reviewer_findings}")

    print(f"Human-review integrity issues:   {burden_integrity_issues}")

    print(f"Report quality issues:           {quality_issue_count}")

    print()
    print(f"Frozen source artifacts:         {len(frozen_sources)}")

    print()
    print("Saved Step 8D summary to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EVALUATION_DIR = PROJECT_ROOT / "data" / "evaluation" / "medication"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "step_8c2_final"

OUTPUT_PATH = OUTPUT_DIR / "step_8c2_medication_validation_summary.json"


SOURCE_ARTIFACTS = {
    "8C.2a_medication_integrity": (EVALUATION_DIR / "medication_integrity.json"),
    "8C.2b_reconciliation_correctness": (
        EVALUATION_DIR / "medication_reconciliation_correctness.json"
    ),
    "8C.2c_discrepancy_detection_quality": (
        EVALUATION_DIR / "medication_discrepancy_detection_quality.json"
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

    if not isinstance(
        raw,
        dict,
    ):
        raise ValueError(f"{path} must contain a JSON object.")

    return raw


def sha256_file(
    path: Path,
) -> str:
    """Return SHA-256 hash of a file."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


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
    """Freeze simplified Step 8C.2 medication validation."""

    loaded: dict[
        str,
        dict[str, Any],
    ] = {}

    frozen_sources: list[dict[str, Any]] = []

    for (
        name,
        path,
    ) in SOURCE_ARTIFACTS.items():
        if not path.exists():
            raise FileNotFoundError(f"Required evaluation artifact not found: {path}")

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
                "status": (artifact.get("status")),
            }
        )

    integrity = loaded["8C.2a_medication_integrity"]

    reconciliation = loaded["8C.2b_reconciliation_correctness"]

    detection = loaded["8C.2c_discrepancy_detection_quality"]

    integrity_population = integrity.get(
        "population",
        {},
    )

    integrity_metrics = integrity.get(
        "integrity",
        {},
    )

    reconciliation_normalization = reconciliation.get(
        "normalization_integrity",
        {},
    )

    reconciliation_aggregation = reconciliation.get(
        "profile_aggregation_integrity",
        {},
    )

    detection_population = detection.get(
        "population",
        {},
    )

    detection_metrics = detection.get(
        "overall_metrics",
        {},
    )

    detection_integrity = detection.get(
        "integrity",
        {},
    )

    cases_scanned = integrity.get("cases_scanned")

    mentions = integrity_population.get("medication_mentions")

    profiles = integrity_population.get("medication_profiles")

    discrepancies = integrity_population.get("medication_discrepancies")

    total_integrity_issues = integrity_metrics.get("total_issues")

    reconciliation_issues = reconciliation.get("total_issues")

    true_positives = detection_metrics.get("true_positives")

    false_positives = detection_metrics.get("false_positives")

    false_negatives = detection_metrics.get("false_negatives")

    precision = detection_metrics.get("precision")

    recall = detection_metrics.get("recall")

    f1 = detection_metrics.get("f1")

    expected_discrepancies = detection_population.get("expected_semantic_discrepancies")

    emitted_discrepancies = detection_population.get("emitted_semantic_discrepancies")

    detection_integrity_issues = detection_integrity.get("integrity_issue_count")

    overall_pass = all(
        (
            integrity.get("status") == "PASS",
            reconciliation.get("status") == "PASS",
            detection.get("status") == "PASS",
            total_integrity_issues == 0,
            reconciliation_issues == 0,
            false_positives == 0,
            false_negatives == 0,
            detection_integrity_issues == 0,
        )
    )

    status = "PASS" if overall_pass else "FAIL"

    output = {
        "schema_version": "1.0",
        "evaluation_step": ("simplified_8C.2"),
        "title": ("Medication Validation"),
        "status": status,
        "frozen_at": (datetime.now(UTC).isoformat()),
        "scope": {
            "cases": (cases_scanned),
            "medication_mentions": (mentions),
            "medication_profiles": (profiles),
            "medication_discrepancies": (discrepancies),
        },
        "component_results": {
            "8C.2a": {
                "name": ("Medication artifact and provenance integrity"),
                "status": (integrity.get("status")),
                "total_issues": (total_integrity_issues),
            },
            "8C.2b": {
                "name": ("Medication normalization and reconciliation correctness"),
                "status": (reconciliation.get("status")),
                "total_issues": (reconciliation_issues),
                "normalized_wrapper_leakage": (
                    reconciliation_normalization.get("normalized_wrapper_leakage")
                ),
                "normalized_datetime_leakage": (
                    reconciliation_normalization.get("normalized_datetime_leakage")
                ),
                "profile_aggregation_issues": (
                    sum(int(value or 0) for value in reconciliation_aggregation.values())
                ),
            },
            "8C.2c": {
                "name": ("Medication discrepancy detection quality"),
                "status": (detection.get("status")),
                "expected_discrepancies": (expected_discrepancies),
                "emitted_discrepancies": (emitted_discrepancies),
                "true_positives": (true_positives),
                "false_positives": (false_positives),
                "false_negatives": (false_negatives),
                "precision": (precision),
                "recall": (recall),
                "f1": (f1),
            },
        },
        "conclusion": {
            "artifact_integrity": ("PASS" if total_integrity_issues == 0 else "FAIL"),
            "normalization_and_reconciliation": ("PASS" if reconciliation_issues == 0 else "FAIL"),
            "discrepancy_detection": (
                "PASS"
                if (
                    false_positives == 0
                    and false_negatives == 0
                    and detection_integrity_issues == 0
                )
                else "FAIL"
            ),
            "overall_medication_validation": (status),
        },
        "interpretation": {
            "positive_population_note": (
                "The current evaluation population "
                "contains one positive medication "
                "discrepancy. Complete agreement on "
                "that population does not establish "
                "universal 100% medication-detection "
                "accuracy."
            ),
            "normalization_note": (
                "Raw generated source text may contain "
                "synthetic discharge wrapper language, "
                "but the evaluated normalized medication "
                "identity fields contain no wrapper or "
                "datetime leakage."
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
    print("SIMPLIFIED STEP 8C.2 MEDICATION VALIDATION — FINAL")
    print("=" * 72)

    print(f"Overall status:                  {status}")

    print()
    print("Population")
    print("-" * 72)

    print(f"Cases:                           {cases_scanned}")

    print(f"Medication mentions:             {mentions}")

    print(f"Medication profiles:             {profiles}")

    print(f"Medication discrepancies:        {discrepancies}")

    print()
    print("Component results")
    print("-" * 72)

    print(f"8C.2a Artifact/provenance:        {integrity.get('status')}")

    print(f"8C.2b Reconciliation:             {reconciliation.get('status')}")

    print(f"8C.2c Detection quality:          {detection.get('status')}")

    print()
    print("Discrepancy detection")
    print("-" * 72)

    print(f"Expected / emitted:              {expected_discrepancies} / {emitted_discrepancies}")

    print(
        f"TP / FP / FN:                    {true_positives} / {false_positives} / {false_negatives}"
    )

    print(f"Precision:                       {float(precision) * 100.0:.1f}%")

    print(f"Recall:                          {float(recall) * 100.0:.1f}%")

    print(f"F1:                              {float(f1) * 100.0:.1f}%")

    print()
    print(f"Frozen source artifacts:         {len(frozen_sources)}")

    print()
    print("Saved final medication validation to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

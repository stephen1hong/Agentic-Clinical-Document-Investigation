from __future__ import annotations

import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluate_end_to_end_regression import (
    get_report_findings,
    load_json,
    sha256_file,
    validate_one_case,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

STEP_9A_PATH = PROJECT_ROOT / "data" / "evaluation" / "step_9a" / "end_to_end_regression.json"

STEP_9B1_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "step_9b1" / "missing_partial_artifact_robustness.json"
)

STEP_9B2_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "step_9b2" / "malformed_schema_robustness.json"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "step_9b3"

WORKSPACE_DIR = OUTPUT_DIR / "workspace"

OUTPUT_PATH = OUTPUT_DIR / "provenance_breakage_robustness.json"


PROVENANCE_CONFIG = {
    "evidence": {
        "finding_field": "evidence_ids",
        "artifact": "evidence_items.json",
        "record_id_field": "evidence_id",
        "expected_category": ("unresolved_evidence_reference"),
    },
    "claim": {
        "finding_field": "claim_ids",
        "artifact": "clinical_claims.json",
        "record_id_field": "claim_id",
        "expected_category": ("unresolved_claim_reference"),
    },
    "event": {
        "finding_field": "event_ids",
        "artifact": "canonical_timeline.json",
        "record_id_field": "event_id",
        "expected_category": ("unresolved_timeline_reference"),
    },
}


def write_json(
    path: Path,
    payload: Any,
) -> None:
    """Write formatted JSON."""

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def artifact_status(
    artifact: dict[str, Any],
) -> str | None:
    """Read evaluation status."""

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


def load_required_evaluation(
    path: Path,
    name: str,
) -> dict[str, Any]:
    """Load one prerequisite evaluation."""

    if not path.exists():
        raise FileNotFoundError(f"{name} artifact not found: {path}")

    payload = load_json(path)

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(f"{name} artifact must contain a JSON object.")

    if artifact_status(payload) != "PASS":
        raise RuntimeError(f"{name} must be PASS before running Step 9B.3.")

    return payload


def all_case_dirs() -> list[Path]:
    """Return production investigation cases."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    return sorted(path for path in CASE_ROOT.iterdir() if path.is_dir())


def find_reference(
    provenance_type: str,
) -> dict[str, Any]:
    """Find or construct a usable provenance reference candidate."""

    config = PROVENANCE_CONFIG[provenance_type]

    finding_field = str(config["finding_field"])

    artifact_name = str(config["artifact"])

    record_id_field = str(config["record_id_field"])

    #
    # First preference:
    # use a provenance reference that is already
    # present on a current final finding.
    #
    natural_candidates: list[dict[str, Any]] = []

    #
    # Fallback:
    # if no current finding uses this provenance
    # type, pair one real finding with one real
    # same-case provenance record. The mutation
    # workspace will attach that valid reference
    # before breaking it.
    #
    fallback_candidates: list[dict[str, Any]] = []

    for case_dir in all_case_dirs():
        report_path = case_dir / "final_investigation_report.json"

        provenance_path = case_dir / artifact_name

        if not (report_path.exists() and provenance_path.exists()):
            continue

        report = load_json(report_path)

        provenance_records = load_json(provenance_path)

        if not isinstance(
            report,
            dict,
        ):
            continue

        if not isinstance(
            provenance_records,
            list,
        ):
            continue

        record_ids = [
            str(
                record.get(
                    record_id_field,
                    "",
                )
            )
            for record in provenance_records
            if isinstance(
                record,
                dict,
            )
            and record.get(record_id_field)
        ]

        if not record_ids:
            continue

        findings = get_report_findings(report)

        if not findings:
            continue

        available_ids = set(record_ids)

        for finding in findings:
            finding_id = str(
                finding.get(
                    "finding_id",
                    "",
                )
            )

            if not finding_id:
                continue

            references = [
                str(value)
                for value in (
                    finding.get(
                        finding_field,
                        [],
                    )
                    or []
                )
                if value
            ]

            resolved = [value for value in references if value in available_ids]

            if resolved:
                natural_candidates.append(
                    {
                        "case_dir": (case_dir),
                        "case_id": (case_dir.name),
                        "finding_id": (finding_id),
                        "reference_id": (resolved[0]),
                        "reference_count": (len(references)),
                        "finding_count": (len(findings)),
                        "reference_was_preexisting": (True),
                    }
                )

        #
        # Keep one same-case real record as a
        # synthetic-but-valid fallback candidate.
        #
        fallback_candidates.append(
            {
                "case_dir": (case_dir),
                "case_id": (case_dir.name),
                "finding_id": str(
                    findings[0].get(
                        "finding_id",
                        "",
                    )
                ),
                "reference_id": (record_ids[0]),
                "reference_count": 0,
                "finding_count": (len(findings)),
                "reference_was_preexisting": (False),
            }
        )

    if natural_candidates:
        natural_candidates.sort(
            key=lambda item: (
                int(item["reference_count"]),
                int(item["finding_count"]),
                str(item["case_id"]),
            ),
            reverse=True,
        )

        return natural_candidates[0]

    if fallback_candidates:
        fallback_candidates.sort(
            key=lambda item: (
                int(item["finding_count"]),
                str(item["case_id"]),
            ),
            reverse=True,
        )

        return fallback_candidates[0]

    raise RuntimeError(f"No usable provenance candidate found for {provenance_type}.")


def find_cross_case_id(
    *,
    provenance_type: str,
    excluded_case_id: str,
) -> str:
    """Return a valid provenance ID from another case."""

    config = PROVENANCE_CONFIG[provenance_type]

    artifact_name = str(config["artifact"])

    record_id_field = str(config["record_id_field"])

    for case_dir in all_case_dirs():
        if case_dir.name == excluded_case_id:
            continue

        artifact_path = case_dir / artifact_name

        if not artifact_path.exists():
            continue

        payload = load_json(artifact_path)

        if not isinstance(
            payload,
            list,
        ):
            continue

        for record in payload:
            if not isinstance(
                record,
                dict,
            ):
                continue

            value = record.get(record_id_field)

            if value:
                return str(value)

    raise RuntimeError(f"Unable to locate a cross-case {provenance_type} ID.")


def copy_case(
    *,
    source_case: Path,
    mutation_name: str,
) -> Path:
    """Copy one production case into isolated workspace."""

    mutation_root = WORKSPACE_DIR / mutation_name

    mutation_case = mutation_root / source_case.name

    if mutation_root.exists():
        shutil.rmtree(mutation_root)

    mutation_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copytree(
        source_case,
        mutation_case,
    )

    return mutation_case


def find_report_finding(
    *,
    report: dict[str, Any],
    finding_id: str,
) -> dict[str, Any]:
    """Find one persisted report finding."""

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

    raise ValueError(f"Finding {finding_id} not found in final report.")


def ensure_valid_reference(
    *,
    finding: dict[str, Any],
    provenance_type: str,
    reference_id: str,
) -> list[str]:
    """Ensure the mutation finding contains one valid local reference."""

    finding_field = str(PROVENANCE_CONFIG[provenance_type]["finding_field"])

    references = [
        str(value)
        for value in (
            finding.get(
                finding_field,
                [],
            )
            or []
        )
        if value
    ]

    if reference_id not in references:
        references.append(reference_id)

    finding[finding_field] = references

    return references


def issue_categories(
    issues: list[dict[str, Any]],
) -> set[str]:
    """Return detected issue categories."""

    return {
        str(
            issue.get(
                "category",
                "",
            )
        )
        for issue in issues
        if issue.get("category")
    }


def validate_mutation_result(
    *,
    mutation_name: str,
    provenance_type: str,
    mutation_case: Path,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Run validator and score one mutation."""

    expected_category = str(PROVENANCE_CONFIG[provenance_type]["expected_category"])

    try:
        (
            case_result,
            issues,
        ) = validate_one_case(mutation_case)
    except Exception as exc:
        return {
            "mutation": mutation_name,
            "provenance_type": (provenance_type),
            "status": "FAIL",
            "validator_exception": (f"{type(exc).__name__}: {exc}"),
            "expected_category": (expected_category),
            "expected_category_detected": (False),
            "failed_closed": False,
            **metadata,
        }

    categories = issue_categories(issues)

    expected_detected = expected_category in categories

    failed_closed = case_result.get("status") == "FAIL"

    passed = failed_closed and expected_detected

    return {
        "mutation": mutation_name,
        "provenance_type": (provenance_type),
        "expected_category": (expected_category),
        "validator_status": (case_result.get("status")),
        "issue_count": len(issues),
        "detected_categories": (sorted(categories)),
        "expected_category_detected": (expected_detected),
        "failed_closed": (failed_closed),
        "status": ("PASS" if passed else "FAIL"),
        "issues": issues,
        **metadata,
    }


def mutate_replace_with_dangling(
    *,
    provenance_type: str,
    reference: dict[str, Any],
) -> dict[str, Any]:
    """Replace valid reference with nonexistent ID."""

    mutation_name = f"{provenance_type}_replace_with_dangling"

    source_case = reference["case_dir"]

    mutation_case = copy_case(
        source_case=source_case,
        mutation_name=mutation_name,
    )

    report_path = mutation_case / "final_investigation_report.json"

    report = load_json(report_path)

    if not isinstance(
        report,
        dict,
    ):
        raise ValueError("Final report must contain an object.")

    finding = find_report_finding(
        report=report,
        finding_id=str(reference["finding_id"]),
    )

    finding_field = str(PROVENANCE_CONFIG[provenance_type]["finding_field"])

    dangling_id = f"9b3-dangling-{provenance_type}-id"

    finding[finding_field] = [dangling_id]

    write_json(
        report_path,
        report,
    )

    return validate_mutation_result(
        mutation_name=mutation_name,
        provenance_type=provenance_type,
        mutation_case=mutation_case,
        metadata={
            "case_id": (source_case.name),
            "finding_id": (reference["finding_id"]),
            "original_reference_id": (reference["reference_id"]),
            "injected_reference_id": (dangling_id),
            "mutation_mode": ("replace_reference"),
        },
    )


def mutate_append_dangling(
    *,
    provenance_type: str,
    reference: dict[str, Any],
) -> dict[str, Any]:
    """Keep valid refs and append one invalid ref."""

    mutation_name = f"{provenance_type}_mixed_valid_and_dangling"

    source_case = reference["case_dir"]

    mutation_case = copy_case(
        source_case=source_case,
        mutation_name=mutation_name,
    )

    report_path = mutation_case / "final_investigation_report.json"

    report = load_json(report_path)

    if not isinstance(
        report,
        dict,
    ):
        raise ValueError("Final report must contain an object.")

    finding = find_report_finding(
        report=report,
        finding_id=str(reference["finding_id"]),
    )

    finding_field = str(PROVENANCE_CONFIG[provenance_type]["finding_field"])

    references = ensure_valid_reference(
        finding=finding,
        provenance_type=(provenance_type),
        reference_id=str(reference["reference_id"]),
    )

    dangling_id = f"9b3-mixed-dangling-{provenance_type}-id"

    references.append(dangling_id)

    finding[finding_field] = references

    write_json(
        report_path,
        report,
    )

    return validate_mutation_result(
        mutation_name=mutation_name,
        provenance_type=provenance_type,
        mutation_case=mutation_case,
        metadata={
            "case_id": (source_case.name),
            "finding_id": (reference["finding_id"]),
            "valid_reference_preserved": (reference["reference_id"] in references),
            "injected_reference_id": (dangling_id),
            "mutation_mode": ("mixed_valid_invalid"),
        },
    )


def mutate_remove_source_record(
    *,
    provenance_type: str,
    reference: dict[str, Any],
) -> dict[str, Any]:
    """Remove the record referenced by a valid finding."""

    mutation_name = f"{provenance_type}_remove_referenced_record"

    source_case = reference["case_dir"]

    mutation_case = copy_case(
        source_case=source_case,
        mutation_name=mutation_name,
    )

    report_path = mutation_case / "final_investigation_report.json"

    report = load_json(report_path)

    if not isinstance(
        report,
        dict,
    ):
        raise ValueError("Final report must contain an object.")

    finding = find_report_finding(
        report=report,
        finding_id=str(reference["finding_id"]),
    )

    ensure_valid_reference(
        finding=finding,
        provenance_type=(provenance_type),
        reference_id=str(reference["reference_id"]),
    )

    write_json(
        report_path,
        report,
    )

    config = PROVENANCE_CONFIG[provenance_type]

    artifact_path = mutation_case / str(config["artifact"])

    payload = load_json(artifact_path)

    if not isinstance(
        payload,
        list,
    ):
        raise ValueError("Expected provenance artifact to contain a list.")

    id_field = str(config["record_id_field"])

    reference_id = str(reference["reference_id"])

    original_count = len(payload)

    filtered = [
        record
        for record in payload
        if not (
            isinstance(
                record,
                dict,
            )
            and str(
                record.get(
                    id_field,
                    "",
                )
            )
            == reference_id
        )
    ]

    if len(filtered) == original_count:
        raise ValueError("Referenced provenance record was not found.")

    write_json(
        artifact_path,
        filtered,
    )

    return validate_mutation_result(
        mutation_name=mutation_name,
        provenance_type=provenance_type,
        mutation_case=mutation_case,
        metadata={
            "case_id": (source_case.name),
            "finding_id": (reference["finding_id"]),
            "removed_reference_id": (reference_id),
            "original_record_count": (original_count),
            "mutated_record_count": (len(filtered)),
            "mutation_mode": ("remove_source_record"),
        },
    )


def mutate_cross_case_reference(
    *,
    provenance_type: str,
    reference: dict[str, Any],
) -> dict[str, Any]:
    """Replace local provenance ID with valid ID from another case."""

    mutation_name = f"{provenance_type}_cross_case_reference"

    source_case = reference["case_dir"]

    cross_case_id = find_cross_case_id(
        provenance_type=(provenance_type),
        excluded_case_id=(source_case.name),
    )

    mutation_case = copy_case(
        source_case=source_case,
        mutation_name=mutation_name,
    )

    report_path = mutation_case / "final_investigation_report.json"

    report = load_json(report_path)

    if not isinstance(
        report,
        dict,
    ):
        raise ValueError("Final report must contain an object.")

    finding = find_report_finding(
        report=report,
        finding_id=str(reference["finding_id"]),
    )

    finding_field = str(PROVENANCE_CONFIG[provenance_type]["finding_field"])

    finding[finding_field] = [cross_case_id]

    write_json(
        report_path,
        report,
    )

    return validate_mutation_result(
        mutation_name=mutation_name,
        provenance_type=provenance_type,
        mutation_case=mutation_case,
        metadata={
            "case_id": (source_case.name),
            "finding_id": (reference["finding_id"]),
            "original_reference_id": (reference["reference_id"]),
            "cross_case_reference_id": (cross_case_id),
            "mutation_mode": ("cross_case_reference"),
        },
    )


def main() -> int:
    """Run Step 9B.3 provenance robustness tests."""

    load_required_evaluation(
        STEP_9A_PATH,
        "Step 9A",
    )

    load_required_evaluation(
        STEP_9B1_PATH,
        "Step 9B.1",
    )

    load_required_evaluation(
        STEP_9B2_PATH,
        "Step 9B.2",
    )

    references = {
        provenance_type: (find_reference(provenance_type))
        for provenance_type in (
            "evidence",
            "claim",
            "event",
        )
    }

    production_cases_used = {
        str(reference["case_id"]): reference["case_dir"] for reference in (references.values())
    }

    baseline_hashes: dict[
        str,
        dict[str, str],
    ] = {}

    for (
        case_id,
        case_dir,
    ) in production_cases_used.items():
        baseline_hashes[case_id] = {
            path.name: (sha256_file(path)) for path in (case_dir.iterdir()) if path.is_file()
        }

    if WORKSPACE_DIR.exists():
        shutil.rmtree(WORKSPACE_DIR)

    WORKSPACE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[dict[str, Any]] = []

    for provenance_type in (
        "evidence",
        "claim",
        "event",
    ):
        reference = references[provenance_type]

        results.append(
            mutate_replace_with_dangling(
                provenance_type=(provenance_type),
                reference=reference,
            )
        )

        results.append(
            mutate_append_dangling(
                provenance_type=(provenance_type),
                reference=reference,
            )
        )

        results.append(
            mutate_remove_source_record(
                provenance_type=(provenance_type),
                reference=reference,
            )
        )

        results.append(
            mutate_cross_case_reference(
                provenance_type=(provenance_type),
                reference=reference,
            )
        )

    production_cases_unchanged = True

    for (
        case_id,
        case_dir,
    ) in production_cases_used.items():
        current_hashes = {
            path.name: (sha256_file(path)) for path in (case_dir.iterdir()) if path.is_file()
        }

        if current_hashes != baseline_hashes[case_id]:
            production_cases_unchanged = False

    passed = sum(1 for result in results if result.get("status") == "PASS")

    failed = len(results) - passed

    all_failed_closed = all(
        bool(
            result.get(
                "failed_closed",
                False,
            )
        )
        for result in results
    )

    all_expected_detected = all(
        bool(
            result.get(
                "expected_category_detected",
                False,
            )
        )
        for result in results
    )

    category_counts: Counter[str] = Counter()

    for result in results:
        for category in (
            result.get(
                "detected_categories",
                [],
            )
            or []
        ):
            category_counts[str(category)] += 1

    provenance_summary: dict[
        str,
        dict[str, int],
    ] = {}

    for provenance_type in (
        "evidence",
        "claim",
        "event",
    ):
        scoped = [result for result in results if result.get("provenance_type") == provenance_type]

        provenance_summary[provenance_type] = {
            "mutations": len(scoped),
            "passed": sum(1 for result in scoped if result.get("status") == "PASS"),
            "failed": sum(1 for result in scoped if result.get("status") != "PASS"),
        }

    overall_pass = all(
        (
            len(results) == 12,
            passed == 12,
            failed == 0,
            all_failed_closed,
            all_expected_detected,
            production_cases_unchanged,
        )
    )

    status = "PASS" if overall_pass else "FAIL"

    output = {
        "schema_version": "1.0",
        "acceptance_step": "9B.3",
        "acceptance_name": ("Provenance Breakage and Dangling-Reference Detection"),
        "status": status,
        "evaluated_at": (datetime.now(UTC).isoformat()),
        "prerequisites": {
            "9A": "PASS",
            "9B.1": "PASS",
            "9B.2": "PASS",
        },
        "reference_cases": {
            provenance_type: {
                "case_id": (reference["case_id"]),
                "finding_id": (reference["finding_id"]),
                "reference_id": (reference["reference_id"]),
                "reference_was_preexisting": (reference["reference_was_preexisting"]),
            }
            for (
                provenance_type,
                reference,
            ) in references.items()
        },
        "mutation_summary": {
            "mutations": len(results),
            "passed": passed,
            "failed": failed,
            "all_failed_closed": (all_failed_closed),
            "all_expected_categories_detected": (all_expected_detected),
            "production_cases_unchanged": (production_cases_unchanged),
            "detected_issue_categories": dict(sorted(category_counts.items())),
        },
        "provenance_summary": (provenance_summary),
        "acceptance_criteria": {
            "dangling_evidence_detected": (provenance_summary["evidence"]["failed"] == 0),
            "dangling_claims_detected": (provenance_summary["claim"]["failed"] == 0),
            "dangling_events_detected": (provenance_summary["event"]["failed"] == 0),
            "mixed_valid_invalid_rejected": all(
                result.get("status") == "PASS"
                for result in results
                if result.get("mutation_mode") == "mixed_valid_invalid"
            ),
            "removed_source_records_detected": all(
                result.get("status") == "PASS"
                for result in results
                if result.get("mutation_mode") == "remove_source_record"
            ),
            "cross_case_references_rejected": all(
                result.get("status") == "PASS"
                for result in results
                if result.get("mutation_mode") == "cross_case_reference"
            ),
            "production_artifacts_immutable": (production_cases_unchanged),
        },
        "mutation_results": (results),
        "ready_for_9b4": (overall_pass),
        "methodological_notes": [
            ("All provenance mutations are performed on isolated workspace copies."),
            ("A provenance ID is valid only when it resolves inside the same investigation case."),
            (
                "Cross-case IDs are intentionally "
                "valid IDs from another production "
                "case and therefore must still be "
                "rejected locally."
            ),
            (
                "Mixed-reference mutations preserve "
                "at least one valid provenance "
                "reference while adding a dangling "
                "reference, verifying that one valid "
                "reference does not mask corruption."
            ),
            (
                "Duplicate and empty-string "
                "provenance-ID validation is not "
                "part of this substep because the "
                "current 9A acceptance boundary does "
                "not yet define dedicated rejection "
                "semantics for those conditions."
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
    print("STEP 9B.3 — PROVENANCE BREAKAGE / DANGLING-REFERENCE DETECTION")
    print("=" * 72)

    print(f"Overall status:                   {status}")

    print()
    print("Prerequisites")
    print("-" * 72)

    print("Step 9A status:                   PASS")

    print("Step 9B.1 status:                 PASS")

    print("Step 9B.2 status:                 PASS")

    print()
    print("Mutation results")
    print("-" * 72)

    print(f"Mutations executed:               {len(results)}")

    print(f"Mutations passed:                 {passed}")

    print(f"Mutations failed:                 {failed}")

    print(f"All failed closed:                {all_failed_closed}")

    print(f"Expected categories detected:    {all_expected_detected}")

    print()
    print("By provenance type")
    print("-" * 72)

    for provenance_type in (
        "evidence",
        "claim",
        "event",
    ):
        summary = provenance_summary[provenance_type]

        print(
            f"{provenance_type.capitalize():<12}"
            f"passed / total: "
            f"{summary['passed']} / "
            f"{summary['mutations']}"
        )

    print()
    print("Safety")
    print("-" * 72)

    print(f"Production cases unchanged:       {production_cases_unchanged}")

    print()
    print(f"Ready for Step 9B.4:              {overall_pass}")

    print()
    print("Saved Step-9B.3 result to:")

    print(OUTPUT_PATH)

    if WORKSPACE_DIR.exists():
        shutil.rmtree(WORKSPACE_DIR)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

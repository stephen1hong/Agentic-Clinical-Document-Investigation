from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

EVALUATION_ROOT = PROJECT_ROOT / "data" / "evaluation"

TIMELINE_DIR = EVALUATION_ROOT / "timeline"

OUTPUT_DIR = EVALUATION_ROOT / "step_8d_final"

OUTPUT_PATH = OUTPUT_DIR / "step_8d_final_summary.json"


SOURCE_ARTIFACTS = {
    "8D.1": (TIMELINE_DIR / "timeline_integrity.json"),
    "8D.2": (TIMELINE_DIR / "timestamp_normalization_correctness.json"),
    "8D.3": (TIMELINE_DIR / "timeline_ordering_consistency.json"),
    "8D.4": (TIMELINE_DIR / "missing_event_time_verification.json"),
    "8D.5": (TIMELINE_DIR / "timeline_finding_coverage_audit.json"),
    "8D.5b": (TIMELINE_DIR / "timeline_suppression_rule_validation.json"),
    "8D.6": (TIMELINE_DIR / "timeline_conflict_detection_quality.json"),
}


EXPECTED_REPORTS = 20
EXPECTED_TIMELINE_EVENTS = 5891
EXPECTED_TIMED_EVENTS = 5309
EXPECTED_UNTIMED_EVENTS = 582

EXPECTED_MISSING_TIME_FINDINGS = 316

EXPECTED_COVERED_UNTIMED = 316
EXPECTED_SUPPRESSED_UNTIMED = 266

EXPECTED_SUPPRESSED_MEDICATION_STATUS = 182
EXPECTED_SUPPRESSED_NARRATIVE_EVENT = 84


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object."""

    raw = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(raw, dict):
        raise ValueError(f"Expected JSON object: {path}")

    return raw


def sha256_file(path: Path) -> str:
    """Calculate SHA-256 for an artifact."""

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def relative_path(path: Path) -> str:
    """Return project-relative path."""

    return str(path.relative_to(PROJECT_ROOT))


def require_equal(
    *,
    label: str,
    actual: Any,
    expected: Any,
) -> None:
    """Raise if an expected frozen value differs."""

    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def require_zero(
    *,
    label: str,
    actual: Any,
) -> None:
    """Require an integer-like zero value."""

    require_equal(
        label=label,
        actual=actual,
        expected=0,
    )


def require_percentage(
    *,
    label: str,
    actual: Any,
    expected: float,
    tolerance: float = 1e-6,
) -> None:
    """Validate percentage-like numeric values."""

    if not isinstance(
        actual,
        int | float,
    ):
        raise ValueError(f"{label}: expected numeric value, got {actual!r}")

    if abs(float(actual) - expected) > tolerance:
        raise ValueError(f"{label}: expected {expected}, got {actual}")


def validate_required_artifacts() -> None:
    """Require all source artifacts before freezing."""

    missing = [path for path in SOURCE_ARTIFACTS.values() if not path.exists()]

    if not missing:
        return

    lines = ["Step 8D cannot be frozen because required artifacts are missing:"]

    lines.extend(f"  - {relative_path(path)}" for path in missing)

    raise FileNotFoundError("\n".join(lines))


def validate_8d1(
    data: dict[str, Any],
) -> None:
    """Validate Step 8D.1."""

    require_equal(
        label="8D.1 reports_scanned",
        actual=data.get("reports_scanned"),
        expected=EXPECTED_REPORTS,
    )

    require_equal(
        label="8D.1 total_timeline_events",
        actual=data.get("total_timeline_events"),
        expected=EXPECTED_TIMELINE_EVENTS,
    )

    timeline_summary = data.get(
        "timeline_summary",
        {},
    )

    require_equal(
        label=("8D.1 events_with_normalized_time"),
        actual=timeline_summary.get("events_with_normalized_time"),
        expected=EXPECTED_TIMED_EVENTS,
    )

    require_equal(
        label=("8D.1 events_without_normalized_time"),
        actual=timeline_summary.get("events_without_normalized_time"),
        expected=EXPECTED_UNTIMED_EVENTS,
    )

    provenance = data.get(
        "provenance_integrity",
        {},
    )

    require_zero(
        label="8D.1 duplicate_event_ids",
        actual=provenance.get("duplicate_event_ids"),
    )

    require_zero(
        label="8D.1 case_id_mismatches",
        actual=provenance.get("case_id_mismatches"),
    )

    require_zero(
        label=("8D.1 unresolved evidence references"),
        actual=provenance.get("unresolved_evidence_references"),
    )

    require_zero(
        label=("8D.1 unresolved claim references"),
        actual=provenance.get("unresolved_claim_references"),
    )

    temporal = data.get(
        "temporal_integrity",
        {},
    )

    require_zero(
        label="8D.1 invalid_timestamps",
        actual=temporal.get("invalid_timestamps"),
    )

    require_zero(
        label="8D.1 invalid_intervals",
        actual=temporal.get("invalid_intervals"),
    )

    missing_time = data.get(
        "missing_event_time_validation",
        {},
    )

    require_equal(
        label=("8D.1 missing-time findings evaluated"),
        actual=missing_time.get("findings_evaluated"),
        expected=EXPECTED_MISSING_TIME_FINDINGS,
    )

    require_equal(
        label=("8D.1 valid missing-time findings"),
        actual=missing_time.get("valid_findings"),
        expected=EXPECTED_MISSING_TIME_FINDINGS,
    )

    require_zero(
        label=("8D.1 unresolved missing-time event refs"),
        actual=missing_time.get("unresolved_event_references"),
    )

    require_zero(
        label=("8D.1 findings pointing to timed events"),
        actual=missing_time.get("findings_pointing_to_timed_events"),
    )

    require_zero(
        label="8D.1 integrity_issue_count",
        actual=data.get("integrity_issue_count"),
    )


def validate_8d2(
    data: dict[str, Any],
) -> None:
    """Validate Step 8D.2."""

    require_equal(
        label="8D.2 status",
        actual=data.get("status"),
        expected="PASS",
    )

    require_equal(
        label="8D.2 reports_scanned",
        actual=data.get("reports_scanned"),
        expected=EXPECTED_REPORTS,
    )

    require_equal(
        label="8D.2 persisted_events",
        actual=data.get("persisted_events"),
        expected=EXPECTED_TIMELINE_EVENTS,
    )

    require_equal(
        label="8D.2 rebuilt_events",
        actual=data.get("rebuilt_events"),
        expected=EXPECTED_TIMELINE_EVENTS,
    )

    require_equal(
        label="8D.2 matched_events",
        actual=data.get("matched_events"),
        expected=EXPECTED_TIMELINE_EVENTS,
    )

    reproducibility = data.get(
        "timeline_event_reproducibility",
        {},
    )

    require_zero(
        label="8D.2 missing_after_rebuild",
        actual=reproducibility.get("missing_after_rebuild"),
    )

    require_zero(
        label="8D.2 unexpected_after_rebuild",
        actual=reproducibility.get("unexpected_after_rebuild"),
    )

    temporal = data.get(
        "temporal_field_validation",
        {},
    )

    for field in (
        "wrong_normalized_time",
        "wrong_time_end",
        "wrong_time_precision",
        "wrong_time_source",
    ):
        require_zero(
            label=f"8D.2 {field}",
            actual=temporal.get(field),
        )

    provenance = data.get(
        "provenance_comparison",
        {},
    )

    require_zero(
        label="8D.2 provenance mismatches",
        actual=provenance.get("mismatches"),
    )

    require_zero(
        label="8D.2 total_issue_count",
        actual=data.get("total_issue_count"),
    )


def validate_8d3(
    data: dict[str, Any],
) -> None:
    """Validate Step 8D.3."""

    require_equal(
        label="8D.3 status",
        actual=data.get("status"),
        expected="PASS",
    )

    require_equal(
        label="8D.3 reports_scanned",
        actual=data.get("reports_scanned"),
        expected=EXPECTED_REPORTS,
    )

    require_equal(
        label="8D.3 total_events",
        actual=data.get("total_events"),
        expected=EXPECTED_TIMELINE_EVENTS,
    )

    population = data.get(
        "timeline_population",
        {},
    )

    require_equal(
        label="8D.3 timed_events",
        actual=population.get("timed_events"),
        expected=EXPECTED_TIMED_EVENTS,
    )

    require_equal(
        label="8D.3 unknown_time_events",
        actual=population.get("unknown_time_events"),
        expected=EXPECTED_UNTIMED_EVENTS,
    )

    ordering = data.get(
        "ordering_validation",
        {},
    )

    require_zero(
        label=("8D.3 persisted_order_regressions"),
        actual=ordering.get("persisted_order_regressions"),
    )

    require_zero(
        label=("8D.3 timed_projection_regressions"),
        actual=ordering.get("timed_projection_regressions"),
    )

    require_zero(
        label=("8D.3 cases_with_ordering_issues"),
        actual=ordering.get("cases_with_ordering_issues"),
    )

    intervals = data.get(
        "interval_validation",
        {},
    )

    require_zero(
        label="8D.3 invalid_intervals",
        actual=intervals.get("invalid_intervals"),
    )

    timestamp = data.get(
        "timestamp_validation",
        {},
    )

    require_zero(
        label="8D.3 invalid timestamps",
        actual=timestamp.get("invalid_timestamp_values"),
    )

    require_zero(
        label="8D.3 total_issue_count",
        actual=data.get("total_issue_count"),
    )


def validate_8d4(
    data: dict[str, Any],
) -> None:
    """Validate Step 8D.4."""

    require_equal(
        label="8D.4 status",
        actual=data.get("status"),
        expected="PASS",
    )

    require_equal(
        label="8D.4 reports_scanned",
        actual=data.get("reports_scanned"),
        expected=EXPECTED_REPORTS,
    )

    require_equal(
        label="8D.4 timeline_events_scanned",
        actual=data.get("timeline_events_scanned"),
        expected=EXPECTED_TIMELINE_EVENTS,
    )

    require_equal(
        label="8D.4 untimed_timeline_events",
        actual=data.get("untimed_timeline_events"),
        expected=EXPECTED_UNTIMED_EVENTS,
    )

    require_equal(
        label="8D.4 findings_evaluated",
        actual=data.get("findings_evaluated"),
        expected=EXPECTED_MISSING_TIME_FINDINGS,
    )

    summary = data.get(
        "verification_summary",
        {},
    )

    require_equal(
        label="8D.4 verified_missing",
        actual=summary.get("verified_missing"),
        expected=EXPECTED_MISSING_TIME_FINDINGS,
    )

    require_zero(
        label=("8D.4 contradicted_by_source_time"),
        actual=summary.get("contradicted_by_source_time"),
    )

    require_zero(
        label="8D.4 manual_review",
        actual=summary.get("manual_review"),
    )

    require_zero(
        label=("8D.4 unresolved_event_references"),
        actual=summary.get("unresolved_event_references"),
    )

    require_zero(
        label=("8D.4 unresolved_evidence_references"),
        actual=summary.get("unresolved_evidence_references"),
    )


def validate_8d5(
    data: dict[str, Any],
) -> None:
    """Validate Step 8D.5."""

    require_equal(
        label="8D.5 status",
        actual=data.get("status"),
        expected=("PASS_WITH_DOCUMENTED_SUPPRESSION"),
    )

    require_equal(
        label="8D.5 reports_scanned",
        actual=data.get("reports_scanned"),
        expected=EXPECTED_REPORTS,
    )

    require_equal(
        label="8D.5 total_timeline_events",
        actual=data.get("total_timeline_events"),
        expected=EXPECTED_TIMELINE_EVENTS,
    )

    require_equal(
        label="8D.5 untimed_events",
        actual=data.get("untimed_events"),
        expected=EXPECTED_UNTIMED_EVENTS,
    )

    require_equal(
        label="8D.5 missing_event_time_findings",
        actual=data.get("missing_event_time_findings"),
        expected=EXPECTED_MISSING_TIME_FINDINGS,
    )

    coverage = data.get(
        "coverage",
        {},
    )

    require_equal(
        label="8D.5 covered_untimed_events",
        actual=coverage.get("covered_untimed_events"),
        expected=EXPECTED_COVERED_UNTIMED,
    )

    require_equal(
        label="8D.5 suppressed_untimed_events",
        actual=coverage.get("suppressed_untimed_events"),
        expected=EXPECTED_SUPPRESSED_UNTIMED,
    )

    mapping = data.get(
        "mapping_integrity",
        {},
    )

    require_zero(
        label=("8D.5 findings_without_event_ids"),
        actual=mapping.get("findings_without_event_ids"),
    )

    require_zero(
        label=("8D.5 unresolved_event_references"),
        actual=mapping.get("unresolved_event_references"),
    )

    require_zero(
        label=("8D.5 timed_events_referenced"),
        actual=mapping.get("timed_events_referenced_by_missing_findings"),
    )

    require_zero(
        label=("8D.5 duplicate_finding_event_pairs"),
        actual=mapping.get("duplicate_finding_event_pairs"),
    )

    require_zero(
        label="8D.5 mapping_issue_count",
        actual=mapping.get("mapping_issue_count"),
    )

    suppressed = data.get(
        "suppressed_population",
        {},
    )

    by_type = suppressed.get(
        "by_event_type",
        {},
    )

    require_equal(
        label=("8D.5 suppressed medication_status"),
        actual=by_type.get("medication_status"),
        expected=(EXPECTED_SUPPRESSED_MEDICATION_STATUS),
    )

    require_equal(
        label=("8D.5 suppressed narrative_event"),
        actual=by_type.get("narrative_event"),
        expected=(EXPECTED_SUPPRESSED_NARRATIVE_EVENT),
    )


def validate_8d5b(
    data: dict[str, Any],
) -> None:
    """Validate Step 8D.5b."""

    require_equal(
        label="8D.5b status",
        actual=data.get("status"),
        expected="PASS",
    )

    require_equal(
        label="8D.5b reports_scanned",
        actual=data.get("reports_scanned"),
        expected=EXPECTED_REPORTS,
    )

    require_equal(
        label="8D.5b timeline_events",
        actual=data.get("timeline_events"),
        expected=EXPECTED_TIMELINE_EVENTS,
    )

    require_equal(
        label="8D.5b untimed_events",
        actual=data.get("untimed_events"),
        expected=EXPECTED_UNTIMED_EVENTS,
    )

    eligibility = data.get(
        "eligibility",
        {},
    )

    require_equal(
        label="8D.5b expected_eligible",
        actual=eligibility.get("expected_eligible"),
        expected=EXPECTED_COVERED_UNTIMED,
    )

    require_equal(
        label="8D.5b expected_suppressed",
        actual=eligibility.get("expected_suppressed"),
        expected=EXPECTED_SUPPRESSED_UNTIMED,
    )

    require_equal(
        label="8D.5b actual_covered",
        actual=eligibility.get("actual_covered"),
        expected=EXPECTED_COVERED_UNTIMED,
    )

    require_percentage(
        label=("8D.5b eligible coverage"),
        actual=eligibility.get("eligible_coverage_percentage"),
        expected=100.0,
    )

    require_percentage(
        label=("8D.5b suppression accuracy"),
        actual=eligibility.get("suppression_accuracy_percentage"),
        expected=100.0,
    )

    validation = data.get(
        "validation",
        {},
    )

    require_zero(
        label=("8D.5b eligible events missed"),
        actual=validation.get("eligible_events_without_findings"),
    )

    require_zero(
        label=("8D.5b suppressed events with findings"),
        actual=validation.get("suppressed_events_with_findings"),
    )

    require_zero(
        label="8D.5b unexpected findings",
        actual=validation.get("unexpected_findings"),
    )

    require_zero(
        label="8D.5b rule violations",
        actual=validation.get("rule_violation_count"),
    )


def validate_8d6(
    data: dict[str, Any],
) -> None:
    """Validate Step 8D.6."""

    require_equal(
        label="8D.6 status",
        actual=data.get("status"),
        expected="PASS",
    )

    require_equal(
        label="8D.6 reports_scanned",
        actual=data.get("reports_scanned"),
        expected=EXPECTED_REPORTS,
    )

    require_equal(
        label="8D.6 timeline_events",
        actual=data.get("timeline_events"),
        expected=EXPECTED_TIMELINE_EVENTS,
    )

    require_equal(
        label="8D.6 emitted_conflicts",
        actual=data.get("emitted_conflicts"),
        expected=EXPECTED_MISSING_TIME_FINDINGS,
    )

    metrics = data.get(
        "overall_metrics",
        {},
    )

    require_equal(
        label="8D.6 true positives",
        actual=metrics.get("true_positives"),
        expected=EXPECTED_MISSING_TIME_FINDINGS,
    )

    require_zero(
        label="8D.6 false positives",
        actual=metrics.get("false_positives"),
    )

    require_zero(
        label="8D.6 false negatives",
        actual=metrics.get("false_negatives"),
    )

    require_percentage(
        label="8D.6 precision",
        actual=metrics.get("precision_percentage"),
        expected=100.0,
    )

    require_percentage(
        label="8D.6 recall",
        actual=metrics.get("recall_percentage"),
        expected=100.0,
    )

    require_percentage(
        label="8D.6 F1",
        actual=metrics.get("f1_percentage"),
        expected=100.0,
    )

    by_type = data.get(
        "by_conflict_type",
        {},
    )

    missing_time = by_type.get(
        "missing_event_time",
        {},
    )

    require_equal(
        label="8D.6 missing-time emitted",
        actual=missing_time.get("emitted"),
        expected=EXPECTED_MISSING_TIME_FINDINGS,
    )

    require_equal(
        label="8D.6 missing-time expected",
        actual=missing_time.get("expected"),
        expected=EXPECTED_MISSING_TIME_FINDINGS,
    )

    require_zero(
        label="8D.6 missing-time FP",
        actual=missing_time.get("false_positives"),
    )

    require_zero(
        label="8D.6 missing-time FN",
        actual=missing_time.get("false_negatives"),
    )

    medication = by_type.get(
        "medication_stop_before_start",
        {},
    )

    require_zero(
        label=("8D.6 medication stop-before-start emitted"),
        actual=medication.get("emitted"),
    )

    require_zero(
        label=("8D.6 medication stop-before-start expected"),
        actual=medication.get("expected"),
    )

    outside = by_type.get(
        "event_outside_encounter",
        {},
    )

    require_zero(
        label=("8D.6 outside-encounter emitted"),
        actual=outside.get("emitted"),
    )

    require_zero(
        label=("8D.6 outside-encounter expected"),
        actual=outside.get("expected"),
    )

    integrity = data.get(
        "integrity",
        {},
    )

    require_zero(
        label=("8D.6 unresolved event references"),
        actual=integrity.get("unresolved_event_references"),
    )

    require_zero(
        label="8D.6 duplicate conflict IDs",
        actual=integrity.get("duplicate_conflict_ids"),
    )


def artifact_manifest() -> list[dict[str, Any]]:
    """Create frozen artifact provenance."""

    result: list[dict[str, Any]] = []

    for step, path in SOURCE_ARTIFACTS.items():
        result.append(
            {
                "step": step,
                "path": (relative_path(path)),
                "size_bytes": (path.stat().st_size),
                "sha256": (sha256_file(path)),
            }
        )

    return result


def main() -> int:
    """Freeze the final Step 8D evaluation."""

    validate_required_artifacts()

    data_8d1 = load_json(SOURCE_ARTIFACTS["8D.1"])

    data_8d2 = load_json(SOURCE_ARTIFACTS["8D.2"])

    data_8d3 = load_json(SOURCE_ARTIFACTS["8D.3"])

    data_8d4 = load_json(SOURCE_ARTIFACTS["8D.4"])

    data_8d5 = load_json(SOURCE_ARTIFACTS["8D.5"])

    data_8d5b = load_json(SOURCE_ARTIFACTS["8D.5b"])

    data_8d6 = load_json(SOURCE_ARTIFACTS["8D.6"])

    validate_8d1(data_8d1)

    validate_8d2(data_8d2)

    validate_8d3(data_8d3)

    validate_8d4(data_8d4)

    validate_8d5(data_8d5)

    validate_8d5b(data_8d5b)

    validate_8d6(data_8d6)

    artifacts = artifact_manifest()

    coverage_rate = EXPECTED_COVERED_UNTIMED / EXPECTED_UNTIMED_EVENTS

    suppression_rate = EXPECTED_SUPPRESSED_UNTIMED / EXPECTED_UNTIMED_EVENTS

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8D.7",
        "evaluation_name": ("Final Timeline Evaluation"),
        "overall_status": "PASS",
        "population": {
            "reports": (EXPECTED_REPORTS),
            "timeline_events": (EXPECTED_TIMELINE_EVENTS),
            "timed_events": (EXPECTED_TIMED_EVENTS),
            "untimed_events": (EXPECTED_UNTIMED_EVENTS),
            "timestamp_coverage_percentage": (
                EXPECTED_TIMED_EVENTS / EXPECTED_TIMELINE_EVENTS * 100.0
            ),
        },
        "missing_event_time_findings": {
            "findings": (EXPECTED_MISSING_TIME_FINDINGS),
            "semantically_verified": (EXPECTED_MISSING_TIME_FINDINGS),
            "contradicted_by_source_time": 0,
            "manual_review": 0,
            "semantic_verification_percentage": (100.0),
        },
        "untimed_event_coverage": {
            "eligible_and_covered": (EXPECTED_COVERED_UNTIMED),
            "intentionally_suppressed": (EXPECTED_SUPPRESSED_UNTIMED),
            "coverage_percentage": (coverage_rate * 100.0),
            "suppression_percentage": (suppression_rate * 100.0),
            "suppressed_by_event_type": {
                "medication_status": (EXPECTED_SUPPRESSED_MEDICATION_STATUS),
                "narrative_event": (EXPECTED_SUPPRESSED_NARRATIVE_EVENT),
            },
            "production_policy_validation": {
                "eligible_event_coverage_percentage": (100.0),
                "suppression_accuracy_percentage": (100.0),
                "rule_violations": 0,
            },
        },
        "conflict_detection": {
            "emitted_conflicts": (EXPECTED_MISSING_TIME_FINDINGS),
            "true_positives": (EXPECTED_MISSING_TIME_FINDINGS),
            "false_positives": 0,
            "false_negatives": 0,
            "precision_percentage": (100.0),
            "recall_percentage": (100.0),
            "f1_percentage": (100.0),
            "by_type": {
                "missing_event_time": {
                    "emitted": 316,
                    "expected": 316,
                    "true_positives": 316,
                    "false_positives": 0,
                    "false_negatives": 0,
                },
                "medication_stop_before_start": {
                    "emitted": 0,
                    "expected": 0,
                    "true_positives": 0,
                    "false_positives": 0,
                    "false_negatives": 0,
                },
                "event_outside_encounter": {
                    "emitted": 0,
                    "expected": 0,
                    "true_positives": 0,
                    "false_positives": 0,
                    "false_negatives": 0,
                },
            },
        },
        "integrity": {
            "duplicate_event_ids": 0,
            "case_id_mismatches": 0,
            "unresolved_evidence_references": 0,
            "unresolved_claim_references": 0,
            "invalid_timestamps": 0,
            "invalid_intervals": 0,
            "ordering_regressions": 0,
            "unresolved_conflict_event_references": 0,
            "duplicate_conflict_ids": 0,
        },
        "step_results": {
            "8D.1": {
                "status": "PASS",
                "description": ("Timeline structural and provenance integrity."),
                "timeline_events": 5891,
                "integrity_issues": 0,
            },
            "8D.2": {
                "status": "PASS",
                "description": (
                    "Production-semantic timeline "
                    "reconstruction reproducibility "
                    "and timestamp normalization."
                ),
                "persisted_events": 5891,
                "rebuilt_events": 5891,
                "temporal_mismatches": 0,
            },
            "8D.3": {
                "status": "PASS",
                "description": ("Chronological ordering and interval consistency."),
                "ordering_regressions": 0,
                "invalid_intervals": 0,
            },
            "8D.4": {
                "status": "PASS",
                "description": ("Independent semantic challenge of missing_event_time findings."),
                "findings_evaluated": 316,
                "verified_missing": 316,
                "contradicted": 0,
                "manual_review": 0,
            },
            "8D.5": {
                "status": ("PASS_WITH_DOCUMENTED_SUPPRESSION"),
                "description": ("Untimed-event finding coverage and suppression audit."),
                "covered": 316,
                "suppressed": 266,
            },
            "8D.5b": {
                "status": "PASS",
                "description": ("Production suppression-rule validation."),
                "eligible_coverage_percentage": (100.0),
                "suppression_accuracy_percentage": (100.0),
                "rule_violations": 0,
            },
            "8D.6": {
                "status": "PASS",
                "description": ("Timeline conflict detection quality."),
                "precision_percentage": 100.0,
                "recall_percentage": 100.0,
                "f1_percentage": 100.0,
            },
            "8D.7": {
                "status": "PASS",
                "description": (
                    "Final timeline evaluation "
                    "frozen after validation of all "
                    "required source artifacts."
                ),
            },
        },
        "methodological_notes": [
            (
                "Step 8D.2 demonstrates deterministic "
                "reproducibility under the current "
                "production timestamp-resolution "
                "semantics. It is not, by itself, an "
                "independent semantic validation of "
                "clinical dates."
            ),
            (
                "Step 8D.4 independently challenged "
                "all 316 emitted missing_event_time "
                "findings against source evidence. "
                "All 316 were verified and none were "
                "contradicted by recoverable source "
                "timestamps."
            ),
            (
                "The 266 untimed events without "
                "missing_event_time findings are "
                "intentional production-policy "
                "suppressions rather than unmapped "
                "events. They consist of 182 "
                "medication_status events and 84 "
                "narrative_event events."
            ),
            (
                "Step 8D.6 initially appeared to "
                "identify 517 medication-related "
                "false negatives because the first "
                "evaluation implementation compared "
                "medication starts and stops across "
                "different medication episodes. "
                "The evaluator was corrected to use "
                "the production episode semantics: "
                "matching medication subject plus "
                "shared claim or evidence provenance."
            ),
            (
                "After correction, Step 8D.6 observed "
                "316 true positives, zero false "
                "positives, and zero false negatives "
                "for the evaluated timeline conflict "
                "types."
            ),
            (
                "Observed 100% conflict precision and "
                "recall apply to the evaluated "
                "20-case dataset and deterministic "
                "conflict types. They should not be "
                "interpreted as proof of universal "
                "clinical timeline accuracy."
            ),
        ],
        "frozen_source_artifacts": (artifacts),
        "frozen_source_artifact_count": (len(artifacts)),
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
    print("STEP 8D.7 FINAL TIMELINE EVALUATION SUMMARY")
    print("=" * 72)

    print("Overall status:                 PASS")

    print(f"Final reports:                  {EXPECTED_REPORTS}")

    print(f"Timeline events:                {EXPECTED_TIMELINE_EVENTS}")

    print(f"Timed events:                   {EXPECTED_TIMED_EVENTS}")

    print(f"Untimed events:                 {EXPECTED_UNTIMED_EVENTS}")

    print()
    print("Missing-event-time validation")
    print("-" * 72)

    print(f"Findings evaluated:             {EXPECTED_MISSING_TIME_FINDINGS}")

    print(f"Verified missing:               {EXPECTED_MISSING_TIME_FINDINGS}")

    print("Contradicted by source time:    0")

    print("Manual review:                  0")

    print()
    print("Untimed-event policy")
    print("-" * 72)

    print(f"Eligible / covered:             {EXPECTED_COVERED_UNTIMED}")

    print(f"Intentionally suppressed:       {EXPECTED_SUPPRESSED_UNTIMED}")

    print(f"  medication_status:            {EXPECTED_SUPPRESSED_MEDICATION_STATUS}")

    print(f"  narrative_event:              {EXPECTED_SUPPRESSED_NARRATIVE_EVENT}")

    print("Suppression-rule violations:    0")

    print()
    print("Timeline conflict detection")
    print("-" * 72)

    print(f"True positives:                 {EXPECTED_MISSING_TIME_FINDINGS}")

    print("False positives:                0")

    print("False negatives:                0")

    print("Precision:                      100.0%")

    print("Recall:                         100.0%")

    print("F1:                             100.0%")

    print()
    print(f"Frozen source artifacts:        {len(artifacts)}")

    print()
    print("Saved frozen summary to:")

    print(OUTPUT_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

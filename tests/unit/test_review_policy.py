from clinical_investigation.agents.models import (
    FindingSeverity,
    FindingType,
)
from clinical_investigation.agents.review_policy import (
    should_require_human_review,
)


def test_missing_event_time_does_not_require_review() -> None:
    assert not should_require_human_review(
        finding_type=FindingType.TEMPORAL_UNCERTAINTY,
        subtype="missing_event_time",
        severity=FindingSeverity.INFO,
        upstream_requires_review=True,
    )


def test_discharge_only_medication_does_not_require_review() -> None:
    assert not should_require_human_review(
        finding_type=FindingType.MEDICATION_DISCREPANCY,
        subtype="discharge_only_medication",
        severity=FindingSeverity.LOW,
        upstream_requires_review=True,
    )


def test_ambiguous_status_does_not_require_review() -> None:
    assert not should_require_human_review(
        finding_type=FindingType.MEDICATION_DISCREPANCY,
        subtype="ambiguous_status",
        severity=FindingSeverity.INFO,
        upstream_requires_review=True,
    )


def test_insufficient_evidence_support_requires_review() -> None:
    assert should_require_human_review(
        finding_type=FindingType.UNSUPPORTED_CLAIM,
        subtype="insufficient_evidence_support",
        severity=FindingSeverity.MEDIUM,
        upstream_requires_review=True,
    )


def test_dose_conflict_requires_review() -> None:
    assert should_require_human_review(
        finding_type=FindingType.MEDICATION_DISCREPANCY,
        subtype="dose_conflict",
        severity=FindingSeverity.HIGH,
        upstream_requires_review=True,
    )


def test_unknown_high_severity_finding_requires_review() -> None:
    assert should_require_human_review(
        finding_type=FindingType.OTHER,
        subtype="unexpected_high_risk_issue",
        severity=FindingSeverity.HIGH,
        upstream_requires_review=False,
    )

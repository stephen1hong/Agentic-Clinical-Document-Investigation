from __future__ import annotations

import json

import pytest

from clinical_investigation.agents.models import (
    InvestigationFinding,
)
from clinical_investigation.agents.workflow import (
    investigation_graph,
)
from clinical_investigation.config import settings

REQUIRED_FINAL_STATE_KEYS = {
    "case_id",
    "evidence_items",
    "clinical_claims",
    "canonical_timeline",
    "timeline_conflicts",
    "medication_profiles",
    "medication_discrepancies",
    "timeline_findings",
    "medication_findings",
    "contradiction_findings",
    "follow_up_findings",
    "unsupported_claim_findings",
    "investigation_findings",
    "validation_errors",
    "requires_human_review",
    "review_status",
    "review_reasons",
    "final_report",
}


def get_real_case_ids(
    *,
    limit: int = 5,
) -> list[str]:
    """Return real investigation case IDs for integration testing."""

    case_root = settings.investigation_cases_dir

    if not case_root.exists():
        return []

    case_ids = sorted(path.name for path in case_root.iterdir() if path.is_dir())

    return case_ids[:limit]


def assert_final_state_shape(
    result: dict,
) -> None:
    """Verify that the completed graph exposes required state."""

    missing_keys = REQUIRED_FINAL_STATE_KEYS - result.keys()

    assert not missing_keys, f"Final graph state is missing keys: {sorted(missing_keys)}"


def assert_finding_types(
    result: dict,
) -> None:
    """Verify synthesized findings use the canonical model."""

    findings = result["investigation_findings"]

    assert all(
        isinstance(
            finding,
            InvestigationFinding,
        )
        for finding in findings
    )


def assert_finding_case_ids(
    result: dict,
) -> None:
    """Verify findings belong to the workflow case."""

    case_id = result["case_id"]

    for finding in result["investigation_findings"]:
        assert finding.case_id == case_id


def assert_review_routing(
    result: dict,
) -> None:
    """Verify final review status matches routing inputs."""

    validation_errors = result["validation_errors"]

    requires_review = result["requires_human_review"]

    review_status = result["review_status"]

    review_reasons = result["review_reasons"]

    assert review_status in {
        "not_required",
        "pending",
    }

    if validation_errors:
        assert requires_review is True
        assert review_status == "pending"
        assert review_reasons

    if requires_review:
        assert review_status == "pending"

    if review_status == "not_required":
        assert validation_errors == []
        assert requires_review is False
        assert review_reasons == []


def assert_finding_counts_are_consistent(
    result: dict,
) -> None:
    """Verify synthesis includes every detector output."""

    expected_count = sum(
        [
            len(result["timeline_findings"]),
            len(result["medication_findings"]),
            len(result["contradiction_findings"]),
            len(result["follow_up_findings"]),
            len(result["unsupported_claim_findings"]),
        ]
    )

    actual_count = len(result["investigation_findings"])

    assert actual_count == expected_count


def assert_final_report_consistency(
    result: dict,
) -> None:
    """Verify final report is consistent with workflow state."""

    report = result["final_report"]

    assert report

    assert report["case_id"] == result["case_id"]

    assert report["finding_count"] == len(result["investigation_findings"])

    assert report["review_status"] == result["review_status"]

    expected_review_count = sum(
        1 for finding in result["investigation_findings"] if finding.requires_human_review
    )

    assert report["review_finding_count"] == expected_review_count

    assert len(report["high_priority_findings"]) + len(report["other_findings"]) == len(
        result["investigation_findings"]
    )


def assert_persisted_final_report(
    result: dict,
) -> None:
    """Verify workflow persistence wrote the final report."""

    case_id = result["case_id"]

    report_path = settings.investigation_cases_dir / case_id / "final_investigation_report.json"

    assert report_path.exists()

    persisted = json.loads(
        report_path.read_text(
            encoding="utf-8",
        )
    )

    assert persisted == result["final_report"]


def test_complete_real_investigation_cases() -> None:
    """Run several complete real cases through the workflow."""

    case_ids = get_real_case_ids(limit=5)

    if not case_ids:
        pytest.skip("No real investigation cases are available.")

    for case_id in case_ids:
        try:
            result = investigation_graph.invoke(
                {
                    "case_id": case_id,
                }
            )

            assert result["case_id"] == case_id

            assert_final_state_shape(result)

            assert_finding_types(result)

            assert_finding_case_ids(result)

            assert_finding_counts_are_consistent(result)

            assert_review_routing(result)

            assert_final_report_consistency(result)

            assert_persisted_final_report(result)

            assert_resolved_provenance_when_valid(result)

        except Exception as exc:
            pytest.fail(
                "Complete investigation workflow "
                f"failed for case {case_id}: "
                f"{type(exc).__name__}: {exc}"
            )


def assert_resolved_provenance_when_valid(
    result: dict,
) -> None:
    """Verify references resolve when validation reports no errors."""

    if result["validation_errors"]:
        return

    known_claim_ids = {
        str(claim.get("claim_id")) for claim in result["clinical_claims"] if claim.get("claim_id")
    }

    known_evidence_ids = {
        str(evidence.get("evidence_id"))
        for evidence in result["evidence_items"]
        if evidence.get("evidence_id")
    }

    known_event_ids = {
        str(event.get("event_id"))
        for event in result["canonical_timeline"]
        if event.get("event_id")
    }

    for finding in result["investigation_findings"]:
        assert set(finding.claim_ids) <= known_claim_ids

        assert set(finding.evidence_ids) <= known_evidence_ids

        assert set(finding.event_ids) <= known_event_ids

        report = result["final_report"]

        report_findings = report["high_priority_findings"] + report["other_findings"]

        for finding in report_findings:
            assert set(finding["claim_ids"]) <= known_claim_ids
            assert set(finding["evidence_ids"]) <= known_evidence_ids
            assert set(finding["event_ids"]) <= known_event_ids


def assert_unique_finding_ids(
    result: dict,
) -> None:
    """Verify synthesized finding IDs are unique."""

    finding_ids = [finding.finding_id for finding in result["investigation_findings"]]

    assert len(finding_ids) == len(set(finding_ids))


def test_investigation_workflow_is_repeatable() -> None:
    """Verify repeated execution yields the same findings."""

    case_ids = get_real_case_ids(limit=1)

    if not case_ids:
        pytest.skip("No real investigation cases are available.")

    case_id = case_ids[0]

    first_result = investigation_graph.invoke(
        {
            "case_id": case_id,
        }
    )

    second_result = investigation_graph.invoke(
        {
            "case_id": case_id,
        }
    )

    first_ids = [finding.finding_id for finding in first_result["investigation_findings"]]

    second_ids = [finding.finding_id for finding in second_result["investigation_findings"]]

    assert first_ids == second_ids

    assert first_result["validation_errors"] == second_result["validation_errors"]

    assert first_result["review_status"] == second_result["review_status"]

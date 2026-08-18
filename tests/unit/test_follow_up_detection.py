from clinical_investigation.agents.follow_up import (
    detect_missing_follow_ups,
)
from clinical_investigation.agents.models import (
    FindingSeverity,
    FindingType,
)


def test_missing_follow_up_is_detected() -> None:
    clinical_claims = [
        {
            "claim_id": "claim-1",
            "claim_type": ("follow_up_action"),
            "subject": "cardiology",
            "predicate": "follow_up",
            "value": ("Follow up with cardiology"),
            "time_start": ("2026-01-01T10:00:00+00:00"),
            "source_evidence_ids": ["evidence-1"],
        }
    ]

    evidence_items = [
        {
            "evidence_id": "evidence-1",
            "document_type": ("discharge_summary"),
            "text_span": ("Follow up with cardiology."),
        }
    ]

    findings = detect_missing_follow_ups(
        case_id="case-001",
        clinical_claims=clinical_claims,
        evidence_items=evidence_items,
        canonical_timeline=[],
    )

    assert len(findings) == 1

    finding = findings[0]

    assert finding.finding_type == FindingType.MISSING_FOLLOW_UP

    assert finding.subtype == "no_documented_completion"

    assert finding.severity == FindingSeverity.MEDIUM

    assert finding.requires_human_review is True


def test_completed_follow_up_is_not_missing() -> None:
    clinical_claims = [
        {
            "claim_id": "claim-1",
            "claim_type": ("follow_up_action"),
            "subject": "cardiology",
            "predicate": "follow_up",
            "value": ("Follow up with cardiology"),
            "time_start": ("2026-01-01T10:00:00+00:00"),
            "source_evidence_ids": ["evidence-1"],
        }
    ]

    evidence_items = [
        {
            "evidence_id": "evidence-1",
            "document_type": ("discharge_summary"),
            "text_span": ("Follow up with cardiology."),
        },
        {
            "evidence_id": "evidence-2",
            "document_type": ("follow_up_note"),
            "text_span": ("Patient returned for cardiology follow-up."),
        },
    ]

    findings = detect_missing_follow_ups(
        case_id="case-001",
        clinical_claims=clinical_claims,
        evidence_items=evidence_items,
        canonical_timeline=[],
    )

    assert findings == []


def test_planned_follow_up_is_not_completion() -> None:
    clinical_claims = [
        {
            "claim_id": "claim-1",
            "claim_type": ("follow_up_action"),
            "subject": "cardiology",
            "predicate": "follow_up",
            "value": ("Follow up with cardiology"),
            "source_evidence_ids": ["evidence-1"],
        }
    ]

    evidence_items = [
        {
            "evidence_id": "evidence-1",
            "document_type": ("discharge_summary"),
            "text_span": ("Follow up with cardiology."),
        },
        {
            "evidence_id": "evidence-2",
            "document_type": ("follow_up_note"),
            "text_span": ("Cardiology follow-up recommended."),
        },
    ]

    findings = detect_missing_follow_ups(
        case_id="case-001",
        clinical_claims=clinical_claims,
        evidence_items=evidence_items,
        canonical_timeline=[],
    )

    assert len(findings) == 1


def test_later_timeline_completion_clears_follow_up() -> None:
    clinical_claims = [
        {
            "claim_id": "claim-1",
            "claim_type": ("follow_up_action"),
            "subject": "cardiology",
            "predicate": "follow_up",
            "value": ("Follow up with cardiology"),
            "time_start": ("2026-01-01T10:00:00+00:00"),
            "source_evidence_ids": ["evidence-1"],
        }
    ]

    evidence_items = [
        {
            "evidence_id": "evidence-1",
            "document_type": ("discharge_summary"),
            "text_span": ("Follow up with cardiology."),
        }
    ]

    canonical_timeline = [
        {
            "event_id": "event-1",
            "event_type": "follow_up",
            "subject": "cardiology",
            "description": ("Patient returned and completed cardiology follow-up."),
            "normalized_time": ("2026-01-10T10:00:00+00:00"),
        }
    ]

    findings = detect_missing_follow_ups(
        case_id="case-001",
        clinical_claims=clinical_claims,
        evidence_items=evidence_items,
        canonical_timeline=(canonical_timeline),
    )

    assert findings == []

from clinical_investigation.agents.contradiction import (
    detect_medication_status_contradictions,
)
from clinical_investigation.agents.models import (
    FindingSeverity,
    FindingType,
)


def test_detect_medication_status_contradiction() -> None:
    evidence_items = [
        {
            "evidence_id": "evidence-1",
            "document_type": ("progress_note"),
        },
        {
            "evidence_id": "evidence-2",
            "document_type": ("medication_reconciliation"),
        },
    ]

    clinical_claims = [
        {
            "claim_id": "claim-1",
            "claim_type": ("medication_status"),
            "subject": "Lisinopril",
            "predicate": ("documented_medication_fact"),
            "value": "continued",
            "time_start": None,
            "source_evidence_ids": ["evidence-1"],
        },
        {
            "claim_id": "claim-2",
            "claim_type": ("medication_status"),
            "subject": "Lisinopril",
            "predicate": ("documented_medication_fact"),
            "value": "discontinued",
            "time_start": None,
            "source_evidence_ids": ["evidence-2"],
        },
    ]

    findings = detect_medication_status_contradictions(
        case_id="case-001",
        clinical_claims=(clinical_claims),
        evidence_items=(evidence_items),
    )

    assert len(findings) == 1

    finding = findings[0]

    assert finding.finding_type == FindingType.CONTRADICTION

    assert finding.subtype == "medication_status_conflict"

    assert finding.severity == FindingSeverity.HIGH

    assert finding.requires_human_review is True


def test_same_status_is_not_contradiction() -> None:
    evidence_items = [
        {
            "evidence_id": "evidence-1",
            "document_type": ("progress_note"),
        },
        {
            "evidence_id": "evidence-2",
            "document_type": ("discharge_summary"),
        },
    ]

    clinical_claims = [
        {
            "claim_id": "claim-1",
            "claim_type": ("medication_status"),
            "subject": "Lisinopril",
            "value": "continued",
            "time_start": None,
            "source_evidence_ids": ["evidence-1"],
        },
        {
            "claim_id": "claim-2",
            "claim_type": ("medication_status"),
            "subject": "Lisinopril",
            "value": "continued",
            "time_start": None,
            "source_evidence_ids": ["evidence-2"],
        },
    ]

    findings = detect_medication_status_contradictions(
        case_id="case-001",
        clinical_claims=(clinical_claims),
        evidence_items=(evidence_items),
    )

    assert findings == []


def test_status_change_over_time_is_not_contradiction() -> None:
    evidence_items = [
        {
            "evidence_id": "evidence-1",
            "document_type": ("progress_note"),
        },
        {
            "evidence_id": "evidence-2",
            "document_type": ("discharge_summary"),
        },
    ]

    clinical_claims = [
        {
            "claim_id": "claim-1",
            "claim_type": ("medication_status"),
            "subject": "Lisinopril",
            "value": "continued",
            "time_start": ("2026-01-01T10:00:00+00:00"),
            "source_evidence_ids": ["evidence-1"],
        },
        {
            "claim_id": "claim-2",
            "claim_type": ("medication_status"),
            "subject": "Lisinopril",
            "value": "discontinued",
            "time_start": ("2026-01-05T10:00:00+00:00"),
            "source_evidence_ids": ["evidence-2"],
        },
    ]

    findings = detect_medication_status_contradictions(
        case_id="case-001",
        clinical_claims=(clinical_claims),
        evidence_items=(evidence_items),
    )

    assert findings == []

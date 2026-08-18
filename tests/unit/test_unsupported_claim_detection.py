from clinical_investigation.agents.models import (
    FindingType,
)
from clinical_investigation.agents.unsupported_claim import (
    detect_unsupported_claims,
)


def test_supported_claim_produces_no_finding() -> None:
    clinical_claims = [
        {
            "claim_id": "claim-1",
            "claim_type": "lab_result",
            "subject": "potassium",
            "predicate": "has_value",
            "value": "5.8",
            "source_evidence_ids": ["evidence-1"],
        }
    ]

    evidence_items = [
        {
            "evidence_id": "evidence-1",
            "document_type": "lab_report",
            "normalized_fact": ("Potassium has value 5.8 mmol/L"),
            "text_span": ("Potassium: 5.8 mmol/L"),
        }
    ]

    findings = detect_unsupported_claims(
        case_id="case-001",
        clinical_claims=clinical_claims,
        evidence_items=evidence_items,
    )

    assert findings == []


def test_missing_provenance_is_detected() -> None:
    clinical_claims = [
        {
            "claim_id": "claim-1",
            "claim_type": "lab_result",
            "subject": "potassium",
            "predicate": "has_value",
            "value": "5.8",
            "source_evidence_ids": [],
        }
    ]

    findings = detect_unsupported_claims(
        case_id="case-001",
        clinical_claims=clinical_claims,
        evidence_items=[],
    )

    assert len(findings) == 1

    finding = findings[0]

    assert finding.finding_type == FindingType.UNSUPPORTED_CLAIM

    assert finding.subtype == "missing_provenance"


def test_missing_source_evidence_is_detected() -> None:
    clinical_claims = [
        {
            "claim_id": "claim-1",
            "claim_type": "lab_result",
            "subject": "potassium",
            "predicate": "has_value",
            "value": "5.8",
            "source_evidence_ids": ["evidence-missing"],
        }
    ]

    findings = detect_unsupported_claims(
        case_id="case-001",
        clinical_claims=clinical_claims,
        evidence_items=[],
    )

    assert len(findings) == 1

    assert findings[0].subtype == "missing_source_evidence"


def test_numeric_mismatch_is_unsupported() -> None:
    clinical_claims = [
        {
            "claim_id": "claim-1",
            "claim_type": "lab_result",
            "subject": "potassium",
            "predicate": "has_value",
            "value": "5.8",
            "source_evidence_ids": ["evidence-1"],
        }
    ]

    evidence_items = [
        {
            "evidence_id": "evidence-1",
            "document_type": "lab_report",
            "normalized_fact": ("Potassium has value 4.1 mmol/L"),
            "text_span": ("Potassium: 4.1 mmol/L"),
        }
    ]

    findings = detect_unsupported_claims(
        case_id="case-001",
        clinical_claims=clinical_claims,
        evidence_items=evidence_items,
    )

    assert len(findings) == 1

    assert findings[0].subtype == "insufficient_evidence_support"


def test_textually_unrelated_evidence_is_unsupported() -> None:
    clinical_claims = [
        {
            "claim_id": "claim-1",
            "claim_type": "diagnosis",
            "subject": "pneumonia",
            "predicate": "diagnosed_with",
            "value": "present",
            "source_evidence_ids": ["evidence-1"],
        }
    ]

    evidence_items = [
        {
            "evidence_id": "evidence-1",
            "document_type": "progress_note",
            "normalized_fact": ("Patient denies chest pain."),
            "text_span": ("No chest pain reported."),
        }
    ]

    findings = detect_unsupported_claims(
        case_id="case-001",
        clinical_claims=clinical_claims,
        evidence_items=evidence_items,
    )

    assert len(findings) == 1

    assert findings[0].finding_type == FindingType.UNSUPPORTED_CLAIM

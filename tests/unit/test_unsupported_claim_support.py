from clinical_investigation.agents.unsupported_claim import (
    claim_supported_by_evidence,
    detect_unsupported_claims,
)


def test_medication_claim_supported_by_exact_evidence() -> None:
    claim = {
        "subject": "Cisplatin 50 MG Injection",
        "predicate": "documented_medication_fact",
        "value": "Cisplatin 50 MG Injection",
    }

    evidence = {
        "normalized_fact": "Cisplatin 50 MG Injection",
        "text_span": ("- Cisplatin 50 MG Injection [Source: medications:2495]"),
        "section": "Medications Present During Encounter",
    }

    assert claim_supported_by_evidence(
        claim=claim,
        evidence=evidence,
    )


def test_medication_claim_support_is_case_insensitive() -> None:
    claim = {
        "subject": "paclitaxel 100 mg injection",
        "predicate": "documented_medication_fact",
        "value": "paclitaxel 100 mg injection",
    }

    evidence = {
        "normalized_fact": "PACLitaxel 100 MG Injection",
        "text_span": "- PACLitaxel 100 MG Injection",
    }

    assert claim_supported_by_evidence(
        claim=claim,
        evidence=evidence,
    )


def test_medication_claim_rejects_different_dose() -> None:
    claim = {
        "subject": "Cisplatin 50 MG Injection",
        "predicate": "documented_medication_fact",
        "value": "Cisplatin 50 MG Injection",
    }

    evidence = {
        "normalized_fact": "Cisplatin 25 MG Injection",
        "text_span": "- Cisplatin 25 MG Injection",
    }

    assert not claim_supported_by_evidence(
        claim=claim,
        evidence=evidence,
    )


def test_medication_claim_rejects_different_medication() -> None:
    claim = {
        "subject": "Cisplatin 50 MG Injection",
        "predicate": "documented_medication_fact",
        "value": "Cisplatin 50 MG Injection",
    }

    evidence = {
        "normalized_fact": "Paclitaxel 50 MG Injection",
        "text_span": "- Paclitaxel 50 MG Injection",
    }

    assert not claim_supported_by_evidence(
        claim=claim,
        evidence=evidence,
    )


def test_detector_flags_different_medication_as_insufficient_support() -> None:
    case_id = "case-001"

    claim = {
        "claim_id": "claim-001",
        "case_id": case_id,
        "claim_type": "medication_status",
        "subject": "Cisplatin 50 MG Injection",
        "predicate": "documented_medication_fact",
        "value": "Cisplatin 50 MG Injection",
        "source_evidence_ids": [
            "evidence-001",
        ],
    }

    evidence = {
        "evidence_id": "evidence-001",
        "case_id": case_id,
        "document_type": "admission_note",
        "section": "Medications Present During Encounter",
        "normalized_fact": "Paclitaxel 50 MG Injection",
        "text_span": "- Paclitaxel 50 MG Injection",
    }

    findings = detect_unsupported_claims(
        case_id=case_id,
        clinical_claims=[claim],
        evidence_items=[evidence],
    )

    assert len(findings) == 1

    finding = findings[0]

    assert finding.finding_type.value == "unsupported_claim"
    assert finding.subtype == "insufficient_evidence_support"
    assert finding.claim_ids == ["claim-001"]
    assert finding.evidence_ids == ["evidence-001"]
    assert finding.requires_human_review is True


def test_detector_flags_different_dose_as_insufficient_support() -> None:
    case_id = "case-002"

    claim = {
        "claim_id": "claim-002",
        "case_id": case_id,
        "claim_type": "medication_status",
        "subject": "Cisplatin 50 MG Injection",
        "predicate": "documented_medication_fact",
        "value": "Cisplatin 50 MG Injection",
        "source_evidence_ids": [
            "evidence-002",
        ],
    }

    evidence = {
        "evidence_id": "evidence-002",
        "case_id": case_id,
        "document_type": "admission_note",
        "section": "Medications Present During Encounter",
        "normalized_fact": "Cisplatin 25 MG Injection",
        "text_span": "- Cisplatin 25 MG Injection",
    }

    findings = detect_unsupported_claims(
        case_id=case_id,
        clinical_claims=[claim],
        evidence_items=[evidence],
    )

    assert len(findings) == 1

    finding = findings[0]

    assert finding.subtype == "insufficient_evidence_support"
    assert finding.claim_ids == ["claim-002"]
    assert finding.evidence_ids == ["evidence-002"]


def test_detector_does_not_flag_directly_supported_medication_claim() -> None:
    case_id = "case-003"

    claim = {
        "claim_id": "claim-003",
        "case_id": case_id,
        "claim_type": "medication_status",
        "subject": "Cisplatin 50 MG Injection",
        "predicate": "documented_medication_fact",
        "value": "Cisplatin 50 MG Injection",
        "source_evidence_ids": [
            "evidence-003",
        ],
    }

    evidence = {
        "evidence_id": "evidence-003",
        "case_id": case_id,
        "document_type": "admission_note",
        "section": "Medications Present During Encounter",
        "normalized_fact": "Cisplatin 50 MG Injection",
        "text_span": "- Cisplatin 50 MG Injection",
    }

    findings = detect_unsupported_claims(
        case_id=case_id,
        clinical_claims=[claim],
        evidence_items=[evidence],
    )

    assert findings == []


def test_detector_accepts_any_one_supporting_evidence_item() -> None:
    case_id = "case-004"

    claim = {
        "claim_id": "claim-004",
        "case_id": case_id,
        "claim_type": "medication_status",
        "subject": "Cisplatin 50 MG Injection",
        "predicate": "documented_medication_fact",
        "value": "Cisplatin 50 MG Injection",
        "source_evidence_ids": [
            "evidence-wrong",
            "evidence-correct",
        ],
    }

    wrong_evidence = {
        "evidence_id": "evidence-wrong",
        "case_id": case_id,
        "document_type": "admission_note",
        "section": "Medications Present During Encounter",
        "normalized_fact": "Paclitaxel 50 MG Injection",
        "text_span": "- Paclitaxel 50 MG Injection",
    }

    correct_evidence = {
        "evidence_id": "evidence-correct",
        "case_id": case_id,
        "document_type": "admission_note",
        "section": "Medications Present During Encounter",
        "normalized_fact": "Cisplatin 50 MG Injection",
        "text_span": "- Cisplatin 50 MG Injection",
    }

    findings = detect_unsupported_claims(
        case_id=case_id,
        clinical_claims=[claim],
        evidence_items=[
            wrong_evidence,
            correct_evidence,
        ],
    )

    assert findings == []


def test_detector_preserves_missing_source_evidence_subtype() -> None:
    case_id = "case-005"

    claim = {
        "claim_id": "claim-005",
        "case_id": case_id,
        "claim_type": "medication_status",
        "subject": "Cisplatin 50 MG Injection",
        "predicate": "documented_medication_fact",
        "value": "Cisplatin 50 MG Injection",
        "source_evidence_ids": [
            "evidence-does-not-exist",
        ],
    }

    findings = detect_unsupported_claims(
        case_id=case_id,
        clinical_claims=[claim],
        evidence_items=[],
    )

    assert len(findings) == 1

    finding = findings[0]

    assert finding.subtype == "missing_source_evidence"
    assert finding.claim_ids == ["claim-005"]
    assert finding.evidence_ids == [
        "evidence-does-not-exist",
    ]

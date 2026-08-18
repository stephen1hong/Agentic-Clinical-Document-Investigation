from clinical_investigation.agents.models import (
    FindingSeverity,
    FindingSource,
    FindingType,
    InvestigationFinding,
)
from clinical_investigation.agents.nodes import (
    analyze_medications,
    analyze_timeline,
    detect_contradictions,
    detect_missing_followups,
    detect_unsupported_claims_node,
    human_review,
    initialize_investigation,
    mark_validation_passed,
    synthesize_findings,
    validate_investigation,
)


def test_initialize_investigation() -> None:
    result = initialize_investigation(
        {
            "case_id": "case-001",
        }
    )

    assert result["case_id"] == "case-001"

    assert result["investigation_findings"] == []

    assert result["requires_human_review"] is False


def test_analyze_timeline() -> None:
    state = {
        "case_id": "case-001",
        "timeline_conflicts": [
            {
                "conflict_id": "conflict-1",
                "conflict_type": ("missing_event_time"),
                "severity": "info",
                "summary": ("Event has no timestamp."),
                "rationale": ("No explicit event time."),
                "event_ids": ["event-1"],
                "evidence_ids": ["evidence-1"],
                "confidence": 1.0,
                "requires_human_review": (False),
            }
        ],
    }

    result = analyze_timeline(state)

    findings = result["timeline_findings"]

    assert len(findings) == 1

    assert findings[0].finding_type == "temporal_uncertainty"


def test_analyze_medications() -> None:
    state = {
        "case_id": "case-001",
        "medication_discrepancies": [
            {
                "discrepancy_id": ("med-1"),
                "discrepancy_type": ("dose_conflict"),
                "severity": "medium",
                "summary": ("Dose conflict detected."),
                "rationale": ("Two doses were documented."),
                "medication_key": ("lisinopril"),
                "evidence_ids": [
                    "evidence-1",
                    "evidence-2",
                ],
                "confidence": 0.95,
            }
        ],
    }

    result = analyze_medications(state)

    findings = result["medication_findings"]

    assert len(findings) == 1

    assert findings[0].subtype == "dose_conflict"


def test_synthesize_findings() -> None:
    timeline_finding = InvestigationFinding(
        finding_id="t1",
        case_id="case-001",
        finding_type=(FindingType.TEMPORAL_UNCERTAINTY),
        subtype="missing_event_time",
        severity=FindingSeverity.INFO,
        title="Missing event time",
        summary="No explicit timestamp.",
        confidence=1.0,
        requires_human_review=False,
        source=(FindingSource.TIMELINE_RECONSTRUCTION),
    )

    medication_finding = InvestigationFinding(
        finding_id="m1",
        case_id="case-001",
        finding_type=(FindingType.MEDICATION_DISCREPANCY),
        subtype="dose_conflict",
        severity=FindingSeverity.HIGH,
        title="Dose conflict",
        summary=("Different doses documented."),
        confidence=0.95,
        requires_human_review=True,
        source=(FindingSource.MEDICATION_RECONCILIATION),
    )

    state = {
        "timeline_findings": [timeline_finding],
        "medication_findings": [medication_finding],
    }

    result = synthesize_findings(state)

    findings = result["investigation_findings"]

    assert len(findings) == 2

    assert findings[0].severity == FindingSeverity.HIGH

    assert findings[0].finding_id == "m1"

    assert result["requires_human_review"] is True


def test_detect_contradictions_node() -> None:
    state = {
        "case_id": "case-001",
        "evidence_items": [
            {
                "evidence_id": "e1",
                "document_type": "progress_note",
            },
            {
                "evidence_id": "e2",
                "document_type": "discharge_summary",
            },
        ],
        "clinical_claims": [
            {
                "claim_id": "c1",
                "claim_type": "medication_status",
                "subject": "Lisinopril",
                "value": "continued",
                "time_start": None,
                "source_evidence_ids": ["e1"],
            },
            {
                "claim_id": "c2",
                "claim_type": "medication_status",
                "subject": "Lisinopril",
                "value": "discontinued",
                "time_start": None,
                "source_evidence_ids": ["e2"],
            },
        ],
    }

    result = detect_contradictions(state)

    findings = result["contradiction_findings"]

    assert len(findings) == 1

    assert findings[0].finding_type == FindingType.CONTRADICTION

    assert findings[0].subtype == "medication_status_conflict"

    assert findings[0].case_id == "case-001"


def test_detect_missing_followups_node() -> None:
    state = {
        "case_id": "case-001",
        "clinical_claims": [
            {
                "claim_id": "claim-1",
                "claim_type": ("follow_up_action"),
                "subject": "cardiology",
                "predicate": "follow_up",
                "value": ("Follow up with cardiology"),
                "source_evidence_ids": ["evidence-1"],
            }
        ],
        "evidence_items": [
            {
                "evidence_id": "evidence-1",
                "document_type": ("discharge_summary"),
                "text_span": ("Follow up with cardiology."),
            }
        ],
        "canonical_timeline": [],
    }

    result = detect_missing_followups(state)

    findings = result["follow_up_findings"]

    assert len(findings) == 1

    assert findings[0].finding_type == FindingType.MISSING_FOLLOW_UP

    assert findings[0].case_id == "case-001"


def test_detect_unsupported_claims_node() -> None:
    state = {
        "case_id": "case-001",
        "clinical_claims": [
            {
                "claim_id": "claim-1",
                "claim_type": "lab_result",
                "subject": "potassium",
                "predicate": "has_value",
                "value": "5.8",
                "source_evidence_ids": ["evidence-1"],
            }
        ],
        "evidence_items": [
            {
                "evidence_id": "evidence-1",
                "document_type": "lab_report",
                "normalized_fact": ("Potassium has value 4.1 mmol/L"),
            }
        ],
    }

    result = detect_unsupported_claims_node(state)

    findings = result["unsupported_claim_findings"]

    assert len(findings) == 1

    assert findings[0].finding_type == FindingType.UNSUPPORTED_CLAIM

    assert findings[0].subtype == "insufficient_evidence_support"

    assert findings[0].claim_ids == ["claim-1"]


def test_validate_investigation_node() -> None:
    finding = InvestigationFinding(
        finding_id="finding-1",
        case_id="case-001",
        finding_type=(FindingType.MEDICATION_DISCREPANCY),
        subtype="dose_conflict",
        severity=(FindingSeverity.MEDIUM),
        title="Dose conflict",
        summary=("Different medication doses were documented."),
        evidence_ids=["evidence-1"],
        claim_ids=["claim-1"],
        event_ids=[],
        confidence=0.95,
        requires_human_review=True,
        source=(FindingSource.MEDICATION_RECONCILIATION),
    )

    state = {
        "case_id": "case-001",
        "investigation_findings": [finding],
        "clinical_claims": [
            {
                "claim_id": "claim-1",
            }
        ],
        "evidence_items": [
            {
                "evidence_id": ("evidence-1"),
            }
        ],
        "canonical_timeline": [],
        "requires_human_review": True,
    }

    result = validate_investigation(state)

    assert result["validation_errors"] == []

    assert result["requires_human_review"] is True


def test_validate_investigation_node_sets_review_on_error() -> None:
    finding = InvestigationFinding(
        finding_id="finding-1",
        case_id="case-001",
        finding_type=FindingType.MISSING_FOLLOW_UP,
        subtype="no_documented_completion",
        severity=FindingSeverity.MEDIUM,
        title="Follow-up completion not documented",
        summary="No completion was found.",
        evidence_ids=["missing-evidence"],
        claim_ids=["missing-claim"],
        event_ids=[],
        confidence=0.8,
        requires_human_review=False,
        source=FindingSource.FOLLOW_UP_ANALYSIS,
    )

    state = {
        "case_id": "case-001",
        "investigation_findings": [finding],
        "clinical_claims": [],
        "evidence_items": [],
        "canonical_timeline": [],
        "requires_human_review": False,
    }

    result = validate_investigation(state)

    assert result["validation_errors"]

    assert result["requires_human_review"] is True


def test_mark_validation_passed() -> None:
    result = mark_validation_passed(
        {
            "case_id": "case-001",
        }
    )

    assert result["review_status"] == "not_required"

    assert result["review_reasons"] == []


def test_human_review_from_validation_error() -> None:
    state = {
        "case_id": "case-001",
        "validation_errors": ["Unknown evidence ID."],
        "investigation_findings": [],
        "requires_human_review": True,
    }

    result = human_review(state)

    assert result["review_status"] == "pending"

    assert result["requires_human_review"] is True

    assert len(result["review_reasons"]) == 1

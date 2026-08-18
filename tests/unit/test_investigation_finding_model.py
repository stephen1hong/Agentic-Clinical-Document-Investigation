import pytest
from pydantic import ValidationError

from clinical_investigation.agents.models import (
    FindingSeverity,
    FindingSource,
    FindingType,
    InvestigationFinding,
)


def test_investigation_finding() -> None:
    finding = InvestigationFinding(
        finding_id="finding-1",
        case_id="case-1",
        finding_type=(FindingType.CONTRADICTION),
        subtype="medication_status_conflict",
        severity=FindingSeverity.HIGH,
        title="Medication contradiction",
        summary=("Medication status differs across documents."),
        evidence_ids=[
            "evidence-1",
            "evidence-2",
        ],
        claim_ids=[
            "claim-1",
            "claim-2",
        ],
        event_ids=[],
        confidence=0.95,
        requires_human_review=True,
        source=(FindingSource.CONTRADICTION_ANALYSIS),
    )

    assert finding.finding_type == FindingType.CONTRADICTION

    assert finding.severity == FindingSeverity.HIGH

    assert finding.confidence == 0.95


def test_investigation_finding_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        InvestigationFinding(
            finding_id="finding-1",
            case_id="case-1",
            finding_type=(FindingType.CONTRADICTION),
            subtype="test",
            severity=FindingSeverity.HIGH,
            title="Test",
            summary="Test",
            confidence=1.5,
            source=(FindingSource.CONTRADICTION_ANALYSIS),
        )


def test_investigation_finding_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        InvestigationFinding(
            finding_id="finding-1",
            case_id="case-1",
            finding_type=(FindingType.CONTRADICTION),
            subtype="test",
            severity=FindingSeverity.HIGH,
            title="Test",
            summary="Test",
            confidence=1.0,
            source=(FindingSource.CONTRADICTION_ANALYSIS),
            unexpected_field="bad",
        )

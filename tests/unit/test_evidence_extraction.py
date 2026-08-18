"""Tests for clinical evidence and claim extraction."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from clinical_investigation.investigation.evidence_extraction import (
    DOCUMENT_FILES,
    build_investigation_case,
    extract_case_evidence,
)
from clinical_investigation.investigation.models import (
    ClaimType,
    ClinicalClaim,
    ExtractionMethod,
)


def create_document_fixture(
    root: Path,
) -> Path:
    """Create six minimal generated documents."""

    case_dir = root / "patient-001__encounter-001"
    case_dir.mkdir(parents=True)

    common_header = """\
# {title}

**Case ID:** patient-001__encounter-001
**Patient:** Test Patient
**Patient ID:** patient-001
**Encounter ID:** encounter-001

> Synthetic clinical document generated from Synthea data.
> This document is for software development and evaluation only.

"""

    documents = {
        "admission_note.md": (
            common_header.format(title="Admission Note")
            + """\
## Active Conditions

- Hypertension [Source: conditions:20]

## Medications Present During Encounter

- Lisinopril [Source: medications:30]
"""
        ),
        "progress_note.md": (
            common_header.format(title="Progress Note")
            + """\
## Recent Observations

- Potassium = 5.8 mmol/L [Source: observations:40]

## Procedures

- Blood collection [Source: procedures:50]
"""
        ),
        "lab_report.md": (
            common_header.format(title="Laboratory and Observation Report")
            + """\
## Results

| Date | Observation | Value | Flag status | Source |
|---|---|---:|---|---|
| January 02, 2026 | Potassium | 5.8 mmol/L | Explicitly flagged abnormal: High | observations:40 |
"""
        ),
        "medication_reconciliation.md": (
            common_header.format(title="Medication Reconciliation")
            + """\
## Medication Records

| Medication | Start | Stop | Encounter status | Source |
|---|---|---|---|---|
| Lisinopril | January 01, 2026 | Unknown | Active during encounter | medications:30 |
"""
        ),
        "discharge_summary.md": (
            common_header.format(title="Discharge Summary")
            + """\
## Active Conditions

- Hypertension [Source: conditions:20]

## Medication Status at Encounter End

- Lisinopril; Active during encounter [Source: medications:30]
"""
        ),
        "follow_up_note.md": (
            common_header.format(title="Follow-Up Review Note")
            + """\
## Items for Evidence Review

- Review candidate: abnormal_observation; evidence: Potassium; status: evidence review pending.
"""
        ),
    }

    for filename in DOCUMENT_FILES.values():
        (case_dir / filename).write_text(
            documents[filename],
            encoding="utf-8",
        )

    return case_dir


def test_extracts_all_six_documents(
    tmp_path: Path,
) -> None:
    """Evidence must be extracted from every document."""

    case_dir = create_document_fixture(tmp_path)

    evidence, claims = extract_case_evidence(case_dir)

    document_types = {item.document_type.value for item in evidence}

    assert document_types == {
        "admission_note",
        "progress_note",
        "lab_report",
        "medication_reconciliation",
        "discharge_summary",
        "follow_up_note",
    }

    assert claims


def test_preserves_source_provenance(
    tmp_path: Path,
) -> None:
    """Structured source references must be retained."""

    case_dir = create_document_fixture(tmp_path)

    evidence, _ = extract_case_evidence(case_dir)

    potassium_evidence = [
        item for item in evidence if (item.source_table == "observations" and item.source_row == 40)
    ]

    assert potassium_evidence


def test_every_claim_references_evidence(
    tmp_path: Path,
) -> None:
    """Every claim must link to existing evidence."""

    case_dir = create_document_fixture(tmp_path)

    evidence, claims = extract_case_evidence(case_dir)

    evidence_ids = {item.evidence_id for item in evidence}

    assert claims

    for claim in claims:
        assert claim.source_evidence_ids
        assert set(claim.source_evidence_ids).issubset(evidence_ids)


def test_extracts_observation_claim(
    tmp_path: Path,
) -> None:
    """Lab rows should become observation claims."""

    case_dir = create_document_fixture(tmp_path)

    _, claims = extract_case_evidence(case_dir)

    observation_claims = [
        claim for claim in claims if (claim.claim_type == ClaimType.OBSERVATION_RESULT)
    ]

    assert observation_claims

    assert any("Potassium" in claim.subject for claim in observation_claims)


def test_lab_table_header_does_not_create_claim(
    tmp_path: Path,
) -> None:
    """Lab table headers must remain evidence only, not claims."""

    case_dir = create_document_fixture(tmp_path)

    evidence, claims = extract_case_evidence(case_dir)

    header_evidence = [item for item in evidence if "Date | Observation | Value" in item.text_span]

    assert header_evidence

    assert not any(
        claim.claim_type == ClaimType.OBSERVATION_RESULT
        and claim.subject.strip().lower()
        in {
            "date",
            "observation",
        }
        for claim in claims
    )


def test_medication_table_header_does_not_create_claim(
    tmp_path: Path,
) -> None:
    """Medication reconciliation headers must not become claims."""

    case_dir = create_document_fixture(tmp_path)

    evidence, claims = extract_case_evidence(case_dir)

    header_evidence = [item for item in evidence if "Medication | Start | Stop" in item.text_span]

    assert header_evidence

    assert not any(
        claim.claim_type == ClaimType.MEDICATION_STATUS
        and claim.subject.strip().lower() == "medication"
        for claim in claims
    )


def test_no_observations_placeholder_does_not_create_claim(
    tmp_path: Path,
) -> None:
    """Empty-state observation text must not become a clinical claim."""

    case_dir = create_document_fixture(tmp_path)

    lab_path = case_dir / "lab_report.md"

    with lab_path.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write("\n| — | No observations available | — | — | — |\n")

    evidence, claims = extract_case_evidence(case_dir)

    placeholder_evidence = [
        item for item in evidence if "No observations available" in item.text_span
    ]

    assert placeholder_evidence

    assert not any(
        "no observations available" in (f"{claim.subject} {claim.value}").lower()
        for claim in claims
    )


def test_medication_explanatory_text_does_not_create_claim(
    tmp_path: Path,
) -> None:
    """Medication reconciliation metadata must not become a claim."""

    case_dir = create_document_fixture(tmp_path)

    medication_path = case_dir / "medication_reconciliation.md"

    with medication_path.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write("\nMedication statuses are derived from structured encounter data.\n")

    evidence, claims = extract_case_evidence(case_dir)

    explanatory_evidence = [
        item for item in evidence if "Medication statuses are derived" in item.text_span
    ]

    assert explanatory_evidence

    assert not any(
        "medication statuses are derived" in (f"{claim.subject} {claim.value}").lower()
        for claim in claims
    )


def test_real_lab_table_row_still_creates_claim(
    tmp_path: Path,
) -> None:
    """Filtering headers must not remove real observation rows."""

    case_dir = create_document_fixture(tmp_path)

    _, claims = extract_case_evidence(case_dir)

    potassium_claims = [
        claim
        for claim in claims
        if (
            claim.claim_type == ClaimType.OBSERVATION_RESULT
            and "potassium" in claim.subject.lower()
        )
    ]

    assert potassium_claims

    assert any("5.8 mmol/l" in claim.value.lower() for claim in potassium_claims)


def test_real_medication_table_row_still_creates_claim(
    tmp_path: Path,
) -> None:
    """Filtering headers must not remove real medication rows."""

    case_dir = create_document_fixture(tmp_path)

    _, claims = extract_case_evidence(case_dir)

    lisinopril_claims = [
        claim
        for claim in claims
        if (
            claim.claim_type == ClaimType.MEDICATION_STATUS
            and "lisinopril" in claim.subject.lower()
        )
    ]

    assert lisinopril_claims


def test_rejects_claim_without_evidence() -> None:
    """A claim without evidence links must fail."""

    with pytest.raises(ValidationError):
        ClinicalClaim(
            claim_id="claim-001",
            case_id="case-001",
            claim_type=(ClaimType.NARRATIVE_STATEMENT),
            subject="Example",
            predicate="states",
            value="Example statement",
            source_evidence_ids=[],
            extraction_confidence=1.0,
            extraction_method=(ExtractionMethod.DETERMINISTIC_MARKDOWN),
        )


def test_builds_investigation_case(
    tmp_path: Path,
) -> None:
    """The pipeline should create all three outputs."""

    case_dir = create_document_fixture(tmp_path / "documents")

    output_dir = build_investigation_case(
        document_dir=case_dir,
        output_root=tmp_path / "outputs",
    )

    assert {path.name for path in output_dir.iterdir()} == {
        "evidence_items.json",
        "clinical_claims.json",
        "extraction_manifest.json",
    }

    claims = json.loads((output_dir / "clinical_claims.json").read_text(encoding="utf-8"))

    assert claims

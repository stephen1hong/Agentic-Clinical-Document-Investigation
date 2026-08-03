"""Tests for generated clinical document validation."""

from pathlib import Path

from clinical_investigation.reporting.clinical_documents import (
    generate_encounter_documents,
)
from clinical_investigation.reporting.document_validation import (
    validate_document_set,
)
from tests.unit.test_clinical_documents import (
    create_case_fixture,
)


def test_document_set_passes_validation(
    tmp_path: Path,
) -> None:
    case_dir = create_case_fixture(tmp_path / "cases")

    result = generate_encounter_documents(
        case_dir=case_dir,
        output_root=tmp_path / "documents",
    )

    errors = validate_document_set(result.output_dir)

    assert errors == []

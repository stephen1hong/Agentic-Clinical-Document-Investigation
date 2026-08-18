"""Tests for investigation-case validation."""

from pathlib import Path

from clinical_investigation.investigation.evidence_extraction import (
    build_investigation_case,
)
from clinical_investigation.investigation.validation import (
    validate_investigation_case,
)
from tests.unit.test_evidence_extraction import (
    create_document_fixture,
)


def test_valid_investigation_case(
    tmp_path: Path,
) -> None:
    """A complete extracted case should pass validation."""

    source_dir = create_document_fixture(tmp_path / "documents")

    output_dir = build_investigation_case(
        document_dir=source_dir,
        output_root=tmp_path / "outputs",
    )

    errors = validate_investigation_case(output_dir)

    assert errors == []

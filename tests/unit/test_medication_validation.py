"""Tests for medication reconciliation validation."""

from pathlib import Path

from clinical_investigation.investigation.medication_reconciliation import (
    build_medication_reconciliation,
)
from clinical_investigation.investigation.medication_validation import (
    validate_medication_reconciliation,
)
from tests.unit.test_medication_reconciliation import (
    create_medication_fixture,
)


def test_valid_medication_reconciliation(
    tmp_path: Path,
) -> None:
    """A complete medication case should pass validation."""

    case_dir = create_medication_fixture(tmp_path)

    build_medication_reconciliation(case_dir)

    errors = validate_medication_reconciliation(case_dir)

    assert errors == []

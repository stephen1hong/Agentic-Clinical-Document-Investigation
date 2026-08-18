"""Tests for canonical timeline validation."""

from pathlib import Path

from clinical_investigation.investigation.timeline_reconstruction import (
    build_canonical_timeline,
)
from clinical_investigation.investigation.timeline_validation import (
    validate_canonical_timeline,
)
from tests.unit.test_timeline_reconstruction import (
    create_timeline_fixture,
)


def test_valid_canonical_timeline(
    tmp_path: Path,
) -> None:
    """A complete timeline should pass validation."""

    case_dir = create_timeline_fixture(tmp_path)

    build_canonical_timeline(case_dir)

    errors = validate_canonical_timeline(case_dir)

    assert errors == []

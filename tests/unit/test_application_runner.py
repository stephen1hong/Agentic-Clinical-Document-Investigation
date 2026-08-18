from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from clinical_investigation.application import runner


def patch_investigation_cases_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Patch the read-only investigation_cases_dir property."""

    monkeypatch.setattr(
        type(runner.settings),
        "investigation_cases_dir",
        property(lambda self: tmp_path),
    )


def test_resolve_case_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    case_id = "case-123"
    case_dir = tmp_path / case_id
    case_dir.mkdir()

    patch_investigation_cases_dir(
        monkeypatch,
        tmp_path,
    )

    result = runner.resolve_case_dir(case_id)

    assert result == case_dir


def test_resolve_case_dir_rejects_missing_case(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    patch_investigation_cases_dir(
        monkeypatch,
        tmp_path,
    )

    with pytest.raises(FileNotFoundError):
        runner.resolve_case_dir("missing-case")


def test_run_investigation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    case_id = "case-123"
    case_dir = tmp_path / case_id
    case_dir.mkdir()

    patch_investigation_cases_dir(
        monkeypatch,
        tmp_path,
    )

    graph = MagicMock()

    graph.invoke.return_value = {
        "case_id": case_id,
        "investigation_findings": [
            object(),
            object(),
        ],
        "validation_errors": [],
        "requires_human_review": True,
        "review_status": "pending",
        "final_report": {
            "case_id": case_id,
            "finding_count": 2,
            "review_status": "pending",
        },
    }

    monkeypatch.setattr(
        runner,
        "investigation_graph",
        graph,
    )

    result = runner.run_investigation(case_id)

    graph.invoke.assert_called_once_with(
        {
            "case_id": case_id,
        }
    )

    assert result.case_id == case_id
    assert result.case_dir == case_dir
    assert result.finding_count == 2
    assert result.validation_error_count == 0
    assert result.requires_human_review is True
    assert result.review_status == "pending"


def test_run_investigation_rejects_report_count_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    case_id = "case-123"
    case_dir = tmp_path / case_id
    case_dir.mkdir()

    patch_investigation_cases_dir(
        monkeypatch,
        tmp_path,
    )

    graph = MagicMock()

    graph.invoke.return_value = {
        "case_id": case_id,
        "investigation_findings": [
            object(),
        ],
        "validation_errors": [],
        "requires_human_review": False,
        "review_status": "not_required",
        "final_report": {
            "case_id": case_id,
            "finding_count": 2,
            "review_status": "not_required",
        },
    }

    monkeypatch.setattr(
        runner,
        "investigation_graph",
        graph,
    )

    with pytest.raises(
        RuntimeError,
        match="finding_count",
    ):
        runner.run_investigation(case_id)

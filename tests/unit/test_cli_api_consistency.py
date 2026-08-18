from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from clinical_investigation import cli
from clinical_investigation.application.runner import InvestigationRunResult

api_module = importlib.import_module(
    "clinical_investigation.api.app"
)

client = TestClient(api_module.app)


def make_result(
    *,
    case_id: str,
    finding_count: int,
    validation_error_count: int,
    requires_human_review: bool,
    review_status: str,
) -> InvestigationRunResult:
    """Build one shared synthetic application result."""

    case_dir = (
        Path("data")
        / "investigation_cases"
        / case_id
    )

    return InvestigationRunResult(
        case_id=case_id,
        case_dir=case_dir,
        finding_count=finding_count,
        validation_error_count=validation_error_count,
        requires_human_review=requires_human_review,
        review_status=review_status,
        final_report={
            "case_id": case_id,
            "finding_count": finding_count,
            "review_status": review_status,
        },
        raw_state={
            "case_id": case_id,
        },
    )


def shared_contract(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Extract fields shared by CLI and API contracts."""

    return {
        "case_id": payload["case_id"],
        "case_dir": payload["case_dir"],
        "finding_count": payload["finding_count"],
        "validation_error_count": payload["validation_error_count"],
        "requires_human_review": payload["requires_human_review"],
        "review_status": payload["review_status"],
        "final_report_path": payload["final_report_path"],
    }


def test_cli_and_api_success_contract_match(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI and API expose identical shared success fields."""

    result = make_result(
        case_id="case-a",
        finding_count=7,
        validation_error_count=0,
        requires_human_review=False,
        review_status="not_required",
    )

    def fake_run_investigation(
        case_id: str,
    ) -> InvestigationRunResult:
        assert case_id == "case-a"
        return result

    monkeypatch.setattr(
        cli,
        "run_investigation",
        fake_run_investigation,
    )

    monkeypatch.setattr(
        api_module,
        "run_investigation",
        fake_run_investigation,
    )

    cli_exit_code = cli.run_investigate_command(
        case_id="case-a",
        as_json=True,
    )

    captured = capsys.readouterr()
    cli_payload = json.loads(captured.out)

    api_response = client.post(
        "/investigations/case-a"
    )

    api_payload = api_response.json()

    assert cli_exit_code == 0
    assert api_response.status_code == 200

    assert shared_contract(cli_payload) == shared_contract(
        api_payload
    )


def test_cli_and_api_review_required_contract_match(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI and API preserve the same human-review result."""

    result = make_result(
        case_id="case-review",
        finding_count=19,
        validation_error_count=0,
        requires_human_review=True,
        review_status="pending",
    )

    def fake_run_investigation(
        case_id: str,
    ) -> InvestigationRunResult:
        assert case_id == "case-review"
        return result

    monkeypatch.setattr(
        cli,
        "run_investigation",
        fake_run_investigation,
    )

    monkeypatch.setattr(
        api_module,
        "run_investigation",
        fake_run_investigation,
    )

    cli_exit_code = cli.run_investigate_command(
        case_id="case-review",
        as_json=True,
    )

    captured = capsys.readouterr()
    cli_payload = json.loads(captured.out)

    api_response = client.post(
        "/investigations/case-review"
    )

    api_payload = api_response.json()

    assert cli_exit_code == 0
    assert api_response.status_code == 200

    assert shared_contract(cli_payload) == shared_contract(
        api_payload
    )

    assert cli_payload["requires_human_review"] is True
    assert cli_payload["review_status"] == "pending"


def test_cli_and_api_missing_case_error_semantics(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI and API preserve equivalent missing-case semantics."""

    def raise_cli_missing_case(
        *,
        case_id: str,
    ) -> dict[str, Any]:
        raise FileNotFoundError(
            f"Investigation case not found: {case_id}"
        )

    def raise_api_missing_case(
        case_id: str,
    ) -> InvestigationRunResult:
        raise FileNotFoundError(
            f"Investigation case not found: {case_id}"
        )

    monkeypatch.setattr(
        cli,
        "build_investigation_payload",
        raise_cli_missing_case,
    )

    monkeypatch.setattr(
        api_module,
        "run_investigation",
        raise_api_missing_case,
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "clinical-investigation",
            "investigate",
            "--case-id",
            "missing-case",
            "--json",
        ],
    )

    cli_exit_code = cli.main()

    captured = capsys.readouterr()
    cli_error = json.loads(captured.err)

    api_response = client.post(
        "/investigations/missing-case"
    )

    api_error = api_response.json()["detail"]

    assert cli_exit_code == 1
    assert api_response.status_code == 404

    assert cli_error["status"] == api_error["status"]
    assert cli_error["error_type"] == api_error["error_type"]
    assert cli_error["message"] == api_error["message"]
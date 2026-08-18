from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from clinical_investigation.application.runner import InvestigationRunResult

api_module = importlib.import_module(
    "clinical_investigation.api.app"
)

client = TestClient(api_module.app)


def test_health() -> None:
    """Health endpoint returns service availability."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }


def test_list_cases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Case listing returns persisted case IDs."""

    monkeypatch.setattr(
        api_module,
        "list_case_ids",
        lambda: [
            "case-a",
            "case-b",
        ],
    )

    response = client.get("/cases")

    assert response.status_code == 200

    assert response.json() == {
        "cases": [
            "case-a",
            "case-b",
        ],
        "count": 2,
    }


def test_investigation_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Investigation endpoint returns the public summary contract."""

    case_id = "case-a"

    case_dir = (
        Path("data")
        / "investigation_cases"
        / case_id
    )

    result = InvestigationRunResult(
        case_id=case_id,
        case_dir=case_dir,
        finding_count=7,
        validation_error_count=0,
        requires_human_review=False,
        review_status="not_required",
        final_report={
            "case_id": case_id,
        },
        raw_state={
            "case_id": case_id,
        },
    )

    monkeypatch.setattr(
        api_module,
        "run_investigation",
        lambda case_id: result,
    )

    response = client.post(
        f"/investigations/{case_id}"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload == {
        "case_id": case_id,
        "case_dir": str(case_dir),
        "finding_count": 7,
        "validation_error_count": 0,
        "requires_human_review": False,
        "review_status": "not_required",
        "final_report_path": str(
            case_dir / "final_investigation_report.json"
        ),
    }

    assert "raw_state" not in payload
    assert "final_report" not in payload


def test_investigation_missing_case_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing investigation cases return HTTP 404."""

    def raise_missing_case(
        case_id: str,
    ) -> InvestigationRunResult:
        raise FileNotFoundError(
            f"Investigation case not found: {case_id}"
        )

    monkeypatch.setattr(
        api_module,
        "run_investigation",
        raise_missing_case,
    )

    response = client.post(
        "/investigations/missing-case"
    )

    assert response.status_code == 404

    payload = response.json()

    assert payload["detail"]["status"] == "error"
    assert payload["detail"]["error_type"] == "FileNotFoundError"
    assert (
        "Investigation case not found"
        in payload["detail"]["message"]
    )


def test_investigation_runtime_error_returns_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflow execution failures return HTTP 500."""

    def raise_runtime_error(
        case_id: str,
    ) -> InvestigationRunResult:
        raise RuntimeError(
            f"Workflow failed for {case_id}"
        )

    monkeypatch.setattr(
        api_module,
        "run_investigation",
        raise_runtime_error,
    )

    response = client.post(
        "/investigations/case-a"
    )

    assert response.status_code == 500

    payload = response.json()

    assert payload["detail"]["status"] == "error"
    assert payload["detail"]["error_type"] == "RuntimeError"
    assert (
        "Workflow failed for case-a"
        in payload["detail"]["message"]
    )
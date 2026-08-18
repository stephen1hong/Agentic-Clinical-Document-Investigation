from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from clinical_investigation import cli
from clinical_investigation.application.demo_cases import (
    DEMO_CASES,
    get_demo_case,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEMO_MANIFEST_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "step_10_demo" / "demo_case_manifest.json"
)


def make_payload(
    *,
    case_id: str,
    finding_count: int,
    review_status: str,
    requires_human_review: bool,
) -> dict[str, Any]:
    """Build a synthetic CLI investigation payload."""

    case_dir = PROJECT_ROOT / "data" / "investigation_cases" / case_id

    return {
        "case_id": case_id,
        "case_dir": str(case_dir),
        "finding_count": finding_count,
        "validation_error_count": 0,
        "requires_human_review": requires_human_review,
        "review_status": review_status,
        "final_report_path": str(case_dir / "final_investigation_report.json"),
    }

def raise_missing_case(
    *,
    case_id: str,
) -> dict[str, Any]:
    """Raise a missing-case error for CLI tests."""

    raise FileNotFoundError(
        f"Investigation case not found: {case_id}"
    )

def test_demo_registry_contains_three_frozen_cases() -> None:
    """The release registry contains exactly the frozen demo IDs."""

    assert set(DEMO_CASES) == {
        "demo_a",
        "demo_b",
        "demo_c",
    }


def test_get_demo_case_resolves_demo_c() -> None:
    """Demo C resolves to the frozen human-review case."""

    demo_case = get_demo_case("demo_c")

    assert demo_case.title == "Human-Review Medication Discrepancy"

    assert demo_case.expected_finding_count == 19

    assert demo_case.expected_review_status == "pending"

    assert demo_case.expected_requires_human_review is True


def test_get_demo_case_rejects_unknown_demo() -> None:
    """Unknown demo aliases are rejected."""

    with pytest.raises(
        ValueError,
        match="Unknown demo case",
    ):
        get_demo_case("demo_unknown")


def test_run_demo_command_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The demo command emits the expected JSON contract."""

    demo_case = DEMO_CASES["demo_c"]

    payload = make_payload(
        case_id=demo_case.case_id,
        finding_count=19,
        review_status="pending",
        requires_human_review=True,
    )

    monkeypatch.setattr(
        cli,
        "build_investigation_payload",
        lambda *, case_id: payload,
    )

    exit_code = cli.run_demo_command(
        demo_id="demo_c",
        as_json=True,
    )

    assert exit_code == 0

    captured = capsys.readouterr()

    result = json.loads(captured.out)

    assert result["demo_id"] == "demo_c"

    assert result["demo_title"] == "Human-Review Medication Discrepancy"

    assert result["case_id"] == demo_case.case_id

    assert result["finding_count"] == 19

    assert result["validation_error_count"] == 0

    assert result["requires_human_review"] is True

    assert result["review_status"] == "pending"


def test_demo_command_detects_contract_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The demo command fails when frozen expectations drift."""

    demo_case = DEMO_CASES["demo_c"]

    payload = make_payload(
        case_id=demo_case.case_id,
        finding_count=19,
        review_status="not_required",
        requires_human_review=False,
    )

    monkeypatch.setattr(
        cli,
        "build_investigation_payload",
        lambda *, case_id: payload,
    )

    with pytest.raises(
        RuntimeError,
        match="Demo review status changed",
    ):
        cli.run_demo_command(
            demo_id="demo_c",
            as_json=False,
        )


def test_demo_registry_matches_frozen_manifest() -> None:
    """Runtime demo registry matches the frozen Step 10 manifest."""

    assert DEMO_MANIFEST_PATH.is_file()

    manifest = json.loads(DEMO_MANIFEST_PATH.read_text(encoding="utf-8"))

    manifest_cases = {item["demo_id"]: item for item in manifest["demo_cases"]}

    assert set(manifest_cases) == set(DEMO_CASES)

    for (
        demo_id,
        demo_case,
    ) in DEMO_CASES.items():
        manifest_case = manifest_cases[demo_id]

        assert manifest_case["case_id"] == demo_case.case_id

        assert manifest_case["finding_count"] == demo_case.expected_finding_count

        assert manifest_case["review_status"] == demo_case.expected_review_status

        assert manifest_case["requires_human_review"] == demo_case.expected_requires_human_review

def test_main_runtime_error_plain_text_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Runtime failures return 1 and write plain-text errors to stderr."""

    monkeypatch.setattr(
        cli,
        "build_investigation_payload",
        raise_missing_case,
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "clinical-investigation",
            "investigate",
            "--case-id",
            "missing-case",
        ],
    )

    exit_code = cli.main()

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "ERROR:" in captured.err
    assert "Investigation case not found: missing-case" in captured.err


def test_main_runtime_error_json_to_stderr(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """JSON-mode runtime failures return structured JSON on stderr."""

    monkeypatch.setattr(
        cli,
        "build_investigation_payload",
        raise_missing_case,
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

    exit_code = cli.main()

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""

    payload = json.loads(captured.err)

    assert payload["status"] == "error"
    assert payload["error_type"] == "FileNotFoundError"
    assert payload["message"] == "Investigation case not found: missing-case"


def test_list_cases_invalid_limit_returns_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Invalid list-cases limits return exit code 1."""

    monkeypatch.setattr(
        cli,
        "list_case_ids",
        lambda: ["case-a", "case-b"],
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "clinical-investigation",
            "list-cases",
            "--limit",
            "0",
        ],
    )

    exit_code = cli.main()

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "ERROR: --limit must be greater than 0." in captured.err


def test_invalid_demo_choice_remains_argparse_exit_2(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid demo identifiers remain argparse usage errors."""

    monkeypatch.setattr(
        "sys.argv",
        [
            "clinical-investigation",
            "demo",
            "invalid_demo",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 2

def test_investigate_json_field_contract(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Investigate JSON output exposes the frozen release fields."""

    payload = make_payload(
        case_id="case-a",
        finding_count=7,
        review_status="not_required",
        requires_human_review=False,
    )

    monkeypatch.setattr(
        cli,
        "build_investigation_payload",
        lambda *, case_id: payload,
    )

    exit_code = cli.run_investigate_command(
        case_id="case-a",
        as_json=True,
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert exit_code == 0

    assert set(result) == {
        "case_id",
        "case_dir",
        "finding_count",
        "validation_error_count",
        "requires_human_review",
        "review_status",
        "final_report_path",
    }

    assert isinstance(result["case_id"], str)
    assert isinstance(result["case_dir"], str)
    assert isinstance(result["finding_count"], int)
    assert isinstance(result["validation_error_count"], int)
    assert isinstance(result["requires_human_review"], bool)
    assert isinstance(result["review_status"], str)
    assert isinstance(result["final_report_path"], str)

def test_demo_json_field_contract(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Demo JSON output exposes the frozen release fields."""

    demo_case = DEMO_CASES["demo_a"]

    payload = make_payload(
        case_id=demo_case.case_id,
        finding_count=demo_case.expected_finding_count,
        review_status=demo_case.expected_review_status,
        requires_human_review=demo_case.expected_requires_human_review,
    )

    monkeypatch.setattr(
        cli,
        "build_investigation_payload",
        lambda *, case_id: payload,
    )

    exit_code = cli.run_demo_command(
        demo_id="demo_a",
        as_json=True,
    )

    captured = capsys.readouterr()
    result = json.loads(captured.out)

    assert exit_code == 0

    assert set(result) == {
        "demo_id",
        "demo_title",
        "case_id",
        "case_dir",
        "finding_count",
        "validation_error_count",
        "requires_human_review",
        "review_status",
        "final_report_path",
    }

def test_json_error_field_contract(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """JSON errors expose only the frozen error fields."""

    cli.print_json_error(
        FileNotFoundError("missing case")
    )

    captured = capsys.readouterr()
    result = json.loads(captured.err)

    assert set(result) == {
        "status",
        "error_type",
        "message",
    }

    assert result["status"] == "error"
    assert result["error_type"] == "FileNotFoundError"
    assert result["message"] == "missing case"

    
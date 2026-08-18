from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clinical_investigation.config import settings


class InvestigationToolError(RuntimeError):
    """Raised when an investigation tool cannot load required case data."""


def _get_case_dir(
    case_id: str,
) -> Path:
    """Return the investigation directory for a case."""

    case_dir = settings.investigation_cases_dir / case_id

    if not case_dir.exists():
        raise InvestigationToolError(f"Investigation case does not exist: {case_dir}")

    if not case_dir.is_dir():
        raise InvestigationToolError(f"Investigation case path is not a directory: {case_dir}")

    return case_dir


def _load_json(
    path: Path,
) -> Any:
    """Load JSON from disk with consistent error handling."""

    if not path.exists():
        raise InvestigationToolError(f"Required investigation artifact does not exist: {path}")

    if not path.is_file():
        raise InvestigationToolError(f"Investigation artifact is not a file: {path}")

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except json.JSONDecodeError as exc:
        raise InvestigationToolError(f"Invalid JSON in investigation artifact: {path}") from exc


def load_evidence_tool(
    case_id: str,
) -> list[dict[str, Any]]:
    """Load extracted evidence items for a case."""

    case_dir = _get_case_dir(case_id)

    data = _load_json(case_dir / "evidence_items.json")

    if not isinstance(data, list):
        raise InvestigationToolError("evidence_items.json must contain a JSON list.")

    return data


def load_claims_tool(
    case_id: str,
) -> list[dict[str, Any]]:
    """Load extracted clinical claims for a case."""

    case_dir = _get_case_dir(case_id)

    data = _load_json(case_dir / "clinical_claims.json")

    if not isinstance(data, list):
        raise InvestigationToolError("clinical_claims.json must contain a JSON list.")

    return data


def load_timeline_tool(
    case_id: str,
) -> list[dict[str, Any]]:
    """Load the canonical timeline for a case."""

    case_dir = _get_case_dir(case_id)

    data = _load_json(case_dir / "canonical_timeline.json")

    if not isinstance(data, list):
        raise InvestigationToolError("canonical_timeline.json must contain a JSON list.")

    return data


def load_timeline_conflicts_tool(
    case_id: str,
) -> list[dict[str, Any]]:
    """Load timeline conflicts for a case."""

    case_dir = _get_case_dir(case_id)

    data = _load_json(case_dir / "timeline_conflicts.json")

    if not isinstance(data, list):
        raise InvestigationToolError("timeline_conflicts.json must contain a JSON list.")

    return data


def load_medication_profiles_tool(
    case_id: str,
) -> list[dict[str, Any]]:
    """Load reconciled medication profiles for a case."""

    case_dir = _get_case_dir(case_id)

    data = _load_json(case_dir / "medication_profiles.json")

    if not isinstance(data, list):
        raise InvestigationToolError("medication_profiles.json must contain a JSON list.")

    return data


def load_medication_discrepancies_tool(
    case_id: str,
) -> list[dict[str, Any]]:
    """Load detected medication discrepancies for a case."""

    case_dir = _get_case_dir(case_id)

    data = _load_json(case_dir / "medication_discrepancies.json")

    if not isinstance(data, list):
        raise InvestigationToolError("medication_discrepancies.json must contain a JSON list.")

    return data


def load_case_context_tool(
    case_id: str,
) -> dict[str, Any]:
    """Load the main deterministic investigation artifacts.

    This is the primary context-loading tool for the
    agentic investigation workflow.
    """

    return {
        "case_id": case_id,
        "evidence_items": (load_evidence_tool(case_id)),
        "clinical_claims": (load_claims_tool(case_id)),
        "canonical_timeline": (load_timeline_tool(case_id)),
        "timeline_conflicts": (load_timeline_conflicts_tool(case_id)),
        "medication_profiles": (load_medication_profiles_tool(case_id)),
        "medication_discrepancies": (load_medication_discrepancies_tool(case_id)),
    }

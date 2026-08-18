from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from clinical_investigation.agents.workflow import (
    investigation_graph,
)
from clinical_investigation.config import settings


@dataclass(frozen=True)
class InvestigationRunResult:
    """Stable application-level result for one investigation run."""

    case_id: str
    case_dir: Path

    finding_count: int
    validation_error_count: int

    requires_human_review: bool
    review_status: str

    final_report: dict[str, Any]

    raw_state: dict[str, Any]


def resolve_case_dir(
    case_id: str,
) -> Path:
    """Resolve and validate one persisted investigation case."""

    normalized_case_id = case_id.strip()

    if not normalized_case_id:
        raise ValueError("case_id must not be empty.")

    case_dir = settings.investigation_cases_dir / normalized_case_id

    if not case_dir.exists():
        raise FileNotFoundError(f"Investigation case not found: {case_dir}")

    if not case_dir.is_dir():
        raise NotADirectoryError(f"Investigation case path is not a directory: {case_dir}")

    return case_dir


def run_investigation(
    case_id: str,
) -> InvestigationRunResult:
    """Run the production investigation workflow for one case."""

    case_dir = resolve_case_dir(case_id)

    normalized_case_id = case_dir.name

    result = investigation_graph.invoke(
        {
            "case_id": (normalized_case_id),
        }
    )

    if not isinstance(
        result,
        dict,
    ):
        raise RuntimeError("Investigation workflow returned a non-dictionary state.")

    result_case_id = str(
        result.get(
            "case_id",
            "",
        )
    )

    if result_case_id != normalized_case_id:
        raise RuntimeError(
            "Investigation workflow returned "
            "an unexpected case_id: "
            f"{result_case_id!r}; expected "
            f"{normalized_case_id!r}."
        )

    findings = result.get(
        "investigation_findings",
        [],
    )

    if not isinstance(
        findings,
        list,
    ):
        raise RuntimeError("Workflow state field 'investigation_findings' must be a list.")

    validation_errors = result.get(
        "validation_errors",
        [],
    )

    if not isinstance(
        validation_errors,
        list,
    ):
        raise RuntimeError("Workflow state field 'validation_errors' must be a list.")

    final_report = result.get("final_report")

    if not isinstance(
        final_report,
        dict,
    ):
        raise RuntimeError("Workflow did not return a valid final_report.")

    if final_report.get("case_id") != normalized_case_id:
        raise RuntimeError("Final report case_id does not match the requested case.")

    if final_report.get("finding_count") != len(findings):
        raise RuntimeError(
            "Final report finding_count does not match the workflow finding population."
        )

    review_status = str(
        result.get(
            "review_status",
            "",
        )
    )

    if final_report.get("review_status") != review_status:
        raise RuntimeError("Final report review_status does not match the workflow state.")

    return InvestigationRunResult(
        case_id=normalized_case_id,
        case_dir=case_dir,
        finding_count=len(findings),
        validation_error_count=len(validation_errors),
        requires_human_review=bool(
            result.get(
                "requires_human_review",
                False,
            )
        ),
        review_status=review_status,
        final_report=final_report,
        raw_state=result,
    )

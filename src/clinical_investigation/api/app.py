from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, status

from clinical_investigation.api.models import (
    CaseListResponse,
    ErrorResponse,
    HealthResponse,
    InvestigationResponse,
)
from clinical_investigation.application import (
    InvestigationRunResult,
    run_investigation,
)
from clinical_investigation.config import settings

app = FastAPI(
    title="Agentic Clinical Document Investigation API",
    version="0.1.0",
    description=(
        "Evidence-grounded clinical document investigation API "
        "backed by the production investigation workflow."
    ),
)


def list_case_ids() -> list[str]:
    """Return persisted investigation case identifiers."""

    root = settings.investigation_cases_dir

    if not root.exists():
        return []

    return [
        path.name
        for path in sorted(root.iterdir())
        if path.is_dir()
    ]


def build_investigation_response(
    result: InvestigationRunResult,
) -> InvestigationResponse:
    """Convert an application result into the public API model."""

    return InvestigationResponse(
        case_id=result.case_id,
        case_dir=str(result.case_dir),
        finding_count=result.finding_count,
        validation_error_count=result.validation_error_count,
        requires_human_review=result.requires_human_review,
        review_status=result.review_status,
        final_report_path=str(
            Path(result.case_dir)
            / "final_investigation_report.json"
        ),
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
)
def health() -> HealthResponse:
    """Return API health status."""

    return HealthResponse(
        status="ok",
    )


@app.get(
    "/cases",
    response_model=CaseListResponse,
    status_code=status.HTTP_200_OK,
)
def list_cases() -> CaseListResponse:
    """List persisted investigation cases."""

    case_ids = list_case_ids()

    return CaseListResponse(
        cases=case_ids,
        count=len(case_ids),
    )


@app.post(
    "/investigations/{case_id}",
    response_model=InvestigationResponse,
    responses={
        404: {
            "model": ErrorResponse,
            "description": "Investigation case not found.",
        },
        500: {
            "model": ErrorResponse,
            "description": "Investigation execution failed.",
        },
    },
)
def investigate(
    case_id: str,
) -> InvestigationResponse:
    """Run one persisted clinical investigation."""

    try:
        result = run_investigation(case_id)

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
        ) from exc

    except (
        NotADirectoryError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "status": "error",
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
        ) from exc

    return build_investigation_response(result)
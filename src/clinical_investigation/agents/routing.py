from __future__ import annotations

from typing import Literal

from clinical_investigation.agents.state import (
    InvestigationState,
)

ReviewRoute = Literal[
    "pass",
    "review",
]


def route_after_validation(
    state: InvestigationState,
) -> ReviewRoute:
    """Route validated investigation to pass or human review."""

    validation_errors = state.get(
        "validation_errors",
        [],
    )

    requires_human_review = bool(
        state.get(
            "requires_human_review",
            False,
        )
    )

    if validation_errors:
        return "review"

    if requires_human_review:
        return "review"

    return "pass"

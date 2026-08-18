from clinical_investigation.agents.routing import (
    route_after_validation,
)


def test_route_passes_clean_investigation() -> None:
    state = {
        "validation_errors": [],
        "requires_human_review": False,
    }

    assert route_after_validation(state) == "pass"


def test_route_reviews_validation_errors() -> None:
    state = {
        "validation_errors": ["Unknown evidence ID."],
        "requires_human_review": False,
    }

    assert route_after_validation(state) == "review"


def test_route_reviews_flagged_findings() -> None:
    state = {
        "validation_errors": [],
        "requires_human_review": True,
    }

    assert route_after_validation(state) == "review"

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoCase:
    """Metadata for one frozen demonstration case."""

    demo_id: str
    title: str
    case_id: str
    expected_finding_count: int
    expected_review_status: str
    expected_requires_human_review: bool


DEMO_CASES: dict[str, DemoCase] = {
    "demo_a": DemoCase(
        demo_id="demo_a",
        title="Typical Successful Investigation",
        case_id=("2b36a3c6-e9d6-554e-28c3-a8244a67a553__2b36a3c6-e9d6-554e-cc63-a167ac5cab80"),
        expected_finding_count=13,
        expected_review_status="not_required",
        expected_requires_human_review=False,
    ),
    "demo_b": DemoCase(
        demo_id="demo_b",
        title="Evidence-Rich Temporal Reconstruction",
        case_id=("86919c2e-6fcc-4756-2a76-c0e31e732109__86919c2e-6fcc-4756-d733-973edb1caccd"),
        expected_finding_count=15,
        expected_review_status="not_required",
        expected_requires_human_review=False,
    ),
    "demo_c": DemoCase(
        demo_id="demo_c",
        title="Human-Review Medication Discrepancy",
        case_id=("b23188ac-9529-2450-e0b7-58adb2b38de6__b23188ac-9529-2450-612b-f5fa70a4d52d"),
        expected_finding_count=19,
        expected_review_status="pending",
        expected_requires_human_review=True,
    ),
}


def get_demo_case(
    demo_id: str,
) -> DemoCase:
    """Resolve one frozen demonstration case."""

    normalized_demo_id = demo_id.strip().lower()

    if not normalized_demo_id:
        raise ValueError("demo_id must not be empty.")

    demo_case = DEMO_CASES.get(normalized_demo_id)

    if demo_case is None:
        valid_demo_ids = ", ".join(sorted(DEMO_CASES))

        raise ValueError(f"Unknown demo case: {demo_id!r}. Available demos: {valid_demo_ids}.")

    return demo_case

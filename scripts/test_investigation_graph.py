from clinical_investigation.agents.workflow import (
    investigation_graph,
)
from clinical_investigation.config import (
    settings,
)


def main() -> int:
    print("Starting LangGraph investigation test...")

    case_dirs = sorted(path for path in settings.investigation_cases_dir.iterdir() if path.is_dir())

    if not case_dirs:
        print("No investigation cases found.")
        return 1

    case_id = case_dirs[0].name

    print(f"Selected case: {case_id}")

    initial_state = {
        "case_id": case_id,
    }

    print("Invoking investigation graph...")

    result = investigation_graph.invoke(initial_state)

    print()
    print("=== LangGraph Investigation Summary ===")

    print(f"Case: {result['case_id']}")

    print(f"Evidence items: {len(result['evidence_items'])}")

    print(f"Clinical claims: {len(result['clinical_claims'])}")

    print(f"Timeline events: {len(result['canonical_timeline'])}")

    print(f"Timeline findings: {len(result['timeline_findings'])}")

    print(f"Medication findings: {len(result['medication_findings'])}")

    print(f"Contradiction findings: {len(result['contradiction_findings'])}")

    print(f"Missing follow-up findings: {len(result['follow_up_findings'])}")

    print(f"Unsupported claim findings: {len(result['unsupported_claim_findings'])}")

    print(f"Investigation findings: {len(result['investigation_findings'])}")

    print(f"Requires human review: {result['requires_human_review']}")

    print(f"Validation errors: {len(result['validation_errors'])}")

    print(f"Review status: {result['review_status']}")

    print(f"Review reasons: {len(result['review_reasons'])}")

    print()
    print("Top findings:")

    for finding in result["investigation_findings"][:10]:
        print(
            f"- [{finding.severity.value}] "
            f"{finding.finding_type.value} / "
            f"{finding.subtype}: "
            f"{finding.title}"
        )

    print()
    print("LangGraph investigation test completed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

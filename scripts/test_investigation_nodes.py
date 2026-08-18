from clinical_investigation.agents.nodes import (
    analyze_medications,
    analyze_timeline,
    detect_contradictions,
    detect_missing_followups,
    detect_unsupported_claims_node,
    initialize_investigation,
    retrieve_case_context,
    synthesize_findings,
)
from clinical_investigation.config import settings


def main() -> int:
    print("Starting investigation node test...")

    case_dirs = sorted(path for path in settings.investigation_cases_dir.iterdir() if path.is_dir())

    print(f"Investigation cases found: {len(case_dirs)}")

    if not case_dirs:
        print("No investigation cases found.")
        return 1

    case_id = case_dirs[0].name

    print(f"Selected case: {case_id}")

    state = {
        "case_id": case_id,
    }

    print("1. Initializing investigation...")

    state.update(initialize_investigation(state))

    print("2. Retrieving case context...")

    state.update(retrieve_case_context(state))

    print("3. Analyzing timeline...")

    state.update(analyze_timeline(state))

    print("4. Analyzing medications...")

    state.update(analyze_medications(state))

    print("5. Detecting cross-document contradictions...")

    state.update(detect_contradictions(state))

    print("6. Detecting missing follow-ups...")

    state.update(detect_missing_followups(state))

    print("7. Detecting unsupported claims...")

    state.update(detect_unsupported_claims_node(state))

    print("8. Synthesizing findings...")

    state.update(synthesize_findings(state))

    print()
    print("=== Investigation Summary ===")

    print(f"Case: {case_id}")

    print(f"Evidence items: {len(state['evidence_items'])}")

    print(f"Clinical claims: {len(state['clinical_claims'])}")

    print(f"Timeline events: {len(state['canonical_timeline'])}")

    print(f"Timeline findings: {len(state['timeline_findings'])}")

    print(f"Medication findings: {len(state['medication_findings'])}")

    print(f"Contradiction findings: {len(state['contradiction_findings'])}")

    print(f"Missing follow-up findings: {len(state['follow_up_findings'])}")

    print(f"Unsupported claim findings: {len(state['unsupported_claim_findings'])}")

    print(f"Investigation findings: {len(state['investigation_findings'])}")

    print(f"Requires human review: {state['requires_human_review']}")

    print()
    print("Top findings:")

    for finding in state["investigation_findings"][:10]:
        print(
            f"- [{finding.severity.value}] "
            f"{finding.finding_type.value} / "
            f"{finding.subtype}: "
            f"{finding.title}"
        )

    print()
    print("Investigation node test completed.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

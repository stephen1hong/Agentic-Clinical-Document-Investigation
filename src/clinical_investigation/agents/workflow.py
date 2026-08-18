from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from clinical_investigation.agents.nodes import (
    analyze_medications,
    analyze_timeline,
    detect_contradictions,
    detect_missing_followups,
    detect_unsupported_claims_node,
    generate_final_report,
    human_review,
    initialize_investigation,
    mark_validation_passed,
    persist_final_report_node,
    retrieve_case_context,
    synthesize_findings,
    validate_investigation,
)
from clinical_investigation.agents.routing import (
    route_after_validation,
)
from clinical_investigation.agents.state import (
    InvestigationState,
)


def build_investigation_workflow():
    """Build and compile the clinical investigation workflow."""

    workflow = StateGraph(InvestigationState)

    workflow.add_node(
        "initialize",
        initialize_investigation,
    )

    workflow.add_node(
        "retrieve_case",
        retrieve_case_context,
    )

    workflow.add_node(
        "timeline_analysis",
        analyze_timeline,
    )

    workflow.add_node(
        "medication_analysis",
        analyze_medications,
    )

    workflow.add_node(
        "contradiction_analysis",
        detect_contradictions,
    )

    workflow.add_node(
        "follow_up_analysis",
        detect_missing_followups,
    )

    workflow.add_node(
        "unsupported_claim_analysis",
        detect_unsupported_claims_node,
    )

    workflow.add_node(
        "synthesis",
        synthesize_findings,
    )

    workflow.add_node(
        "validation",
        validate_investigation,
    )

    workflow.add_node(
        "validation_passed",
        mark_validation_passed,
    )

    workflow.add_node(
        "human_review",
        human_review,
    )

    workflow.add_node(
        "final_report",
        generate_final_report,
    )

    workflow.add_node(
        "persist_report",
        persist_final_report_node,
    )

    workflow.add_edge(
        START,
        "initialize",
    )

    workflow.add_edge(
        "initialize",
        "retrieve_case",
    )

    workflow.add_edge(
        "retrieve_case",
        "timeline_analysis",
    )

    workflow.add_edge(
        "timeline_analysis",
        "medication_analysis",
    )

    workflow.add_edge(
        "medication_analysis",
        "contradiction_analysis",
    )

    workflow.add_edge(
        "contradiction_analysis",
        "follow_up_analysis",
    )

    workflow.add_edge(
        "follow_up_analysis",
        "unsupported_claim_analysis",
    )

    workflow.add_edge(
        "unsupported_claim_analysis",
        "synthesis",
    )

    workflow.add_edge(
        "synthesis",
        "validation",
    )

    workflow.add_conditional_edges(
        "validation",
        route_after_validation,
        {
            "pass": "validation_passed",
            "review": "human_review",
        },
    )

    workflow.add_edge(
        "validation_passed",
        "final_report",
    )

    workflow.add_edge(
        "human_review",
        "final_report",
    )

    workflow.add_edge(
        "final_report",
        "persist_report",
    )

    workflow.add_edge(
        "persist_report",
        END,
    )

    return workflow.compile()


investigation_graph = build_investigation_workflow()

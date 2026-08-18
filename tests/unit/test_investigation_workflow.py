from clinical_investigation.agents.workflow import (
    build_investigation_workflow,
)


def test_investigation_workflow_compiles() -> None:
    graph = build_investigation_workflow()

    assert graph is not None

# Architecture

## Agentic Clinical Document Investigation Platform

This document describes the runtime architecture, workflow orchestration, shared state, domain-processing layers, persistence model, human-review boundary, and evaluation boundary of the Agentic Clinical Document Investigation Platform.

The architecture documented here is derived from the current implementation and the frozen Step 9 release baseline.

The source-of-truth inventory is:

```text
ARCHITECTURE_INVENTORY.md
```

Architecture diagrams are stored under:

```text
docs/architecture/
```

Current diagrams:

```text
system_architecture.png
workflow.png
data_artifact_flow.png
human_review_flow.png
```

---

# 1. Architectural Goals

The platform is designed around several core principles:

- evidence-grounded investigation rather than unconstrained generation;
- structured state shared across specialized investigation stages;
- explicit provenance between evidence, claims, findings, and reports;
- separation between orchestration and clinical investigation logic;
- separation between machine output and human-review artifacts;
- deterministic persisted artifacts for evaluation and audit;
- stable release-facing interfaces over the production workflow;
- separation between production execution and release evaluation.

The simplified reasoning hierarchy is:

```text
Evidence
   |
   v
Clinical Claim
   |
   v
Investigation Finding
   |
   v
Final Investigation Report
```

---

# 2. High-Level System Architecture

The release-facing runtime path is:

```text
External Interface
        |
        v
CLI
        |
        v
Application Runner
        |
        v
Compiled LangGraph Workflow
        |
        v
Investigation Nodes
        |
        v
Shared InvestigationState
        |
        v
Final Report
        |
        v
Persistence
```

Evaluation is intentionally separate:

```text
Persisted Investigation Outputs
        |
        v
Evaluation / Regression / Robustness
        |
        v
Release Acceptance Gate
```

This separation prevents release validation logic from becoming part of the production clinical execution path.

---

# 3. External Interface Layer

The current command-line interface is implemented in:

```text
src/clinical_investigation/cli.py
```

The CLI provides release-facing operations such as:

```text
list-cases
investigate
```

Example:

```powershell
python -m clinical_investigation.cli list-cases --limit 5
```

and:

```powershell
python -m clinical_investigation.cli investigate --case-id <CASE_ID>
```

The CLI does not implement clinical investigation logic.

Instead, it delegates execution to the application layer.

The architectural rule is:

```text
CLI
 |
 v
Application Layer
 |
 v
Production Workflow
```

not:

```text
CLI
 |
 v
Independent Clinical Reasoning
```

---

# 4. Application Layer

The stable application boundary is implemented in:

```text
src/clinical_investigation/application/runner.py
```

The primary application function is:

```python
run_investigation(case_id)
```

The application runner performs several responsibilities:

```text
1. normalize and validate case_id
2. resolve the persisted investigation case directory
3. invoke the production investigation graph
4. validate the returned workflow state
5. verify case identity
6. verify finding-count consistency
7. verify review-status consistency
8. return a stable InvestigationRunResult
```

The application layer therefore acts as a contract boundary between release-facing interfaces and workflow internals.

---

# 5. Application Result Contract

The release-facing result object is:

```text
InvestigationRunResult
```

with fields:

```text
case_id
case_dir

finding_count
validation_error_count

requires_human_review
review_status

final_report
raw_state
```

This allows the CLI or future API implementations to depend on a stable interface rather than directly consuming arbitrary LangGraph state.

---

# 6. Workflow Orchestration Layer

The production LangGraph workflow is defined in:

```text
src/clinical_investigation/agents/workflow.py
```

The workflow is compiled into:

```text
investigation_graph
```

The workflow input contract is:

```python
{
    "case_id": "<CASE_ID>"
}
```

The graph uses:

```text
InvestigationState
```

as its shared state object.

---

# 7. Production Workflow

The authoritative workflow sequence is:

```text
START
  |
  v
initialize
  |
  v
retrieve_case
  |
  v
timeline_analysis
  |
  v
medication_analysis
  |
  v
contradiction_analysis
  |
  v
follow_up_analysis
  |
  v
unsupported_claim_analysis
  |
  v
synthesis
  |
  v
validation
  |
  +----------------------+
  |                      |
  v                      v
validation_passed    human_review
  |                      |
  +----------+-----------+
             |
             v
         final_report
             |
             v
        persist_report
             |
             v
            END
```

All primary workflow-node implementations are located in:

```text
src/clinical_investigation/agents/nodes.py
```

---

# 8. Workflow Node Mapping

| Workflow node | Python function |
|---|---|
| `initialize` | `initialize_investigation()` |
| `retrieve_case` | `retrieve_case_context()` |
| `timeline_analysis` | `analyze_timeline()` |
| `medication_analysis` | `analyze_medications()` |
| `contradiction_analysis` | `detect_contradictions()` |
| `follow_up_analysis` | `detect_missing_followups()` |
| `unsupported_claim_analysis` | `detect_unsupported_claims_node()` |
| `synthesis` | `synthesize_findings()` |
| `validation` | `validate_investigation()` |
| `validation_passed` | `mark_validation_passed()` |
| `human_review` | `human_review()` |
| `final_report` | `generate_final_report()` |
| `persist_report` | `persist_final_report_node()` |

This mapping is the authoritative relationship between LangGraph nodes and production functions.

---

# 9. Shared Workflow State

The shared workflow state is defined in:

```text
src/clinical_investigation/agents/state.py
```

The type is:

```text
InvestigationState
```

It is a `TypedDict` with `total=False`, allowing workflow nodes to incrementally populate state.

The current fields are:

```text
case_id
investigation_question

evidence_items
clinical_claims

canonical_timeline
timeline_conflicts

medication_profiles
medication_discrepancies

timeline_findings
medication_findings
contradiction_findings
follow_up_findings
unsupported_claim_findings

investigation_findings

validation_errors

requires_human_review
review_status
review_reasons

final_report
```

---

# 10. State Evolution

The workflow state evolves incrementally.

A simplified state-flow view is:

```text
initialize
    |
    +--> case_id
    +--> investigation_question

retrieve_case
    |
    +--> evidence_items
    +--> clinical_claims

timeline_analysis
    |
    +--> canonical_timeline
    +--> timeline_conflicts
    +--> timeline_findings

medication_analysis
    |
    +--> medication_profiles
    +--> medication_discrepancies
    +--> medication_findings

contradiction_analysis
    |
    +--> contradiction_findings

follow_up_analysis
    |
    +--> follow_up_findings

unsupported_claim_analysis
    |
    +--> unsupported_claim_findings

synthesis
    |
    +--> investigation_findings

validation
    |
    +--> validation_errors
    +--> requires_human_review
    +--> review_status
    +--> review_reasons

final_report
    |
    +--> final_report
```

This shared-state model allows specialized investigation stages to contribute structured outputs without requiring each stage to construct a complete report independently.

---

# 11. Domain Model Layer

The core domain models are separate from orchestration.

## Investigation Finding

Defined in:

```text
src/clinical_investigation/agents/models.py
```

Model:

```text
InvestigationFinding
```

A finding is a structured investigation conclusion, not merely an extracted fact.

---

## Evidence Item

Defined in:

```text
src/clinical_investigation/investigation/models.py
```

Model:

```text
EvidenceItem
```

---

## Clinical Claim

Defined in:

```text
src/clinical_investigation/investigation/models.py
```

Model:

```text
ClinicalClaim
```

---

# 12. Evidence and Claim Processing

Evidence extraction logic is located in:

```text
src/clinical_investigation/investigation/evidence_extraction.py
```

Evidence and clinical claims populate:

```text
evidence_items
clinical_claims
```

These become the structured foundation for later timeline, medication, contradiction, follow-up, and unsupported-claim analysis.

---

# 13. Timeline Architecture

Timeline models are defined in:

```text
src/clinical_investigation/investigation/timeline_models.py
```

Important model classes include:

```text
TimelineEventType
TimelineConflictType
TimelineConflict
TimelineManifest
```

Timeline reconstruction logic is implemented in:

```text
src/clinical_investigation/investigation/timeline_reconstruction.py
```

The workflow exposes timeline results through:

```text
canonical_timeline
timeline_conflicts
timeline_findings
```

The timeline stage is therefore responsible for transforming distributed temporal evidence into a canonical investigation context.

---

# 14. Medication Architecture

Medication models are defined in:

```text
src/clinical_investigation/investigation/medication_models.py
```

Important models include:

```text
MedicationStatus
MedicationSourceType
MedicationDiscrepancyType
MedicationMention
MedicationProfile
MedicationDiscrepancy
MedicationReconciliationManifest
```

Medication reconciliation logic is implemented in:

```text
src/clinical_investigation/investigation/medication_reconciliation.py
```

Its state outputs include:

```text
medication_profiles
medication_discrepancies
medication_findings
```

---

# 15. Contradiction Analysis

The production contradiction-analysis node is:

```text
detect_contradictions()
```

implemented in:

```text
src/clinical_investigation/agents/nodes.py
```

Its results populate:

```text
contradiction_findings
```

These findings are later merged during synthesis.

---

# 16. Missing Follow-Up Analysis

The missing-follow-up node is:

```text
detect_missing_followups()
```

implemented in:

```text
src/clinical_investigation/agents/nodes.py
```

Its state output is:

```text
follow_up_findings
```

---

# 17. Unsupported-Claim Analysis

The unsupported-claim node is:

```text
detect_unsupported_claims_node()
```

implemented in:

```text
src/clinical_investigation/agents/nodes.py
```

Its state output is:

```text
unsupported_claim_findings
```

---

# 18. Finding Synthesis

Specialized findings are consolidated by:

```text
synthesize_findings()
```

The specialized populations are:

```text
timeline_findings
medication_findings
contradiction_findings
follow_up_findings
unsupported_claim_findings
```

The synthesized result is stored as:

```text
investigation_findings
```

This consolidated population becomes the input to release validation and final-report generation.

---

# 19. Validation Architecture

The primary production validation node is:

```text
validate_investigation()
```

implemented in:

```text
src/clinical_investigation/agents/nodes.py
```

Supporting validation logic also exists in:

```text
src/clinical_investigation/agents/validation.py
```

including:

```text
validate_investigation_findings()
```

Case-level validation also exists in:

```text
src/clinical_investigation/investigation/validation.py
```

including:

```text
validate_investigation_case()
```

The validation stage populates:

```text
validation_errors
requires_human_review
review_status
review_reasons
```

---

# 20. Validation Routing

The workflow contains one conditional branch after validation.

Conceptually:

```text
validation
    |
    +---- pass ----> validation_passed
    |
    +---- review --> human_review
```

The no-review branch executes:

```text
mark_validation_passed()
```

The review-required branch executes:

```text
human_review()
```

Both paths converge before final-report generation.

---

# 21. Review Status Contract

For a case where human review is not required:

```text
requires_human_review = False
review_status = not_required
```

For a case requiring review:

```text
requires_human_review = True
review_status = pending
```

The current production workflow therefore uses:

```text
pending
```

rather than:

```text
review_required
```

as the persisted review status for a review-required case.

---

# 22. Human Review Boundary

The production workflow contains a `human_review` node for review-required routing.

Reviewer-facing artifact generation is implemented separately under:

```text
src/clinical_investigation/review/
```

Relevant modules include:

```text
bundle.py
generation.py
persistence.py
renderer.py
review_persistence.py
service.py
```

The reviewer artifacts are designed to remain separate from the original machine-generated final investigation report.

This separation supports:

- auditability;
- preservation of machine output;
- independent reviewer interpretation;
- future review-service integration.

---

# 23. Reviewer Artifacts

Reviewer persistence is implemented in:

```text
src/clinical_investigation/review/persistence.py
```

The authoritative filenames are:

```text
reviewer_bundle.json
reviewer_report.md
```

These artifacts belong to the human-review layer and should not be treated as replacements for:

```text
final_investigation_report.json
```

---

# 24. Final Report Generation

The production final-report node is:

```text
generate_final_report()
```

implemented in:

```text
src/clinical_investigation/agents/nodes.py
```

The generated report is placed into:

```text
InvestigationState.final_report
```

before persistence.

---

# 25. Final Report Persistence

The final-report persistence implementation is:

```text
src/clinical_investigation/agents/report_persistence.py
```

The authoritative filename is:

```text
final_investigation_report.json
```

The persisted location is:

```text
data/investigation_cases/<CASE_ID>/
    final_investigation_report.json
```

Persistence is triggered by:

```text
persist_final_report_node()
```

---

# 26. Investigation Case Root

The case root is resolved through:

```text
settings.investigation_cases_dir
```

defined in:

```text
src/clinical_investigation/config.py
```

The logical path is:

```text
data/investigation_cases/
```

Each investigation case is stored beneath:

```text
data/investigation_cases/<CASE_ID>/
```

---

# 27. Data and Artifact Flow

The primary data flow is:

```text
Clinical / Synthetic Source Documents
        |
        v
Investigation Case
        |
        v
Evidence + Claims
        |
        v
Timeline / Medication Context
        |
        v
Specialized Findings
        |
        v
Synthesis
        |
        v
Validation
        |
        v
Final Report
        |
        v
Persisted Case Artifacts
```

Supporting artifacts can include outputs from:

```text
evidence extraction
timeline reconstruction
medication reconciliation
review generation
```

These artifacts provide traceability between source material and final investigation output.

---

# 28. Production Persistence vs Evaluation Persistence

Production artifacts are stored under:

```text
data/investigation_cases/
```

Evaluation artifacts are stored separately under:

```text
data/evaluation/
```

This is an important architectural boundary.

Production execution should not depend on release-evaluation artifacts for clinical reasoning.

Evaluation consumes persisted production outputs.

---

# 29. Evaluation Architecture

The evaluation layer is implemented primarily under:

```text
src/clinical_investigation/evaluation/
```

The evaluation subsystem performs activities including:

```text
quality evaluation
persisted-output validation
regression testing
mutation testing
robustness testing
failure testing
recovery testing
release aggregation
```

Conceptually:

```text
Frozen Investigation Outputs
        |
        v
Evaluation Layer
        |
        v
Step 8 Quality Baseline
        |
        v
Step 9 Regression / Robustness / Acceptance
        |
        v
Release Gate
```

---

# 30. Release Acceptance Boundary

The authoritative release artifact is:

```text
data/evaluation/step_9_final/
    step_9_release_readiness_summary.json
```

The frozen release contract is:

```text
status = PASS
step_9_complete = true
release_ready = true
validation_issue_count = 0
```

The release gate is separate from runtime workflow execution.

---

# 31. Frozen Release Architecture

The Step 9 clinical release is frozen.

Step 10 architecture, documentation, CLI, API, and demonstration work should consume the accepted production path rather than reimplement clinical logic.

The release-facing architecture should remain:

```text
CLI / API / Demo
       |
       v
Application Layer
       |
       v
Accepted Production Workflow
```

not:

```text
CLI / API / Demo
       |
       v
Independent Clinical Reasoning
```

---

# 32. Architecture Diagrams

The current architecture diagrams are stored under:

```text
docs/architecture/
```

## System Architecture

```text
docs/architecture/system_architecture.png
```

Shows the major runtime layers:

```text
External Interface
Application Layer
Workflow Orchestration
Investigation Logic
Shared State
Persistence
Evaluation Boundary
```

---

## Workflow / Agent Execution

```text
docs/architecture/workflow.png
```

Shows the detailed LangGraph execution order and `InvestigationState` evolution.

---

## Data & Artifact Flow

```text
docs/architecture/data_artifact_flow.png
```

Shows how investigation data moves from case inputs through structured state to persisted outputs and the separate evaluation layer.

---

## Human Review Flow

```text
docs/architecture/human_review_flow.png
```

Shows the review-routing concept and reviewer artifact boundary.

The implementation source remains authoritative if a diagram contains a conceptual element not represented in the frozen workflow.

---

# 33. Diagram Interpretation Rule

Architecture diagrams are explanatory views.

They do not override source code.

The source-of-truth precedence is:

```text
1. Frozen production implementation
2. ARCHITECTURE_INVENTORY.md
3. ARCHITECTURE.md
4. Architecture diagrams
5. README summaries
```

If a diagram and source implementation disagree, the implementation must be treated as authoritative and the diagram should be corrected.

---

# 34. Important Human-Review Clarification

The current production LangGraph workflow supports:

```text
validation
    |
    +--> validation_passed
    |
    +--> human_review
```

followed by convergence into:

```text
final_report
    |
    v
persist_report
```

The current frozen workflow should not be described as containing additional iterative reviewer feedback loops, approval/rejection cycles, or automatic re-entry into earlier analysis nodes unless those behaviors are explicitly implemented and evaluated in a future release.

Reviewer-generation and reviewer-service modules exist as supporting functionality, but conceptual review diagrams should not be interpreted as expanding the frozen LangGraph execution contract.

---

# 35. Architectural Separation of Concerns

The implementation maintains several important boundaries.

## Interface vs application

```text
CLI
    !=
workflow implementation
```

## Application vs orchestration

```text
run_investigation()
    !=
clinical reasoning
```

## Orchestration vs domain logic

```text
LangGraph node sequencing
    !=
timeline / medication domain models
```

## Machine report vs reviewer artifacts

```text
final_investigation_report.json
    !=
reviewer_bundle.json
    !=
reviewer_report.md
```

## Production vs evaluation

```text
data/investigation_cases/
    !=
data/evaluation/
```

These boundaries improve maintainability, reproducibility, and auditability.

---

# 36. Current Architecture Baseline

The current frozen architecture can be summarized as:

```text
Clinical Case
    |
    v
Evidence / Claims
    |
    v
LangGraph Investigation Workflow
    |
    +--> Timeline Analysis
    |
    +--> Medication Analysis
    |
    +--> Contradiction Analysis
    |
    +--> Missing Follow-Up Analysis
    |
    +--> Unsupported Claim Analysis
    |
    v
Finding Synthesis
    |
    v
Validation
    |
    +--> No Review Required
    |
    +--> Human Review Required
    |
    v
Final Investigation Report
    |
    v
Persistence
    |
    v
Evaluation / Release Acceptance
```

---

# 37. Architecture Status

```text
10C.1 - Architecture Inventory / Source of Truth
COMPLETE

10C.2 - System Architecture Diagram
COMPLETE

10C.3 - Workflow / Agent Execution Diagram
COMPLETE

10C.4 - Data & Artifact Flow Diagram
COMPLETE

10C.5 - Human Review Flow Diagram
COMPLETE

10C.6 - Architecture Narrative
COMPLETE
```

The next architecture substep is:

```text
10C.7 - Architecture Consistency Check / Freeze
```
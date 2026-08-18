# Architecture Inventory

## Agentic Clinical Document Investigation Platform

This document identifies the authoritative implementation source for each major architectural responsibility in the current frozen release.

The purpose is to ensure that architecture documentation and diagrams are derived from the actual repository rather than from conceptual or outdated designs.

---

# 1. Architecture Source-of-Truth Principle

For Step 10C, architecture documentation follows this rule:

```text
Actual source code
      |
      v
Architecture inventory
      |
      v
Architecture diagrams
      |
      v
External documentation
```

Architecture diagrams must not introduce components, agents, state fields, or persistence paths that are not supported by the current implementation.

---

# 2. Top-Level Execution Architecture

The release execution path is:

```text
CLI
 |
 v
Application Runner
 |
 v
Compiled LangGraph Workflow
 |
 v
Production Workflow Nodes
 |
 v
Validation / Review Routing
 |
 v
Final Report Generation
 |
 v
Persistence
```

The major authoritative sources are:

| Responsibility | Authoritative source |
|---|---|
| CLI entrypoint | `src/clinical_investigation/cli.py` |
| Stable application boundary | `src/clinical_investigation/application/runner.py` |
| Application exports | `src/clinical_investigation/application/__init__.py` |
| Production graph definition | `src/clinical_investigation/agents/workflow.py` |
| Workflow state | `src/clinical_investigation/agents/state.py` |
| Production workflow nodes | `src/clinical_investigation/agents/nodes.py` |
| Workflow routing | `src/clinical_investigation/agents/routing.py` |
| Investigation finding model | `src/clinical_investigation/agents/models.py` |
| Final report persistence | `src/clinical_investigation/agents/report_persistence.py` |
| Reviewer generation | `src/clinical_investigation/review/generation.py` |
| Reviewer persistence | `src/clinical_investigation/review/persistence.py` |
| Release acceptance artifact | `data/evaluation/step_9_final/step_9_release_readiness_summary.json` |

---

# 3. Production Workflow

The production workflow is defined in:

```text
src/clinical_investigation/agents/workflow.py
```

The graph is compiled into the production singleton:

```text
investigation_graph
```

The authoritative execution order is:

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

The graph input contract is:

```python
{
    "case_id": "<CASE_ID>"
}
```

---

# 4. Workflow Node Ownership

All primary production workflow node functions are implemented in:

```text
src/clinical_investigation/agents/nodes.py
```

| Workflow node | Function |
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
| `human_review` | `human_review()` |
| `validation_passed` | `mark_validation_passed()` |
| `final_report` | `generate_final_report()` |
| `persist_report` | `persist_final_report_node()` |

This table is the authoritative mapping between LangGraph nodes and Python implementations.

---

# 5. Workflow State

The shared workflow state is defined in:

```text
src/clinical_investigation/agents/state.py
```

The authoritative state type is:

```text
InvestigationState
```

The current state fields are:

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

The state is a `TypedDict` with `total=False`, allowing workflow nodes to populate fields incrementally.

---

# 6. Core Domain Models

## Investigation Finding

Authoritative source:

```text
src/clinical_investigation/agents/models.py
```

Model:

```text
InvestigationFinding
```

This represents a structured investigation conclusion produced by the workflow.

---

## Evidence Item

Authoritative source:

```text
src/clinical_investigation/investigation/models.py
```

Model:

```text
EvidenceItem
```

This represents structured source evidence extracted from clinical documents.

---

## Clinical Claim

Authoritative source:

```text
src/clinical_investigation/investigation/models.py
```

Model:

```text
ClinicalClaim
```

This represents a structured clinical assertion associated with evidence.

---

# 7. Timeline Architecture

Timeline-related models are defined in:

```text
src/clinical_investigation/investigation/timeline_models.py
```

Important models include:

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

Timeline reconstruction can persist timeline-related artifacts through this implementation layer.

The workflow exposes timeline results through state fields including:

```text
canonical_timeline
timeline_conflicts
timeline_findings
```

---

# 8. Medication Architecture

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

Workflow state fields include:

```text
medication_profiles
medication_discrepancies
medication_findings
```

---

# 9. Evidence and Claim Extraction

Evidence extraction implementation is located in:

```text
src/clinical_investigation/investigation/evidence_extraction.py
```

Core domain models are:

```text
EvidenceItem
ClinicalClaim
```

from:

```text
src/clinical_investigation/investigation/models.py
```

The workflow state stores extracted information in:

```text
evidence_items
clinical_claims
```

---

# 10. Contradiction Analysis

The production contradiction workflow node is:

```text
detect_contradictions()
```

implemented in:

```text
src/clinical_investigation/agents/nodes.py
```

The resulting findings are stored in:

```text
contradiction_findings
```

and later merged into:

```text
investigation_findings
```

during synthesis.

---

# 11. Missing Follow-Up Analysis

The production missing-follow-up node is:

```text
detect_missing_followups()
```

implemented in:

```text
src/clinical_investigation/agents/nodes.py
```

Its workflow state output is:

```text
follow_up_findings
```

---

# 12. Unsupported-Claim Analysis

The production node is:

```text
detect_unsupported_claims_node()
```

implemented in:

```text
src/clinical_investigation/agents/nodes.py
```

Its workflow state output is:

```text
unsupported_claim_findings
```

---

# 13. Finding Synthesis

The synthesis node is:

```text
synthesize_findings()
```

implemented in:

```text
src/clinical_investigation/agents/nodes.py
```

It consolidates specialized finding populations into:

```text
investigation_findings
```

The final investigation population therefore comes after the specialized analysis stages rather than directly from raw documents.

---

# 14. Validation Architecture

The production validation node is:

```text
validate_investigation()
```

implemented in:

```text
src/clinical_investigation/agents/nodes.py
```

Additional investigation-finding validation functionality exists in:

```text
src/clinical_investigation/agents/validation.py
```

including:

```text
validate_investigation_findings()
```

Additional case-level validation functionality exists in:

```text
src/clinical_investigation/investigation/validation.py
```

including:

```text
validate_investigation_case()
```

The workflow validation state includes:

```text
validation_errors
requires_human_review
review_status
review_reasons
```

---

# 15. Human Review Architecture

The production workflow node is:

```text
human_review()
```

implemented in:

```text
src/clinical_investigation/agents/nodes.py
```

The no-review branch uses:

```text
mark_validation_passed()
```

The authoritative production review-status contract is:

```text
No review required:
requires_human_review = False
review_status = not_required
```

```text
Review required:
requires_human_review = True
review_status = pending
```

Reviewer artifact generation is implemented under:

```text
src/clinical_investigation/review/
```

Key sources include:

```text
bundle.py
generation.py
persistence.py
renderer.py
review_persistence.py
service.py
```

---

# 16. Reviewer Artifact Persistence

Reviewer artifact filenames are defined in:

```text
src/clinical_investigation/review/persistence.py
```

The authoritative filenames are:

```text
reviewer_bundle.json
reviewer_report.md
```

Persistence functions include:

```text
persist_reviewer_bundle()
persist_reviewer_report()
```

These artifacts remain separate from the machine-generated final investigation report.

---

# 17. Final Report Generation

The production final-report node is:

```text
generate_final_report()
```

implemented in:

```text
src/clinical_investigation/agents/nodes.py
```

The generated report is placed into the workflow state field:

```text
final_report
```

before persistence.

---

# 18. Final Report Persistence

The final-report filename is defined in:

```text
src/clinical_investigation/agents/report_persistence.py
```

as:

```text
final_investigation_report.json
```

The report is persisted under:

```text
data/investigation_cases/<CASE_ID>/
    final_investigation_report.json
```

The workflow node responsible for persistence is:

```text
persist_final_report_node()
```

---

# 19. Investigation Case Root

The investigation case directory is provided by configuration through:

```text
settings.investigation_cases_dir
```

defined in:

```text
src/clinical_investigation/config.py
```

It is used by:

```text
CLI
Application Runner
Agent tools
Workflow nodes
```

to resolve case-level persistence.

The logical case root is:

```text
data/investigation_cases/
```

---

# 20. Stable Application Boundary

The release-facing application boundary is:

```text
src/clinical_investigation/application/runner.py
```

Primary API:

```python
run_investigation(case_id)
```

The application runner:

```text
1. validates the case ID;
2. resolves the persisted investigation case;
3. invokes the production investigation_graph;
4. validates returned workflow state;
5. validates final-report consistency;
6. returns a stable application-level result.
```

The application layer does not implement independent clinical reasoning.

---

# 21. Application Result Contract

The stable result object is:

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

This contract is intended for release-facing interfaces such as CLI and future API adapters.

---

# 22. CLI Boundary

The command-line interface is:

```text
src/clinical_investigation/cli.py
```

Supported release-facing operations currently include:

```text
list-cases
investigate
```

The investigation path is:

```text
CLI
 |
 v
run_investigation()
 |
 v
Application Runner
 |
 v
investigation_graph
```

Clinical investigation logic must remain outside the CLI.

---

# 23. Persistence Architecture

The current persisted-artifact model includes multiple producer layers.

## Final investigation report

Producer:

```text
src/clinical_investigation/agents/report_persistence.py
```

Artifact:

```text
final_investigation_report.json
```

## Reviewer bundle

Producer:

```text
src/clinical_investigation/review/persistence.py
```

Artifact:

```text
reviewer_bundle.json
```

## Reviewer report

Producer:

```text
src/clinical_investigation/review/persistence.py
```

Artifact:

```text
reviewer_report.md
```

## Timeline artifacts

Producer:

```text
src/clinical_investigation/investigation/timeline_reconstruction.py
```

## Medication reconciliation artifacts

Producer:

```text
src/clinical_investigation/investigation/medication_reconciliation.py
```

## Evidence extraction artifacts

Producer:

```text
src/clinical_investigation/investigation/evidence_extraction.py
```

Evaluation artifacts are persisted independently under the evaluation subsystem and are not production case outputs.

---

# 24. Production vs Evaluation Architecture

The repository contains two distinct architectural concerns.

## Production investigation

```text
Clinical case
    |
    v
Investigation workflow
    |
    v
Findings
    |
    v
Final report
```

Primary packages:

```text
agents/
application/
investigation/
evidence/
reconciliation/
retrieval/
reporting/
review/
```

## Evaluation and release validation

```text
Frozen investigation outputs
        |
        v
Evaluation
        |
        v
Robustness / Regression
        |
        v
Release gate
```

Primary package:

```text
evaluation/
```

These concerns should remain separate in architecture diagrams.

---

# 25. Release Acceptance Source of Truth

The authoritative release gate is:

```text
data/evaluation/step_9_final/
    step_9_release_readiness_summary.json
```

The accepted release state is:

```text
status = PASS
step_9_complete = true
release_ready = true
validation_issue_count = 0
```

This artifact is the source of truth for release acceptance, not README text or CLI output.

---

# 26. Architecture Responsibility Map

| Responsibility | Authoritative source | Primary output |
|---|---|---|
| CLI | `src/clinical_investigation/cli.py` | CLI result |
| Application boundary | `src/clinical_investigation/application/runner.py` | `InvestigationRunResult` |
| Graph orchestration | `src/clinical_investigation/agents/workflow.py` | Workflow execution |
| Shared state | `src/clinical_investigation/agents/state.py` | `InvestigationState` |
| Production nodes | `src/clinical_investigation/agents/nodes.py` | State updates |
| Finding model | `src/clinical_investigation/agents/models.py` | `InvestigationFinding` |
| Evidence model | `src/clinical_investigation/investigation/models.py` | `EvidenceItem` |
| Claim model | `src/clinical_investigation/investigation/models.py` | `ClinicalClaim` |
| Timeline models | `src/clinical_investigation/investigation/timeline_models.py` | Timeline objects |
| Timeline reconstruction | `src/clinical_investigation/investigation/timeline_reconstruction.py` | Timeline artifacts |
| Medication models | `src/clinical_investigation/investigation/medication_models.py` | Medication objects |
| Medication reconciliation | `src/clinical_investigation/investigation/medication_reconciliation.py` | Medication artifacts |
| Evidence extraction | `src/clinical_investigation/investigation/evidence_extraction.py` | Evidence artifacts |
| Validation | `src/clinical_investigation/agents/nodes.py` | Validation state |
| Additional finding validation | `src/clinical_investigation/agents/validation.py` | Finding validation |
| Case validation | `src/clinical_investigation/investigation/validation.py` | Case validation |
| Human review | `src/clinical_investigation/agents/nodes.py` | Review state |
| Reviewer generation | `src/clinical_investigation/review/generation.py` | Reviewer artifacts |
| Reviewer persistence | `src/clinical_investigation/review/persistence.py` | Reviewer files |
| Final report generation | `src/clinical_investigation/agents/nodes.py` | `final_report` |
| Final report persistence | `src/clinical_investigation/agents/report_persistence.py` | `final_investigation_report.json` |
| Release gate | `data/evaluation/step_9_final/step_9_release_readiness_summary.json` | Release decision |

---

# 27. Architecture Boundaries

The architecture should preserve these boundaries:

```text
External Interface
      |
      v
Application Layer
      |
      v
Workflow Orchestration
      |
      v
Investigation Logic
      |
      v
Structured State
      |
      v
Persistence
```

Evaluation sits beside, not inside, the production execution path:

```text
Production Workflow -----> Persisted Outputs
                               |
                               v
                         Evaluation Layer
                               |
                               v
                          Release Gate
```

---

# 28. Architecture Documentation Rule

All Step 10C diagrams should be generated from this inventory.

If a diagram introduces a component not listed here, the implementation must first be verified before the component is documented as part of the production architecture.

Likewise, if source code changes after the frozen release, this inventory must be reviewed before reusing the existing architecture diagrams.

---

# 29. Current Architecture Baseline

The current frozen architecture can be summarized as:

```text
Clinical Case Artifacts
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
        +--> Validation Pass
        |
        +--> Human Review
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

This is the architecture source-of-truth baseline for Step 10C.
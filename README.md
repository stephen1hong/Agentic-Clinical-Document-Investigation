# Agentic Clinical Document Investigation Platform

An evidence-grounded agentic AI platform for investigating longitudinal clinical documents, reconstructing clinical timelines, reconciling medications, detecting contradictions and unsupported claims, identifying missing follow-up, and generating provenance-linked investigation reports with human-review routing.

## Overview

Clinical records are distributed across multiple documents, encounters, medication lists, laboratory reports, discharge summaries, and follow-up notes. Important inconsistencies often become visible only when those sources are examined together.

The **Agentic Clinical Document Investigation Platform** treats a clinical case as a connected evidence set rather than analyzing each document independently.

The system:

- retrieves the persisted clinical case context;
- reconstructs a longitudinal timeline;
- analyzes medication history and discrepancies;
- detects contradictions across sources;
- identifies missing follow-up;
- detects potentially unsupported claims;
- synthesizes structured investigation findings;
- validates findings and provenance;
- routes review-required findings to human review;
- generates and persists a final investigation report.

This is an **investigation system**, not a general-purpose medical chatbot.

---

## Core Information Model

The platform follows a structured evidence hierarchy:

```text
Clinical Documents
        |
        v
Structured Evidence
        |
        v
Clinical Claims
        |
        v
Timeline / Medication Context
        |
        v
Investigation Findings
        |
        v
Final Investigation Report
```

The core reasoning relationship is:

```text
Evidence -> Claim -> Finding -> Final Report
```

A **finding** is a structured investigation conclusion generated after analyzing evidence, claims, timeline events, medication information, and cross-document relationships.

It is not simply a raw fact extracted from a document.

---

## Investigation Workflow

The production workflow is orchestrated with LangGraph.

```text
START
  |
  v
Initialize Investigation
  |
  v
Retrieve Case Context
  |
  v
Timeline Analysis
  |
  v
Medication Analysis
  |
  v
Contradiction Analysis
  |
  v
Missing Follow-Up Analysis
  |
  v
Unsupported Claim Analysis
  |
  v
Synthesize Findings
  |
  v
Validate Investigation
  |
  +---------------------------+
  |                           |
  v                           v
Validation Passed        Human Review
  |                           |
  +-------------+-------------+
                |
                v
        Generate Final Report
                |
                v
        Persist Final Report
                |
                v
               END
```

The application layer and CLI are intentionally thin interfaces over this existing production workflow. They do not implement a parallel investigation pipeline.

---

## Investigation Finding Types

The current workflow supports the following finding categories:

```text
timeline_conflict
temporal_uncertainty
medication_discrepancy
contradiction
missing_follow_up
unsupported_claim
other
```

Findings are designed to remain traceable to the evidence and investigation context from which they were produced.

---

## Key Capabilities

### Longitudinal Timeline Investigation

The platform reconstructs clinical events across documents and evaluates temporal relationships.

Examples of investigation targets include:

- conflicting event dates;
- inconsistent temporal ordering;
- ambiguous timing;
- uncertainty about whether an event occurred before or after another event.

### Medication Reconciliation

Medication information is compared across the clinical case to identify discrepancies such as inconsistent medication state or documentation across sources.

Medication findings can be routed for human review when appropriate.

### Cross-Document Contradiction Detection

The system evaluates whether clinical claims made in different documents conflict with one another.

The goal is not simply text similarity or document comparison. Contradictions are represented as investigation findings linked to relevant evidence.

### Missing Follow-Up Detection

The workflow evaluates whether documented clinical events indicate follow-up actions that appear to be missing from the available case evidence.

### Unsupported Claim Detection

Potentially unsupported claims are evaluated against the structured evidence available in the investigation case.

### Evidence-Grounded Reporting

The final report is derived from structured investigation findings rather than free-form generation over raw documents alone.

### Human Review Routing

The validation layer determines whether findings require human review.

Cases can therefore follow one of two paths:

```text
Validation
    |
    +----> validation_passed
    |
    +----> human_review
```

Both paths ultimately produce the machine-generated final investigation report.

---

## Human Review Model

Human review is treated as a separate layer from machine-generated investigation output.

For a case with no review-required findings:

```text
requires_human_review = False
review_status = not_required
```

For a case requiring human review:

```text
requires_human_review = True
review_status = pending
```

The machine-generated final report remains separate from reviewer artifacts.

Human review therefore does not silently replace or overwrite the original machine investigation output.

---

## Application Architecture

The production execution path is:

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
Investigation Agents / Nodes
 |
 v
Validation + Human Review Routing
 |
 v
Final Report Generation
 |
 v
Persistence
```

The stable programmatic application interface is located under:

```text
src/clinical_investigation/application/
```

The command-line interface is:

```text
src/clinical_investigation/cli.py
```

---

## Quick Start

### 1. Python

The package currently declares:

```text
Python >=3.10,<3.13
```

The current release environment has been validated with:

```text
Python 3.12.10
Windows 11
```

### 2. Create and Activate a Virtual Environment

Example on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install the Project

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 4. Configure Environment Variables

If required for the configured runtime:

```powershell
Copy-Item .env.example .env
```

Then populate any required environment variables or API credentials.

---

## Verify the Release Environment

Before running the system, execute:

```powershell
python .\scripts\check_release_environment.py
```

The current validated release environment produces:

```text
========================================================================
STEP 10A.6 - RELEASE ENVIRONMENT / REPRODUCIBILITY CHECK
========================================================================
Overall status:                   PASS

Environment
------------------------------------------------------------------------
Python:                          3.12.10
Investigation cases:             20

Checks
------------------------------------------------------------------------
PASS python_version
PASS pyproject
PASS clinical_package
PASS import:clinical_investigation
PASS import:langgraph
PASS import:pydantic
PASS investigation_cases
PASS step_9_release_artifact
PASS step_9_status
PASS step_9_complete
PASS release_ready
PASS release_validation_issues

Failures
------------------------------------------------------------------------
None

Reproducible execution ready:    True
```

This check validates:

- Python compatibility;
- project structure;
- package availability;
- required runtime imports;
- availability of investigation cases;
- existence of the frozen Step 9 release artifact;
- Step 9 PASS status;
- Step 9 completion status;
- release-readiness status;
- zero frozen-release validation issues.

---

## CLI Usage

### List Investigation Cases

```powershell
python -m clinical_investigation.cli list-cases
```

Limit the output:

```powershell
python -m clinical_investigation.cli list-cases --limit 5
```

Example:

```text
2b36a3c6-e9d6-554e-28c3-a8244a67a553__2b36a3c6-e9d6-554e-cc63-a167ac5cab80
307ab11f-ff8e-63d6-fb00-b97e91b2234e__307ab11f-ff8e-63d6-2f59-5f0578497b62
307ab11f-ff8e-63d6-fb00-b97e91b2234e__307ab11f-ff8e-63d6-6913-5d398d138394
```

### Run an Investigation

```powershell
python -m clinical_investigation.cli investigate --case-id <CASE_ID>
```

Example:

```powershell
python -m clinical_investigation.cli investigate `
    --case-id 2b36a3c6-e9d6-554e-28c3-a8244a67a553__2b36a3c6-e9d6-554e-cc63-a167ac5cab80
```

Example output from the validated release:

```text
Clinical Investigation
========================================
Case: 2b36a3c6-e9d6-554e-28c3-a8244a67a553__2b36a3c6-e9d6-554e-cc63-a167ac5cab80
Findings: 13
Validation errors: 0
Requires human review: False
Review status: not_required
Final report: ...\final_investigation_report.json
```

### JSON CLI Output

For machine-readable output:

```powershell
python -m clinical_investigation.cli investigate `
    --case-id <CASE_ID> `
    --json
```

---

## Programmatic Usage

Applications should use the stable application interface rather than importing and invoking workflow internals directly.

```python
from clinical_investigation.application import run_investigation

result = run_investigation("<CASE_ID>")

print(result.case_id)
print(result.finding_count)
print(result.validation_error_count)
print(result.requires_human_review)
print(result.review_status)
```

The returned application-level result includes:

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

The application runner also performs basic output-contract validation before returning the result.

---

## Investigation Case Layout

A persisted investigation case is stored under:

```text
data/investigation_cases/<case_id>/
```

An investigation case represents the complete unit consumed and produced by the investigation workflow.

It includes artifacts representing areas such as:

```text
evidence
clinical claims
timeline reconstruction
medication analysis
investigation findings
final investigation report
human-review artifacts when applicable
```

The persisted final machine report is:

```text
data/investigation_cases/<case_id>/final_investigation_report.json
```

---

## Synthetic Clinical Documents

Generated encounter cases use six clinical document types:

```text
admission_note.md
progress_note.md
lab_report.md
medication_reconciliation.md
discharge_summary.md
follow_up_note.md
```

The project uses synthetic clinical data for development and release evaluation.

An important clinical-data convention is:

> A value is considered abnormal only when the source data explicitly identifies it as abnormal.

The investigation pipeline does not independently infer clinical abnormality solely from a numerical value.

---

## Data Layout

```text
data/
|
+-- raw/
|   +-- synthea_csv/
|   +-- synthea_fhir/
|
+-- interim/
|
+-- processed/
|   +-- patients/
|   +-- encounter_cases/
|
+-- generated_documents/
|   +-- encounter_cases/
|
+-- investigation_cases/
|
+-- evaluation/
```

Synthea source data is placed under:

```text
data/raw/synthea_csv/
data/raw/synthea_fhir/
```

---

## Repository Structure

```text
Agentic-Clinical-Document-Investigation/
|
+-- config/
|
+-- data/
|
+-- logs/
|
+-- notebooks/
|
+-- outputs/
|
+-- scripts/
|
+-- src/
|   +-- clinical_investigation/
|       |
|       +-- agents/
|       +-- application/
|       +-- evaluation/
|       +-- evidence/
|       +-- extraction/
|       +-- ingestion/
|       +-- investigation/
|       +-- reconciliation/
|       +-- reporting/
|       +-- retrieval/
|       +-- review/
|       +-- schemas/
|       +-- tools/
|       +-- ui/
|       +-- workflows/
|       |
|       +-- cli.py
|
+-- tests/
|
+-- pyproject.toml
|
+-- README.md
```

### Major Source Packages

#### `agents/`

LangGraph workflow, investigation nodes, routing, and agent orchestration.

#### `application/`

Stable application-level execution interface used by the CLI and future application adapters.

#### `evaluation/`

Evaluation utilities, release validation, robustness evaluation, and supporting evaluation logic.

#### `evidence/`

Evidence-related processing and data handling.

#### `extraction/`

Clinical information and fact extraction.

#### `ingestion/`

Source-data ingestion, including synthetic clinical data.

#### `investigation/`

Investigation-specific timeline, medication, and related processing.

#### `reconciliation/`

Cross-source reconciliation logic.

#### `reporting/`

Final investigation-report generation and persistence support.

#### `retrieval/`

Case-context and supporting retrieval functionality.

#### `review/`

Human-review artifacts and review-related functionality.

#### `schemas/`

Structured domain and workflow models.

#### `tools/`

Reusable workflow and agent tools.

#### `workflows/`

Supporting workflow orchestration utilities.

#### `ui/`

Optional user-interface components.

---

## Evaluation Strategy

The system has undergone a dedicated evaluation and refinement phase followed by end-to-end release acceptance testing.

Evaluation covers areas including:

- evidence-grounding integrity;
- finding validity;
- provenance consistency;
- timeline analysis;
- medication reconciliation;
- unsupported-claim analysis;
- human-review routing;
- final-report consistency;
- malformed or missing artifacts;
- schema-invalid inputs;
- provenance failures;
- controlled robustness perturbations;
- deterministic failure behavior;
- successful recovery after induced failures;
- reviewer artifact consistency.

---

## Step 8 - Evaluation & Refinement

Step 8 is complete and frozen.

The final Step 8 gate evaluated:

| Metric | Result |
|---|---:|
| Investigation cases | 20 |
| Findings | 317 |
| Review-required findings | 1 |
| Contextual findings | 316 |
| Historical defects resolved | 4 |
| Frozen Step 8 artifacts | 9 |
| Final status | PASS |

Step 8 established the quality baseline used by Step 9.

---

## Step 9 - End-to-End Acceptance Testing

Step 9 is complete and frozen.

The authoritative release-readiness artifact is:

```text
data/evaluation/step_9_final/
    step_9_release_readiness_summary.json
```

The final release gate reported:

```text
========================================================================
STEP 9D - RELEASE-READINESS FREEZE
========================================================================
Overall Step 9 status:            PASS

Release gates
------------------------------------------------------------------------
9A - End-to-end regression:       PASS
9B - Robustness:                  PASS
9C - Report / human review:       PASS

Release population
------------------------------------------------------------------------
Cases:                           20 / 20
Findings:                        317 / 317
Review-required findings:        1 / 1
Contextual findings:             316 / 316
Cases requiring review:          1 / 1

Robustness
------------------------------------------------------------------------
9B mutations:                    49 / 49
Repeated failure runs:           10 / 10
Successful recoveries:           10 / 10

Integrity
------------------------------------------------------------------------
Release validation issues:       0
Frozen artifacts:                3

Step 9 complete:                  True
Release ready:                    True
```

### Release Metrics

| Release Metric | Result |
|---|---:|
| End-to-end cases accepted | 20 / 20 |
| Findings accepted | 317 / 317 |
| Review-required findings | 1 / 1 |
| Contextual findings | 316 / 316 |
| Cases requiring review | 1 / 1 |
| Robustness mutations | 49 / 49 |
| Deterministic failure runs | 10 / 10 |
| Successful recovery runs | 10 / 10 |
| Final release validation issues | 0 |
| Release status | PASS |
| Release ready | True |

---

## Step 10 - Packaging, Documentation, and Demonstration

Step 10 packages the frozen release for reproducible execution, documentation, demonstration, and portfolio/publication use.

### Step 10A - Reproducible Execution & Release Entrypoint

Completed.

Implemented and validated:

```text
Stable application runner
        |
        v
Unit-tested execution boundary
        |
        v
Production workflow smoke test
        |
        v
Command-line interface
        |
        v
Release-environment verification
```

The release-environment check currently reports:

```text
Overall status: PASS
Reproducible execution ready: True
```

### Current Step 10 Roadmap

```text
10A - Reproducible Execution & Release Entrypoint     COMPLETE

10B - Release Documentation & Operator Guide         IN PROGRESS

10C - Architecture Documentation & Diagrams

10D - Curated Demonstration Cases

10E - CLI / API Usability

10F - Portfolio / Publication Packaging

10G - Final Packaging & Demo Freeze
```

---

## Development Quality Checks

### Ruff

Check and automatically fix supported issues:

```powershell
python -m ruff check . --fix
```

Format:

```powershell
python -m ruff format .
```

Final lint check:

```powershell
python -m ruff check .
```

### Unit Tests

```powershell
python -m pytest
```

On Windows systems where the default pytest temporary directory is not writable, use a project-local temporary directory:

```powershell
New-Item -ItemType Directory -Force .\tmp\pytest

python -m pytest `
    --basetemp=.\tmp\pytest `
    -p no:cacheprovider
```

For the application-runner unit tests specifically:

```powershell
python -m pytest .\tests\unit\test_application_runner.py -v `
    --basetemp=.\tmp\pytest-10a `
    -p no:cacheprovider
```

The current application-runner unit-test baseline is:

```text
4 passed
```

---

## Application Smoke Test

The stable application interface can be tested against the real production workflow with:

```powershell
python .\scripts\smoke_test_application_runner.py
```

This differs from the unit tests because it executes the actual production investigation graph rather than a mocked graph.

---

## Known LangGraph Warning

Depending on the installed LangGraph version, execution may display:

```text
LangChainPendingDeprecationWarning:
The default value of `allowed_objects` will change in a future version.
```

This originates from the installed LangGraph package.

It is currently treated as a non-blocking dependency warning and does not by itself indicate an investigation-workflow failure.

---

## Reproducibility Boundaries

The frozen Step 9 release is the authoritative clinical-logic acceptance baseline.

Step 10 packaging work is designed to consume that baseline rather than modify the accepted clinical investigation logic.

Release-facing interfaces therefore follow this principle:

```text
CLI / API / Demo
       |
       v
Application Interface
       |
       v
Frozen Production Workflow
```

Clinical logic should not be reimplemented independently inside CLI, API, demonstration, or documentation layers.

---

## Intended Use

This repository is a research and engineering platform for developing and evaluating evidence-grounded agentic clinical document investigation.

It demonstrates techniques for:

- longitudinal clinical-document analysis;
- evidence-grounded agentic workflows;
- clinical timeline reconstruction;
- medication reconciliation;
- cross-document contradiction detection;
- provenance-aware AI systems;
- structured validation;
- human-in-the-loop clinical AI;
- robustness evaluation;
- reproducible AI release testing.

---

## Important Limitations

This project is **not** intended to:

- independently diagnose patients;
- independently prescribe treatment;
- replace physicians, pharmacists, nurses, or other qualified clinicians;
- make autonomous clinical decisions;
- serve as a certified medical device;
- represent regulatory approval;
- claim universal clinical accuracy;
- demonstrate exhaustive real-world safety.

The current release evaluation is based on the defined synthetic investigation population and controlled test conditions.

A PASS result means the system satisfied the project's specified release acceptance criteria for that tested release.

It does **not** establish universal clinical correctness, exhaustive robustness, or suitability for unsupervised clinical use.

---

## Release Status

```text
Project:
Agentic Clinical Document Investigation Platform

Package:
agentic-clinical-document-investigation

Package version:
0.1.0

Step 8:
PASS / COMPLETE / FROZEN

Step 9:
PASS / COMPLETE / RELEASE READY / FROZEN

Step 10A:
COMPLETE

Current work:
Step 10B - Release Documentation & Operator Guide
```

The current frozen release is ready for reproducible packaging, demonstration, architecture documentation, and portfolio/publication preparation.

## Portfolio and Evaluation

This project is packaged as an evidence-grounded agentic clinical investigation system rather than a generic RAG or chatbot demo.

Key validated results include:

- 20/20 investigation cases passed the frozen evaluation baseline.
- 317 investigation findings were validated.
- 1 expected review-required case was correctly routed for human review.
- 49/49 mutation checks passed.
- 10/10 repeated failure-recovery runs succeeded.
- 25/25 CLI/API usability tests passed.

For the full technical case study, architecture rationale, safety design, evaluation results, and curated demos, see [`PORTFOLIO.md`](PORTFOLIO.md).
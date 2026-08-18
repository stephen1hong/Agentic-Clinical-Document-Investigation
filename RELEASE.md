# Release Notes

## Agentic Clinical Document Investigation Platform

Current package version:

```text
0.1.0
```

Current release state:

```text
Step 8: PASS / COMPLETE / FROZEN
Step 9: PASS / COMPLETE / RELEASE READY / FROZEN
Step 10A: COMPLETE
Step 10B: IN PROGRESS
```

---

# 1. Release Purpose

This release establishes the accepted baseline for the Agentic Clinical Document Investigation Platform.

The release includes:

- evidence-grounded clinical investigation;
- longitudinal timeline analysis;
- medication reconciliation;
- contradiction detection;
- missing follow-up detection;
- unsupported-claim detection;
- finding synthesis;
- validation;
- human-review routing;
- final investigation-report generation;
- persisted machine output;
- release-quality evaluation;
- robustness testing;
- reproducible application and CLI execution.

The frozen release is the clinical-logic baseline consumed by Step 10 packaging work.

---

# 2. Release Architecture

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
Finding Synthesis
 |
 v
Validation
 |
 +----------------------+
 |                      |
 v                      v
Validation Passed    Human Review
 |                      |
 +----------+-----------+
            |
            v
      Final Report
            |
            v
         Persist
```

Step 10 interfaces must call this accepted production path rather than implement alternate clinical reasoning logic.

---

# 3. Release Population

The frozen release population contains:

| Metric | Result |
|---|---:|
| Investigation cases | 20 |
| Total findings | 317 |
| Review-required findings | 1 |
| Contextual findings | 316 |
| Cases requiring review | 1 |

The release population is deterministic and is used as the acceptance baseline for Step 9.

---

# 4. Step 8 - Evaluation & Refinement

Step 8 established the quality baseline before end-to-end release acceptance.

Final Step 8 status:

```text
PASS
```

Final Step 8 population:

```text
Cases:                     20
Findings:                  317
Review-required findings:  1
Contextual findings:       316
Historical defects fixed:  4
Frozen artifacts:          9
```

Step 8 is complete and frozen.

The Step 8 outputs should not be modified during Step 10 packaging work.

---

# 5. Step 9 - End-to-End Acceptance Testing

Step 9 validated the frozen clinical system as an integrated release candidate.

The final acceptance structure was:

```text
9A - End-to-End Regression
9B - Robustness Testing
9C - Final Report / Human Review Acceptance
9D - Release-Readiness Freeze
```

All gates passed.

---

# 6. Step 9A - End-to-End Regression

Step 9A validated persisted release behavior across the full release population.

Final status:

```text
PASS
```

Accepted population:

```text
20 / 20 cases
317 / 317 findings
```

The regression evaluation audited persisted outputs rather than relying only on transient workflow state.

---

# 7. Step 9B - Robustness Testing

Step 9B evaluated controlled failure and perturbation scenarios.

Final robustness results:

| Metric | Result |
|---|---:|
| Robustness mutations | 49 / 49 |
| Repeated failure runs | 10 / 10 |
| Successful recovery validations | 10 / 10 |

The robustness suite included controlled scenarios involving areas such as:

- missing artifacts;
- partial artifacts;
- malformed data;
- schema-invalid data;
- provenance breakage;
- timeline perturbations;
- medication perturbations;
- deterministic failure behavior;
- recovery after induced failure.

Final status:

```text
PASS
```

---

# 8. Step 9C - Final Report and Human Review Acceptance

Step 9C validated:

- final-report consistency;
- machine output integrity;
- human-review routing;
- reviewer artifact consistency;
- review-status semantics.

Final status:

```text
PASS
```

The production review-status contract is:

For no review required:

```text
requires_human_review = False
review_status = not_required
```

For review required:

```text
requires_human_review = True
review_status = pending
```

The persisted review status is not:

```text
review_required
```

Human review remains separate from the machine-generated final investigation report.

---

# 9. Step 9D - Release-Readiness Freeze

The final Step 9 freeze reported:

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

---

# 10. Authoritative Release Artifact

The authoritative Step 9 release artifact is:

```text
data/evaluation/step_9_final/
    step_9_release_readiness_summary.json
```

This artifact is the primary machine-readable release gate.

A valid frozen release must report:

```text
status = PASS
step_9_complete = true
release_ready = true
validation_issue_count = 0
```

---

# 11. Release Environment

The release environment has been validated using:

```text
Python 3.12.10
Windows 11
```

The package currently declares:

```text
Python >=3.10,<3.13
```

The release environment checker is:

```powershell
python .\scripts\check_release_environment.py
```

The validated result is:

```text
Overall status:                   PASS
Reproducible execution ready:    True
```

The release checker verifies:

- Python version;
- project configuration;
- package structure;
- required imports;
- investigation-case availability;
- frozen Step 9 artifact existence;
- Step 9 PASS status;
- Step 9 completion;
- release-readiness status;
- zero validation issues.

---

# 12. Stable Application Interface

Step 10A introduced a stable application boundary over the production workflow.

Programmatic use:

```python
from clinical_investigation.application import run_investigation

result = run_investigation("<CASE_ID>")
```

The application result exposes:

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

The runner validates basic workflow/report consistency before returning.

---

# 13. CLI Release Interface

The release CLI is:

```text
src/clinical_investigation/cli.py
```

List cases:

```powershell
python -m clinical_investigation.cli list-cases --limit 5
```

Run one case:

```powershell
python -m clinical_investigation.cli investigate --case-id <CASE_ID>
```

Machine-readable output:

```powershell
python -m clinical_investigation.cli investigate --case-id <CASE_ID> --json
```

The CLI must remain a thin adapter over the application layer.

---

# 14. Application Runner Validation

The application wrapper has dedicated unit tests.

Current baseline:

```text
4 passed
```

Example command:

```powershell
python -m pytest .\tests\unit\test_application_runner.py -v `
    --basetemp=.\tmp\pytest-10a `
    -p no:cacheprovider
```

A real workflow smoke test is also available:

```powershell
python .\scripts\smoke_test_application_runner.py
```

The smoke test executes the actual production LangGraph rather than a mocked graph.

---

# 15. Release Artifact Boundaries

The release contains different artifact classes.

## Investigation artifacts

Stored under:

```text
data/investigation_cases/<CASE_ID>/
```

These represent case-level investigation state and outputs.

## Evaluation artifacts

Stored under:

```text
data/evaluation/
```

These represent quality, robustness, acceptance, and release-gate outputs.

## Final machine report

Stored under:

```text
data/investigation_cases/<CASE_ID>/
    final_investigation_report.json
```

## Human-review artifacts

Human-review outputs remain logically separate from the machine-generated final report.

---

# 16. Frozen Release Policy

Step 8 and Step 9 are frozen.

Step 10 packaging work may:

- add documentation;
- add release-facing interfaces;
- improve reproducibility tooling;
- create curated demonstrations;
- create architecture documentation;
- prepare portfolio/publication materials.

Step 10 packaging work should not silently alter:

- finding semantics;
- clinical reasoning rules;
- medication reconciliation logic;
- timeline logic;
- contradiction logic;
- unsupported-claim logic;
- human-review routing;
- release acceptance criteria.

Any such change should begin a new post-release development and evaluation cycle.

---

# 17. Meaning of "Release Ready"

Within this project, `release_ready = true` means:

- all defined Step 9 acceptance gates passed;
- the frozen release population was accepted;
- robustness checks passed for the defined perturbations;
- deterministic failure behavior was verified;
- recovery behavior was verified;
- final-report integrity passed;
- human-review routing passed;
- no final release-validation issues remained;
- the release can be executed reproducibly through the supported application interface.

It does not mean:

- regulatory approval;
- medical-device certification;
- universal clinical accuracy;
- exhaustive robustness;
- autonomous clinical suitability;
- validation across every healthcare institution or EHR environment.

---

# 18. Known Dependency Warning

The current environment may display:

```text
LangChainPendingDeprecationWarning
```

related to LangGraph's future `allowed_objects` default behavior.

This warning originates from an installed dependency and is currently non-blocking.

It does not by itself invalidate the release.

---

# 19. Known Development Environment Issue

On some Windows systems, pytest may not be able to access the default temporary directory or `.pytest_cache`.

The validated workaround is:

```powershell
python -m pytest `
    --basetemp=.\tmp\pytest `
    -p no:cacheprovider
```

This is treated as an environment-level test-runner issue rather than a clinical workflow defect.

---

# 20. Data and Evaluation Scope

The current release is developed and evaluated using synthetic clinical data, including Synthea-derived cases and generated clinical documents.

Generated document types include:

```text
admission_note.md
progress_note.md
lab_report.md
medication_reconciliation.md
discharge_summary.md
follow_up_note.md
```

The evaluation results therefore apply to:

- the frozen synthetic release population;
- the implemented investigation logic;
- the tested failure scenarios;
- the defined acceptance criteria.

They should not be generalized automatically to all real-world clinical environments.

---

# 21. Clinical Safety Boundary

The platform is intended for research, engineering, evaluation, demonstration, and human-in-the-loop clinical AI development.

It is not intended to:

- independently diagnose patients;
- autonomously prescribe treatment;
- replace clinician judgment;
- operate without appropriate human oversight;
- serve as a certified medical device;
- claim regulatory approval.

---

# 22. Current Packaging Phase

Current Step 10 status:

```text
10A - Reproducible Execution & Release Entrypoint
      COMPLETE

10B - Release Documentation & Operator Guide
      IN PROGRESS

10C - Architecture Documentation & Diagrams
      NOT STARTED

10D - Curated Demonstration Cases
      NOT STARTED

10E - CLI / API Usability
      NOT STARTED

10F - Portfolio / Publication Packaging
      NOT STARTED

10G - Final Packaging & Demo Freeze
      NOT STARTED
```

---

# 23. Release Documentation Set

Current documentation:

```text
README.md
QUICKSTART.md
OPERATOR_GUIDE.md
RELEASE.md
```

Planned documentation will add evaluation and architecture detail during later Step 10 work.

---

# 24. Release Summary

```text
Package:
agentic-clinical-document-investigation

Version:
0.1.0

Clinical release baseline:
Step 9

Step 8:
PASS / COMPLETE / FROZEN

Step 9:
PASS / COMPLETE / FROZEN

Release ready:
True

Release validation issues:
0

Cases:
20

Findings:
317

Robustness mutations:
49 / 49

Failure runs:
10 / 10

Recovery validations:
10 / 10

Step 10A:
COMPLETE

Current work:
Step 10B - Documentation
```


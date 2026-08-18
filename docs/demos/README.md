# Curated Demonstration Cases

This directory contains the frozen demonstration package for the Agentic Clinical Document Investigation Platform.

The demo set is designed to show three distinct production behaviors:

```text
Demo A
Typical successful investigation
        |
        v
Demo B
Evidence-rich temporal reconstruction
        |
        v
Demo C
Human-review medication discrepancy
```

All three cases use the same production investigation workflow and the same release-facing application layer.

---

# 1. Demo Overview

| Demo | Purpose | Findings | Review Status | Human Review |
|---|---|---:|---|---|
| Demo A | Typical successful investigation | 13 | `not_required` | No |
| Demo B | Evidence-rich temporal reconstruction | 15 | `not_required` | No |
| Demo C | Medication dose-conflict escalation | 19 | `pending` | Yes |

The frozen demo registry is implemented in:

```text
src/clinical_investigation/application/demo_cases.py
```

The corresponding frozen packaging manifest is:

```text
data/evaluation/step_10_demo/demo_case_manifest.json
```

---

# 2. Demo A - Typical Successful Investigation

Detailed narrative:

```text
docs/demos/demo_a.md
```

Case ID:

```text
2b36a3c6-e9d6-554e-28c3-a8244a67a553__2b36a3c6-e9d6-554e-cc63-a167ac5cab80
```

Primary characteristics:

```text
Findings:              13
Finding class:         temporal_uncertainty
Subtype:               missing_event_time
Validation errors:     0
Human review:          False
Review status:         not_required
```

Run:

```powershell
python -m clinical_investigation.cli demo demo_a
```

JSON mode:

```powershell
python -m clinical_investigation.cli demo demo_a --json
```

Use Demo A when demonstrating:

- standard end-to-end execution;
- successful validation;
- normal no-review routing;
- final-report persistence;
- the default CLI workflow.

---

# 3. Demo B - Evidence-Rich Temporal Reconstruction

Detailed narrative:

```text
docs/demos/demo_b.md
```

Case ID:

```text
86919c2e-6fcc-4756-2a76-c0e31e732109__86919c2e-6fcc-4756-d733-973edb1caccd
```

Primary characteristics:

```text
Findings:              15
Finding class:         temporal_uncertainty
Subtype:               missing_event_time
Evidence references:   86
Validation errors:     0
Human review:          False
Review status:         not_required
```

Representative artifact scale:

```text
evidence_items.json        ~751 KB
clinical_claims.json       ~380 KB
canonical_timeline.json    ~497 KB
medication_mentions.json   ~132 KB
final report               ~13 KB
```

Run:

```powershell
python -m clinical_investigation.cli demo demo_b
```

JSON mode:

```powershell
python -m clinical_investigation.cli demo demo_b --json
```

Use Demo B when demonstrating:

- evidence aggregation;
- longitudinal timeline reconstruction;
- structured artifact processing;
- evidence-to-finding consolidation;
- explicit preservation of temporal uncertainty.

---

# 4. Demo C - Human-Review Medication Discrepancy

Detailed narrative:

```text
docs/demos/demo_c.md
```

Case ID:

```text
b23188ac-9529-2450-e0b7-58adb2b38de6__b23188ac-9529-2450-612b-f5fa70a4d52d
```

Primary characteristics:

```text
Findings:                19
Temporal findings:       18
Medication findings:      1
Review findings:          1
Validation errors:        0
Human review:             True
Review status:            pending
```

Review-triggering finding:

```text
finding_type: medication_discrepancy
subtype:      dose_conflict
severity:     high
medication:   lisinopril
confidence:   1.0
```

Run:

```powershell
python -m clinical_investigation.cli demo demo_c
```

JSON mode:

```powershell
python -m clinical_investigation.cli demo demo_c --json
```

Use Demo C when demonstrating:

- medication reconciliation;
- conflicting-dose detection;
- high-priority findings;
- safety-oriented escalation;
- human-review routing;
- preservation of unresolved clinical ambiguity.

---

# 5. Recommended Presentation Sequence

For a short presentation, use the demos in this order:

```text
Demo A
   |
   v
Demo B
   |
   v
Demo C
```

This creates a progression from normal behavior to more complex evidence processing and finally to safety escalation.

---

# 6. Three-Minute Demo

For a very short technical demonstration:

## Step 1 - Introduce the architecture

Explain:

```text
Evidence
   |
   v
Clinical claims
   |
   v
Specialized investigation
   |
   v
Structured findings
   |
   v
Validation
   |
   v
Final report / human-review routing
```

## Step 2 - Run Demo A

```powershell
python -m clinical_investigation.cli demo demo_a
```

Highlight:

```text
13 findings
0 validation errors
human review = False
review_status = not_required
```

Message:

> The normal production path completes successfully and produces a persisted investigation report without manual escalation.

## Step 3 - Run Demo C

```powershell
python -m clinical_investigation.cli demo demo_c
```

Highlight:

```text
19 findings
0 validation errors
human review = True
review_status = pending
```

Message:

> When the system detects conflicting explicit lisinopril doses, it does not choose one automatically. It preserves the discrepancy and routes the case to human review.

For a three-minute demo, Demo B can be described rather than executed.

---

# 7. Five-Minute Demo

For a five-minute technical presentation, run all three cases.

## Demo A

```powershell
python -m clinical_investigation.cli demo demo_a
```

Explain normal successful execution.

## Demo B

```powershell
python -m clinical_investigation.cli demo demo_b
```

Explain that this case begins with a substantially larger evidence and timeline footprint and consolidates that information into 15 temporal findings.

## Demo C

```powershell
python -m clinical_investigation.cli demo demo_c
```

Explain the transition from contextual findings to a review-required medication discrepancy.

Close with:

```text
Routine investigation
        |
        v
Evidence-rich investigation
        |
        v
Safety escalation
```

---

# 8. Suggested Presentation Narrative

A concise portfolio narrative is:

> The platform is an evidence-grounded clinical document investigation system rather than a general-purpose clinical chatbot. It converts structured clinical evidence into claims, longitudinal timelines, medication representations, and investigation findings. The first demonstration shows the standard production path, the second shows consolidation of a large evidence base into structured temporal findings, and the third shows a safety-critical medication dose conflict that is deliberately escalated to human review rather than automatically resolved.

---

# 9. Architecture Assets

The supporting architecture diagrams are located under:

```text
docs/architecture/
```

Relevant diagrams:

```text
system_architecture.png
workflow.png
data_artifact_flow.png
human_review_flow.png
```

Suggested presentation order:

```text
system_architecture.png
        |
        v
workflow.png
        |
        v
data_artifact_flow.png
        |
        v
human_review_flow.png
```

Use the first two for technical architecture discussions.

Use `human_review_flow.png` primarily when presenting Demo C.

---

# 10. Demo Artifact Locations

Demo case artifacts are stored under:

```text
data/investigation_cases/<CASE_ID>/
```

Typical artifacts include:

```text
evidence_items.json
clinical_claims.json
canonical_timeline.json
timeline_conflicts.json
medication_mentions.json
medication_profiles.json
medication_discrepancies.json
final_investigation_report.json
reviewer_bundle.json
reviewer_report.md
```

These artifacts allow the presenter to move from the final report back to structured evidence and intermediate investigation results.

---

# 11. Machine-Readable Demo Output

All demos support JSON output:

```powershell
python -m clinical_investigation.cli demo demo_a --json
python -m clinical_investigation.cli demo demo_b --json
python -m clinical_investigation.cli demo demo_c --json
```

The JSON contract includes:

```text
demo_id
demo_title
case_id
case_dir
finding_count
validation_error_count
requires_human_review
review_status
final_report_path
```

This allows demonstrations to be integrated into scripts, REST adapters, or external presentation tooling without parsing console text.

---

# 12. Demo Safety Boundary

The demos should be described as:

```text
clinical document investigation
```

not:

```text
autonomous clinical decision-making
```

The platform can identify and structure evidence-grounded discrepancies, but it does not independently determine treatment decisions.

Demo C is the clearest example:

```text
Conflicting lisinopril doses
        |
        v
Structured discrepancy
        |
        v
Human review required
```

The machine does not decide which dose is clinically correct.

---

# 13. Known Runtime Warning

Current executions may display a LangGraph warning concerning:

```text
allowed_objects
```

This is an installed-package deprecation warning and does not indicate investigation failure.

The demo result should be evaluated using:

```text
finding_count
validation_error_count
requires_human_review
review_status
final_report_path
```

---

# 14. Frozen Demo Contract

The curated demo set is frozen as:

```text
demo_a
demo_b
demo_c
```

The CLI validates expected demo behavior against the runtime demo registry.

The unit tests also verify that the runtime registry matches:

```text
data/evaluation/step_10_demo/demo_case_manifest.json
```

Demo case identities should not be changed casually after this point.

Any future replacement of a demo case should be treated as a new packaging change and revalidated.

---

# 15. Demo Package Status

```text
Demo A narrative
COMPLETE

Demo B narrative
COMPLETE

Demo C narrative
COMPLETE

Demo CLI aliases
COMPLETE

Demo CLI unit tests
6 PASSED

Demo manifest
FROZEN
```

The next packaging step is:

```text
10D.8 - Demo Consistency Check / Freeze
```
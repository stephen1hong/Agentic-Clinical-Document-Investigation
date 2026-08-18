@'
# Demo C - Human-Review Medication Discrepancy

## Purpose

Demo C demonstrates the platform's safety-oriented human-review path. This case contains a high-severity medication discrepancy that the system deliberately does not resolve autonomously.

## Case

Case ID:

b23188ac-9529-2450-e0b7-58adb2b38de6__b23188ac-9529-2450-612b-f5fa70a4d52d

## Investigation Result

- Finding count: 19
- Temporal findings: 18
- Medication findings: 1
- Review finding count: 1
- Validation errors: 0
- Requires human review: True
- Review status: pending

## High-Priority Finding

- finding_type: medication_discrepancy
- subtype: dose_conflict
- severity: high
- medication: lisinopril
- confidence: 1.0
- requires_human_review: True

Finding title:

lisinopril has conflicting documented doses.

The system found multiple explicit dose values for the same normalized medication.

## Evidence Grounding

The high-priority medication discrepancy is supported by nine evidence references.

The system detects conflicting lisinopril dose documentation, creates a structured medication_discrepancy / dose_conflict finding, and routes the case to human review.

## Safety Boundary

The machine-generated conclusion is:

conflicting documented doses detected

It is not:

correct dose determined

The system preserves the unresolved discrepancy for qualified human review.

## Demo Command

python -m clinical_investigation.cli demo demo_c

JSON mode:

python -m clinical_investigation.cli demo demo_c --json

## Expected Result

- Findings: 19
- Validation errors: 0
- Requires human review: True
- Review status: pending

## Demo Narrative

This case demonstrates the platform's human-review safety path. Eighteen findings are contextual temporal uncertainties, while one high-severity lisinopril dose_conflict requires review. The system does not select a medication dose automatically. Instead, it preserves the discrepancy, records its supporting evidence, and leaves the case in pending review status.

## What This Demo Shows

- medication normalization
- medication discrepancy detection
- dose_conflict identification
- evidence-backed findings
- severity classification
- human-review escalation
- requires_human_review = True
- review_status = pending
- separation of contextual and high-priority findings
- preservation of machine-generated output
- human-review safety boundary

## Demo Classification

- Demo ID: demo_c
- Demo type: Human-Review Medication Discrepancy
- Primary finding class: medication_discrepancy
- Primary subtype: dose_conflict
- Medication: lisinopril
- Severity: high
- Finding count: 19
- Review finding count: 1
- Review status: pending
- Human review required: True
- Recommended use: Safety and human-review demo

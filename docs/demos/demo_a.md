@'
# Demo A - Typical Successful Investigation

## Purpose

Demo A is the default successful investigation example for the Agentic Clinical Document Investigation Platform. It demonstrates the normal end-to-end production path without human-review escalation.

## Case

Case ID:

2b36a3c6-e9d6-554e-28c3-a8244a67a553__2b36a3c6-e9d6-554e-cc63-a167ac5cab80

## Investigation Result

- Finding count: 13
- Finding type: temporal_uncertainty
- Subtype: missing_event_time
- Severity: info
- Validation errors: 0
- Requires human review: False
- Review status: not_required

All 13 findings represent temporal uncertainty where an event has no usable normalized timestamp.

## Evidence and Artifacts

Representative artifacts:

- evidence_items.json - 508862 bytes
- clinical_claims.json - 290573 bytes
- canonical_timeline.json - 367062 bytes
- medication_mentions.json - 143111 bytes
- medication_profiles.json - 34286 bytes
- timeline_conflicts.json - 9396 bytes
- final_investigation_report.json - 10007 bytes

## Demo Command

python -m clinical_investigation.cli demo demo_a

JSON mode:

python -m clinical_investigation.cli demo demo_a --json

## Expected Result

- Findings: 13
- Validation errors: 0
- Requires human review: False
- Review status: not_required

## Demo Narrative

This case demonstrates the platform's standard investigation path. The system processes structured clinical evidence and claims, reconstructs the longitudinal timeline, identifies 13 temporal_uncertainty / missing_event_time findings, validates the result without errors, and persists the final investigation report without requiring manual review.

## What This Demo Shows

- end-to-end production execution
- evidence-grounded investigation
- timeline reconstruction
- temporal uncertainty detection
- structured findings
- validation
- automatic no-review routing
- final report persistence
- release-facing CLI execution

## Demo Classification

- Demo ID: demo_a
- Demo type: Typical Successful Investigation
- Primary finding class: temporal_uncertainty
- Primary subtype: missing_event_time
- Finding count: 13
- Review status: not_required
- Human review required: False
- Recommended use: Default live CLI demo

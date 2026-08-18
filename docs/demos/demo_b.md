@'
# Demo B - Evidence-Rich Temporal Reconstruction

## Purpose

Demo B demonstrates how the Agentic Clinical Document Investigation Platform processes a large structured evidence base and consolidates it into a compact set of evidence-grounded temporal findings.

## Case

Case ID:

86919c2e-6fcc-4756-2a76-c0e31e732109__86919c2e-6fcc-4756-d733-973edb1caccd

## Investigation Result

- Finding count: 15
- Finding type: temporal_uncertainty
- Subtype: missing_event_time
- Severity: info
- Evidence references: 86
- Validation errors: 0
- Requires human review: False
- Review status: not_required

All 15 findings are temporal_uncertainty findings involving missing normalized event times.

## Evidence-Rich Characteristics

Representative artifacts:

- evidence_items.json - 750676 bytes
- canonical_timeline.json - 496891 bytes
- clinical_claims.json - 379501 bytes
- medication_mentions.json - 132103 bytes
- medication_profiles.json - 28465 bytes
- timeline_conflicts.json - 12585 bytes
- final_investigation_report.json - 13274 bytes

The candidate scan identified 86 evidence references across 15 findings, the highest evidence-reference count in the frozen 20-case demo population.

## Demo Command

python -m clinical_investigation.cli demo demo_b

JSON mode:

python -m clinical_investigation.cli demo demo_b --json

## Expected Result

- Findings: 15
- Validation errors: 0
- Requires human review: False
- Review status: not_required

## Demo Narrative

This case demonstrates evidence-rich temporal reconstruction. Approximately 751 KB of evidence items, 380 KB of clinical claims, and a 497 KB canonical timeline are processed into 15 structured temporal findings. When reliable timestamps cannot be established, the system preserves temporal uncertainty rather than inventing timestamps.

## What This Demo Shows

- evidence aggregation
- structured clinical claim processing
- longitudinal timeline reconstruction
- evidence-to-finding consolidation
- explicit temporal uncertainty
- avoidance of fabricated timestamps
- validation
- automatic no-review routing
- persisted investigation artifacts

## Demo Classification

- Demo ID: demo_b
- Demo type: Evidence-Rich Temporal Reconstruction
- Primary finding class: temporal_uncertainty
- Primary subtype: missing_event_time
- Finding count: 15
- Evidence references: 86
- Review status: not_required
- Human review required: False
- Recommended use: Architecture and evidence-grounding demo

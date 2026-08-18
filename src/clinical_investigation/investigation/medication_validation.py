"""Validate medication reconciliation outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from clinical_investigation.investigation.medication_models import (
    MedicationDiscrepancy,
    MedicationMention,
    MedicationProfile,
    MedicationReconciliationManifest,
)
from clinical_investigation.investigation.models import (
    ClinicalClaim,
    EvidenceItem,
)
from clinical_investigation.investigation.timeline_models import (
    CanonicalEvent,
)

REQUIRED_MEDICATION_FILES = {
    "medication_mentions.json",
    "medication_profiles.json",
    "medication_discrepancies.json",
    "medication_reconciliation_manifest.json",
}


def read_json(path: Path) -> Any:
    """Read JSON."""

    return json.loads(path.read_text(encoding="utf-8"))


def validate_medication_reconciliation(
    case_dir: Path,
) -> list[str]:
    """Validate one medication reconciliation output."""

    errors: list[str] = []

    existing_files = {path.name for path in case_dir.iterdir() if path.is_file()}

    missing = REQUIRED_MEDICATION_FILES - existing_files

    for filename in sorted(missing):
        errors.append(f"Missing required file: {filename}")

    if errors:
        return errors

    try:
        raw_evidence = read_json(case_dir / "evidence_items.json")
        raw_claims = read_json(case_dir / "clinical_claims.json")
        raw_timeline = read_json(case_dir / "canonical_timeline.json")
        raw_mentions = read_json(case_dir / "medication_mentions.json")
        raw_profiles = read_json(case_dir / "medication_profiles.json")
        raw_discrepancies = read_json(case_dir / "medication_discrepancies.json")
        raw_manifest = read_json(case_dir / "medication_reconciliation_manifest.json")
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON: {exc}"]

    try:
        evidence_items = [EvidenceItem.model_validate(item) for item in raw_evidence]
        claims = [ClinicalClaim.model_validate(item) for item in raw_claims]
        timeline_events = [CanonicalEvent.model_validate(item) for item in raw_timeline]
        mentions = [MedicationMention.model_validate(item) for item in raw_mentions]
        profiles = [MedicationProfile.model_validate(item) for item in raw_profiles]
        discrepancies = [MedicationDiscrepancy.model_validate(item) for item in raw_discrepancies]
        manifest = MedicationReconciliationManifest.model_validate(raw_manifest)
    except ValidationError as exc:
        return [f"Medication reconciliation schema validation failed: {exc}"]

    if manifest.case_id != case_dir.name:
        errors.append("Medication manifest case_id mismatch")

    evidence_ids = {item.evidence_id for item in evidence_items}

    claim_ids = {claim.claim_id for claim in claims}

    timeline_event_ids = {event.event_id for event in timeline_events}

    mention_ids = [mention.mention_id for mention in mentions]

    if len(mention_ids) != len(set(mention_ids)):
        errors.append("Duplicate medication mention IDs found")

    mention_id_set = set(mention_ids)

    profile_ids = [profile.profile_id for profile in profiles]

    if len(profile_ids) != len(set(profile_ids)):
        errors.append("Duplicate medication profile IDs found")

    discrepancy_ids = [item.discrepancy_id for item in discrepancies]

    if len(discrepancy_ids) != len(set(discrepancy_ids)):
        errors.append("Duplicate medication discrepancy IDs found")

    for mention in mentions:
        missing_evidence = set(mention.evidence_ids) - evidence_ids

        if missing_evidence:
            errors.append(
                f"Mention {mention.mention_id} "
                "references missing evidence: "
                f"{sorted(missing_evidence)}"
            )

        missing_claims = set(mention.source_claim_ids) - claim_ids

        if missing_claims:
            errors.append(
                f"Mention {mention.mention_id} references missing claims: {sorted(missing_claims)}"
            )

        missing_events = set(mention.timeline_event_ids) - timeline_event_ids

        if missing_events:
            errors.append(
                f"Mention {mention.mention_id} "
                "references missing timeline events: "
                f"{sorted(missing_events)}"
            )

    for profile in profiles:
        missing_mentions = set(profile.mention_ids) - mention_id_set

        if missing_mentions:
            errors.append(
                f"Profile {profile.profile_id} "
                "references missing mentions: "
                f"{sorted(missing_mentions)}"
            )

    for discrepancy in discrepancies:
        missing_mentions = set(discrepancy.mention_ids) - mention_id_set

        if missing_mentions:
            errors.append(
                f"Discrepancy "
                f"{discrepancy.discrepancy_id} "
                "references missing mentions: "
                f"{sorted(missing_mentions)}"
            )

        missing_evidence = set(discrepancy.evidence_ids) - evidence_ids

        if missing_evidence:
            errors.append(
                f"Discrepancy "
                f"{discrepancy.discrepancy_id} "
                "references missing evidence: "
                f"{sorted(missing_evidence)}"
            )

    if manifest.medication_mention_count != len(mentions):
        errors.append("Manifest medication_mention_count mismatch")

    if manifest.medication_profile_count != len(profiles):
        errors.append("Manifest medication_profile_count mismatch")

    if manifest.discrepancy_count != len(discrepancies):
        errors.append("Manifest discrepancy_count mismatch")

    return errors

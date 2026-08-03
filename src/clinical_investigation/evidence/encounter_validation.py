"""Validate encounter-centered evidence bundles."""

from pathlib import Path

from clinical_investigation.evidence.encounter_case import (
    read_json,
)

REQUIRED_FILES = {
    "case.json",
    "patient_context.json",
    "encounter.json",
    "active_conditions.json",
    "medications.json",
    "observations.json",
    "procedures.json",
    "discharge_candidates.json",
    "timeline.json",
    "summary.json",
    "manifest.json",
}


def validate_encounter_case(
    case_dir: Path,
) -> list[str]:
    """Validate one encounter evidence bundle."""

    errors: list[str] = []

    existing_files = {path.name for path in case_dir.iterdir() if path.is_file()}

    missing = REQUIRED_FILES - existing_files

    for filename in sorted(missing):
        errors.append(f"Missing file: {filename}")

    if errors:
        return errors

    case = read_json(case_dir / "case.json")
    encounter = read_json(case_dir / "encounter.json")
    timeline = read_json(case_dir / "timeline.json")
    summary = read_json(case_dir / "summary.json")
    manifest = read_json(case_dir / "manifest.json")

    case_id = case_dir.name

    if case.get("case_id") != case_id:
        errors.append("case.json case_id mismatch")

    if summary.get("case_id") != case_id:
        errors.append("summary.json case_id mismatch")

    if manifest.get("case_id") != case_id:
        errors.append("manifest.json case_id mismatch")

    encounter_id = str(encounter.get("id") or encounter.get("Id") or "")

    if encounter_id != str(case.get("encounter_id")):
        errors.append("Encounter ID mismatch")

    if not isinstance(timeline, list):
        errors.append("timeline.json must contain a list")
        return errors

    timestamps = [str(event.get("timestamp")) for event in timeline if event.get("timestamp")]

    if timestamps != sorted(timestamps):
        errors.append("Timeline is not chronologically sorted")

    event_types = {event.get("event_type") for event in timeline}

    if "encounter_start" not in event_types:
        errors.append("Timeline lacks encounter_start")

    if encounter.get("stop") and "encounter_stop" not in event_types:
        errors.append("Timeline lacks encounter_stop")

    return errors

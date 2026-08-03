"""Validate generated patient evidence packages."""

import json
from pathlib import Path
from typing import Any

REQUIRED_FILES = {
    "patient.json",
    "encounters.json",
    "conditions.json",
    "medications.json",
    "observations.json",
    "procedures.json",
    "timeline.json",
    "summary.json",
    "manifest.json",
}


class PackageValidationError(RuntimeError):
    """Raised when a patient package is invalid."""


def read_json(path: Path) -> Any:
    """Read one JSON file with useful error reporting."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PackageValidationError(f"Required file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PackageValidationError(f"Invalid JSON in {path}: {exc}") from exc


def validate_required_files(
    patient_dir: Path,
) -> list[str]:
    """Validate the required package files."""

    errors: list[str] = []

    existing_files = {path.name for path in patient_dir.iterdir() if path.is_file()}

    missing_files = REQUIRED_FILES - existing_files

    for filename in sorted(missing_files):
        errors.append(f"Missing required file: {filename}")

    return errors


def validate_patient_identity(
    patient_dir: Path,
) -> list[str]:
    """Check patient identifiers across package files."""

    errors: list[str] = []

    patient = read_json(patient_dir / "patient.json")
    manifest = read_json(patient_dir / "manifest.json")
    summary = read_json(patient_dir / "summary.json")

    folder_patient_id = patient_dir.name

    patient_id = str(patient.get("id") or patient.get("Id") or "")

    manifest_patient_id = str(manifest.get("patient_id") or "")

    summary_patient_id = str(summary.get("patient_id") or "")

    if patient_id != folder_patient_id:
        errors.append("patient.json ID does not match folder name")

    if manifest_patient_id != folder_patient_id:
        errors.append("manifest.json patient_id does not match folder name")

    if summary_patient_id != folder_patient_id:
        errors.append("summary.json patient_id does not match folder name")

    return errors


def validate_timeline(
    patient_dir: Path,
) -> list[str]:
    """Validate timeline ordering and required event fields."""

    errors: list[str] = []
    timeline = read_json(patient_dir / "timeline.json")

    if not isinstance(timeline, list):
        return ["timeline.json must contain a JSON list"]

    timestamps: list[str] = []

    required_fields = {
        "event_id",
        "event_type",
        "timestamp",
        "source_table",
        "payload",
    }

    for index, event in enumerate(timeline):
        if not isinstance(event, dict):
            errors.append(f"Timeline event {index} is not an object")
            continue

        missing = required_fields - set(event)

        if missing:
            errors.append(f"Timeline event {index} is missing: {sorted(missing)}")

        timestamp = event.get("timestamp")

        if timestamp:
            timestamps.append(str(timestamp))

    if timestamps != sorted(timestamps):
        errors.append("Timeline events are not chronologically sorted")

    return errors


def validate_patient_package(
    patient_dir: Path,
) -> list[str]:
    """Validate one generated patient package."""

    if not patient_dir.exists():
        return [f"Patient directory does not exist: {patient_dir}"]

    errors = validate_required_files(patient_dir)

    if errors:
        return errors

    errors.extend(validate_patient_identity(patient_dir))
    errors.extend(validate_timeline(patient_dir))

    return errors

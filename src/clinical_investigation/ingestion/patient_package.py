"""Build normalized longitudinal evidence packages from Synthea CSV data."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

PATIENT_TABLES = (
    "encounters",
    "conditions",
    "medications",
    "observations",
    "procedures",
)

TABLE_DATE_COLUMNS: dict[str, tuple[str, ...]] = {
    "encounters": ("START", "STOP"),
    "conditions": ("START", "STOP"),
    "medications": ("START", "STOP"),
    "observations": ("DATE",),
    "procedures": ("DATE", "STOP"),
}


class PatientPackageError(RuntimeError):
    """Raised when a patient evidence package cannot be created."""


@dataclass(frozen=True)
class PatientPackageResult:
    """Result produced after writing one patient package."""

    patient_id: str
    output_dir: Path
    record_counts: dict[str, int]
    timeline_event_count: int


def to_json_value(value: Any) -> Any:
    """Convert pandas and NumPy values into JSON-compatible values."""

    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, datetime):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            return value.item()
        except (AttributeError, ValueError):
            pass

    return value


def normalize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one raw CSV record for JSON output."""

    return {str(key).lower(): to_json_value(value) for key, value in record.items()}


def dataframe_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame into normalized JSON records."""

    return [normalize_record(record) for record in frame.to_dict(orient="records")]


def get_patient_id_column(patients: pd.DataFrame) -> str:
    """Return the patient identifier column used by patients.csv."""

    for column in ("Id", "ID"):
        if column in patients.columns:
            return column

    raise PatientPackageError("patients.csv must contain either an 'Id' or 'ID' column")


def filter_patient_records(
    frame: pd.DataFrame,
    patient_id: str,
) -> pd.DataFrame:
    """Return records belonging to one patient."""

    if "PATIENT" not in frame.columns:
        raise PatientPackageError("Expected a PATIENT column in a patient-level Synthea table")

    result = frame[frame["PATIENT"].astype(str) == str(patient_id)].copy()

    return result.reset_index(drop=False).rename(columns={"index": "_source_row"})


def normalize_date_columns(
    frame: pd.DataFrame,
    columns: Iterable[str],
) -> pd.DataFrame:
    """Convert supported date columns to ISO-8601 strings."""

    normalized = frame.copy()

    for column in columns:
        if column not in normalized.columns:
            continue

        parsed = pd.to_datetime(
            normalized[column],
            errors="coerce",
            utc=True,
        )

        normalized[column] = parsed.map(
            lambda value: value.isoformat() if not pd.isna(value) else None
        )

    return normalized


def first_available(
    record: Mapping[str, Any],
    *keys: str,
) -> Any:
    """Return the first non-empty value among candidate keys."""

    for key in keys:
        value = record.get(key)

        if value is not None and value != "":
            return value

    return None


def event_timestamp(
    table_name: str,
    record: Mapping[str, Any],
) -> Any:
    """Find the main event timestamp for a Synthea record."""

    candidates: dict[str, tuple[str, ...]] = {
        "encounters": ("START",),
        "conditions": ("START",),
        "medications": ("START",),
        "observations": ("DATE",),
        "procedures": ("DATE", "START"),
    }

    return first_available(
        record,
        *candidates.get(table_name, ()),
    )


def event_end_timestamp(
    table_name: str,
    record: Mapping[str, Any],
) -> Any:
    """Find an optional end timestamp for a Synthea record."""

    candidates: dict[str, tuple[str, ...]] = {
        "encounters": ("STOP",),
        "conditions": ("STOP",),
        "medications": ("STOP",),
        "procedures": ("STOP",),
    }

    return first_available(
        record,
        *candidates.get(table_name, ()),
    )


def event_display(
    table_name: str,
    record: Mapping[str, Any],
) -> str:
    """Create a human-readable label for a timeline event."""

    description = first_available(
        record,
        "DESCRIPTION",
        "REASONDESCRIPTION",
        "CATEGORY",
        "CODE",
    )

    if description is not None:
        return str(description)

    return table_name.rstrip("s").replace("_", " ").title()


def create_timeline_event(
    table_name: str,
    record: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Convert one Synthea record into a normalized timeline event."""

    timestamp = event_timestamp(table_name, record)

    if timestamp is None:
        return None

    event_type_map = {
        "encounters": "encounter",
        "conditions": "condition",
        "medications": "medication",
        "observations": "observation",
        "procedures": "procedure",
    }

    return {
        "event_id": (f"{table_name}:{record.get('_source_row', 'unknown')}"),
        "event_type": event_type_map[table_name],
        "timestamp": timestamp,
        "end_timestamp": event_end_timestamp(
            table_name,
            record,
        ),
        "display": event_display(table_name, record),
        "code": record.get("CODE"),
        "encounter_id": record.get("ENCOUNTER"),
        "source_table": table_name,
        "source_row": record.get("_source_row"),
        "payload": normalize_record(record),
    }


def timeline_sort_key(event: Mapping[str, Any]) -> tuple[str, str]:
    """Return a stable chronological timeline sort key."""

    timestamp = str(event.get("timestamp") or "")
    event_type = str(event.get("event_type") or "")

    return timestamp, event_type


def build_timeline(
    patient_frames: Mapping[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    """Build one chronological timeline from patient tables."""

    timeline: list[dict[str, Any]] = []

    for table_name in PATIENT_TABLES:
        frame = patient_frames[table_name]

        for record in frame.to_dict(orient="records"):
            event = create_timeline_event(table_name, record)

            if event is not None:
                timeline.append(event)

    return sorted(timeline, key=timeline_sort_key)


def build_patient_summary(
    patient_id: str,
    patient_frames: Mapping[str, pd.DataFrame],
    timeline: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a concise patient evidence summary."""

    medication_count = len(patient_frames["medications"])
    observation_count = len(patient_frames["observations"])
    encounter_count = len(patient_frames["encounters"])
    condition_count = len(patient_frames["conditions"])
    procedure_count = len(patient_frames["procedures"])

    timeline_dates = [event["timestamp"] for event in timeline if event.get("timestamp")]

    return {
        "patient_id": patient_id,
        "record_counts": {
            "encounters": encounter_count,
            "conditions": condition_count,
            "medications": medication_count,
            "observations": observation_count,
            "procedures": procedure_count,
        },
        "timeline": {
            "event_count": len(timeline),
            "first_event": (min(timeline_dates) if timeline_dates else None),
            "last_event": (max(timeline_dates) if timeline_dates else None),
        },
        "characteristics": {
            "has_multiple_encounters": encounter_count >= 2,
            "has_multiple_medications": medication_count >= 3,
            "has_observations": observation_count > 0,
            "has_procedures": procedure_count > 0,
        },
    }


def write_json(
    path: Path,
    payload: Any,
) -> None:
    """Write deterministic formatted JSON."""

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=False,
        )
        + "\n",
        encoding="utf-8",
    )


def build_patient_package(
    patient_id: str,
    tables: Mapping[str, pd.DataFrame],
    output_root: Path,
) -> PatientPackageResult:
    """Build and write one longitudinal patient evidence package."""

    patients = tables["patients"]
    patient_id_column = get_patient_id_column(patients)

    patient_matches = patients[patients[patient_id_column].astype(str) == str(patient_id)].copy()

    if patient_matches.empty:
        raise PatientPackageError(f"Patient not found in patients.csv: {patient_id}")

    if len(patient_matches) > 1:
        raise PatientPackageError(f"Duplicate patient rows found for: {patient_id}")

    patient_frames: dict[str, pd.DataFrame] = {}

    for table_name in PATIENT_TABLES:
        if table_name not in tables:
            raise PatientPackageError(f"Required Synthea table is missing: {table_name}")

        frame = filter_patient_records(
            tables[table_name],
            patient_id,
        )

        frame = normalize_date_columns(
            frame,
            TABLE_DATE_COLUMNS[table_name],
        )

        patient_frames[table_name] = frame

    normalized_patient = normalize_record(patient_matches.iloc[0].to_dict())

    timeline = build_timeline(patient_frames)

    summary = build_patient_summary(
        patient_id=patient_id,
        patient_frames=patient_frames,
        timeline=timeline,
    )

    output_dir = output_root / str(patient_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    write_json(
        output_dir / "patient.json",
        normalized_patient,
    )

    for table_name, frame in patient_frames.items():
        write_json(
            output_dir / f"{table_name}.json",
            dataframe_to_records(frame),
        )

    write_json(
        output_dir / "timeline.json",
        timeline,
    )

    write_json(
        output_dir / "summary.json",
        summary,
    )

    record_counts = {table_name: len(frame) for table_name, frame in patient_frames.items()}

    manifest = {
        "schema_version": "1.0",
        "patient_id": patient_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "Synthea CSV",
        "files": [
            "patient.json",
            "encounters.json",
            "conditions.json",
            "medications.json",
            "observations.json",
            "procedures.json",
            "timeline.json",
            "summary.json",
        ],
        "record_counts": record_counts,
        "timeline_event_count": len(timeline),
    }

    write_json(
        output_dir / "manifest.json",
        manifest,
    )

    return PatientPackageResult(
        patient_id=patient_id,
        output_dir=output_dir,
        record_counts=record_counts,
        timeline_event_count=len(timeline),
    )

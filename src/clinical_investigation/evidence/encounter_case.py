"""Build and manage encounter-centered clinical evidence bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

SUPPORTED_ENCOUNTER_CLASSES = {
    "inpatient",
    "emergency",
    "urgentcare",
    "ambulatory",
}


class EncounterCaseError(RuntimeError):
    """Raised when an encounter case cannot be created or loaded."""


@dataclass(frozen=True)
class EncounterCandidate:
    """A scored encounter candidate for clinical investigation."""

    case_id: str
    patient_id: str
    encounter_id: str
    encounter_class: str
    start: str
    stop: str | None
    description: str
    score: float
    condition_count: int
    medication_count: int
    observation_count: int
    procedure_count: int
    discharge_candidate_count: int


@dataclass(frozen=True)
class EncounterCaseResult:
    """Result produced after writing an encounter evidence bundle."""

    case_id: str
    patient_id: str
    encounter_id: str
    output_dir: Path
    timeline_event_count: int


def read_json(path: Path) -> Any:
    """Read one JSON file with useful error reporting."""

    if not path.exists():
        raise EncounterCaseError(f"Required file not found: {path}")

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EncounterCaseError(f"Invalid JSON file {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    """Write formatted JSON to disk."""

    path.parent.mkdir(parents=True, exist_ok=True)

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


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO-8601 date or datetime into UTC."""

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def normalize_encounter_class(
    encounter: dict[str, Any],
) -> str:
    """Return a normalized encounter-class value."""

    value = encounter.get("encounterclass") or encounter.get("class") or encounter.get("type") or ""

    return str(value).strip().lower()


def encounter_identifier(
    encounter: dict[str, Any],
) -> str:
    """Return the encounter's unique identifier."""

    value = encounter.get("id") or encounter.get("Id") or encounter.get("ID")

    if not value:
        raise EncounterCaseError("Encounter record does not contain an ID")

    return str(value)


def record_encounter_id(
    record: dict[str, Any],
) -> str | None:
    """Return the encounter ID referenced by a clinical record."""

    value = (
        record.get("encounter")
        or record.get("encounter_id")
        or record.get("encounterid")
        or record.get("ENCOUNTER")
    )

    return str(value) if value else None


def record_start(
    table_name: str,
    record: dict[str, Any],
) -> datetime | None:
    """Return the primary timestamp for a clinical record."""

    candidates = {
        "conditions": ("start", "date"),
        "medications": ("start", "date"),
        "observations": ("date", "start"),
        "procedures": ("date", "start"),
    }

    for field in candidates.get(table_name, ()):
        parsed = parse_datetime(record.get(field))

        if parsed is not None:
            return parsed

    return None


def record_stop(
    table_name: str,
    record: dict[str, Any],
) -> datetime | None:
    """Return the optional stop timestamp for a clinical record."""

    candidates = {
        "conditions": ("stop", "end"),
        "medications": ("stop", "end"),
        "procedures": ("stop", "end"),
    }

    for field in candidates.get(table_name, ()):
        parsed = parse_datetime(record.get(field))

        if parsed is not None:
            return parsed

    return None


def timestamps_overlap(
    record_start_time: datetime | None,
    record_stop_time: datetime | None,
    encounter_start: datetime,
    encounter_stop: datetime,
) -> bool:
    """Return whether a record overlaps an encounter window."""

    if record_start_time is None:
        return False

    effective_stop = record_stop_time or record_start_time

    return record_start_time <= encounter_stop and effective_stop >= encounter_start


def record_belongs_to_encounter(
    table_name: str,
    record: dict[str, Any],
    encounter_id: str,
    encounter_start: datetime,
    encounter_stop: datetime,
) -> bool:
    """Determine whether a record belongs to an encounter."""

    referenced_encounter = record_encounter_id(record)

    if referenced_encounter == encounter_id:
        return True

    return timestamps_overlap(
        record_start_time=record_start(table_name, record),
        record_stop_time=record_stop(table_name, record),
        encounter_start=encounter_start,
        encounter_stop=encounter_stop,
    )


def active_during_encounter(
    table_name: str,
    record: dict[str, Any],
    encounter_start: datetime,
    encounter_stop: datetime,
) -> bool:
    """Return whether a condition or medication was active."""

    start_time = record_start(table_name, record)
    stop_time = record_stop(table_name, record)

    if start_time is None:
        return False

    if stop_time is None:
        return start_time <= encounter_stop

    return timestamps_overlap(
        record_start_time=start_time,
        record_stop_time=stop_time,
        encounter_start=encounter_start,
        encounter_stop=encounter_stop,
    )


def extract_encounter_evidence(
    encounter: dict[str, Any],
    conditions: list[dict[str, Any]],
    medications: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    procedures: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Extract evidence associated with one encounter."""

    encounter_id = encounter_identifier(encounter)

    encounter_start = parse_datetime(encounter.get("start"))

    if encounter_start is None:
        raise EncounterCaseError(f"Encounter {encounter_id} has no valid start date")

    encounter_stop = parse_datetime(encounter.get("stop")) or encounter_start + timedelta(hours=24)

    active_conditions = [
        record
        for record in conditions
        if (
            record_belongs_to_encounter(
                table_name="conditions",
                record=record,
                encounter_id=encounter_id,
                encounter_start=encounter_start,
                encounter_stop=encounter_stop,
            )
            or active_during_encounter(
                table_name="conditions",
                record=record,
                encounter_start=encounter_start,
                encounter_stop=encounter_stop,
            )
        )
    ]

    encounter_medications = [
        record
        for record in medications
        if (
            record_belongs_to_encounter(
                table_name="medications",
                record=record,
                encounter_id=encounter_id,
                encounter_start=encounter_start,
                encounter_stop=encounter_stop,
            )
            or active_during_encounter(
                table_name="medications",
                record=record,
                encounter_start=encounter_start,
                encounter_stop=encounter_stop,
            )
        )
    ]

    encounter_observations = [
        record
        for record in observations
        if record_belongs_to_encounter(
            table_name="observations",
            record=record,
            encounter_id=encounter_id,
            encounter_start=encounter_start,
            encounter_stop=encounter_stop,
        )
    ]

    encounter_procedures = [
        record
        for record in procedures
        if record_belongs_to_encounter(
            table_name="procedures",
            record=record,
            encounter_id=encounter_id,
            encounter_start=encounter_start,
            encounter_stop=encounter_stop,
        )
    ]

    return {
        "active_conditions": active_conditions,
        "medications": encounter_medications,
        "observations": encounter_observations,
        "procedures": encounter_procedures,
    }


def is_abnormal_observation(
    observation: dict[str, Any],
) -> bool:
    """Detect an explicitly flagged abnormal observation."""

    searchable_fields = (
        "abnormal",
        "flag",
        "interpretation",
        "status",
    )

    abnormal_terms = {
        "abnormal",
        "high",
        "low",
        "critical",
        "positive",
    }

    for field in searchable_fields:
        value = observation.get(field)

        if value is None:
            continue

        normalized = str(value).strip().lower()

        if any(term in normalized for term in abnormal_terms):
            return True

    return False


def build_discharge_candidates(
    encounter: dict[str, Any],
    medications: list[dict[str, Any]],
    observations: list[dict[str, Any]],
    procedures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Identify events potentially relevant to discharge review."""

    encounter_id = encounter_identifier(encounter)

    encounter_start = parse_datetime(encounter.get("start"))

    if encounter_start is None:
        raise EncounterCaseError(f"Encounter {encounter_id} has no valid start date")

    encounter_stop = parse_datetime(encounter.get("stop")) or encounter_start + timedelta(hours=24)

    review_window_start = encounter_stop - timedelta(hours=48)

    candidates: list[dict[str, Any]] = []

    for observation in observations:
        event_time = record_start(
            "observations",
            observation,
        )

        if event_time is None:
            continue

        if review_window_start <= event_time <= encounter_stop:
            abnormal = is_abnormal_observation(observation)

            candidates.append(
                {
                    "candidate_type": (
                        "abnormal_observation" if abnormal else "recent_observation"
                    ),
                    "timestamp": event_time.isoformat(),
                    "display": (
                        observation.get("description") or observation.get("code") or "Observation"
                    ),
                    "source_table": "observations",
                    "source_row": observation.get("_source_row"),
                    "priority": ("high" if abnormal else "normal"),
                    "payload": observation,
                }
            )

    for medication in medications:
        start_time = record_start(
            "medications",
            medication,
        )
        stop_time = record_stop(
            "medications",
            medication,
        )

        if start_time is not None and review_window_start <= start_time <= encounter_stop:
            candidates.append(
                {
                    "candidate_type": ("medication_started_near_discharge"),
                    "timestamp": start_time.isoformat(),
                    "display": (
                        medication.get("description") or medication.get("code") or "Medication"
                    ),
                    "source_table": "medications",
                    "source_row": medication.get("_source_row"),
                    "priority": "normal",
                    "payload": medication,
                }
            )

        if stop_time is not None and review_window_start <= stop_time <= encounter_stop:
            candidates.append(
                {
                    "candidate_type": ("medication_stopped_near_discharge"),
                    "timestamp": stop_time.isoformat(),
                    "display": (
                        medication.get("description") or medication.get("code") or "Medication"
                    ),
                    "source_table": "medications",
                    "source_row": medication.get("_source_row"),
                    "priority": "high",
                    "payload": medication,
                }
            )

    for procedure in procedures:
        event_time = record_start(
            "procedures",
            procedure,
        )

        if event_time is None:
            continue

        if review_window_start <= event_time <= encounter_stop:
            candidates.append(
                {
                    "candidate_type": "recent_procedure",
                    "timestamp": event_time.isoformat(),
                    "display": (
                        procedure.get("description") or procedure.get("code") or "Procedure"
                    ),
                    "source_table": "procedures",
                    "source_row": procedure.get("_source_row"),
                    "priority": "normal",
                    "payload": procedure,
                }
            )

    candidates.append(
        {
            "candidate_type": "encounter_discharge",
            "timestamp": encounter_stop.isoformat(),
            "display": "Encounter discharge",
            "source_table": "encounters",
            "source_row": encounter.get("_source_row"),
            "priority": "normal",
            "payload": {
                "encounter_id": encounter_id,
                "stop": encounter_stop.isoformat(),
            },
        }
    )

    return sorted(
        candidates,
        key=lambda item: (
            item.get("timestamp") or "",
            item.get("candidate_type") or "",
        ),
    )


def encounter_duration_hours(
    encounter: dict[str, Any],
) -> float:
    """Calculate encounter duration in hours."""

    start = parse_datetime(encounter.get("start"))
    stop = parse_datetime(encounter.get("stop"))

    if start is None or stop is None:
        return 0.0

    duration = (stop - start).total_seconds() / 3600

    return max(duration, 0.0)


def score_encounter_candidate(
    patient_id: str,
    encounter: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    discharge_candidates: list[dict[str, Any]],
) -> EncounterCandidate:
    """Score an encounter for investigation suitability."""

    encounter_id = encounter_identifier(encounter)
    encounter_class = normalize_encounter_class(encounter)

    condition_count = len(evidence["active_conditions"])
    medication_count = len(evidence["medications"])
    observation_count = len(evidence["observations"])
    procedure_count = len(evidence["procedures"])

    abnormal_count = sum(
        1 for observation in evidence["observations"] if is_abnormal_observation(observation)
    )

    duration_hours = encounter_duration_hours(encounter)

    class_score = {
        "inpatient": 20,
        "emergency": 15,
        "urgentcare": 10,
        "ambulatory": 4,
    }.get(encounter_class, 0)

    score = float(
        class_score
        + min(condition_count, 5) * 2
        + min(medication_count, 10) * 3
        + min(observation_count, 20)
        + min(procedure_count, 5) * 2
        + abnormal_count * 5
        + min(len(discharge_candidates), 10)
    )

    if duration_hours >= 24:
        score += 5

    if medication_count >= 3:
        score += 5

    if observation_count >= 5:
        score += 5

    if encounter_class == "inpatient" and encounter.get("stop"):
        score += 10

    case_id = f"{patient_id}__{encounter_id}"

    return EncounterCandidate(
        case_id=case_id,
        patient_id=patient_id,
        encounter_id=encounter_id,
        encounter_class=encounter_class,
        start=str(encounter.get("start") or ""),
        stop=(str(encounter.get("stop")) if encounter.get("stop") else None),
        description=str(encounter.get("description") or encounter.get("code") or "Encounter"),
        score=score,
        condition_count=condition_count,
        medication_count=medication_count,
        observation_count=observation_count,
        procedure_count=procedure_count,
        discharge_candidate_count=len(discharge_candidates),
    )


def load_patient_package(
    patient_dir: Path,
) -> dict[str, Any]:
    """Load and validate one patient-level evidence package."""

    if not patient_dir.exists():
        raise EncounterCaseError(f"Patient package directory does not exist: {patient_dir}")

    required_files = {
        "patient": patient_dir / "patient.json",
        "encounters": patient_dir / "encounters.json",
        "conditions": patient_dir / "conditions.json",
        "medications": patient_dir / "medications.json",
        "observations": patient_dir / "observations.json",
        "procedures": patient_dir / "procedures.json",
        "timeline": patient_dir / "timeline.json",
        "summary": patient_dir / "summary.json",
    }

    package = {name: read_json(path) for name, path in required_files.items()}

    list_fields = (
        "encounters",
        "conditions",
        "medications",
        "observations",
        "procedures",
        "timeline",
    )

    for field in list_fields:
        if not isinstance(package[field], list):
            raise EncounterCaseError(
                f"{field}.json must contain a JSON list: {required_files[field]}"
            )

    if not isinstance(package["patient"], dict):
        raise EncounterCaseError(
            f"patient.json must contain a JSON object: {required_files['patient']}"
        )

    if not isinstance(package["summary"], dict):
        raise EncounterCaseError(
            f"summary.json must contain a JSON object: {required_files['summary']}"
        )

    return package


def discover_encounter_candidates(
    patient_packages_root: Path,
) -> list[EncounterCandidate]:
    """Discover and score encounters across patient packages."""

    if not patient_packages_root.exists():
        raise EncounterCaseError(
            f"Patient packages directory does not exist: {patient_packages_root}"
        )

    candidates: list[EncounterCandidate] = []

    patient_dirs = sorted(path for path in patient_packages_root.iterdir() if path.is_dir())

    for patient_dir in patient_dirs:
        package = load_patient_package(patient_dir)
        patient_id = patient_dir.name

        for encounter in package["encounters"]:
            if not isinstance(encounter, dict):
                continue

            encounter_class = normalize_encounter_class(encounter)

            if encounter_class not in SUPPORTED_ENCOUNTER_CLASSES:
                continue

            if not encounter.get("start"):
                continue

            evidence = extract_encounter_evidence(
                encounter=encounter,
                conditions=package["conditions"],
                medications=package["medications"],
                observations=package["observations"],
                procedures=package["procedures"],
            )

            discharge_candidates = build_discharge_candidates(
                encounter=encounter,
                medications=evidence["medications"],
                observations=evidence["observations"],
                procedures=evidence["procedures"],
            )

            candidate = score_encounter_candidate(
                patient_id=patient_id,
                encounter=encounter,
                evidence=evidence,
                discharge_candidates=(discharge_candidates),
            )

            candidates.append(candidate)

    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate.score,
            candidate.patient_id,
            candidate.start,
        ),
    )


def select_encounter_candidates(
    candidates: list[EncounterCandidate],
    target_count: int = 20,
    max_cases_per_patient: int = 2,
) -> list[EncounterCandidate]:
    """Select a diverse encounter cohort."""

    selected: list[EncounterCandidate] = []
    patient_counts: dict[str, int] = {}

    priority_classes = (
        "inpatient",
        "emergency",
        "urgentcare",
        "ambulatory",
    )

    for encounter_class in priority_classes:
        class_candidates = [
            candidate for candidate in candidates if (candidate.encounter_class == encounter_class)
        ]

        for candidate in class_candidates:
            current_count = patient_counts.get(
                candidate.patient_id,
                0,
            )

            if current_count >= max_cases_per_patient:
                continue

            selected.append(candidate)

            patient_counts[candidate.patient_id] = current_count + 1

            if len(selected) >= target_count:
                return selected

    return selected


def build_encounter_timeline(
    encounter: dict[str, Any],
    evidence: dict[str, list[dict[str, Any]]],
    discharge_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create an encounter-centered chronological timeline."""

    timeline: list[dict[str, Any]] = []

    encounter_id = encounter_identifier(encounter)

    if encounter.get("start"):
        timeline.append(
            {
                "event_id": (f"encounter:{encounter_id}:start"),
                "event_type": "encounter_start",
                "timestamp": encounter["start"],
                "display": (encounter.get("description") or "Encounter start"),
                "source_table": "encounters",
                "source_row": encounter.get("_source_row"),
                "payload": encounter,
            }
        )

    table_to_event_type = {
        "active_conditions": "condition",
        "medications": "medication",
        "observations": "observation",
        "procedures": "procedure",
    }

    table_to_source = {
        "active_conditions": "conditions",
        "medications": "medications",
        "observations": "observations",
        "procedures": "procedures",
    }

    for evidence_name, records in evidence.items():
        source_table = table_to_source[evidence_name]
        event_type = table_to_event_type[evidence_name]

        for record in records:
            timestamp = record_start(
                source_table,
                record,
            )

            if timestamp is None:
                continue

            timeline.append(
                {
                    "event_id": (f"{source_table}:{record.get('_source_row', 'unknown')}"),
                    "event_type": event_type,
                    "timestamp": timestamp.isoformat(),
                    "display": (
                        record.get("description") or record.get("code") or event_type.title()
                    ),
                    "source_table": source_table,
                    "source_row": record.get("_source_row"),
                    "payload": record,
                }
            )

    if encounter.get("stop"):
        timeline.append(
            {
                "event_id": (f"encounter:{encounter_id}:stop"),
                "event_type": "encounter_stop",
                "timestamp": encounter["stop"],
                "display": "Encounter discharge",
                "source_table": "encounters",
                "source_row": encounter.get("_source_row"),
                "payload": encounter,
            }
        )

    for candidate in discharge_candidates:
        if candidate["candidate_type"] == "encounter_discharge":
            continue

        timeline.append(
            {
                "event_id": (
                    "discharge_candidate:"
                    f"{candidate['source_table']}:"
                    f"{candidate.get('source_row', 'unknown')}:"
                    f"{candidate['candidate_type']}"
                ),
                "event_type": ("discharge_candidate"),
                "timestamp": candidate["timestamp"],
                "display": candidate["display"],
                "source_table": candidate["source_table"],
                "source_row": candidate.get("source_row"),
                "payload": candidate,
            }
        )

    return sorted(
        timeline,
        key=lambda event: (
            event.get("timestamp") or "",
            event.get("event_type") or "",
        ),
    )


def build_encounter_case_bundle(
    candidate: EncounterCandidate,
    patient_packages_root: Path,
    output_root: Path,
) -> EncounterCaseResult:
    """Build one encounter-centered evidence bundle."""

    patient_dir = patient_packages_root / candidate.patient_id

    package = load_patient_package(patient_dir)

    matching_encounters = [
        encounter
        for encounter in package["encounters"]
        if encounter_identifier(encounter) == candidate.encounter_id
    ]

    if not matching_encounters:
        raise EncounterCaseError(f"Encounter not found: {candidate.encounter_id}")

    if len(matching_encounters) > 1:
        raise EncounterCaseError(f"Duplicate encounter ID: {candidate.encounter_id}")

    encounter = matching_encounters[0]

    evidence = extract_encounter_evidence(
        encounter=encounter,
        conditions=package["conditions"],
        medications=package["medications"],
        observations=package["observations"],
        procedures=package["procedures"],
    )

    discharge_candidates = build_discharge_candidates(
        encounter=encounter,
        medications=evidence["medications"],
        observations=evidence["observations"],
        procedures=evidence["procedures"],
    )

    timeline = build_encounter_timeline(
        encounter=encounter,
        evidence=evidence,
        discharge_candidates=discharge_candidates,
    )

    output_dir = output_root / candidate.case_id
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    patient_context = {
        "patient_id": candidate.patient_id,
        "patient": package["patient"],
        "longitudinal_summary": package["summary"],
    }

    case_metadata = {
        "case_id": candidate.case_id,
        "patient_id": candidate.patient_id,
        "encounter_id": (candidate.encounter_id),
        "encounter_class": (candidate.encounter_class),
        "selection_score": candidate.score,
        "investigation_scope": [
            "admission_context",
            "active_conditions",
            "medication_reconciliation",
            "laboratory_and_observation_review",
            "procedure_review",
            "discharge_candidate_review",
        ],
    }

    summary = {
        "case_id": candidate.case_id,
        "patient_id": candidate.patient_id,
        "encounter_id": (candidate.encounter_id),
        "encounter_class": (candidate.encounter_class),
        "start": candidate.start,
        "stop": candidate.stop,
        "description": candidate.description,
        "record_counts": {
            "active_conditions": len(evidence["active_conditions"]),
            "medications": len(evidence["medications"]),
            "observations": len(evidence["observations"]),
            "procedures": len(evidence["procedures"]),
            "discharge_candidates": len(discharge_candidates),
            "timeline_events": len(timeline),
        },
    }

    write_json(
        output_dir / "case.json",
        case_metadata,
    )
    write_json(
        output_dir / "patient_context.json",
        patient_context,
    )
    write_json(
        output_dir / "encounter.json",
        encounter,
    )
    write_json(
        output_dir / "active_conditions.json",
        evidence["active_conditions"],
    )
    write_json(
        output_dir / "medications.json",
        evidence["medications"],
    )
    write_json(
        output_dir / "observations.json",
        evidence["observations"],
    )
    write_json(
        output_dir / "procedures.json",
        evidence["procedures"],
    )
    write_json(
        output_dir / "discharge_candidates.json",
        discharge_candidates,
    )
    write_json(
        output_dir / "timeline.json",
        timeline,
    )
    write_json(
        output_dir / "summary.json",
        summary,
    )

    manifest = {
        "schema_version": "1.0",
        "case_id": candidate.case_id,
        "patient_id": candidate.patient_id,
        "encounter_id": (candidate.encounter_id),
        "generated_at": (datetime.now(UTC).isoformat()),
        "source": ("Synthea patient-level evidence package"),
        "files": [
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
        ],
        "record_counts": summary["record_counts"],
    }

    write_json(
        output_dir / "manifest.json",
        manifest,
    )

    return EncounterCaseResult(
        case_id=candidate.case_id,
        patient_id=candidate.patient_id,
        encounter_id=candidate.encounter_id,
        output_dir=output_dir,
        timeline_event_count=len(timeline),
    )

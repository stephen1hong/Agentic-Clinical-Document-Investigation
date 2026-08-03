"""Tests for encounter-centered evidence bundles."""

from clinical_investigation.evidence.encounter_case import (
    build_discharge_candidates,
    extract_encounter_evidence,
    is_abnormal_observation,
)


def test_explicit_abnormal_observation() -> None:
    observation = {
        "description": "Potassium",
        "value": 5.8,
        "units": "mmol/L",
        "interpretation": "High",
    }

    assert is_abnormal_observation(observation) is True


def test_extract_encounter_evidence() -> None:
    encounter = {
        "id": "encounter-001",
        "start": "2026-01-01T10:00:00+00:00",
        "stop": "2026-01-03T10:00:00+00:00",
        "encounterclass": "inpatient",
    }

    conditions = [
        {
            "_source_row": 1,
            "patient": "patient-001",
            "encounter": "encounter-001",
            "start": "2026-01-01T10:00:00+00:00",
            "description": "Example condition",
        }
    ]

    medications = [
        {
            "_source_row": 2,
            "patient": "patient-001",
            "encounter": "encounter-001",
            "start": "2026-01-01T12:00:00+00:00",
            "stop": "2026-01-03T08:00:00+00:00",
            "description": "Example medication",
        }
    ]

    observations = [
        {
            "_source_row": 3,
            "patient": "patient-001",
            "encounter": "encounter-001",
            "date": "2026-01-02T08:00:00+00:00",
            "description": "Example observation",
        }
    ]

    procedures = [
        {
            "_source_row": 4,
            "patient": "patient-001",
            "encounter": "encounter-001",
            "date": "2026-01-02T12:00:00+00:00",
            "description": "Example procedure",
        }
    ]

    evidence = extract_encounter_evidence(
        encounter=encounter,
        conditions=conditions,
        medications=medications,
        observations=observations,
        procedures=procedures,
    )

    assert len(evidence["active_conditions"]) == 1
    assert len(evidence["medications"]) == 1
    assert len(evidence["observations"]) == 1
    assert len(evidence["procedures"]) == 1


def test_build_discharge_candidates() -> None:
    encounter = {
        "id": "encounter-001",
        "start": "2026-01-01T10:00:00+00:00",
        "stop": "2026-01-03T10:00:00+00:00",
    }

    observations = [
        {
            "_source_row": 3,
            "date": "2026-01-03T08:00:00+00:00",
            "description": "Potassium",
            "interpretation": "High",
        }
    ]

    candidates = build_discharge_candidates(
        encounter=encounter,
        medications=[],
        observations=observations,
        procedures=[],
    )

    candidate_types = {candidate["candidate_type"] for candidate in candidates}

    assert "abnormal_observation" in candidate_types
    assert "encounter_discharge" in candidate_types

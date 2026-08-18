from __future__ import annotations

import json
import shutil
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from clinical_investigation.investigation.medication_reconciliation import (
    reconcile_case_medications,
)
from clinical_investigation.investigation.timeline_reconstruction import (
    reconstruct_case_timeline,
)
from evaluate_end_to_end_regression import (
    load_json,
    sha256_file,
    validate_one_case,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

STEP_9A_PATH = PROJECT_ROOT / "data" / "evaluation" / "step_9a" / "end_to_end_regression.json"

STEP_9B1_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "step_9b1" / "missing_partial_artifact_robustness.json"
)

STEP_9B2_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "step_9b2" / "malformed_schema_robustness.json"
)

STEP_9B3_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "step_9b3" / "provenance_breakage_robustness.json"
)

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "step_9b4"

WORKSPACE_DIR = OUTPUT_DIR / "workspace"

OUTPUT_PATH = OUTPUT_DIR / "medication_timeline_perturbation_robustness.json"


TIMELINE_FILENAME = "canonical_timeline.json"

MENTIONS_FILENAME = "medication_mentions.json"

PROFILES_FILENAME = "medication_profiles.json"

DISCREPANCIES_FILENAME = "medication_discrepancies.json"

MANIFEST_FILENAME = "medication_reconciliation_manifest.json"


MutationFunction = Callable[
    [Path],
    dict[str, Any],
]


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
        )
        + "\n",
        encoding="utf-8",
    )


def artifact_status(
    artifact: dict[str, Any],
) -> str | None:
    """Read evaluation status."""

    for key in (
        "status",
        "overall_status",
    ):
        value = artifact.get(key)

        if isinstance(
            value,
            str,
        ):
            return value

    return None


def load_required_pass(
    path: Path,
    name: str,
) -> dict[str, Any]:
    """Load required PASS artifact."""

    if not path.exists():
        raise FileNotFoundError(f"{name} artifact not found: {path}")

    payload = load_json(path)

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(f"{name} artifact must contain a JSON object.")

    status = artifact_status(payload)

    if status != "PASS":
        raise RuntimeError(f"{name} must be PASS; found {status!r}.")

    return payload


def case_dirs() -> list[Path]:
    """Return investigation case directories."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    return sorted(path for path in CASE_ROOT.iterdir() if path.is_dir())


def as_dict_list(
    value: Any,
) -> list[dict[str, Any]]:
    """Return list of JSON objects."""

    if not isinstance(
        value,
        list,
    ):
        return []

    return [
        item
        for item in value
        if isinstance(
            item,
            dict,
        )
    ]


def canonicalize(
    value: Any,
) -> str:
    """Canonical JSON representation."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
    )


def model_list_to_json(
    values: list[Any],
) -> list[dict[str, Any]]:
    """Convert Pydantic model list to JSON-compatible dictionaries."""

    return [value.model_dump(mode="json") for value in values]


def reconstruct_expected_timeline(
    case_dir: Path,
) -> list[dict[str, Any]]:
    """Regenerate canonical timeline from upstream evidence and claims."""

    result = reconstruct_case_timeline(case_dir)

    if not isinstance(
        result,
        tuple,
    ):
        raise TypeError("reconstruct_case_timeline() did not return a tuple.")

    if not result:
        raise ValueError("reconstruct_case_timeline() returned an empty tuple.")

    events = result[0]

    if not isinstance(
        events,
        list,
    ):
        raise TypeError("First reconstruct_case_timeline() return value must be the event list.")

    return model_list_to_json(events)


def reconstruct_expected_medication(
    case_dir: Path,
) -> dict[str, list[dict[str, Any]]]:
    """Regenerate medication artifacts from current upstream inputs."""

    (
        mentions,
        profiles,
        discrepancies,
    ) = reconcile_case_medications(case_dir)

    return {
        MENTIONS_FILENAME: (model_list_to_json(mentions)),
        PROFILES_FILENAME: (model_list_to_json(profiles)),
        DISCREPANCIES_FILENAME: (model_list_to_json(discrepancies)),
    }


def medication_manifest_count_issues(
    case_dir: Path,
) -> list[dict[str, Any]]:
    """Validate medication manifest artifact counts."""

    manifest = load_json(case_dir / MANIFEST_FILENAME)

    if not isinstance(
        manifest,
        dict,
    ):
        return [
            {
                "category": ("invalid_medication_manifest"),
                "detail": ("Medication manifest is not a JSON object."),
            }
        ]

    counts = {
        "medication_mention_count": len(as_dict_list(load_json(case_dir / MENTIONS_FILENAME))),
        "medication_profile_count": len(as_dict_list(load_json(case_dir / PROFILES_FILENAME))),
        "discrepancy_count": len(as_dict_list(load_json(case_dir / DISCREPANCIES_FILENAME))),
    }

    issues: list[dict[str, Any]] = []

    for (
        field,
        actual,
    ) in counts.items():
        persisted = manifest.get(field)

        if persisted != actual:
            issues.append(
                {
                    "category": ("medication_manifest_count_mismatch"),
                    "detail": (f"{field}={persisted}; actual={actual}."),
                }
            )

    return issues


def timeline_regeneration_issues(
    case_dir: Path,
) -> list[dict[str, Any]]:
    """Compare persisted timeline to production reconstruction."""

    persisted = load_json(case_dir / TIMELINE_FILENAME)

    expected = reconstruct_expected_timeline(case_dir)

    if canonicalize(persisted) == canonicalize(expected):
        return []

    return [
        {
            "category": ("timeline_reconstruction_mismatch"),
            "detail": (
                "Persisted canonical timeline "
                "does not match deterministic "
                "reconstruction from evidence "
                "and clinical claims."
            ),
        }
    ]


def medication_regeneration_issues(
    case_dir: Path,
) -> list[dict[str, Any]]:
    """Compare persisted medication artifacts to production reconciliation."""

    expected = reconstruct_expected_medication(case_dir)

    issues: list[dict[str, Any]] = []

    for (
        filename,
        expected_payload,
    ) in expected.items():
        persisted = load_json(case_dir / filename)

        if canonicalize(persisted) == canonicalize(expected_payload):
            continue

        issues.append(
            {
                "category": ("medication_reconciliation_mismatch"),
                "artifact": (filename),
                "detail": (f"{filename} does not match deterministic medication reconciliation."),
            }
        )

    return issues


def semantic_issues(
    case_dir: Path,
) -> list[dict[str, Any]]:
    """Run deterministic timeline and medication consistency checks."""

    issues: list[dict[str, Any]] = []

    issues.extend(timeline_regeneration_issues(case_dir))

    issues.extend(medication_regeneration_issues(case_dir))

    issues.extend(medication_manifest_count_issues(case_dir))

    return issues


def semantic_categories(
    issues: list[dict[str, Any]],
) -> set[str]:
    """Return issue categories."""

    return {
        str(
            issue.get(
                "category",
                "",
            )
        )
        for issue in issues
        if issue.get("category")
    }


def is_complete_candidate(
    case_dir: Path,
) -> bool:
    """Check required 9B.4 artifacts."""

    required = (
        TIMELINE_FILENAME,
        MENTIONS_FILENAME,
        PROFILES_FILENAME,
        DISCREPANCIES_FILENAME,
        MANIFEST_FILENAME,
        "evidence_items.json",
        "clinical_claims.json",
        "final_investigation_report.json",
        "reviewer_bundle.json",
        "reviewer_report.md",
    )

    return all((case_dir / filename).exists() for filename in required)


def choose_primary_case() -> Path:
    """Choose a complete medication-rich baseline case."""

    candidates: list[tuple[int, int, str, Path]] = []

    for case_dir in case_dirs():
        if not is_complete_candidate(case_dir):
            continue

        mentions = as_dict_list(load_json(case_dir / MENTIONS_FILENAME))

        timeline = as_dict_list(load_json(case_dir / TIMELINE_FILENAME))

        if not mentions:
            continue

        candidates.append(
            (
                len(mentions),
                len(timeline),
                case_dir.name,
                case_dir,
            )
        )

    if not candidates:
        raise RuntimeError("No medication-rich reference case found.")

    candidates.sort(reverse=True)

    return candidates[0][3]


def choose_discrepancy_case() -> Path:
    """Choose a case containing at least one medication discrepancy."""

    candidates: list[tuple[int, str, Path]] = []

    for case_dir in case_dirs():
        if not is_complete_candidate(case_dir):
            continue

        discrepancies = as_dict_list(load_json(case_dir / DISCREPANCIES_FILENAME))

        if not discrepancies:
            continue

        candidates.append(
            (
                len(discrepancies),
                case_dir.name,
                case_dir,
            )
        )

    if not candidates:
        raise RuntimeError("No case with medication discrepancies found.")

    candidates.sort(reverse=True)

    return candidates[0][2]


def choose_medication_timeline_case() -> Path:
    """Choose case with medication timeline events."""

    medication_event_types = {
        "medication_start",
        "medication_stop",
        "medication_status",
    }

    candidates: list[tuple[int, str, Path]] = []

    for case_dir in case_dirs():
        if not is_complete_candidate(case_dir):
            continue

        timeline = as_dict_list(load_json(case_dir / TIMELINE_FILENAME))

        medication_events = [
            event
            for event in timeline
            if str(
                event.get(
                    "event_type",
                    "",
                )
            )
            in medication_event_types
        ]

        if not medication_events:
            continue

        candidates.append(
            (
                len(medication_events),
                case_dir.name,
                case_dir,
            )
        )

    if not candidates:
        raise RuntimeError("No case with medication timeline events found.")

    candidates.sort(reverse=True)

    return candidates[0][2]


def case_hashes(
    case_dir: Path,
) -> dict[str, str]:
    """Hash all persisted files in one production case."""

    return {path.name: (sha256_file(path)) for path in (case_dir.iterdir()) if path.is_file()}


def copy_case(
    *,
    source_case: Path,
    mutation_name: str,
) -> Path:
    """Copy production case into isolated workspace."""

    mutation_root = WORKSPACE_DIR / mutation_name

    mutation_case = mutation_root / source_case.name

    if mutation_root.exists():
        shutil.rmtree(mutation_root)

    mutation_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copytree(
        source_case,
        mutation_case,
    )

    return mutation_case


def first_timeline_event(
    case_dir: Path,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
]:
    """Return timeline payload and one event."""

    timeline = as_dict_list(load_json(case_dir / TIMELINE_FILENAME))

    if not timeline:
        raise RuntimeError("Timeline contains no events.")

    return (
        timeline,
        timeline[0],
    )


def first_timed_event(
    case_dir: Path,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
]:
    """Return one timeline event with normalized time."""

    timeline = as_dict_list(load_json(case_dir / TIMELINE_FILENAME))

    for event in timeline:
        if event.get("normalized_time"):
            return (
                timeline,
                event,
            )

    raise RuntimeError("No timed event found.")


def first_medication_event(
    case_dir: Path,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
]:
    """Return one medication timeline event."""

    timeline = as_dict_list(load_json(case_dir / TIMELINE_FILENAME))

    for event in timeline:
        if str(
            event.get(
                "event_type",
                "",
            )
        ) in {
            "medication_start",
            "medication_stop",
            "medication_status",
        }:
            return (
                timeline,
                event,
            )

    raise RuntimeError("No medication timeline event found.")


#
# Timeline mutations
#


def mutate_timeline_timestamp(
    case_dir: Path,
) -> dict[str, Any]:
    """Alter one persisted normalized timestamp."""

    (
        timeline,
        event,
    ) = first_timed_event(case_dir)

    original = str(event["normalized_time"])

    parsed = datetime.fromisoformat(
        original.replace(
            "Z",
            "+00:00",
        )
    )

    mutated = (parsed + timedelta(days=7)).isoformat()

    event["normalized_time"] = mutated

    write_json(
        case_dir / TIMELINE_FILENAME,
        timeline,
    )

    return {
        "artifact": (TIMELINE_FILENAME),
        "event_id": (event.get("event_id")),
        "original_value": (original),
        "mutated_value": (mutated),
    }


def mutate_timeline_subject(
    case_dir: Path,
) -> dict[str, Any]:
    """Alter one timeline event subject."""

    (
        timeline,
        event,
    ) = first_timeline_event(case_dir)

    original = str(
        event.get(
            "subject",
            "",
        )
    )

    event["subject"] = original + " [9B4 PERTURBED]"

    write_json(
        case_dir / TIMELINE_FILENAME,
        timeline,
    )

    return {
        "artifact": (TIMELINE_FILENAME),
        "event_id": (event.get("event_id")),
        "original_value": (original),
        "mutated_value": (event["subject"]),
    }


def mutate_timeline_case_id(
    case_dir: Path,
) -> dict[str, Any]:
    """Alter one timeline event case identity."""

    (
        timeline,
        event,
    ) = first_timeline_event(case_dir)

    original = str(
        event.get(
            "case_id",
            "",
        )
    )

    event["case_id"] = "9b4-corrupted-case-id"

    write_json(
        case_dir / TIMELINE_FILENAME,
        timeline,
    )

    return {
        "artifact": (TIMELINE_FILENAME),
        "event_id": (event.get("event_id")),
        "original_value": (original),
        "mutated_value": (event["case_id"]),
    }


def mutate_timeline_event_type(
    case_dir: Path,
) -> dict[str, Any]:
    """Alter one timeline event type to another valid type."""

    (
        timeline,
        event,
    ) = first_timeline_event(case_dir)

    original = str(
        event.get(
            "event_type",
            "",
        )
    )

    replacement = "procedure_event" if original != "procedure_event" else "observation_result"

    event["event_type"] = replacement

    write_json(
        case_dir / TIMELINE_FILENAME,
        timeline,
    )

    return {
        "artifact": (TIMELINE_FILENAME),
        "event_id": (event.get("event_id")),
        "original_value": (original),
        "mutated_value": (replacement),
    }


#
# Medication mutations
#


def mutate_medication_mention_dose(
    case_dir: Path,
) -> dict[str, Any]:
    """Alter one persisted medication dose."""

    path = case_dir / MENTIONS_FILENAME

    mentions = as_dict_list(load_json(path))

    target = next(
        (mention for mention in mentions if mention.get("dose")),
        None,
    )

    if target is None:
        target = mentions[0]

    original = target.get("dose")

    target["dose"] = "999 MG"

    write_json(
        path,
        mentions,
    )

    return {
        "artifact": (MENTIONS_FILENAME),
        "mention_id": (target.get("mention_id")),
        "original_value": (original),
        "mutated_value": ("999 MG"),
    }


def mutate_medication_mention_status(
    case_dir: Path,
) -> dict[str, Any]:
    """Alter one medication lifecycle status."""

    path = case_dir / MENTIONS_FILENAME

    mentions = as_dict_list(load_json(path))

    if not mentions:
        raise RuntimeError("No medication mentions found.")

    target = mentions[0]

    original = str(
        target.get(
            "status",
            "",
        )
    )

    replacement = "stopped" if original != "stopped" else "active"

    target["status"] = replacement

    write_json(
        path,
        mentions,
    )

    return {
        "artifact": (MENTIONS_FILENAME),
        "mention_id": (target.get("mention_id")),
        "original_value": (original),
        "mutated_value": (replacement),
    }


def mutate_medication_profile_dose(
    case_dir: Path,
) -> dict[str, Any]:
    """Alter one profile's aggregated dose set."""

    path = case_dir / PROFILES_FILENAME

    profiles = as_dict_list(load_json(path))

    if not profiles:
        raise RuntimeError("No medication profiles found.")

    target = profiles[0]

    original = list(
        target.get(
            "doses",
            [],
        )
        or []
    )

    target["doses"] = [
        *original,
        "999 MG",
    ]

    write_json(
        path,
        profiles,
    )

    return {
        "artifact": (PROFILES_FILENAME),
        "profile_id": (target.get("profile_id")),
        "original_value": (original),
        "mutated_value": (target["doses"]),
    }


def mutate_medication_profile_case_id(
    case_dir: Path,
) -> dict[str, Any]:
    """Alter medication profile case identity."""

    path = case_dir / PROFILES_FILENAME

    profiles = as_dict_list(load_json(path))

    if not profiles:
        raise RuntimeError("No medication profiles found.")

    target = profiles[0]

    original = str(
        target.get(
            "case_id",
            "",
        )
    )

    target["case_id"] = "9b4-corrupted-case-id"

    write_json(
        path,
        profiles,
    )

    return {
        "artifact": (PROFILES_FILENAME),
        "profile_id": (target.get("profile_id")),
        "original_value": (original),
        "mutated_value": (target["case_id"]),
    }


def mutate_remove_medication_mention(
    case_dir: Path,
) -> dict[str, Any]:
    """Remove one persisted medication mention."""

    path = case_dir / MENTIONS_FILENAME

    mentions = as_dict_list(load_json(path))

    if not mentions:
        raise RuntimeError("No medication mentions found.")

    removed = mentions.pop()

    write_json(
        path,
        mentions,
    )

    return {
        "artifact": (MENTIONS_FILENAME),
        "removed_id": (removed.get("mention_id")),
    }


def mutate_remove_medication_profile(
    case_dir: Path,
) -> dict[str, Any]:
    """Remove one persisted medication profile."""

    path = case_dir / PROFILES_FILENAME

    profiles = as_dict_list(load_json(path))

    if not profiles:
        raise RuntimeError("No medication profiles found.")

    removed = profiles.pop()

    write_json(
        path,
        profiles,
    )

    return {
        "artifact": (PROFILES_FILENAME),
        "removed_id": (removed.get("profile_id")),
    }


def mutate_discrepancy_payload(
    case_dir: Path,
) -> dict[str, Any]:
    """Alter one persisted medication discrepancy."""

    path = case_dir / DISCREPANCIES_FILENAME

    discrepancies = as_dict_list(load_json(path))

    if not discrepancies:
        raise RuntimeError("Reference case contains no medication discrepancy.")

    target = discrepancies[0]

    original = str(
        target.get(
            "summary",
            "",
        )
    )

    target["summary"] = original + " [9B4 PERTURBED]"

    write_json(
        path,
        discrepancies,
    )

    return {
        "artifact": (DISCREPANCIES_FILENAME),
        "discrepancy_id": (target.get("discrepancy_id")),
        "original_value": (original),
        "mutated_value": (target["summary"]),
    }


def mutate_manifest_count(
    case_dir: Path,
) -> dict[str, Any]:
    """Alter persisted medication manifest count."""

    path = case_dir / MANIFEST_FILENAME

    manifest = load_json(path)

    if not isinstance(
        manifest,
        dict,
    ):
        raise ValueError("Medication manifest must contain a JSON object.")

    original = manifest.get("medication_mention_count")

    manifest["medication_mention_count"] = 999999

    write_json(
        path,
        manifest,
    )

    return {
        "artifact": (MANIFEST_FILENAME),
        "field": ("medication_mention_count"),
        "original_value": (original),
        "mutated_value": (999999),
    }


def mutate_medication_timeline_timestamp(
    case_dir: Path,
) -> dict[str, Any]:
    """Perturb medication timeline event without refreshing medication layer."""

    (
        timeline,
        event,
    ) = first_medication_event(case_dir)

    original = event.get("normalized_time")

    if original:
        parsed = datetime.fromisoformat(
            str(original).replace(
                "Z",
                "+00:00",
            )
        )

        mutated = (parsed + timedelta(days=30)).isoformat()
    else:
        mutated = datetime(
            2099,
            1,
            1,
            tzinfo=UTC,
        ).isoformat()

    event["normalized_time"] = mutated

    write_json(
        case_dir / TIMELINE_FILENAME,
        timeline,
    )

    return {
        "artifact": (TIMELINE_FILENAME),
        "event_id": (event.get("event_id")),
        "event_type": (event.get("event_type")),
        "original_value": (original),
        "mutated_value": (mutated),
    }


MUTATION_PLAN = (
    (
        "timeline_timestamp_shift",
        "primary",
        mutate_timeline_timestamp,
        {
            "timeline_reconstruction_mismatch",
        },
    ),
    (
        "timeline_subject_change",
        "primary",
        mutate_timeline_subject,
        {
            "timeline_reconstruction_mismatch",
        },
    ),
    (
        "timeline_case_id_change",
        "primary",
        mutate_timeline_case_id,
        {
            "timeline_reconstruction_mismatch",
            "case_id_mismatch",
        },
    ),
    (
        "timeline_event_type_change",
        "primary",
        mutate_timeline_event_type,
        {
            "timeline_reconstruction_mismatch",
        },
    ),
    (
        "medication_mention_dose_change",
        "primary",
        mutate_medication_mention_dose,
        {
            "medication_reconciliation_mismatch",
        },
    ),
    (
        "medication_mention_status_change",
        "primary",
        mutate_medication_mention_status,
        {
            "medication_reconciliation_mismatch",
        },
    ),
    (
        "medication_profile_dose_change",
        "primary",
        mutate_medication_profile_dose,
        {
            "medication_reconciliation_mismatch",
        },
    ),
    (
        "medication_profile_case_id_change",
        "primary",
        mutate_medication_profile_case_id,
        {
            "medication_reconciliation_mismatch",
            "case_id_mismatch",
        },
    ),
    (
        "remove_medication_mention",
        "primary",
        mutate_remove_medication_mention,
        {
            "medication_reconciliation_mismatch",
            "medication_manifest_count_mismatch",
        },
    ),
    (
        "remove_medication_profile",
        "primary",
        mutate_remove_medication_profile,
        {
            "medication_reconciliation_mismatch",
            "medication_manifest_count_mismatch",
        },
    ),
    (
        "medication_discrepancy_payload_change",
        "discrepancy",
        mutate_discrepancy_payload,
        {
            "medication_reconciliation_mismatch",
        },
    ),
    (
        "medication_manifest_count_change",
        "primary",
        mutate_manifest_count,
        {
            "medication_manifest_count_mismatch",
        },
    ),
    (
        "timeline_medication_cross_layer_shift",
        "medication_timeline",
        mutate_medication_timeline_timestamp,
        {
            "timeline_reconstruction_mismatch",
            "medication_reconciliation_mismatch",
        },
    ),
)


def run_mutation(
    *,
    source_case: Path,
    mutation_name: str,
    mutation_function: MutationFunction,
    expected_categories: set[str],
) -> dict[str, Any]:
    """Run one 9B.4 perturbation."""

    mutation_case = copy_case(
        source_case=source_case,
        mutation_name=mutation_name,
    )

    try:
        mutation_metadata = mutation_function(mutation_case)
    except Exception as exc:
        return {
            "mutation": (mutation_name),
            "status": "FAIL",
            "setup_error": (f"{type(exc).__name__}: {exc}"),
            "expected_categories": (sorted(expected_categories)),
            "detected_categories": [],
            "expected_categories_detected": (False),
            "failed_closed": False,
        }

    acceptance_issues: list[dict[str, Any]]

    try:
        (
            case_result,
            acceptance_issues,
        ) = validate_one_case(mutation_case)
    except Exception as exc:
        return {
            "mutation": (mutation_name),
            "status": "FAIL",
            "validator_exception": (f"{type(exc).__name__}: {exc}"),
            "expected_categories": (sorted(expected_categories)),
            "detected_categories": [],
            "expected_categories_detected": (False),
            "failed_closed": False,
            **mutation_metadata,
        }

    try:
        deterministic_issues = semantic_issues(mutation_case)
    except Exception as exc:
        return {
            "mutation": (mutation_name),
            "status": "FAIL",
            "semantic_validator_exception": (f"{type(exc).__name__}: {exc}"),
            "expected_categories": (sorted(expected_categories)),
            "detected_categories": [],
            "expected_categories_detected": (False),
            "failed_closed": False,
            **mutation_metadata,
        }

    all_issues = [
        *acceptance_issues,
        *deterministic_issues,
    ]

    detected = semantic_categories(all_issues)

    expected_detected = expected_categories <= detected

    failed_closed = bool(all_issues)

    passed = expected_detected and failed_closed

    return {
        "mutation": (mutation_name),
        "case_id": (source_case.name),
        "status": ("PASS" if passed else "FAIL"),
        "acceptance_validator_status": (case_result.get("status")),
        "expected_categories": (sorted(expected_categories)),
        "detected_categories": (sorted(detected)),
        "expected_categories_detected": (expected_detected),
        "failed_closed": (failed_closed),
        "acceptance_issue_count": (len(acceptance_issues)),
        "deterministic_issue_count": (len(deterministic_issues)),
        "issues": (all_issues),
        **mutation_metadata,
    }


def validate_clean_baseline(
    case_dir: Path,
) -> None:
    """Require deterministic regeneration equality before mutation testing."""

    issues = semantic_issues(case_dir)

    if issues:
        raise RuntimeError(f"Reference case does not match deterministic regeneration: {issues}")

    (
        case_result,
        acceptance_issues,
    ) = validate_one_case(case_dir)

    if case_result.get("status") != "PASS" or acceptance_issues:
        raise RuntimeError("Reference case does not pass the Step 9A acceptance validator.")


def main() -> int:
    """Run Step 9B.4."""

    load_required_pass(
        STEP_9A_PATH,
        "Step 9A",
    )

    load_required_pass(
        STEP_9B1_PATH,
        "Step 9B.1",
    )

    load_required_pass(
        STEP_9B2_PATH,
        "Step 9B.2",
    )

    load_required_pass(
        STEP_9B3_PATH,
        "Step 9B.3",
    )

    primary_case = choose_primary_case()

    discrepancy_case = choose_discrepancy_case()

    medication_timeline_case = choose_medication_timeline_case()

    source_cases = {
        "primary": (primary_case),
        "discrepancy": (discrepancy_case),
        "medication_timeline": (medication_timeline_case),
    }

    unique_cases = {case.name: case for case in (source_cases.values())}

    #
    # Validate the unmodified persisted
    # baseline against production regeneration
    # before perturbing anything.
    #
    for case_dir in unique_cases.values():
        validate_clean_baseline(case_dir)

    baseline_hashes = {
        case_id: case_hashes(case_dir)
        for (
            case_id,
            case_dir,
        ) in unique_cases.items()
    }

    if WORKSPACE_DIR.exists():
        shutil.rmtree(WORKSPACE_DIR)

    WORKSPACE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results: list[dict[str, Any]] = []

    for (
        mutation_name,
        source_key,
        mutation_function,
        expected_categories,
    ) in MUTATION_PLAN:
        results.append(
            run_mutation(
                source_case=(source_cases[source_key]),
                mutation_name=(mutation_name),
                mutation_function=(mutation_function),
                expected_categories=(expected_categories),
            )
        )

    production_cases_unchanged = all(
        case_hashes(case_dir) == baseline_hashes[case_id]
        for (
            case_id,
            case_dir,
        ) in unique_cases.items()
    )

    passed = sum(1 for result in results if result.get("status") == "PASS")

    failed = len(results) - passed

    all_failed_closed = all(
        bool(
            result.get(
                "failed_closed",
                False,
            )
        )
        for result in results
    )

    all_expected_detected = all(
        bool(
            result.get(
                "expected_categories_detected",
                False,
            )
        )
        for result in results
    )

    category_counts: Counter[str] = Counter()

    for result in results:
        for category in (
            result.get(
                "detected_categories",
                [],
            )
            or []
        ):
            category_counts[str(category)] += 1

    timeline_results = [
        result
        for result in results
        if str(
            result.get(
                "mutation",
                "",
            )
        ).startswith("timeline_")
    ]

    medication_results = [result for result in results if (result not in timeline_results)]

    overall_pass = all(
        (
            len(results) == len(MUTATION_PLAN),
            failed == 0,
            all_failed_closed,
            all_expected_detected,
            production_cases_unchanged,
        )
    )

    status = "PASS" if overall_pass else "FAIL"

    output = {
        "schema_version": ("1.0"),
        "acceptance_step": ("9B.4"),
        "acceptance_name": ("Medication and Timeline Perturbation Robustness"),
        "status": (status),
        "evaluated_at": (datetime.now(UTC).isoformat()),
        "prerequisites": {
            "9A": "PASS",
            "9B.1": "PASS",
            "9B.2": "PASS",
            "9B.3": "PASS",
        },
        "reference_cases": {
            key: value.name
            for (
                key,
                value,
            ) in source_cases.items()
        },
        "mutation_summary": {
            "mutations": (len(results)),
            "passed": (passed),
            "failed": (failed),
            "all_failed_closed": (all_failed_closed),
            "all_expected_categories_detected": (all_expected_detected),
            "production_cases_unchanged": (production_cases_unchanged),
            "detected_issue_categories": dict(sorted(category_counts.items())),
        },
        "domain_summary": {
            "timeline": {
                "mutations": (len(timeline_results)),
                "passed": sum(1 for result in timeline_results if result.get("status") == "PASS"),
            },
            "medication": {
                "mutations": (len(medication_results)),
                "passed": sum(1 for result in medication_results if result.get("status") == "PASS"),
            },
        },
        "acceptance_criteria": {
            "timeline_perturbations_detected": all(
                result.get("status") == "PASS" for result in timeline_results
            ),
            "medication_perturbations_detected": all(
                result.get("status") == "PASS" for result in medication_results
            ),
            "deterministic_regeneration_used": (True),
            "production_artifacts_immutable": (production_cases_unchanged),
        },
        "mutation_results": (results),
        "ready_for_9b5": (overall_pass),
        "methodological_notes": [
            (
                "Timeline perturbations are "
                "evaluated against production "
                "reconstruct_case_timeline()."
            ),
            (
                "Medication perturbations are "
                "evaluated against production "
                "reconcile_case_medications()."
            ),
            (
                "This avoids relying only on "
                "the Step 9A structural validator "
                "for semantic artifact drift."
            ),
            ("All mutations are applied only to isolated workspace copies."),
            (
                "Unmodified reference cases "
                "must exactly match deterministic "
                "production regeneration before "
                "mutation testing begins."
            ),
        ],
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("STEP 9B.4 — MEDICATION / TIMELINE PERTURBATION ROBUSTNESS")
    print("=" * 72)

    print(f"Overall status:                   {status}")

    print()
    print("Prerequisites")
    print("-" * 72)

    print("Step 9A status:                   PASS")

    print("Step 9B.1 status:                 PASS")

    print("Step 9B.2 status:                 PASS")

    print("Step 9B.3 status:                 PASS")

    print()
    print("Mutation results")
    print("-" * 72)

    print(f"Mutations executed:               {len(results)}")

    print(f"Mutations passed:                 {passed}")

    print(f"Mutations failed:                 {failed}")

    print(f"All failed closed:                {all_failed_closed}")

    print(f"Expected categories detected:    {all_expected_detected}")

    print()
    print("Domain results")
    print("-" * 72)

    print(
        "Timeline passed / total:          "
        f"{sum(1 for result in timeline_results if result.get('status') == 'PASS')}"
        f" / {len(timeline_results)}"
    )

    print(
        "Medication passed / total:        "
        f"{sum(1 for result in medication_results if result.get('status') == 'PASS')}"
        f" / {len(medication_results)}"
    )

    print()
    print("Safety")
    print("-" * 72)

    print(f"Production cases unchanged:       {production_cases_unchanged}")

    print()
    print(f"Ready for Step 9B.5:              {overall_pass}")

    print()
    print("Saved Step-9B.4 result to:")

    print(OUTPUT_PATH)

    if WORKSPACE_DIR.exists():
        shutil.rmtree(WORKSPACE_DIR)

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())

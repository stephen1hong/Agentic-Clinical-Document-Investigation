from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "medication"
OUTPUT_PATH = OUTPUT_DIR / "medication_discrepancy_detection_quality.json"


ACTIVE_LIKE_STATUSES = {
    "active",
    "continued",
}

STOPPED_LIKE_STATUSES = {
    "stopped",
    "discontinued",
}


EVALUATED_DISCREPANCY_TYPES = {
    "conflicting_status",
    "stopped_but_later_continued",
    "missing_at_discharge",
    "discharge_only_medication",
    "dose_conflict",
    "frequency_conflict",
    "route_conflict",
    "ambiguous_status",
}


def load_json(path: Path) -> Any:
    """Load JSON from disk."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def load_list(
    path: Path,
) -> list[dict[str, Any]]:
    """Load an artifact that must contain a JSON list."""

    raw = load_json(path)

    if not isinstance(raw, list):
        raise ValueError(f"{path} must contain a JSON list.")

    return [item for item in raw if isinstance(item, dict)]


def nonempty_string(
    value: Any,
) -> str | None:
    """Return cleaned string or None."""

    if not isinstance(value, str):
        return None

    cleaned = value.strip()

    return cleaned or None


def string_values(
    value: Any,
) -> list[str]:
    """Normalize a scalar/list value to strings."""

    if isinstance(value, str):
        return [value] if value else []

    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]

    return []


def normalized_attribute(
    value: str,
) -> str:
    """Match production medication-attribute normalization."""

    return re.sub(
        r"\s+",
        "",
        value.lower(),
    )


def parse_datetime(
    value: Any,
) -> datetime | None:
    """Parse a medication event time."""

    text = nonempty_string(value)

    if text is None:
        return None

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    return datetime.fromisoformat(text)


def mention_status(
    mention: dict[str, Any],
) -> str:
    """Return normalized mention status."""

    return str(
        mention.get(
            "status",
            "unknown",
        )
    ).lower()


def is_timeline_mention(
    mention: dict[str, Any],
) -> bool:
    """Return whether a mention came from the timeline."""

    return (
        str(
            mention.get(
                "source_type",
                "",
            )
        ).lower()
        == "timeline"
    )


def expected_conflicting_status(
    mentions: list[dict[str, Any]],
) -> bool:
    """Mirror production conflicting-status semantics."""

    comparable = [
        mention
        for mention in mentions
        if (
            not is_timeline_mention(mention)
            and mention_status(mention) in (ACTIVE_LIKE_STATUSES | STOPPED_LIKE_STATUSES)
        )
    ]

    active = [mention for mention in comparable if mention_status(mention) in ACTIVE_LIKE_STATUSES]

    stopped = [
        mention for mention in comparable if mention_status(mention) in STOPPED_LIKE_STATUSES
    ]

    return bool(active and stopped)


def expected_stopped_but_later_continued(
    mentions: list[dict[str, Any]],
) -> int:
    """
    Count expected stopped-but-later-continued discrepancies.

    Production can emit one discrepancy for each timed stop
    that has one or more later active-like mentions.
    """

    stops: list[
        tuple[
            dict[str, Any],
            datetime,
        ]
    ] = []

    active: list[
        tuple[
            dict[str, Any],
            datetime,
        ]
    ] = []

    for mention in mentions:
        event_time = parse_datetime(mention.get("event_time"))

        if event_time is None:
            continue

        status = mention_status(mention)

        if status in STOPPED_LIKE_STATUSES:
            stops.append(
                (
                    mention,
                    event_time,
                )
            )

        elif status in ACTIVE_LIKE_STATUSES:
            active.append(
                (
                    mention,
                    event_time,
                )
            )

    count = 0

    for _, stop_time in stops:
        later_active = [mention for mention, active_time in active if active_time > stop_time]

        if later_active:
            count += 1

    return count


def expected_missing_at_discharge(
    mentions: list[dict[str, Any]],
) -> bool:
    """Mirror production missing-at-discharge semantics."""

    pre_discharge_active = [
        mention
        for mention in mentions
        if (
            mention_status(mention) in ACTIVE_LIKE_STATUSES
            and mention.get("document_type") != "discharge_summary"
        )
    ]

    discharge_mentions = [
        mention for mention in mentions if mention.get("document_type") == "discharge_summary"
    ]

    return bool(pre_discharge_active and not discharge_mentions)


def expected_discharge_only(
    mentions: list[dict[str, Any]],
) -> bool:
    """Mirror production discharge-only semantics."""

    discharge_mentions = [
        mention for mention in mentions if mention.get("document_type") == "discharge_summary"
    ]

    non_discharge_mentions = [
        mention for mention in mentions if mention.get("document_type") != "discharge_summary"
    ]

    return bool(discharge_mentions and not non_discharge_mentions)


def expected_attribute_conflict(
    mentions: list[dict[str, Any]],
    field: str,
) -> bool:
    """Detect production-style dose/frequency/route conflicts."""

    values = {
        normalized_attribute(value)
        for mention in mentions
        if (value := nonempty_string(mention.get(field)))
    }

    return len(values) > 1


def expected_ambiguous_status(
    mentions: list[dict[str, Any]],
) -> bool:
    """Mirror production ambiguous-status semantics."""

    if not mentions:
        return False

    return all(mention_status(mention) == "unknown" for mention in mentions)


def expected_keys_for_profile(
    *,
    case_id: str,
    profile: dict[str, Any],
    mentions: list[dict[str, Any]],
) -> list[
    tuple[
        str,
        str,
        str,
    ]
]:
    """
    Create expected discrepancy keys.

    Key:
        case_id,
        normalized medication key,
        discrepancy type

    Most production rules emit at most one discrepancy per
    profile/type. stopped_but_later_continued is handled
    separately because production may emit multiple records
    before stable-ID deduplication.
    """

    medication_key = str(
        profile.get(
            "normalized_key",
            "",
        )
    )

    expected: list[
        tuple[
            str,
            str,
            str,
        ]
    ] = []

    if expected_conflicting_status(mentions):
        expected.append(
            (
                case_id,
                medication_key,
                "conflicting_status",
            )
        )

    stopped_later_count = expected_stopped_but_later_continued(mentions)

    if stopped_later_count:
        #
        # Production stable IDs can differ by summary only
        # at the profile/type level here, so for quality
        # evaluation we treat the rule as one semantic
        # profile-level discrepancy.
        #
        expected.append(
            (
                case_id,
                medication_key,
                "stopped_but_later_continued",
            )
        )

    if expected_missing_at_discharge(mentions):
        expected.append(
            (
                case_id,
                medication_key,
                "missing_at_discharge",
            )
        )

    if expected_discharge_only(mentions):
        expected.append(
            (
                case_id,
                medication_key,
                "discharge_only_medication",
            )
        )

    if expected_attribute_conflict(
        mentions,
        "dose",
    ):
        expected.append(
            (
                case_id,
                medication_key,
                "dose_conflict",
            )
        )

    if expected_attribute_conflict(
        mentions,
        "frequency",
    ):
        expected.append(
            (
                case_id,
                medication_key,
                "frequency_conflict",
            )
        )

    if expected_attribute_conflict(
        mentions,
        "route",
    ):
        expected.append(
            (
                case_id,
                medication_key,
                "route_conflict",
            )
        )

    if expected_ambiguous_status(mentions):
        expected.append(
            (
                case_id,
                medication_key,
                "ambiguous_status",
            )
        )

    return expected


def emitted_key(
    discrepancy: dict[str, Any],
) -> tuple[
    str,
    str,
    str,
]:
    """Create normalized emitted discrepancy key."""

    return (
        str(
            discrepancy.get(
                "case_id",
                "",
            )
        ),
        str(
            discrepancy.get(
                "medication_key",
                "",
            )
        ),
        str(
            discrepancy.get(
                "discrepancy_type",
                "",
            )
        ),
    )


def wilson_interval(
    successes: int,
    total: int,
    *,
    z: float = 1.959963984540054,
) -> tuple[
    float,
    float,
]:
    """Compute Wilson binomial confidence interval."""

    if total == 0:
        return (
            1.0,
            1.0,
        )

    p = successes / total

    z2 = z * z

    denominator = 1.0 + z2 / total

    center = (p + z2 / (2.0 * total)) / denominator

    margin = z * ((p * (1.0 - p) / total + z2 / (4.0 * total * total)) ** 0.5) / denominator

    return (
        max(
            0.0,
            center - margin,
        ),
        min(
            1.0,
            center + margin,
        ),
    )


def main() -> int:
    """Run simplified Step 8C.2c medication detection evaluation."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    cases_scanned = 0
    mentions_scanned = 0
    profiles_scanned = 0
    emitted_discrepancy_count = 0

    expected_keys: set[
        tuple[
            str,
            str,
            str,
        ]
    ] = set()

    emitted_keys: set[
        tuple[
            str,
            str,
            str,
        ]
    ] = set()

    expected_by_type: Counter[str] = Counter()

    emitted_by_type: Counter[str] = Counter()

    duplicate_emitted_keys: list[dict[str, Any]] = []

    unsupported_emitted_types: list[dict[str, Any]] = []

    expected_context: dict[
        tuple[
            str,
            str,
            str,
        ],
        dict[str, Any],
    ] = {}

    emitted_context: dict[
        tuple[
            str,
            str,
            str,
        ],
        dict[str, Any],
    ] = {}

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        mention_path = case_dir / "medication_mentions.json"

        profile_path = case_dir / "medication_profiles.json"

        discrepancy_path = case_dir / "medication_discrepancies.json"

        if not all(
            path.exists()
            for path in (
                mention_path,
                profile_path,
                discrepancy_path,
            )
        ):
            continue

        cases_scanned += 1
        case_id = case_dir.name

        mentions = load_list(mention_path)

        profiles = load_list(profile_path)

        discrepancies = load_list(discrepancy_path)

        mentions_scanned += len(mentions)

        profiles_scanned += len(profiles)

        emitted_discrepancy_count += len(discrepancies)

        mentions_by_key: defaultdict[
            str,
            list[dict[str, Any]],
        ] = defaultdict(list)

        for mention in mentions:
            normalized_key = str(
                mention.get(
                    "normalized_key",
                    "",
                )
            )

            mentions_by_key[normalized_key].append(mention)

        for profile in profiles:
            normalized_key = str(
                profile.get(
                    "normalized_key",
                    "",
                )
            )

            profile_mentions = mentions_by_key.get(
                normalized_key,
                [],
            )

            for key in expected_keys_for_profile(
                case_id=case_id,
                profile=profile,
                mentions=profile_mentions,
            ):
                expected_keys.add(key)

                expected_by_type[key[2]] += 1

                expected_context[key] = {
                    "case_id": case_id,
                    "medication_key": (normalized_key),
                    "medication_name": (profile.get("normalized_name")),
                    "discrepancy_type": (key[2]),
                    "mention_count": (len(profile_mentions)),
                    "statuses": sorted({mention_status(mention) for mention in profile_mentions}),
                    "doses": sorted(
                        {
                            str(mention["dose"])
                            for mention in profile_mentions
                            if mention.get("dose")
                        }
                    ),
                    "frequencies": sorted(
                        {
                            str(mention["frequency"])
                            for mention in profile_mentions
                            if mention.get("frequency")
                        }
                    ),
                    "routes": sorted(
                        {
                            str(mention["route"])
                            for mention in profile_mentions
                            if mention.get("route")
                        }
                    ),
                    "document_types": sorted(
                        {
                            str(mention["document_type"])
                            for mention in profile_mentions
                            if mention.get("document_type")
                        }
                    ),
                }

        for discrepancy in discrepancies:
            key = emitted_key(discrepancy)

            discrepancy_type = key[2]

            if discrepancy_type not in EVALUATED_DISCREPANCY_TYPES:
                unsupported_emitted_types.append(
                    {
                        "case_id": (case_id),
                        "discrepancy_id": (discrepancy.get("discrepancy_id")),
                        "discrepancy_type": (discrepancy_type),
                    }
                )

                continue

            if key in emitted_keys:
                duplicate_emitted_keys.append(
                    {
                        "case_id": (case_id),
                        "medication_key": (key[1]),
                        "discrepancy_type": (key[2]),
                        "discrepancy_id": (discrepancy.get("discrepancy_id")),
                    }
                )

            emitted_keys.add(key)

            emitted_by_type[discrepancy_type] += 1

            emitted_context[key] = {
                "case_id": (case_id),
                "discrepancy_id": (discrepancy.get("discrepancy_id")),
                "medication_key": (discrepancy.get("medication_key")),
                "medication_name": (discrepancy.get("medication_name")),
                "discrepancy_type": (discrepancy_type),
                "conflicting_values": (string_values(discrepancy.get("conflicting_values"))),
                "mention_ids": (string_values(discrepancy.get("mention_ids"))),
                "evidence_ids": (string_values(discrepancy.get("evidence_ids"))),
            }

    true_positive_keys = expected_keys & emitted_keys

    false_positive_keys = emitted_keys - expected_keys

    false_negative_keys = expected_keys - emitted_keys

    true_positives = len(true_positive_keys)

    false_positives = len(false_positive_keys)

    false_negatives = len(false_negative_keys)

    precision_denominator = true_positives + false_positives

    recall_denominator = true_positives + false_negatives

    precision = true_positives / precision_denominator if precision_denominator else 1.0

    recall = true_positives / recall_denominator if recall_denominator else 1.0

    f1 = 0.0 if precision + recall == 0 else (2.0 * precision * recall / (precision + recall))

    precision_ci = wilson_interval(
        true_positives,
        precision_denominator,
    )

    recall_ci = wilson_interval(
        true_positives,
        recall_denominator,
    )

    false_positives_detail = [emitted_context[key] for key in sorted(false_positive_keys)]

    false_negatives_detail = [expected_context[key] for key in sorted(false_negative_keys)]

    by_type: dict[
        str,
        dict[str, Any],
    ] = {}

    for discrepancy_type in sorted(EVALUATED_DISCREPANCY_TYPES):
        type_expected = {key for key in expected_keys if key[2] == discrepancy_type}

        type_emitted = {key for key in emitted_keys if key[2] == discrepancy_type}

        type_tp = len(type_expected & type_emitted)

        type_fp = len(type_emitted - type_expected)

        type_fn = len(type_expected - type_emitted)

        by_type[discrepancy_type] = {
            "expected": len(type_expected),
            "emitted": len(type_emitted),
            "true_positives": (type_tp),
            "false_positives": (type_fp),
            "false_negatives": (type_fn),
        }

    integrity_issues = len(duplicate_emitted_keys) + len(unsupported_emitted_types)

    detection_issues = false_positives + false_negatives

    status = "PASS" if (integrity_issues == 0 and detection_issues == 0) else "FAIL"

    output = {
        "schema_version": "1.0",
        "evaluation_step": ("simplified_8C.2c"),
        "status": status,
        "evaluation_method": (
            "Independent artifact-level reconstruction "
            "of expected medication discrepancies from "
            "persisted medication mentions and profiles "
            "using the documented production rule "
            "semantics, compared with emitted "
            "medication_discrepancies.json."
        ),
        "cases_scanned": (cases_scanned),
        "population": {
            "medication_mentions": (mentions_scanned),
            "medication_profiles": (profiles_scanned),
            "emitted_discrepancy_records": (emitted_discrepancy_count),
            "expected_semantic_discrepancies": (len(expected_keys)),
            "emitted_semantic_discrepancies": (len(emitted_keys)),
        },
        "overall_metrics": {
            "true_positives": (true_positives),
            "false_positives": (false_positives),
            "false_negatives": (false_negatives),
            "precision": (precision),
            "precision_percentage": (precision * 100.0),
            "recall": (recall),
            "recall_percentage": (recall * 100.0),
            "f1": (f1),
            "f1_percentage": (f1 * 100.0),
            "precision_wilson_95": [
                precision_ci[0],
                precision_ci[1],
            ],
            "recall_wilson_95": [
                recall_ci[0],
                recall_ci[1],
            ],
        },
        "by_discrepancy_type": (by_type),
        "integrity": {
            "duplicate_emitted_semantic_keys": (len(duplicate_emitted_keys)),
            "unsupported_emitted_types": (len(unsupported_emitted_types)),
            "integrity_issue_count": (integrity_issues),
        },
        "issues": {
            "false_positives": (false_positives_detail),
            "false_negatives": (false_negatives_detail),
            "duplicate_emitted_semantic_keys": (duplicate_emitted_keys),
            "unsupported_emitted_types": (unsupported_emitted_types),
        },
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
    print("SIMPLIFIED STEP 8C.2c MEDICATION DISCREPANCY DETECTION QUALITY")
    print("=" * 72)

    print(f"Status:                         {status}")

    print(f"Cases scanned:                  {cases_scanned}")

    print(f"Medication mentions:            {mentions_scanned}")

    print(f"Medication profiles:            {profiles_scanned}")

    print()
    print("Discrepancy population")
    print("-" * 72)

    print(f"Expected discrepancies:         {len(expected_keys)}")

    print(f"Emitted discrepancies:          {len(emitted_keys)}")

    print()
    print("Detection quality")
    print("-" * 72)

    print(f"True positives:                 {true_positives}")

    print(f"False positives:                {false_positives}")

    print(f"False negatives:                {false_negatives}")

    print(f"Precision:                      {precision * 100.0:.1f}%")

    print(f"Recall:                         {recall * 100.0:.1f}%")

    print(f"F1:                             {f1 * 100.0:.1f}%")

    print()
    print("By discrepancy type")
    print("-" * 72)

    for discrepancy_type in sorted(EVALUATED_DISCREPANCY_TYPES):
        metrics = by_type[discrepancy_type]

        print(f"{discrepancy_type}")

        print(f"  emitted / expected:           {metrics['emitted']} / {metrics['expected']}")

        print(
            "  TP / FP / FN:                 "
            f"{metrics['true_positives']} / "
            f"{metrics['false_positives']} / "
            f"{metrics['false_negatives']}"
        )

    print()
    print("Integrity")
    print("-" * 72)

    print(f"Duplicate semantic keys:        {len(duplicate_emitted_keys)}")

    print(f"Unsupported emitted types:      {len(unsupported_emitted_types)}")

    print()
    print("Saved evaluation to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "medication"
OUTPUT_PATH = OUTPUT_DIR / "medication_reconciliation_correctness.json"


WRAPPER_PATTERN = re.compile(
    r"medication(?:started|stopped)neardischarge",
    flags=re.IGNORECASE,
)

UTC_DATE_PATTERN = re.compile(
    r"(?:january|february|march|april|may|june|"
    r"july|august|september|october|november|december)"
    r"\s+\d{1,2},?\s+\d{4}\s+at\s+\d{1,2}:\d{2}\s+utc",
    flags=re.IGNORECASE,
)


def load_json(path: Path) -> Any:
    """Load JSON from disk."""

    return json.loads(path.read_text(encoding="utf-8"))


def load_records(
    path: Path,
) -> list[dict[str, Any]]:
    """Load a JSON list."""

    raw = load_json(path)

    if not isinstance(raw, list):
        raise ValueError(f"{path.name} must contain a list")

    return [item for item in raw if isinstance(item, dict)]


def string_values(value: Any) -> set[str]:
    """Normalize a scalar/list value to strings."""

    if isinstance(value, str):
        return {value} if value else set()

    if isinstance(value, list):
        return {item for item in value if isinstance(item, str) and item}

    return set()


def normalize_compare(value: Any) -> str:
    """Normalize text only for equality comparison."""

    if not isinstance(value, str):
        return ""

    return " ".join(value.casefold().split())


def main() -> int:
    """Run simplified Step 8C.2b."""

    cases_scanned = 0
    mentions_scanned = 0
    profiles_scanned = 0

    duplicate_profile_keys: list[dict[str, Any]] = []
    orphan_mentions: list[dict[str, Any]] = []
    profile_membership_mismatches: list[dict[str, Any]] = []
    mention_key_mismatches: list[dict[str, Any]] = []

    raw_wrapper_leakage: list[dict[str, Any]] = []
    normalized_wrapper_leakage: list[dict[str, Any]] = []
    normalized_datetime_leakage: list[dict[str, Any]] = []

    raw_name_mismatches: list[dict[str, Any]] = []
    status_mismatches: list[dict[str, Any]] = []
    dose_mismatches: list[dict[str, Any]] = []
    route_mismatches: list[dict[str, Any]] = []
    document_type_mismatches: list[dict[str, Any]] = []

    mentions_by_key_total: Counter[str] = Counter()

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        mention_path = case_dir / "medication_mentions.json"

        profile_path = case_dir / "medication_profiles.json"

        if not mention_path.exists() or not profile_path.exists():
            continue

        cases_scanned += 1

        case_id = case_dir.name

        mentions = load_records(mention_path)

        profiles = load_records(profile_path)

        mentions_scanned += len(mentions)

        profiles_scanned += len(profiles)

        mention_index = {
            str(mention["mention_id"]): mention for mention in mentions if mention.get("mention_id")
        }

        mentions_by_key: defaultdict[
            str,
            list[dict[str, Any]],
        ] = defaultdict(list)

        for mention in mentions:
            key = str(
                mention.get(
                    "normalized_key",
                    "",
                )
            )

            mentions_by_key[key].append(mention)

            mentions_by_key_total[key] += 1

            raw_name = str(
                mention.get(
                    "medication_name_raw",
                    "",
                )
            )

            normalized_name = str(
                mention.get(
                    "normalized_name",
                    "",
                )
            )

            normalized_key = str(
                mention.get(
                    "normalized_key",
                    "",
                )
            )

            #
            # Wrapper text is allowed in raw generated
            # source text, but must never survive into
            # normalized medication identity fields.
            #
            if WRAPPER_PATTERN.search(normalized_name) or WRAPPER_PATTERN.search(normalized_key):
                normalized_wrapper_leakage.append(
                    {
                        "case_id": case_id,
                        "mention_id": (mention.get("mention_id")),
                        "medication_name_raw": (raw_name),
                        "normalized_name": (normalized_name),
                        "normalized_key": (normalized_key),
                    }
                )

            if UTC_DATE_PATTERN.search(normalized_name) or UTC_DATE_PATTERN.search(normalized_key):
                normalized_datetime_leakage.append(
                    {
                        "case_id": case_id,
                        "mention_id": (mention.get("mention_id")),
                        "normalized_name": (normalized_name),
                        "normalized_key": (normalized_key),
                    }
                )

            #
            # Keep track of wrapper-bearing raw source
            # mentions for audit purposes. These are
            # not themselves errors.
            #
            if WRAPPER_PATTERN.search(raw_name):
                raw_wrapper_leakage.append(
                    {
                        "case_id": case_id,
                        "mention_id": (mention.get("mention_id")),
                        "medication_name_raw": (raw_name),
                        "normalized_name": (normalized_name),
                        "normalized_key": (normalized_key),
                    }
                )

        profile_by_key: dict[
            str,
            dict[str, Any],
        ] = {}

        for profile in profiles:
            key = str(
                profile.get(
                    "normalized_key",
                    "",
                )
            )

            if key in profile_by_key:
                duplicate_profile_keys.append(
                    {
                        "case_id": case_id,
                        "normalized_key": key,
                        "profile_ids": [
                            profile_by_key[key].get("profile_id"),
                            profile.get("profile_id"),
                        ],
                    }
                )

                continue

            profile_by_key[key] = profile

        #
        # Every normalized medication mention must
        # resolve to exactly one profile.
        #
        for key, grouped_mentions in mentions_by_key.items():
            profile = profile_by_key.get(key)

            if profile is None:
                orphan_mentions.append(
                    {
                        "case_id": case_id,
                        "normalized_key": key,
                        "mention_ids": [mention.get("mention_id") for mention in grouped_mentions],
                    }
                )

                continue

            expected_ids = {
                str(mention["mention_id"])
                for mention in grouped_mentions
                if mention.get("mention_id")
            }

            profile_ids = string_values(profile.get("mention_ids"))

            if expected_ids != profile_ids:
                profile_membership_mismatches.append(
                    {
                        "case_id": case_id,
                        "profile_id": (profile.get("profile_id")),
                        "normalized_key": key,
                        "expected_mention_ids": (sorted(expected_ids)),
                        "profile_mention_ids": (sorted(profile_ids)),
                    }
                )

        #
        # Ensure profile member mentions all carry
        # the profile's normalized medication key.
        #
        for profile in profiles:
            profile_id = str(
                profile.get(
                    "profile_id",
                    "",
                )
            )

            key = str(
                profile.get(
                    "normalized_key",
                    "",
                )
            )

            member_mentions: list[dict[str, Any]] = []

            for mention_id in string_values(profile.get("mention_ids")):
                mention = mention_index.get(mention_id)

                if mention is None:
                    continue

                member_mentions.append(mention)

                if mention.get("normalized_key") != key:
                    mention_key_mismatches.append(
                        {
                            "case_id": case_id,
                            "profile_id": (profile_id),
                            "mention_id": (mention_id),
                            "profile_key": key,
                            "mention_key": (mention.get("normalized_key")),
                        }
                    )

            #
            # Validate deterministic profile aggregation.
            #
            expected_raw_names = {
                str(mention["medication_name_raw"])
                for mention in member_mentions
                if mention.get("medication_name_raw")
            }

            actual_raw_names = string_values(profile.get("raw_names"))

            if expected_raw_names != actual_raw_names:
                raw_name_mismatches.append(
                    {
                        "case_id": case_id,
                        "profile_id": profile_id,
                        "normalized_key": key,
                        "expected": sorted(expected_raw_names),
                        "actual": sorted(actual_raw_names),
                    }
                )

            expected_statuses = {
                str(mention["status"]) for mention in member_mentions if mention.get("status")
            }

            actual_statuses = string_values(profile.get("statuses"))

            if expected_statuses != actual_statuses:
                status_mismatches.append(
                    {
                        "case_id": case_id,
                        "profile_id": profile_id,
                        "normalized_key": key,
                        "expected": sorted(expected_statuses),
                        "actual": sorted(actual_statuses),
                    }
                )

            expected_doses = {
                str(mention["dose"]) for mention in member_mentions if mention.get("dose")
            }

            actual_doses = string_values(profile.get("doses"))

            if expected_doses != actual_doses:
                dose_mismatches.append(
                    {
                        "case_id": case_id,
                        "profile_id": profile_id,
                        "normalized_key": key,
                        "expected": sorted(expected_doses),
                        "actual": sorted(actual_doses),
                    }
                )

            expected_routes = {
                str(mention["route"]) for mention in member_mentions if mention.get("route")
            }

            actual_routes = string_values(profile.get("routes"))

            if expected_routes != actual_routes:
                route_mismatches.append(
                    {
                        "case_id": case_id,
                        "profile_id": profile_id,
                        "normalized_key": key,
                        "expected": sorted(expected_routes),
                        "actual": sorted(actual_routes),
                    }
                )

            expected_documents = {
                str(mention["document_type"])
                for mention in member_mentions
                if mention.get("document_type")
            }

            actual_documents = string_values(profile.get("document_types"))

            if expected_documents != actual_documents:
                document_type_mismatches.append(
                    {
                        "case_id": case_id,
                        "profile_id": profile_id,
                        "normalized_key": key,
                        "expected": sorted(expected_documents),
                        "actual": sorted(actual_documents),
                    }
                )

    issue_count = sum(
        (
            len(duplicate_profile_keys),
            len(orphan_mentions),
            len(profile_membership_mismatches),
            len(mention_key_mismatches),
            len(normalized_wrapper_leakage),
            len(normalized_datetime_leakage),
            len(raw_name_mismatches),
            len(status_mismatches),
            len(dose_mismatches),
            len(route_mismatches),
            len(document_type_mismatches),
        )
    )

    status = "PASS" if issue_count == 0 else "FAIL"

    output = {
        "schema_version": "1.0",
        "evaluation_step": ("simplified_8C.2b"),
        "status": status,
        "cases_scanned": (cases_scanned),
        "population": {
            "medication_mentions": (mentions_scanned),
            "medication_profiles": (profiles_scanned),
            "raw_wrapper_mentions": (len(raw_wrapper_leakage)),
        },
        "normalization_integrity": {
            "duplicate_profile_keys": (len(duplicate_profile_keys)),
            "orphan_mentions": (len(orphan_mentions)),
            "profile_membership_mismatches": (len(profile_membership_mismatches)),
            "mention_key_mismatches": (len(mention_key_mismatches)),
            "normalized_wrapper_leakage": (len(normalized_wrapper_leakage)),
            "normalized_datetime_leakage": (len(normalized_datetime_leakage)),
        },
        "profile_aggregation_integrity": {
            "raw_name_mismatches": (len(raw_name_mismatches)),
            "status_mismatches": (len(status_mismatches)),
            "dose_mismatches": (len(dose_mismatches)),
            "route_mismatches": (len(route_mismatches)),
            "document_type_mismatches": (len(document_type_mismatches)),
        },
        "total_issues": issue_count,
        "issues": {
            "duplicate_profile_keys": (duplicate_profile_keys),
            "orphan_mentions": (orphan_mentions),
            "profile_membership_mismatches": (profile_membership_mismatches),
            "mention_key_mismatches": (mention_key_mismatches),
            "normalized_wrapper_leakage": (normalized_wrapper_leakage),
            "normalized_datetime_leakage": (normalized_datetime_leakage),
            "raw_name_mismatches": (raw_name_mismatches),
            "status_mismatches": (status_mismatches),
            "dose_mismatches": (dose_mismatches),
            "route_mismatches": (route_mismatches),
            "document_type_mismatches": (document_type_mismatches),
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
    print("SIMPLIFIED STEP 8C.2b MEDICATION NORMALIZATION / RECONCILIATION")
    print("=" * 72)

    print(f"Status:                         {status}")

    print(f"Cases scanned:                  {cases_scanned}")

    print(f"Medication mentions:            {mentions_scanned}")

    print(f"Medication profiles:            {profiles_scanned}")

    print()
    print("Normalization integrity")
    print("-" * 72)

    print(f"Duplicate profile keys:         {len(duplicate_profile_keys)}")

    print(f"Orphan mentions:                {len(orphan_mentions)}")

    print(f"Membership mismatches:          {len(profile_membership_mismatches)}")

    print(f"Mention/profile key mismatch:   {len(mention_key_mismatches)}")

    print(f"Normalized wrapper leakage:     {len(normalized_wrapper_leakage)}")

    print(f"Normalized datetime leakage:    {len(normalized_datetime_leakage)}")

    print()
    print("Profile aggregation integrity")
    print("-" * 72)

    print(f"Raw-name mismatches:            {len(raw_name_mismatches)}")

    print(f"Status mismatches:              {len(status_mismatches)}")

    print(f"Dose mismatches:                {len(dose_mismatches)}")

    print(f"Route mismatches:               {len(route_mismatches)}")

    print(f"Document-type mismatches:       {len(document_type_mismatches)}")

    print()
    print(f"Raw wrapper-bearing mentions:   {len(raw_wrapper_leakage)}")

    print(f"Total issues:                   {issue_count}")

    print()
    print("Saved evaluation to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

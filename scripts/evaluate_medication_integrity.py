from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "medication"

OUTPUT_PATH = OUTPUT_DIR / "medication_integrity.json"


REQUIRED_FILES = (
    "evidence_items.json",
    "clinical_claims.json",
    "canonical_timeline.json",
    "medication_mentions.json",
    "medication_profiles.json",
    "medication_discrepancies.json",
    "medication_reconciliation_manifest.json",
    "final_investigation_report.json",
)


def load_json(path: Path) -> Any:
    """Load JSON from disk."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def flatten_records(
    raw: Any,
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Extract records from common list/wrapper structures."""

    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]

    if isinstance(raw, dict):
        for key in keys:
            value = raw.get(key)

            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]

    return []


def load_records(
    path: Path,
    keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Load records from a JSON artifact."""

    return flatten_records(
        load_json(path),
        keys,
    )


def string_ids(value: Any) -> list[str]:
    """Normalize scalar/list ID fields."""

    if isinstance(value, str):
        return [value] if value else []

    if isinstance(value, list):
        return [item for item in value if isinstance(item, str) and item]

    return []


def nonempty_string(value: Any) -> bool:
    """Return whether value is a nonempty string."""

    return isinstance(value, str) and bool(value.strip())


def build_id_set(
    records: list[dict[str, Any]],
    field: str,
) -> set[str]:
    """Build an ID set from a record collection."""

    return {str(record[field]) for record in records if nonempty_string(record.get(field))}


def duplicate_ids(
    records: list[dict[str, Any]],
    field: str,
) -> list[str]:
    """Return duplicate IDs for a record collection."""

    counter: Counter[str] = Counter(
        str(record[field]) for record in records if nonempty_string(record.get(field))
    )

    return sorted(key for key, count in counter.items() if count > 1)


def validate_reference_list(
    *,
    case_id: str,
    owner_type: str,
    owner_id: str,
    field: str,
    values: Any,
    valid_ids: set[str],
    issues: list[dict[str, Any]],
) -> None:
    """Validate a list of referenced IDs."""

    for reference_id in string_ids(values):
        if reference_id in valid_ids:
            continue

        issues.append(
            {
                "case_id": case_id,
                "owner_type": owner_type,
                "owner_id": owner_id,
                "field": field,
                "unresolved_id": reference_id,
            }
        )


def main() -> int:
    """Run simplified Step 8C.2a medication integrity."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    cases_scanned = 0

    total_mentions = 0
    total_profiles = 0
    total_discrepancies = 0

    missing_artifacts: list[dict[str, Any]] = []

    duplicate_mention_ids: list[dict[str, Any]] = []

    duplicate_profile_ids: list[dict[str, Any]] = []

    duplicate_discrepancy_ids: list[dict[str, Any]] = []

    case_id_mismatches: list[dict[str, Any]] = []

    unresolved_references: list[dict[str, Any]] = []

    invalid_mentions: list[dict[str, Any]] = []

    invalid_profiles: list[dict[str, Any]] = []

    invalid_discrepancies: list[dict[str, Any]] = []

    manifest_count_mismatches: list[dict[str, Any]] = []

    discrepancy_type_counts: Counter[str] = Counter()

    profile_status_counts: Counter[str] = Counter()

    case_summaries: list[dict[str, Any]] = []

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        missing = [filename for filename in REQUIRED_FILES if not (case_dir / filename).exists()]

        if missing:
            missing_artifacts.append(
                {
                    "case_id": (case_dir.name),
                    "missing_files": missing,
                }
            )

            continue

        cases_scanned += 1

        case_id = case_dir.name

        evidence = load_records(
            case_dir / "evidence_items.json",
            (
                "evidence_items",
                "items",
                "records",
            ),
        )

        claims = load_records(
            case_dir / "clinical_claims.json",
            (
                "clinical_claims",
                "claims",
                "records",
            ),
        )

        timeline = load_records(
            case_dir / "canonical_timeline.json",
            (
                "events",
                "timeline",
                "records",
            ),
        )

        mentions = load_records(
            case_dir / "medication_mentions.json",
            (
                "mentions",
                "medication_mentions",
                "records",
            ),
        )

        profiles = load_records(
            case_dir / "medication_profiles.json",
            (
                "profiles",
                "medication_profiles",
                "records",
            ),
        )

        discrepancies = load_records(
            case_dir / "medication_discrepancies.json",
            (
                "discrepancies",
                "medication_discrepancies",
                "records",
            ),
        )

        manifest = load_json(case_dir / "medication_reconciliation_manifest.json")

        if not isinstance(
            manifest,
            dict,
        ):
            raise ValueError(
                f"medication_reconciliation_manifest.json must contain an object: {case_id}"
            )

        total_mentions += len(mentions)

        total_profiles += len(profiles)

        total_discrepancies += len(discrepancies)

        evidence_ids = build_id_set(
            evidence,
            "evidence_id",
        )

        claim_ids = build_id_set(
            claims,
            "claim_id",
        )

        timeline_ids = build_id_set(
            timeline,
            "event_id",
        )

        mention_ids = build_id_set(
            mentions,
            "mention_id",
        )

        for duplicate_id in duplicate_ids(
            mentions,
            "mention_id",
        ):
            duplicate_mention_ids.append(
                {
                    "case_id": case_id,
                    "mention_id": (duplicate_id),
                }
            )

        for duplicate_id in duplicate_ids(
            profiles,
            "profile_id",
        ):
            duplicate_profile_ids.append(
                {
                    "case_id": case_id,
                    "profile_id": (duplicate_id),
                }
            )

        for duplicate_id in duplicate_ids(
            discrepancies,
            "discrepancy_id",
        ):
            duplicate_discrepancy_ids.append(
                {
                    "case_id": case_id,
                    "discrepancy_id": (duplicate_id),
                }
            )

        for mention in mentions:
            mention_id = str(
                mention.get(
                    "mention_id",
                    "",
                )
            )

            if mention.get("case_id") != case_id:
                case_id_mismatches.append(
                    {
                        "case_id": case_id,
                        "owner_type": ("medication_mention"),
                        "owner_id": (mention_id),
                        "record_case_id": (mention.get("case_id")),
                    }
                )

            if not nonempty_string(mention.get("normalized_name")):
                invalid_mentions.append(
                    {
                        "case_id": case_id,
                        "mention_id": (mention_id),
                        "issue": ("missing_normalized_name"),
                    }
                )

            if not nonempty_string(mention.get("normalized_key")):
                invalid_mentions.append(
                    {
                        "case_id": case_id,
                        "mention_id": (mention_id),
                        "issue": ("missing_normalized_key"),
                    }
                )

            validate_reference_list(
                case_id=case_id,
                owner_type=("medication_mention"),
                owner_id=mention_id,
                field="evidence_ids",
                values=mention.get("evidence_ids"),
                valid_ids=evidence_ids,
                issues=unresolved_references,
            )

            validate_reference_list(
                case_id=case_id,
                owner_type=("medication_mention"),
                owner_id=mention_id,
                field=("source_claim_ids"),
                values=mention.get("source_claim_ids"),
                valid_ids=claim_ids,
                issues=unresolved_references,
            )

            validate_reference_list(
                case_id=case_id,
                owner_type=("medication_mention"),
                owner_id=mention_id,
                field=("timeline_event_ids"),
                values=mention.get("timeline_event_ids"),
                valid_ids=timeline_ids,
                issues=unresolved_references,
            )

        for profile in profiles:
            profile_id = str(
                profile.get(
                    "profile_id",
                    "",
                )
            )

            if profile.get("case_id") != case_id:
                case_id_mismatches.append(
                    {
                        "case_id": case_id,
                        "owner_type": ("medication_profile"),
                        "owner_id": (profile_id),
                        "record_case_id": (profile.get("case_id")),
                    }
                )

            if not nonempty_string(profile.get("normalized_name")):
                invalid_profiles.append(
                    {
                        "case_id": case_id,
                        "profile_id": (profile_id),
                        "issue": ("missing_normalized_name"),
                    }
                )

            if not nonempty_string(profile.get("normalized_key")):
                invalid_profiles.append(
                    {
                        "case_id": case_id,
                        "profile_id": (profile_id),
                        "issue": ("missing_normalized_key"),
                    }
                )

            for status in profile.get("statuses") or []:
                profile_status_counts[str(status)] += 1

            validate_reference_list(
                case_id=case_id,
                owner_type=("medication_profile"),
                owner_id=profile_id,
                field="mention_ids",
                values=profile.get("mention_ids"),
                valid_ids=mention_ids,
                issues=unresolved_references,
            )

            validate_reference_list(
                case_id=case_id,
                owner_type=("medication_profile"),
                owner_id=profile_id,
                field="evidence_ids",
                values=profile.get("evidence_ids"),
                valid_ids=evidence_ids,
                issues=unresolved_references,
            )

            validate_reference_list(
                case_id=case_id,
                owner_type=("medication_profile"),
                owner_id=profile_id,
                field=("source_claim_ids"),
                values=profile.get("source_claim_ids"),
                valid_ids=claim_ids,
                issues=unresolved_references,
            )

            validate_reference_list(
                case_id=case_id,
                owner_type=("medication_profile"),
                owner_id=profile_id,
                field=("timeline_event_ids"),
                values=profile.get("timeline_event_ids"),
                valid_ids=timeline_ids,
                issues=unresolved_references,
            )

        for discrepancy in discrepancies:
            discrepancy_id = str(
                discrepancy.get(
                    "discrepancy_id",
                    "",
                )
            )

            if discrepancy.get("case_id") != case_id:
                case_id_mismatches.append(
                    {
                        "case_id": case_id,
                        "owner_type": ("medication_discrepancy"),
                        "owner_id": (discrepancy_id),
                        "record_case_id": (discrepancy.get("case_id")),
                    }
                )

            discrepancy_type = str(
                discrepancy.get(
                    "discrepancy_type",
                    "unknown",
                )
            )

            discrepancy_type_counts[discrepancy_type] += 1

            if not nonempty_string(discrepancy.get("medication_key")):
                invalid_discrepancies.append(
                    {
                        "case_id": case_id,
                        "discrepancy_id": (discrepancy_id),
                        "issue": ("missing_medication_key"),
                    }
                )

            matching_profiles = [
                profile
                for profile in profiles
                if profile.get("normalized_key") == discrepancy.get("medication_key")
            ]

            if not matching_profiles:
                invalid_discrepancies.append(
                    {
                        "case_id": case_id,
                        "discrepancy_id": (discrepancy_id),
                        "issue": ("no_matching_profile"),
                        "medication_key": (discrepancy.get("medication_key")),
                    }
                )

            validate_reference_list(
                case_id=case_id,
                owner_type=("medication_discrepancy"),
                owner_id=(discrepancy_id),
                field="mention_ids",
                values=discrepancy.get("mention_ids"),
                valid_ids=mention_ids,
                issues=unresolved_references,
            )

            validate_reference_list(
                case_id=case_id,
                owner_type=("medication_discrepancy"),
                owner_id=(discrepancy_id),
                field="evidence_ids",
                values=discrepancy.get("evidence_ids"),
                valid_ids=evidence_ids,
                issues=unresolved_references,
            )

            validate_reference_list(
                case_id=case_id,
                owner_type=("medication_discrepancy"),
                owner_id=(discrepancy_id),
                field=("source_claim_ids"),
                values=discrepancy.get("source_claim_ids"),
                valid_ids=claim_ids,
                issues=unresolved_references,
            )

            validate_reference_list(
                case_id=case_id,
                owner_type=("medication_discrepancy"),
                owner_id=(discrepancy_id),
                field=("timeline_event_ids"),
                values=discrepancy.get("timeline_event_ids"),
                valid_ids=timeline_ids,
                issues=unresolved_references,
            )

        manifest_case_id = manifest.get("case_id")

        if manifest_case_id != case_id:
            case_id_mismatches.append(
                {
                    "case_id": case_id,
                    "owner_type": ("medication_manifest"),
                    "owner_id": ("manifest"),
                    "record_case_id": (manifest_case_id),
                }
            )

        expected_counts = {
            "source_evidence_count": (len(evidence)),
            "source_claim_count": (len(claims)),
            "source_timeline_event_count": (len(timeline)),
            "medication_mention_count": (len(mentions)),
            "medication_profile_count": (len(profiles)),
            "discrepancy_count": (len(discrepancies)),
        }

        for (
            field,
            expected,
        ) in expected_counts.items():
            actual = manifest.get(field)

            if actual == expected:
                continue

            manifest_count_mismatches.append(
                {
                    "case_id": case_id,
                    "field": field,
                    "expected": (expected),
                    "actual": (actual),
                }
            )

        case_summaries.append(
            {
                "case_id": case_id,
                "evidence_count": (len(evidence)),
                "claim_count": (len(claims)),
                "timeline_event_count": (len(timeline)),
                "mention_count": (len(mentions)),
                "profile_count": (len(profiles)),
                "discrepancy_count": (len(discrepancies)),
            }
        )

    issue_count = sum(
        (
            len(missing_artifacts),
            len(duplicate_mention_ids),
            len(duplicate_profile_ids),
            len(duplicate_discrepancy_ids),
            len(case_id_mismatches),
            len(unresolved_references),
            len(invalid_mentions),
            len(invalid_profiles),
            len(invalid_discrepancies),
            len(manifest_count_mismatches),
        )
    )

    status = "PASS" if issue_count == 0 else "FAIL"

    output = {
        "schema_version": "1.0",
        "evaluation_step": ("simplified_8C.2a"),
        "status": status,
        "cases_scanned": (cases_scanned),
        "population": {
            "medication_mentions": (total_mentions),
            "medication_profiles": (total_profiles),
            "medication_discrepancies": (total_discrepancies),
        },
        "integrity": {
            "missing_artifacts": (len(missing_artifacts)),
            "duplicate_mention_ids": (len(duplicate_mention_ids)),
            "duplicate_profile_ids": (len(duplicate_profile_ids)),
            "duplicate_discrepancy_ids": (len(duplicate_discrepancy_ids)),
            "case_id_mismatches": (len(case_id_mismatches)),
            "unresolved_references": (len(unresolved_references)),
            "invalid_mentions": (len(invalid_mentions)),
            "invalid_profiles": (len(invalid_profiles)),
            "invalid_discrepancies": (len(invalid_discrepancies)),
            "manifest_count_mismatches": (len(manifest_count_mismatches)),
            "total_issues": (issue_count),
        },
        "discrepancy_type_counts": dict(sorted(discrepancy_type_counts.items())),
        "profile_status_counts": dict(sorted(profile_status_counts.items())),
        "case_summaries": (case_summaries),
        "issues": {
            "missing_artifacts": (missing_artifacts),
            "duplicate_mention_ids": (duplicate_mention_ids),
            "duplicate_profile_ids": (duplicate_profile_ids),
            "duplicate_discrepancy_ids": (duplicate_discrepancy_ids),
            "case_id_mismatches": (case_id_mismatches),
            "unresolved_references": (unresolved_references),
            "invalid_mentions": (invalid_mentions),
            "invalid_profiles": (invalid_profiles),
            "invalid_discrepancies": (invalid_discrepancies),
            "manifest_count_mismatches": (manifest_count_mismatches),
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
    print("SIMPLIFIED STEP 8C.2a MEDICATION ARTIFACT / PROVENANCE INTEGRITY")
    print("=" * 72)

    print(f"Status:                         {status}")

    print(f"Cases scanned:                  {cases_scanned}")

    print()
    print("Medication population")
    print("-" * 72)

    print(f"Medication mentions:            {total_mentions}")

    print(f"Medication profiles:            {total_profiles}")

    print(f"Medication discrepancies:       {total_discrepancies}")

    print()
    print("Integrity")
    print("-" * 72)

    print(f"Missing artifacts:              {len(missing_artifacts)}")

    print(f"Duplicate mention IDs:          {len(duplicate_mention_ids)}")

    print(f"Duplicate profile IDs:          {len(duplicate_profile_ids)}")

    print(f"Duplicate discrepancy IDs:      {len(duplicate_discrepancy_ids)}")

    print(f"Case-ID mismatches:             {len(case_id_mismatches)}")

    print(f"Unresolved references:          {len(unresolved_references)}")

    print(f"Invalid mentions:               {len(invalid_mentions)}")

    print(f"Invalid profiles:               {len(invalid_profiles)}")

    print(f"Invalid discrepancies:          {len(invalid_discrepancies)}")

    print(f"Manifest count mismatches:      {len(manifest_count_mismatches)}")

    print()
    print(f"Total integrity issues:         {issue_count}")

    if discrepancy_type_counts:
        print()
        print("Discrepancy population")
        print("-" * 72)

        for (
            key,
            count,
        ) in sorted(discrepancy_type_counts.items()):
            print(f"{key:<32}{count:>8}")

    print()
    print("Saved evaluation to:")

    print(OUTPUT_PATH)

    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

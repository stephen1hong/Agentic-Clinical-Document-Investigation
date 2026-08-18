from __future__ import annotations

import json
import re
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CASE_ROOT = PROJECT_ROOT / "data" / "investigation_cases"

OUTPUT_DIR = PROJECT_ROOT / "data" / "evaluation" / "evidence_grounding"

OUTPUT_PATH = OUTPUT_DIR / "negative_assertion_verification.json"


TARGET_DISCREPANCY_TYPE = "discharge_only_medication"

DISCHARGE_DOCUMENT_TYPE = "discharge_summary"


WRAPPER_PREFIX_PATTERN = re.compile(
    r"^\s*medication(?:started|stopped)neardischarge\s*:\s*",
    flags=re.IGNORECASE,
)

TRAILING_DATETIME_PATTERN = re.compile(
    r"\s+at\s+"
    r"(?:"
    r"january|february|march|april|may|june|"
    r"july|august|september|october|november|december"
    r")"
    r"\s+\d{1,2},?\s+\d{4}"
    r"\s+at\s+\d{1,2}:\d{2}\s+UTC\s*$",
    flags=re.IGNORECASE,
)

DOSE_TOKEN_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s*"
    r"(?:mg|mcg|g|ml|mL|units?|unt|meq|%)"
    r"(?:/\s*(?:ml|mL|mg|g))?\b",
    flags=re.IGNORECASE,
)

LEADING_QUANTITY_PATTERN = re.compile(
    r"^\s*\d+(?:\.\d+)?\s*(?:ml|mL|mg|g)\s+",
    flags=re.IGNORECASE,
)

FORM_TERMS = {
    "injection",
    "injectable",
    "solution",
    "tablet",
    "tablets",
    "capsule",
    "capsules",
    "oral",
    "extended",
    "release",
    "inhalation",
    "spray",
    "usp",
    "hr",
    "actuat",
}

GENERIC_NOISE_TERMS = {
    "medicationstartedneardischarge",
    "medicationstoppedneardischarge",
}


def load_json(
    path: Path,
) -> Any:
    """Load JSON from disk."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def normalize_space(
    value: str,
) -> str:
    """Collapse repeated whitespace."""

    return " ".join(value.split())


def independent_medication_text(
    value: str,
) -> str:
    """
    Independently normalize a medication string.

    This deliberately does not reuse the production normalized_key.
    """

    text = value.strip()

    text = WRAPPER_PREFIX_PATTERN.sub(
        "",
        text,
    )

    text = TRAILING_DATETIME_PATTERN.sub(
        "",
        text,
    )

    text = LEADING_QUANTITY_PATTERN.sub(
        "",
        text,
    )

    text = DOSE_TOKEN_PATTERN.sub(
        " ",
        text,
    )

    text = re.sub(
        r"[^\w\s-]",
        " ",
        text,
    )

    tokens = []

    for raw_token in normalize_space(text).lower().split():
        token = raw_token.strip("-")

        if not token:
            continue

        if token in FORM_TERMS:
            continue

        if token in GENERIC_NOISE_TERMS:
            continue

        if token.isdigit():
            continue

        tokens.append(token)

    return " ".join(tokens)


def token_set(
    value: str,
) -> set[str]:
    """Return normalized medication tokens."""

    return {token for token in independent_medication_text(value).split() if token}


def similarity(
    left: str,
    right: str,
) -> float:
    """Return lexical sequence similarity."""

    left_norm = independent_medication_text(left)

    right_norm = independent_medication_text(right)

    if not left_norm or not right_norm:
        return 0.0

    return SequenceMatcher(
        None,
        left_norm,
        right_norm,
    ).ratio()


def classify_candidate_match(
    target_name: str,
    candidate_name: str,
) -> tuple[
    str,
    float,
    float,
]:
    """
    Classify a non-discharge medication candidate.

    Returns:
        match_class,
        sequence_similarity,
        token_overlap
    """

    target_norm = independent_medication_text(target_name)

    candidate_norm = independent_medication_text(candidate_name)

    target_tokens = token_set(target_name)

    candidate_tokens = token_set(candidate_name)

    if target_norm and candidate_norm and target_norm == candidate_norm:
        return (
            "clear_match",
            1.0,
            1.0,
        )

    if target_tokens and candidate_tokens:
        intersection = target_tokens & candidate_tokens

        smaller = min(
            len(target_tokens),
            len(candidate_tokens),
        )

        token_overlap = len(intersection) / smaller if smaller else 0.0
    else:
        token_overlap = 0.0

    sequence_similarity = similarity(
        target_name,
        candidate_name,
    )

    if token_overlap == 1.0 and len(target_tokens & candidate_tokens) >= 1:
        return (
            "clear_match",
            sequence_similarity,
            token_overlap,
        )

    if sequence_similarity >= 0.90 and token_overlap >= 0.75:
        return (
            "clear_match",
            sequence_similarity,
            token_overlap,
        )

    if sequence_similarity >= 0.72 or token_overlap >= 0.50:
        return (
            "possible_match",
            sequence_similarity,
            token_overlap,
        )

    return (
        "no_match",
        sequence_similarity,
        token_overlap,
    )


def get_discrepancy_name(
    discrepancy: dict[str, Any],
) -> str:
    """Resolve the best medication name from a discrepancy."""

    for field in (
        "medication_name",
        "normalized_name",
        "summary",
    ):
        value = discrepancy.get(field)

        if (
            isinstance(
                value,
                str,
            )
            and value.strip()
        ):
            return value.strip()

    return ""


def get_discrepancy_evidence_ids(
    discrepancy: dict[str, Any],
) -> list[str]:
    """Return discrepancy evidence IDs."""

    value = discrepancy.get(
        "evidence_ids",
        [],
    )

    if not isinstance(
        value,
        list,
    ):
        return []

    return [str(item) for item in value if item]


def choose_target_discharge_mentions(
    discrepancy: dict[str, Any],
    mentions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Resolve discharge mentions corresponding to the discrepancy.

    Evidence IDs are preferred. If no evidence IDs are stored directly
    on the discrepancy, lexical comparison is used.
    """

    discrepancy_evidence_ids = set(get_discrepancy_evidence_ids(discrepancy))

    discharge_mentions = [
        mention for mention in mentions if mention.get("document_type") == DISCHARGE_DOCUMENT_TYPE
    ]

    if discrepancy_evidence_ids:
        evidence_matches = []

        for mention in discharge_mentions:
            mention_evidence_ids = mention.get(
                "evidence_ids",
                [],
            )

            if not isinstance(
                mention_evidence_ids,
                list,
            ):
                continue

            if discrepancy_evidence_ids & {str(item) for item in mention_evidence_ids if item}:
                evidence_matches.append(mention)

        if evidence_matches:
            return evidence_matches

    target_name = get_discrepancy_name(discrepancy)

    scored: list[
        tuple[
            float,
            dict[str, Any],
        ]
    ] = []

    for mention in discharge_mentions:
        raw_name = str(
            mention.get(
                "medication_name_raw",
                "",
            )
        )

        score = similarity(
            target_name,
            raw_name,
        )

        scored.append(
            (
                score,
                mention,
            )
        )

    if not scored:
        return []

    best_score = max(score for score, _ in scored)

    if best_score < 0.60:
        return []

    return [mention for score, mention in scored if score == best_score]


def verify_discrepancy(
    *,
    case_id: str,
    discrepancy: dict[str, Any],
    mentions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Verify one discharge-only negative assertion."""

    target_discharge_mentions = choose_target_discharge_mentions(
        discrepancy,
        mentions,
    )

    if not target_discharge_mentions:
        return {
            "case_id": case_id,
            "discrepancy_id": discrepancy.get("discrepancy_id"),
            "medication_name": get_discrepancy_name(discrepancy),
            "result": "manual_review",
            "reason": ("Could not reliably resolve the target discharge medication mention."),
            "target_mentions": [],
            "clear_matches": [],
            "possible_matches": [],
        }

    target_names = [
        str(
            mention.get(
                "medication_name_raw",
                "",
            )
        )
        for mention in target_discharge_mentions
    ]

    non_discharge_mentions = [
        mention for mention in mentions if mention.get("document_type") != DISCHARGE_DOCUMENT_TYPE
    ]

    clear_matches: list[dict[str, Any]] = []

    possible_matches: list[dict[str, Any]] = []

    for candidate in non_discharge_mentions:
        candidate_name = str(
            candidate.get(
                "medication_name_raw",
                "",
            )
        )

        best_class = "no_match"
        best_similarity = 0.0
        best_overlap = 0.0
        best_target = ""

        for target_name in target_names:
            (
                match_class,
                sequence_similarity,
                token_overlap,
            ) = classify_candidate_match(
                target_name,
                candidate_name,
            )

            score_tuple = (
                2
                if match_class == "clear_match"
                else (1 if match_class == "possible_match" else 0),
                sequence_similarity,
                token_overlap,
            )

            best_tuple = (
                2 if best_class == "clear_match" else (1 if best_class == "possible_match" else 0),
                best_similarity,
                best_overlap,
            )

            if score_tuple > best_tuple:
                best_class = match_class
                best_similarity = sequence_similarity
                best_overlap = token_overlap
                best_target = target_name

        if best_class == "no_match":
            continue

        record = {
            "mention_id": candidate.get("mention_id"),
            "document_type": candidate.get("document_type"),
            "source_type": candidate.get("source_type"),
            "medication_name_raw": (candidate_name),
            "normalized_name": candidate.get("normalized_name"),
            "normalized_key": candidate.get("normalized_key"),
            "event_time": candidate.get("event_time"),
            "target_name": best_target,
            "target_independent_name": (independent_medication_text(best_target)),
            "candidate_independent_name": (independent_medication_text(candidate_name)),
            "sequence_similarity": round(
                best_similarity,
                4,
            ),
            "token_overlap": round(
                best_overlap,
                4,
            ),
        }

        if best_class == "clear_match":
            clear_matches.append(record)
        else:
            possible_matches.append(record)

    target_records = [
        {
            "mention_id": mention.get("mention_id"),
            "medication_name_raw": mention.get("medication_name_raw"),
            "normalized_name": mention.get("normalized_name"),
            "normalized_key": mention.get("normalized_key"),
            "event_time": mention.get("event_time"),
            "independent_name": (
                independent_medication_text(
                    str(
                        mention.get(
                            "medication_name_raw",
                            "",
                        )
                    )
                )
            ),
        }
        for mention in target_discharge_mentions
    ]

    if clear_matches:
        result = "contradicted_by_other_source"

        reason = "A clear same-medication mention was found in a non-discharge source."

    elif possible_matches:
        result = "manual_review"

        reason = (
            "A potentially equivalent medication "
            "mention was found in a non-discharge "
            "source but identity was not strong "
            "enough for automatic contradiction."
        )

    else:
        result = "verified_absence"

        reason = (
            "No matching or plausibly equivalent "
            "medication mention was found in "
            "non-discharge medication mentions."
        )

    return {
        "case_id": case_id,
        "discrepancy_id": discrepancy.get("discrepancy_id"),
        "medication_name": get_discrepancy_name(discrepancy),
        "result": result,
        "reason": reason,
        "target_mentions": target_records,
        "clear_matches": clear_matches,
        "possible_matches": possible_matches,
    }


def main() -> int:
    """Verify discharge-only medication assertions."""

    if not CASE_ROOT.exists():
        raise FileNotFoundError(f"Case root not found: {CASE_ROOT}")

    reports_scanned = 0
    discrepancies_evaluated = 0

    result_counts: Counter[str] = Counter()

    records: list[dict[str, Any]] = []

    for case_dir in sorted(path for path in CASE_ROOT.iterdir() if path.is_dir()):
        discrepancy_path = case_dir / "medication_discrepancies.json"

        mentions_path = case_dir / "medication_mentions.json"

        if not discrepancy_path.exists() or not mentions_path.exists():
            continue

        discrepancies = load_json(discrepancy_path)

        mentions = load_json(mentions_path)

        if not isinstance(
            discrepancies,
            list,
        ):
            raise ValueError(f"Expected list: {discrepancy_path}")

        if not isinstance(
            mentions,
            list,
        ):
            raise ValueError(f"Expected list: {mentions_path}")

        reports_scanned += 1

        target_discrepancies = [
            discrepancy
            for discrepancy in discrepancies
            if (
                isinstance(
                    discrepancy,
                    dict,
                )
                and discrepancy.get("discrepancy_type") == TARGET_DISCREPANCY_TYPE
            )
        ]

        for discrepancy in target_discrepancies:
            result = verify_discrepancy(
                case_id=case_dir.name,
                discrepancy=discrepancy,
                mentions=[
                    mention
                    for mention in mentions
                    if isinstance(
                        mention,
                        dict,
                    )
                ],
            )

            discrepancies_evaluated += 1

            result_counts[result["result"]] += 1

            records.append(result)

    output = {
        "schema_version": "1.0",
        "evaluation_step": "8C.4",
        "verification_method": (
            "Independent lexical medication identity "
            "challenge against pre-profile "
            "medication_mentions.json records."
        ),
        "reports_scanned": reports_scanned,
        "discrepancies_evaluated": (discrepancies_evaluated),
        "summary": {
            "verified_absence": (result_counts["verified_absence"]),
            "contradicted_by_other_source": (result_counts["contradicted_by_other_source"]),
            "manual_review": (result_counts["manual_review"]),
        },
        "records": records,
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
    print("STEP 8C.4 TARGETED NEGATIVE-ASSERTION VERIFICATION")
    print("=" * 72)

    print(f"Reports scanned:                 {reports_scanned}")

    print(f"Discrepancies evaluated:         {discrepancies_evaluated}")

    print()
    print("Verification results")
    print("-" * 72)

    print(f"Verified absence:                {result_counts['verified_absence']}")

    print(f"Contradicted by other source:    {result_counts['contradicted_by_other_source']}")

    print(f"Manual review:                   {result_counts['manual_review']}")

    print()
    print("Saved verification to:")

    print(OUTPUT_PATH)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

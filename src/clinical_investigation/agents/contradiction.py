from __future__ import annotations

import re
from collections import defaultdict
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from clinical_investigation.agents.models import (
    FindingSeverity,
    FindingSource,
    FindingType,
    InvestigationFinding,
)

ACTIVE_STATUS_TERMS = {
    "active",
    "continue",
    "continued",
    "continues",
    "continuing",
    "start",
    "started",
}

STOPPED_STATUS_TERMS = {
    "stop",
    "stopped",
    "discontinue",
    "discontinued",
    "held",
}


def normalize_text(
    value: str | None,
) -> str:
    """Normalize free text for conservative comparison."""

    if value is None:
        return ""

    normalized = str(value).strip().lower()

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return normalized


def normalize_medication_subject(
    value: str | None,
) -> str:
    """Normalize medication subject for grouping."""

    text = normalize_text(value)

    text = re.sub(
        r"[^\w\s\-./]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def classify_medication_status(
    value: str | None,
) -> str:
    """Classify explicit medication status conservatively."""

    text = normalize_text(value)

    if not text:
        return "unknown"

    words = set(
        re.findall(
            r"[a-z]+",
            text,
        )
    )

    has_active = bool(words & ACTIVE_STATUS_TERMS)

    has_stopped = bool(words & STOPPED_STATUS_TERMS)

    if has_active and not has_stopped:
        return "active"

    if has_stopped and not has_active:
        return "stopped"

    return "unknown"


def build_evidence_index(
    evidence_items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index evidence records by evidence_id."""

    return {
        str(item.get("evidence_id")): item for item in evidence_items if item.get("evidence_id")
    }


def get_claim_document_types(
    claim: dict[str, Any],
    evidence_index: dict[
        str,
        dict[str, Any],
    ],
) -> set[str]:
    """Resolve source document types for a clinical claim."""

    document_types: set[str] = set()

    evidence_ids = (
        claim.get(
            "source_evidence_ids",
            [],
        )
        or []
    )

    for evidence_id in evidence_ids:
        evidence = evidence_index.get(str(evidence_id))

        if evidence is None:
            continue

        document_type = evidence.get("document_type")

        if document_type:
            document_types.add(str(document_type))

    return document_types


def medication_status_from_claim(
    claim: dict[str, Any],
) -> str:
    """Infer explicit medication status from a claim."""

    candidate_text = " ".join(
        [
            str(
                claim.get(
                    "predicate",
                    "",
                )
            ),
            str(
                claim.get(
                    "value",
                    "",
                )
            ),
            str(
                claim.get(
                    "subject",
                    "",
                )
            ),
        ]
    )

    return classify_medication_status(candidate_text)


def claims_are_cross_document(
    first_claim: dict[str, Any],
    second_claim: dict[str, Any],
    evidence_index: dict[
        str,
        dict[str, Any],
    ],
) -> bool:
    """Return True when claims originate from different documents."""

    first_documents = get_claim_document_types(
        first_claim,
        evidence_index,
    )

    second_documents = get_claim_document_types(
        second_claim,
        evidence_index,
    )

    if not first_documents or not second_documents:
        return False

    return bool(first_documents != second_documents or len(first_documents | second_documents) > 1)


def claim_times_are_compatible_for_comparison(
    first_claim: dict[str, Any],
    second_claim: dict[str, Any],
) -> bool:
    """Conservatively decide whether two claims may describe
    the same clinical state.

    If both claims have explicit different timestamps, we avoid
    automatically calling them contradictory because medication
    status may legitimately change over time.
    """

    first_time = first_claim.get("time_start")
    second_time = second_claim.get("time_start")

    return not (first_time and second_time and first_time != second_time)


def build_contradiction_id(
    *,
    case_id: str,
    first_claim_id: str,
    second_claim_id: str,
    subtype: str,
) -> str:
    """Create deterministic contradiction finding ID."""

    ordered_claim_ids = sorted(
        [
            first_claim_id,
            second_claim_id,
        ]
    )

    key = "|".join(
        [
            case_id,
            subtype,
            *ordered_claim_ids,
        ]
    )

    return str(
        uuid5(
            NAMESPACE_URL,
            f"contradiction:{key}",
        )
    )


def detect_medication_status_contradictions(
    *,
    case_id: str,
    clinical_claims: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
) -> list[InvestigationFinding]:
    """Detect incompatible medication statuses across documents."""

    evidence_index = build_evidence_index(evidence_items)

    medication_claims = [
        claim
        for claim in clinical_claims
        if str(
            claim.get(
                "claim_type",
                "",
            )
        )
        == "medication_status"
    ]

    grouped_claims: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for claim in medication_claims:
        medication_key = normalize_medication_subject(claim.get("subject"))

        if not medication_key:
            continue

        grouped_claims[medication_key].append(claim)

    findings: list[InvestigationFinding] = []

    seen_pairs: set[tuple[str, str]] = set()

    for (
        medication_key,
        claims,
    ) in grouped_claims.items():
        for first_index in range(len(claims)):
            first_claim = claims[first_index]

            first_status = medication_status_from_claim(first_claim)

            if first_status == "unknown":
                continue

            for second_index in range(
                first_index + 1,
                len(claims),
            ):
                second_claim = claims[second_index]

                second_status = medication_status_from_claim(second_claim)

                if second_status == "unknown":
                    continue

                if first_status == second_status:
                    continue

                if not claims_are_cross_document(
                    first_claim,
                    second_claim,
                    evidence_index,
                ):
                    continue

                if not (
                    claim_times_are_compatible_for_comparison(
                        first_claim,
                        second_claim,
                    )
                ):
                    continue

                first_claim_id = str(
                    first_claim.get(
                        "claim_id",
                        "",
                    )
                )

                second_claim_id = str(
                    second_claim.get(
                        "claim_id",
                        "",
                    )
                )

                if not first_claim_id or not second_claim_id:
                    continue

                pair_key = tuple(
                    sorted(
                        [
                            first_claim_id,
                            second_claim_id,
                        ]
                    )
                )

                if pair_key in seen_pairs:
                    continue

                seen_pairs.add(pair_key)

                evidence_ids = list(
                    dict.fromkeys(
                        [
                            *(
                                first_claim.get(
                                    "source_evidence_ids",
                                    [],
                                )
                                or []
                            ),
                            *(
                                second_claim.get(
                                    "source_evidence_ids",
                                    [],
                                )
                                or []
                            ),
                        ]
                    )
                )

                first_documents = sorted(
                    get_claim_document_types(
                        first_claim,
                        evidence_index,
                    )
                )

                second_documents = sorted(
                    get_claim_document_types(
                        second_claim,
                        evidence_index,
                    )
                )

                finding_id = build_contradiction_id(
                    case_id=case_id,
                    first_claim_id=(first_claim_id),
                    second_claim_id=(second_claim_id),
                    subtype=("medication_status_conflict"),
                )

                finding = InvestigationFinding(
                    finding_id=(finding_id),
                    case_id=case_id,
                    finding_type=(FindingType.CONTRADICTION),
                    subtype=("medication_status_conflict"),
                    severity=(FindingSeverity.HIGH),
                    title=("Cross-document medication status contradiction"),
                    summary=(
                        f"{medication_key} "
                        f"is documented as "
                        f"{first_status} in "
                        f"{', '.join(first_documents)} "
                        f"and as "
                        f"{second_status} in "
                        f"{', '.join(second_documents)}."
                    ),
                    evidence_ids=[str(evidence_id) for evidence_id in evidence_ids],
                    claim_ids=[
                        first_claim_id,
                        second_claim_id,
                    ],
                    event_ids=[],
                    medication_key=(medication_key),
                    confidence=0.95,
                    requires_human_review=True,
                    source=(FindingSource.CONTRADICTION_ANALYSIS),
                )

                findings.append(finding)

    return findings

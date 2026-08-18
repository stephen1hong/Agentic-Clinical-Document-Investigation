from __future__ import annotations

import re
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from clinical_investigation.agents.models import (
    FindingSeverity,
    FindingSource,
    FindingType,
    InvestigationFinding,
)

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "was",
    "were",
    "with",
}

MEDICATION_GENERIC_TOKENS = {
    "mg",
    "ml",
    "mcg",
    "g",
    "tablet",
    "tablets",
    "capsule",
    "capsules",
    "injection",
    "solution",
    "oral",
    "intravenous",
    "iv",
}


def normalize_text(
    value: Any,
) -> str:
    """Normalize arbitrary text for deterministic comparison."""

    if value is None:
        return ""

    text = str(value).strip().lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def tokenize_text(
    value: Any,
) -> set[str]:
    """Extract meaningful normalized tokens."""

    text = normalize_text(value)

    words = set(
        re.findall(
            r"[a-z0-9]+(?:\.[0-9]+)?",
            text,
        )
    )

    return {word for word in words if word not in STOP_WORDS and len(word) > 1}


def extract_numeric_tokens(
    value: Any,
) -> set[str]:
    """Extract explicit numeric values from text."""

    return set(
        re.findall(
            r"\b\d+(?:\.\d+)?\b",
            normalize_text(value),
        )
    )


def extract_medication_identity_tokens(
    value: Any,
) -> set[str]:
    """Extract medication-name tokens while excluding dose/form tokens."""

    tokens = tokenize_text(value)
    numeric_tokens = extract_numeric_tokens(value)

    return {
        token
        for token in tokens
        if token not in MEDICATION_GENERIC_TOKENS and token not in numeric_tokens
    }


def build_claim_text(
    claim: dict[str, Any],
) -> str:
    """Build the semantic content of a clinical claim."""

    fields = (
        "subject",
        "predicate",
        "value",
    )

    return " ".join(
        normalize_text(
            claim.get(
                field_name,
                "",
            )
        )
        for field_name in fields
        if claim.get(field_name)
    ).strip()


def build_claim_support_text(
    claim: dict[str, Any],
) -> str:
    """Build factual claim content used for evidence matching.

    Predicates are excluded because structured predicates such as
    ``documented_medication_fact`` describe the extracted relationship
    and are not expected to appear verbatim in source evidence.
    """

    fields = (
        "subject",
        "value",
    )

    return " ".join(
        normalize_text(
            claim.get(
                field_name,
                "",
            )
        )
        for field_name in fields
        if claim.get(field_name)
    ).strip()


def build_evidence_text(
    evidence: dict[str, Any],
) -> str:
    """Build searchable evidence text from supported fields."""

    fields = (
        "normalized_fact",
        "text_span",
        "subject",
        "value",
        "section",
    )

    return " ".join(
        normalize_text(
            evidence.get(
                field_name,
                "",
            )
        )
        for field_name in fields
        if evidence.get(field_name)
    ).strip()


def build_evidence_index(
    evidence_items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Index evidence records by evidence ID."""

    return {
        str(evidence.get("evidence_id")): evidence
        for evidence in evidence_items
        if evidence.get("evidence_id")
    }


def claim_supported_by_evidence(
    *,
    claim: dict[str, Any],
    evidence: dict[str, Any],
) -> bool:
    """Determine whether one evidence item appears to support a claim.

    This is deliberately conservative. Strong lexical or numeric
    agreement is treated as support. Ambiguous cases are not
    automatically rejected unless support is clearly insufficient.
    """

    claim_text = build_claim_support_text(claim)

    evidence_text = build_evidence_text(evidence)

    if not claim_text or not evidence_text:
        return False

    #
    # Strongest case:
    # the entire normalized claim content appears
    # in the source evidence.
    #
    if claim_text in evidence_text:
        return True

    claim_tokens = tokenize_text(claim_text)

    evidence_tokens = tokenize_text(evidence_text)

    if not claim_tokens:
        return False

    shared_tokens = claim_tokens & evidence_tokens

    token_coverage = len(shared_tokens) / len(claim_tokens)

    #
    # Numeric claims require explicit numeric agreement.
    #
    claim_numbers = extract_numeric_tokens(claim_text)

    evidence_numbers = extract_numeric_tokens(evidence_text)

    if claim_numbers and not (claim_numbers <= evidence_numbers):
        return False

        #
    # Structured medication facts must preserve medication identity.
    # Matching dose/form tokens alone must not allow one medication
    # to support a claim about a different medication.
    #
    predicate = normalize_text(
        claim.get(
            "predicate",
            "",
        )
    )

    if predicate == "documented_medication_fact":
        subject = claim.get(
            "subject",
            "",
        )

        medication_identity_tokens = extract_medication_identity_tokens(
            subject,
        )

        if medication_identity_tokens:
            evidence_identity_tokens = extract_medication_identity_tokens(
                evidence_text,
            )

            if not (medication_identity_tokens <= evidence_identity_tokens):
                return False

    #
    # High lexical overlap is considered sufficient
    # for the deterministic baseline.
    #
    return token_coverage >= 0.6


def claim_supported_by_any_evidence(
    *,
    claim: dict[str, Any],
    evidence_items: list[dict[str, Any]],
) -> bool:
    """Return True if any cited evidence item supports the claim."""

    return any(
        claim_supported_by_evidence(
            claim=claim,
            evidence=evidence,
        )
        for evidence in evidence_items
    )


def build_unsupported_claim_id(
    *,
    case_id: str,
    claim_id: str,
    subtype: str,
) -> str:
    """Create a deterministic finding ID."""

    return str(
        uuid5(
            NAMESPACE_URL,
            (f"unsupported-claim:{case_id}:{claim_id}:{subtype}"),
        )
    )


def build_unsupported_claim_finding(
    *,
    case_id: str,
    claim: dict[str, Any],
    subtype: str,
    summary: str,
    evidence_ids: list[str],
    confidence: float,
) -> InvestigationFinding:
    """Build one standardized unsupported-claim finding."""

    claim_id = str(
        claim.get(
            "claim_id",
            "",
        )
    )

    claim_text = build_claim_text(claim)

    return InvestigationFinding(
        finding_id=(
            build_unsupported_claim_id(
                case_id=case_id,
                claim_id=claim_id,
                subtype=subtype,
            )
        ),
        case_id=case_id,
        finding_type=(FindingType.UNSUPPORTED_CLAIM),
        subtype=subtype,
        severity=(FindingSeverity.MEDIUM),
        title=("Clinical claim lacks sufficient documented support"),
        summary=(f"{summary} Claim: {claim_text}"),
        evidence_ids=evidence_ids,
        claim_ids=[claim_id],
        event_ids=[],
        medication_key=None,
        confidence=confidence,
        requires_human_review=True,
        source=(FindingSource.UNSUPPORTED_CLAIM_ANALYSIS),
    )


def detect_unsupported_claims(
    *,
    case_id: str,
    clinical_claims: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
) -> list[InvestigationFinding]:
    """Detect claims with missing or insufficient provenance support."""

    evidence_index = build_evidence_index(evidence_items)

    findings: list[InvestigationFinding] = []

    for claim in clinical_claims:
        claim_id = str(
            claim.get(
                "claim_id",
                "",
            )
        )

        if not claim_id:
            continue

        source_evidence_ids = [
            str(evidence_id)
            for evidence_id in (
                claim.get(
                    "source_evidence_ids",
                    [],
                )
                or []
            )
            if evidence_id
        ]

        #
        # Case 1:
        # Claim has no provenance at all.
        #
        if not source_evidence_ids:
            findings.append(
                build_unsupported_claim_finding(
                    case_id=case_id,
                    claim=claim,
                    subtype=("missing_provenance"),
                    summary=("The claim does not reference any source evidence."),
                    evidence_ids=[],
                    confidence=1.0,
                )
            )

            continue

        resolved_evidence = [
            evidence_index[evidence_id]
            for evidence_id in source_evidence_ids
            if evidence_id in evidence_index
        ]

        #
        # Case 2:
        # Provenance IDs exist, but none can
        # be resolved to actual evidence records.
        #
        if not resolved_evidence:
            findings.append(
                build_unsupported_claim_finding(
                    case_id=case_id,
                    claim=claim,
                    subtype=("missing_source_evidence"),
                    summary=(
                        "The claim references source "
                        "evidence IDs that are not "
                        "present in the case evidence."
                    ),
                    evidence_ids=(source_evidence_ids),
                    confidence=1.0,
                )
            )

            continue

        #
        # Case 3:
        # At least one referenced evidence item exists,
        # but none sufficiently supports the claim.
        #
        if not claim_supported_by_any_evidence(
            claim=claim,
            evidence_items=resolved_evidence,
        ):
            findings.append(
                build_unsupported_claim_finding(
                    case_id=case_id,
                    claim=claim,
                    subtype=("insufficient_evidence_support"),
                    summary=(
                        "Referenced evidence was found, "
                        "but the deterministic support "
                        "check could not verify sufficient "
                        "agreement with the claim."
                    ),
                    evidence_ids=(source_evidence_ids),
                    confidence=0.75,
                )
            )

    return findings

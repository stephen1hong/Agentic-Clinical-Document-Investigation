"""Extract structured evidence and claims from clinical documents."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from clinical_investigation.investigation.models import (
    ClaimType,
    ClinicalClaim,
    DocumentType,
    EvidenceItem,
    ExtractionManifest,
    ExtractionMethod,
)

DOCUMENT_FILES: dict[DocumentType, str] = {
    DocumentType.ADMISSION_NOTE: "admission_note.md",
    DocumentType.PROGRESS_NOTE: "progress_note.md",
    DocumentType.LAB_REPORT: "lab_report.md",
    DocumentType.MEDICATION_RECONCILIATION: ("medication_reconciliation.md"),
    DocumentType.DISCHARGE_SUMMARY: "discharge_summary.md",
    DocumentType.FOLLOW_UP_NOTE: "follow_up_note.md",
}


PROVENANCE_PATTERN = re.compile(
    r"\[Source:\s*([^:\]]+):([^\]]+)\]",
    flags=re.IGNORECASE,
)

TABLE_PROVENANCE_PATTERN = re.compile(
    r"\b("
    r"conditions|"
    r"medications|"
    r"observations|"
    r"procedures|"
    r"encounters"
    r"):(\d+)\b",
    flags=re.IGNORECASE,
)

MARKDOWN_EMPHASIS_PATTERN = re.compile(r"[*_`]+")

TABLE_SEPARATOR_PATTERN = re.compile(r"^\s*\|?[\s:\-|]+\|?\s*$")


class EvidenceExtractionError(RuntimeError):
    """Raised when evidence extraction cannot be completed."""


def read_json(path: Path) -> Any:
    """Read one JSON file."""

    if not path.exists():
        raise EvidenceExtractionError(f"Required file not found: {path}")

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvidenceExtractionError(f"Invalid JSON file {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    """Write formatted JSON."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    """Calculate the SHA-256 digest of one file."""

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(8192),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def stable_identifier(
    namespace: str,
    *parts: object,
) -> str:
    """Create a reproducible identifier."""

    payload = "|".join(str(part) for part in parts)

    return str(
        uuid5(
            NAMESPACE_URL,
            f"{namespace}:{payload}",
        )
    )


def normalize_whitespace(value: str) -> str:
    """Collapse repeated whitespace."""

    return " ".join(value.split())


def remove_markdown_formatting(
    value: str,
) -> str:
    """Remove common Markdown formatting markers."""

    normalized = value.strip()

    if normalized.startswith("- "):
        normalized = normalized[2:]

    normalized = MARKDOWN_EMPHASIS_PATTERN.sub(
        "",
        normalized,
    )

    return normalize_whitespace(normalized)


def remove_provenance_marker(
    value: str,
) -> str:
    """Remove embedded source markers from display text."""

    return normalize_whitespace(PROVENANCE_PATTERN.sub("", value))


def parse_source_reference(
    line: str,
) -> tuple[str | None, int | None]:
    """Parse source table and row from document provenance."""

    match = PROVENANCE_PATTERN.search(line)

    if match is None:
        match = TABLE_PROVENANCE_PATTERN.search(line)

    if match is None:
        return None, None

    source_table = match.group(1).strip().lower()
    raw_row = match.group(2).strip()

    try:
        source_row = int(raw_row)
    except (TypeError, ValueError):
        source_row = None

    return source_table, source_row


def split_markdown_table_row(
    line: str,
) -> list[str]:
    """Split one Markdown table row into cells."""

    stripped = line.strip().strip("|")

    return [remove_markdown_formatting(cell.strip()) for cell in stripped.split("|")]


def is_ignorable_line(line: str) -> bool:
    """Return whether a line contains no extractable evidence."""

    stripped = line.strip()

    if not stripped:
        return True

    if TABLE_SEPARATOR_PATTERN.match(stripped):
        return True

    if stripped.startswith("> Synthetic clinical document"):
        return True

    return stripped.startswith("> This document is for software")


def evidence_confidence(
    source_table: str | None,
) -> float:
    """Assign confidence based on provenance strength."""

    if source_table is not None:
        return 1.0

    return 0.95


def extract_document_evidence(
    *,
    case_id: str,
    document_type: DocumentType,
    document_path: Path,
) -> list[EvidenceItem]:
    """Extract line-level evidence from one Markdown document."""

    if not document_path.exists():
        raise EvidenceExtractionError(f"Clinical document not found: {document_path}")

    lines = document_path.read_text(encoding="utf-8").splitlines()

    current_section = "Document Header"
    evidence_items: list[EvidenceItem] = []

    for line_number, raw_line in enumerate(
        lines,
        start=1,
    ):
        stripped = raw_line.strip()

        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()

            if heading:
                current_section = heading

            continue

        if is_ignorable_line(raw_line):
            continue

        source_table, source_row = parse_source_reference(raw_line)

        without_source = remove_provenance_marker(raw_line)

        normalized_fact = remove_markdown_formatting(without_source)

        if not normalized_fact:
            continue

        evidence_id = stable_identifier(
            "evidence",
            case_id,
            document_type.value,
            line_number,
            normalized_fact,
        )

        method = (
            ExtractionMethod.DETERMINISTIC_PROVENANCE
            if source_table is not None
            else ExtractionMethod.DETERMINISTIC_MARKDOWN
        )

        if "|" in raw_line:
            method = ExtractionMethod.DETERMINISTIC_TABLE

        evidence_items.append(
            EvidenceItem(
                evidence_id=evidence_id,
                case_id=case_id,
                document_type=document_type,
                source_file=document_path.name,
                source_line=line_number,
                section=current_section,
                text_span=raw_line.strip(),
                normalized_fact=normalized_fact,
                source_table=source_table,
                source_row=source_row,
                extraction_confidence=evidence_confidence(source_table),
                extraction_method=method,
            )
        )

    return evidence_items


def infer_claim_type(
    evidence: EvidenceItem,
) -> ClaimType:
    """Infer a claim category from document and provenance."""

    if evidence.source_table == "conditions":
        return ClaimType.CONDITION_PRESENCE

    if evidence.source_table == "medications":
        return ClaimType.MEDICATION_STATUS

    if evidence.source_table == "observations":
        return ClaimType.OBSERVATION_RESULT

    if evidence.source_table == "procedures":
        return ClaimType.PROCEDURE_EVENT

    if evidence.source_table == "encounters":
        return ClaimType.ENCOUNTER_EVENT

    if evidence.document_type == DocumentType.MEDICATION_RECONCILIATION:
        return ClaimType.MEDICATION_STATUS

    if evidence.document_type == DocumentType.LAB_REPORT:
        return ClaimType.OBSERVATION_RESULT

    if (
        evidence.document_type == DocumentType.FOLLOW_UP_NOTE
        and "follow" in evidence.section.lower()
    ):
        return ClaimType.FOLLOW_UP_ACTION

    return ClaimType.NARRATIVE_STATEMENT


def should_create_claim(
    evidence: EvidenceItem,
) -> bool:
    """Return whether evidence represents a meaningful clinical claim."""

    lower_text = evidence.normalized_fact.strip().lower()

    ignored_prefixes = (
        "case id:",
        "patient:",
        "patient id:",
        "date of birth:",
        "encounter id:",
        "encounter class:",
        "encounter start:",
        "encounter stop:",
    )

    if lower_text.startswith(ignored_prefixes):
        return False

    ignored_phrases = (
        "this report does not apply external",
        "this note summarizes events",
        "this section summarizes structured",
        "structured evidence review pending",
        "this synthetic discharge summary",
        "no real post-discharge clinical encounter",
        "no observations available",
        "medication statuses are derived",
    )

    if any(phrase in lower_text for phrase in ignored_phrases):
        return False

    if lower_text.startswith("observation status is reported as"):
        return False

    #
    # Markdown table headers are structural elements,
    # not clinical facts.
    #
    if "|" in evidence.text_span:
        cells = split_markdown_table_row(remove_provenance_marker(evidence.text_span))

        lower_cells = {cell.strip().lower() for cell in cells if cell.strip()}

        lab_header = {
            "date",
            "observation",
            "value",
            "flag status",
            "source",
        }

        medication_header_base = {
            "medication",
            "start",
            "stop",
            "source",
        }

        has_medication_status_header = any(
            cell
            in {
                "status",
                "encounter status",
            }
            for cell in lower_cells
        )

        if lab_header.issubset(lower_cells):
            return False

        if medication_header_base.issubset(lower_cells) and has_medication_status_header:
            return False

    return True


def claim_parts_from_table(
    evidence: EvidenceItem,
) -> tuple[str, str, str] | None:
    """Extract subject, predicate, and value from a table row."""

    if "|" not in evidence.text_span:
        return None

    cells = split_markdown_table_row(remove_provenance_marker(evidence.text_span))

    if not cells:
        return None

    lower_cells = [cell.lower() for cell in cells]

    if any(
        header in lower_cells
        for header in (
            "observation",
            "medication",
            "date",
        )
    ):
        return None

    if evidence.document_type == DocumentType.LAB_REPORT and len(cells) >= 4:
        subject = cells[1] or "Observation"
        value = f"{cells[2]}; flag status: {cells[3]}"

        return subject, "result", value

    if evidence.document_type == DocumentType.MEDICATION_RECONCILIATION and len(cells) >= 4:
        subject = cells[0] or "Medication"
        value = f"start={cells[1]}; stop={cells[2]}; status={cells[3]}"

        return subject, "encounter_status", value

    return None


def generic_claim_parts(
    evidence: EvidenceItem,
    claim_type: ClaimType,
) -> tuple[str, str, str]:
    """Create normalized claim fields from non-table evidence."""

    fact = evidence.normalized_fact

    if ";" in fact:
        subject, remainder = fact.split(
            ";",
            maxsplit=1,
        )

        subject = subject.strip()
        remainder = remainder.strip()
    else:
        subject = fact
        remainder = fact

    predicates = {
        ClaimType.CONDITION_PRESENCE: "documented_as_active",
        ClaimType.MEDICATION_STATUS: "documented_medication_fact",
        ClaimType.OBSERVATION_RESULT: "documented_observation",
        ClaimType.PROCEDURE_EVENT: "documented_procedure",
        ClaimType.FOLLOW_UP_ACTION: "requires_evidence_review",
        ClaimType.ENCOUNTER_EVENT: "documented_encounter_event",
        ClaimType.NARRATIVE_STATEMENT: "states",
    }

    return (
        subject,
        predicates[claim_type],
        remainder,
    )


def build_claim_from_evidence(
    evidence: EvidenceItem,
) -> ClinicalClaim | None:
    """Build one normalized claim from one evidence item."""

    if not should_create_claim(evidence):
        return None

    claim_type = infer_claim_type(evidence)

    table_parts = claim_parts_from_table(evidence)

    if table_parts is not None:
        subject, predicate, value = table_parts
    else:
        subject, predicate, value = generic_claim_parts(
            evidence,
            claim_type,
        )

    if not subject or not value:
        return None

    claim_id = stable_identifier(
        "claim",
        evidence.case_id,
        claim_type.value,
        evidence.evidence_id,
        subject,
        predicate,
        value,
    )

    return ClinicalClaim(
        claim_id=claim_id,
        case_id=evidence.case_id,
        claim_type=claim_type,
        subject=subject,
        predicate=predicate,
        value=value,
        source_evidence_ids=[evidence.evidence_id],
        extraction_confidence=(evidence.extraction_confidence),
        extraction_method=(evidence.extraction_method),
    )


def deduplicate_claims(
    claims: list[ClinicalClaim],
) -> list[ClinicalClaim]:
    """Remove exact duplicate normalized claims."""

    deduplicated: dict[
        tuple[str, str, str, str],
        ClinicalClaim,
    ] = {}

    for claim in claims:
        key = (
            claim.claim_type.value,
            claim.subject.lower(),
            claim.predicate.lower(),
            claim.value.lower(),
        )

        existing = deduplicated.get(key)

        if existing is None:
            deduplicated[key] = claim
            continue

        combined_ids = sorted(set(existing.source_evidence_ids + claim.source_evidence_ids))

        deduplicated[key] = existing.model_copy(
            update={
                "source_evidence_ids": combined_ids,
                "extraction_confidence": max(
                    existing.extraction_confidence,
                    claim.extraction_confidence,
                ),
            }
        )

    return list(deduplicated.values())


def extract_case_evidence(
    document_dir: Path,
) -> tuple[
    list[EvidenceItem],
    list[ClinicalClaim],
]:
    """Extract all evidence and claims for one case."""

    if not document_dir.exists():
        raise EvidenceExtractionError(f"Document directory does not exist: {document_dir}")

    case_id = document_dir.name

    all_evidence: list[EvidenceItem] = []

    for document_type, filename in DOCUMENT_FILES.items():
        document_path = document_dir / filename

        document_evidence = extract_document_evidence(
            case_id=case_id,
            document_type=document_type,
            document_path=document_path,
        )

        all_evidence.extend(document_evidence)

    all_claims = [
        claim
        for evidence in all_evidence
        if (claim := build_claim_from_evidence(evidence)) is not None
    ]

    return (
        all_evidence,
        deduplicate_claims(all_claims),
    )


def build_investigation_case(
    document_dir: Path,
    output_root: Path,
) -> Path:
    """Build the evidence-extraction output for one case."""

    case_id = document_dir.name

    evidence_items, claims = extract_case_evidence(document_dir)

    evidence_ids = {item.evidence_id for item in evidence_items}

    for claim in claims:
        missing_ids = set(claim.source_evidence_ids) - evidence_ids

        if missing_ids:
            raise EvidenceExtractionError(
                f"Claim {claim.claim_id} references missing evidence IDs: {sorted(missing_ids)}"
            )

    output_dir = output_root / case_id
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    write_json(
        output_dir / "evidence_items.json",
        [item.model_dump(mode="json") for item in evidence_items],
    )

    write_json(
        output_dir / "clinical_claims.json",
        [claim.model_dump(mode="json") for claim in claims],
    )

    document_hashes = {
        filename: sha256_file(document_dir / filename) for filename in DOCUMENT_FILES.values()
    }

    evidence_counts = Counter(item.document_type.value for item in evidence_items)

    claim_counts = Counter(claim.claim_type.value for claim in claims)

    manifest = ExtractionManifest(
        schema_version="1.0",
        case_id=case_id,
        generated_at=datetime.now(UTC),
        extraction_method=("deterministic_markdown_v1"),
        source_documents=list(DOCUMENT_FILES.values()),
        source_document_hashes=(document_hashes),
        evidence_count=len(evidence_items),
        claim_count=len(claims),
        evidence_count_by_document=dict(evidence_counts),
        claim_count_by_type=dict(claim_counts),
    )

    write_json(
        output_dir / "extraction_manifest.json",
        manifest.model_dump(mode="json"),
    )

    return output_dir


def build_investigation_case_from_documents(
    *,
    case_id: str,
    documents_dir: Path,
    output_dir: Path,
) -> Path:
    """Build Milestone 1 evidence and claims from arbitrary documents.

    This entry point is used by both the normal investigation pipeline
    and the mutation-based evaluation pipeline.

    Parameters
    ----------
    case_id:
        Identifier assigned to the investigation case.
    documents_dir:
        Directory containing the six generated Markdown documents.
    output_dir:
        Directory where evidence_items.json, clinical_claims.json,
        and extraction_manifest.json will be written.

    Returns
    -------
    Path
        The output directory.
    """

    if not documents_dir.exists():
        raise EvidenceExtractionError(
            f"Clinical document directory does not exist: {documents_dir}"
        )

    if not documents_dir.is_dir():
        raise EvidenceExtractionError(f"Clinical document path is not a directory: {documents_dir}")

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    evidence_items: list[EvidenceItem] = []
    clinical_claims: list[ClinicalClaim] = []

    source_documents: list[str] = []
    document_hashes: dict[str, str] = {}

    for document_type, filename in DOCUMENT_FILES.items():
        document_path = documents_dir / filename

        if not document_path.exists():
            raise EvidenceExtractionError(f"Missing required clinical document: {document_path}")

        source_documents.append(filename)

        document_text = document_path.read_text(encoding="utf-8")

        document_hashes[filename] = hashlib.sha256(document_text.encode("utf-8")).hexdigest()

        current_section = "document"

        lines = document_text.splitlines()

        for line_number, line in enumerate(
            lines,
            start=1,
        ):
            stripped = line.strip()

            if not stripped:
                continue

            #
            # Track Markdown section.
            #
            if stripped.startswith("#"):
                section_text = stripped.lstrip("#").strip()

                if section_text:
                    current_section = section_text

                continue

            #
            # Skip Markdown table separator rows.
            #
            if re.fullmatch(
                r"\|?(?:\s*:?-+:?\s*\|)+"
                r"\s*:?-+:?\s*\|?",
                stripped,
            ):
                continue

            #
            # Skip synthetic-document disclaimers.
            #
            if stripped.startswith("> Synthetic clinical document"):
                continue

            if stripped.startswith("> This document is for software"):
                continue

            #
            # Ignore obvious Markdown decoration without
            # discarding the underlying text.
            #
            normalized_fact = stripped

            normalized_fact = re.sub(
                r"^\s*[-*+]\s+",
                "",
                normalized_fact,
            )

            normalized_fact = normalized_fact.replace(
                "**",
                "",
            )

            normalized_fact = normalized_fact.strip()

            if not normalized_fact:
                continue

            #
            # Determine source-table provenance such as:
            #
            # [Source: medications:40]
            #
            # or:
            #
            # medications:40
            #
            source_table: str | None = None
            source_row: int | None = None

            source_reference = parse_source_reference(normalized_fact)

            if source_reference is not None:
                raw_source_table = source_reference[0]
                raw_source_row = source_reference[1]

                try:
                    source_row = int(raw_source_row)
                except (TypeError, ValueError):
                    source_table = None
                    source_row = None
                else:
                    source_table = str(raw_source_table).strip()

            #
            # Remove provenance marker only from the
            # normalized human-readable fact.
            #
            fact_without_provenance = re.sub(
                r"\s*\[Source:\s*"
                r"[^:\]]+:[^\]]+\]\s*",
                " ",
                normalized_fact,
                flags=re.IGNORECASE,
            )

            fact_without_provenance = " ".join(fact_without_provenance.split())

            if not fact_without_provenance:
                continue

            #
            # Determine extraction method.
            #
            if source_table is not None:
                extraction_method = ExtractionMethod.DETERMINISTIC_PROVENANCE
            elif stripped.startswith("|"):
                extraction_method = ExtractionMethod.DETERMINISTIC_TABLE
            else:
                extraction_method = ExtractionMethod.DETERMINISTIC_MARKDOWN

            #
            # Try to extract a timestamp from the line.
            #
            event_time = None

            iso_time_match = re.search(
                r"\b\d{4}-\d{2}-\d{2}"
                r"(?:T\d{2}:\d{2}"
                r"(?::\d{2}(?:\.\d+)?)?"
                r"(?:Z|[+-]\d{2}:\d{2})?)?\b",
                fact_without_provenance,
            )

            if iso_time_match is not None:
                time_text = iso_time_match.group(0)

                try:
                    normalized_time_text = (
                        time_text[:-1] + "+00:00" if time_text.endswith("Z") else time_text
                    )

                    parsed_time = datetime.fromisoformat(normalized_time_text)

                    if parsed_time.tzinfo is None:
                        parsed_time = parsed_time.replace(tzinfo=UTC)

                    event_time = parsed_time

                except ValueError:
                    event_time = None

            #
            # Build deterministic evidence ID.
            #
            evidence_key = "|".join(
                [
                    case_id,
                    document_type.value,
                    filename,
                    str(line_number),
                    current_section,
                    fact_without_provenance,
                ]
            )

            evidence_id = str(
                uuid5(
                    NAMESPACE_URL,
                    "evidence:" + evidence_key,
                )
            )

            evidence = EvidenceItem(
                evidence_id=evidence_id,
                case_id=case_id,
                document_type=document_type,
                source_file=filename,
                source_line=line_number,
                section=current_section,
                text_span=stripped,
                normalized_fact=(fact_without_provenance),
                source_table=source_table,
                source_row=source_row,
                event_time=event_time,
                extraction_confidence=1.0,
                extraction_method=(extraction_method),
            )

            evidence_items.append(evidence)

            #
            # Decide whether this evidence should also
            # become a clinical claim.
            #
            if not should_create_claim(evidence):
                continue

            claim_type = infer_claim_type(evidence)

            #
            # Derive a conservative subject/predicate/value.
            #
            subject = fact_without_provenance
            predicate = "documented_clinical_fact"
            value = fact_without_provenance

            #
            # Medication rows.
            #
            if claim_type == ClaimType.MEDICATION_STATUS:
                medication_text = fact_without_provenance

                #
                # Prefer text before semicolon or table
                # delimiter as medication subject.
                #
                if ";" in medication_text:
                    subject = medication_text.split(
                        ";",
                        maxsplit=1,
                    )[0].strip()

                    value = medication_text.split(
                        ";",
                        maxsplit=1,
                    )[1].strip()

                elif "|" in medication_text:
                    cells = [
                        cell.strip()
                        for cell in (medication_text.strip("|").split("|"))
                        if cell.strip()
                    ]

                    if cells:
                        subject = cells[0]

                    value = " | ".join(cells[1:]) if len(cells) > 1 else medication_text

                predicate = "documented_medication_fact"

            #
            # Observation rows.
            #
            elif claim_type == ClaimType.OBSERVATION_RESULT:
                cells = [
                    cell.strip()
                    for cell in (fact_without_provenance.strip("|").split("|"))
                    if cell.strip()
                ]

                if len(cells) >= 2:
                    #
                    # A date often occupies the first
                    # column. Prefer second column as
                    # observation subject in that case.
                    #
                    if re.fullmatch(
                        r"\d{4}-\d{2}-\d{2}.*",
                        cells[0],
                    ):
                        subject = cells[1]

                        value = " | ".join(cells[2:]) if len(cells) > 2 else cells[1]

                    else:
                        subject = cells[0]

                        value = " | ".join(cells[1:])

                predicate = "observation_result"

            #
            # Condition rows.
            #
            elif claim_type == ClaimType.CONDITION_PRESENCE:
                predicate = "condition_present"

            #
            # Procedure rows.
            #
            elif claim_type == ClaimType.PROCEDURE_EVENT:
                predicate = "procedure_documented"

            #
            # Follow-up rows.
            #
            elif claim_type == ClaimType.FOLLOW_UP_ACTION:
                predicate = "follow_up_documented"

            #
            # Encounter rows.
            #
            elif claim_type == ClaimType.ENCOUNTER_EVENT:
                predicate = "encounter_event"

            subject = subject.strip()
            predicate = predicate.strip()
            value = value.strip()

            if not subject:
                subject = fact_without_provenance

            if not value:
                value = fact_without_provenance

            claim_key = "|".join(
                [
                    case_id,
                    claim_type.value,
                    subject,
                    predicate,
                    value,
                    evidence_id,
                ]
            )

            claim_id = str(
                uuid5(
                    NAMESPACE_URL,
                    "claim:" + claim_key,
                )
            )

            claim = ClinicalClaim(
                claim_id=claim_id,
                case_id=case_id,
                claim_type=claim_type,
                subject=subject,
                predicate=predicate,
                value=value,
                time_start=event_time,
                time_end=None,
                source_evidence_ids=[evidence_id],
                extraction_confidence=1.0,
                extraction_method=(extraction_method),
            )

            clinical_claims.append(claim)

    #
    # Deduplicate evidence conservatively by evidence ID.
    #
    evidence_by_id = {item.evidence_id: item for item in evidence_items}

    evidence_items = list(evidence_by_id.values())

    #
    # Deduplicate claims by semantic content.
    #
    claim_groups: dict[
        tuple[
            str,
            str,
            str,
            str,
        ],
        ClinicalClaim,
    ] = {}

    for claim in clinical_claims:
        key = (
            claim.claim_type.value,
            claim.subject.strip().lower(),
            claim.predicate.strip().lower(),
            claim.value.strip().lower(),
        )

        existing = claim_groups.get(key)

        if existing is None:
            claim_groups[key] = claim
            continue

        merged_evidence_ids = list(
            dict.fromkeys(
                [
                    *existing.source_evidence_ids,
                    *claim.source_evidence_ids,
                ]
            )
        )

        claim_groups[key] = existing.model_copy(
            update={
                "source_evidence_ids": (merged_evidence_ids),
                "extraction_confidence": max(
                    existing.extraction_confidence,
                    claim.extraction_confidence,
                ),
            }
        )

    clinical_claims = list(claim_groups.values())

    #
    # Validate claim → evidence references.
    #
    valid_evidence_ids = {item.evidence_id for item in evidence_items}

    for claim in clinical_claims:
        missing_evidence_ids = set(claim.source_evidence_ids) - valid_evidence_ids

        if missing_evidence_ids:
            raise EvidenceExtractionError(
                f"Claim {claim.claim_id} references "
                f"missing evidence IDs: "
                f"{sorted(missing_evidence_ids)}"
            )

    #
    # Stable output ordering.
    #
    evidence_items.sort(
        key=lambda item: (
            item.source_file,
            item.source_line,
            item.evidence_id,
        )
    )

    clinical_claims.sort(
        key=lambda claim: (
            claim.claim_type.value,
            claim.subject.lower(),
            claim.claim_id,
        )
    )

    #
    # Write evidence_items.json.
    #
    write_json(
        output_dir / "evidence_items.json",
        [item.model_dump(mode="json") for item in evidence_items],
    )

    #
    # Write clinical_claims.json.
    #
    write_json(
        output_dir / "clinical_claims.json",
        [claim.model_dump(mode="json") for claim in clinical_claims],
    )

    #
    # Build extraction manifest.
    #
    evidence_count_by_document: dict[str, int] = {}

    for evidence in evidence_items:
        document_key = evidence.document_type.value

        evidence_count_by_document[document_key] = (
            evidence_count_by_document.get(
                document_key,
                0,
            )
            + 1
        )

    claim_count_by_type: dict[str, int] = {}

    for claim in clinical_claims:
        claim_key = claim.claim_type.value

        claim_count_by_type[claim_key] = (
            claim_count_by_type.get(
                claim_key,
                0,
            )
            + 1
        )

    evidence_count_by_document: dict[str, int] = {}

    for evidence in evidence_items:
        document_key = evidence.document_type.value
        evidence_count_by_document[document_key] = (
            evidence_count_by_document.get(
                document_key,
                0,
            )
            + 1
        )

    claim_count_by_type: dict[str, int] = {}

    for claim in clinical_claims:
        claim_key = claim.claim_type.value
        claim_count_by_type[claim_key] = (
            claim_count_by_type.get(
                claim_key,
                0,
            )
            + 1
        )

    manifest = ExtractionManifest(
        schema_version="1.0",
        case_id=case_id,
        generated_at=datetime.now(UTC),
        extraction_method=("deterministic_evidence_extraction_v1"),
        source_documents=source_documents,
        source_document_hashes=document_hashes,
        evidence_count=len(evidence_items),
        claim_count=len(clinical_claims),
        evidence_count_by_document=(evidence_count_by_document),
        claim_count_by_type=(claim_count_by_type),
    )

    write_json(
        output_dir / "extraction_manifest.json",
        manifest.model_dump(mode="json"),
    )

    return output_dir

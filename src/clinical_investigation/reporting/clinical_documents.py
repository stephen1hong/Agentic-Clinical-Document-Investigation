"""Generate deterministic clinical documents from encounter evidence bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

DOCUMENT_TYPES = (
    "admission_note",
    "progress_note",
    "lab_report",
    "medication_reconciliation",
    "discharge_summary",
    "follow_up_note",
)


class ClinicalDocumentError(RuntimeError):
    """Raised when clinical document generation fails."""


@dataclass(frozen=True)
class GeneratedDocument:
    """Metadata describing one generated clinical document."""

    document_type: str
    filename: str
    title: str
    source_files: list[str]
    evidence_count: int


@dataclass(frozen=True)
class DocumentGenerationResult:
    """Result produced after generating one encounter document set."""

    case_id: str
    output_dir: Path
    documents: list[GeneratedDocument]


def read_json(path: Path) -> Any:
    """Read one JSON file."""

    if not path.exists():
        raise ClinicalDocumentError(f"Required file not found: {path}")

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ClinicalDocumentError(f"Invalid JSON file {path}: {exc}") from exc


def write_json(path: Path, payload: Any) -> None:
    """Write formatted JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    """Write normalized UTF-8 text."""

    path.parent.mkdir(parents=True, exist_ok=True)

    normalized = text.rstrip() + "\n"

    path.write_text(
        normalized,
        encoding="utf-8",
    )


def parse_datetime(value: Any) -> datetime | None:
    """Parse an ISO date or datetime."""

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
        try:
            parsed_date = date.fromisoformat(text)
        except ValueError:
            return None

        parsed = datetime.combine(
            parsed_date,
            datetime.min.time(),
            tzinfo=UTC,
        )

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed.astimezone(UTC)


def format_datetime(value: Any) -> str:
    """Format a clinical timestamp for document display."""

    parsed = parse_datetime(value)

    if parsed is None:
        return "Unknown"

    if parsed.hour == 0 and parsed.minute == 0:
        return parsed.strftime("%B %d, %Y")

    return parsed.strftime("%B %d, %Y at %H:%M UTC")


def first_nonempty(
    record: dict[str, Any],
    *fields: str,
    default: str = "Not documented",
) -> str:
    """Return the first usable field value."""

    for field in fields:
        value = record.get(field)

        if value is not None and str(value).strip():
            return str(value).strip()

    return default


def record_reference(
    source_table: str,
    record: dict[str, Any],
) -> str:
    """Create a stable source reference."""

    source_row = record.get("_source_row", "unknown")

    return f"{source_table}:{source_row}"


def provenance_line(
    source_table: str,
    record: dict[str, Any],
) -> str:
    """Create a readable provenance marker."""

    return f"[Source: {record_reference(source_table, record)}]"


def load_encounter_case(case_dir: Path) -> dict[str, Any]:
    """Load one encounter evidence bundle."""

    required_files = {
        "case": case_dir / "case.json",
        "patient_context": case_dir / "patient_context.json",
        "encounter": case_dir / "encounter.json",
        "active_conditions": case_dir / "active_conditions.json",
        "medications": case_dir / "medications.json",
        "observations": case_dir / "observations.json",
        "procedures": case_dir / "procedures.json",
        "discharge_candidates": case_dir / "discharge_candidates.json",
        "timeline": case_dir / "timeline.json",
        "summary": case_dir / "summary.json",
    }

    package = {name: read_json(path) for name, path in required_files.items()}

    object_fields = {
        "case",
        "patient_context",
        "encounter",
        "summary",
    }

    list_fields = {
        "active_conditions",
        "medications",
        "observations",
        "procedures",
        "discharge_candidates",
        "timeline",
    }

    for field in object_fields:
        if not isinstance(package[field], dict):
            raise ClinicalDocumentError(f"{required_files[field]} must contain a JSON object")

    for field in list_fields:
        if not isinstance(package[field], list):
            raise ClinicalDocumentError(f"{required_files[field]} must contain a JSON list")

    return package


def patient_display_name(
    patient_context: dict[str, Any],
) -> str:
    """Return a readable synthetic patient name."""

    patient = patient_context.get("patient", {})

    first = first_nonempty(
        patient,
        "first",
        "FIRST",
        default="Synthetic",
    )

    last = first_nonempty(
        patient,
        "last",
        "LAST",
        default="Patient",
    )

    return f"{first} {last}"


def patient_identifier(
    patient_context: dict[str, Any],
) -> str:
    """Return the synthetic patient identifier."""

    patient = patient_context.get("patient", {})

    return first_nonempty(
        patient,
        "id",
        "Id",
        "ID",
        default=str(patient_context.get("patient_id", "Unknown")),
    )


def patient_birthdate(
    patient_context: dict[str, Any],
) -> str:
    """Return patient birthdate."""

    patient = patient_context.get("patient", {})

    return first_nonempty(
        patient,
        "birthdate",
        "BIRTHDATE",
    )


def encounter_id(
    encounter: dict[str, Any],
) -> str:
    """Return encounter identifier."""

    return first_nonempty(
        encounter,
        "id",
        "Id",
        "ID",
    )


def encounter_description(
    encounter: dict[str, Any],
) -> str:
    """Return encounter description."""

    return first_nonempty(
        encounter,
        "description",
        "DESCRIPTION",
        "code",
        "CODE",
        default="Clinical encounter",
    )


def encounter_class(
    encounter: dict[str, Any],
) -> str:
    """Return encounter class."""

    return first_nonempty(
        encounter,
        "encounterclass",
        "class",
        "type",
        default="unknown",
    )


def document_header(
    title: str,
    case: dict[str, Any],
    patient_context: dict[str, Any],
    encounter: dict[str, Any],
) -> str:
    """Create the shared document header."""

    return "\n".join(
        [
            f"# {title}",
            "",
            f"**Case ID:** {case.get('case_id', 'Unknown')}",
            f"**Patient:** {patient_display_name(patient_context)}",
            f"**Patient ID:** {patient_identifier(patient_context)}",
            f"**Date of Birth:** {patient_birthdate(patient_context)}",
            f"**Encounter ID:** {encounter_id(encounter)}",
            f"**Encounter Class:** {encounter_class(encounter)}",
            f"**Encounter Start:** {format_datetime(encounter.get('start'))}",
            f"**Encounter Stop:** {format_datetime(encounter.get('stop'))}",
            "",
            "> Synthetic clinical document generated from Synthea data.",
            "> This document is for software development and evaluation only.",
            "",
        ]
    )


def render_condition_list(
    conditions: list[dict[str, Any]],
) -> list[str]:
    """Render conditions as markdown bullets."""

    if not conditions:
        return ["- No active conditions found in the supplied evidence."]

    lines: list[str] = []

    for condition in conditions:
        description = first_nonempty(
            condition,
            "description",
            "code",
        )

        start = format_datetime(condition.get("start"))

        lines.append(
            f"- {description}; onset/start: {start} {provenance_line('conditions', condition)}"
        )

    return lines


def render_admission_note(
    package: dict[str, Any],
) -> str:
    """Generate a structured admission note."""

    case = package["case"]
    patient_context = package["patient_context"]
    encounter = package["encounter"]
    conditions = package["active_conditions"]
    medications = package["medications"]

    header = document_header(
        title="Admission Note",
        case=case,
        patient_context=patient_context,
        encounter=encounter,
    )

    medication_lines = []

    if medications:
        for medication in medications:
            description = first_nonempty(
                medication,
                "description",
                "code",
            )

            medication_lines.append(f"- {description} {provenance_line('medications', medication)}")
    else:
        medication_lines.append("- No medications found in the supplied encounter evidence.")

    sections = [
        header,
        "## Reason for Encounter",
        "",
        encounter_description(encounter),
        "",
        "## Admission Context",
        "",
        (
            f"The synthetic patient entered a "
            f"{encounter_class(encounter)} encounter on "
            f"{format_datetime(encounter.get('start'))}."
        ),
        "",
        "## Active Conditions",
        "",
        *render_condition_list(conditions),
        "",
        "## Medications Present During Encounter",
        "",
        *medication_lines,
        "",
        "## Initial Assessment",
        "",
        (
            "This section summarizes structured encounter evidence only. "
            "No diagnosis or treatment recommendation has been generated."
        ),
    ]

    return "\n".join(sections)


def render_progress_note(
    package: dict[str, Any],
) -> str:
    """Generate a structured progress note."""

    case = package["case"]
    patient_context = package["patient_context"]
    encounter = package["encounter"]
    observations = package["observations"]
    procedures = package["procedures"]
    medications = package["medications"]

    header = document_header(
        title="Progress Note",
        case=case,
        patient_context=patient_context,
        encounter=encounter,
    )

    recent_observations = sorted(
        observations,
        key=lambda item: str(item.get("date") or ""),
    )[-10:]

    observation_lines = []

    for observation in recent_observations:
        description = first_nonempty(
            observation,
            "description",
            "code",
        )

        value = first_nonempty(
            observation,
            "value",
            default="Not documented",
        )

        units = first_nonempty(
            observation,
            "units",
            "unit",
            default="",
        )

        value_text = f"{value} {units}".strip()

        observation_lines.append(
            f"- {format_datetime(observation.get('date'))}: "
            f"{description} = {value_text} "
            f"{provenance_line('observations', observation)}"
        )

    if not observation_lines:
        observation_lines.append("- No observations found for this encounter.")

    procedure_lines = []

    for procedure in procedures:
        description = first_nonempty(
            procedure,
            "description",
            "code",
        )

        procedure_lines.append(
            f"- {format_datetime(procedure.get('date'))}: "
            f"{description} "
            f"{provenance_line('procedures', procedure)}"
        )

    if not procedure_lines:
        procedure_lines.append("- No procedures found for this encounter.")

    medication_lines = []

    for medication in medications:
        description = first_nonempty(
            medication,
            "description",
            "code",
        )

        medication_lines.append(
            f"- {description}; "
            f"start: {format_datetime(medication.get('start'))}; "
            f"stop: {format_datetime(medication.get('stop'))} "
            f"{provenance_line('medications', medication)}"
        )

    if not medication_lines:
        medication_lines.append("- No medication records found.")

    sections = [
        header,
        "## Interval Summary",
        "",
        (
            "This note summarizes events found in the structured encounter "
            "record. It does not infer undocumented symptoms, examination "
            "findings, diagnoses, or clinical decisions."
        ),
        "",
        "## Recent Observations",
        "",
        *observation_lines,
        "",
        "## Procedures",
        "",
        *procedure_lines,
        "",
        "## Medication Activity",
        "",
        *medication_lines,
        "",
        "## Assessment Status",
        "",
        "Structured evidence review pending agentic reconciliation.",
    ]

    return "\n".join(sections)


def explicit_abnormal_status(
    observation: dict[str, Any],
) -> str:
    """Return explicit abnormal status without clinical interpretation."""

    fields = (
        "abnormal",
        "flag",
        "interpretation",
        "status",
    )

    abnormal_terms = (
        "abnormal",
        "high",
        "low",
        "critical",
        "positive",
    )

    for field in fields:
        value = observation.get(field)

        if value is None:
            continue

        normalized = str(value).strip().lower()

        if any(term in normalized for term in abnormal_terms):
            return f"Explicitly flagged abnormal: {value}"

    return "No explicit abnormal flag found"


def render_lab_report(
    package: dict[str, Any],
) -> str:
    """Generate a structured laboratory and observation report."""

    case = package["case"]
    patient_context = package["patient_context"]
    encounter = package["encounter"]
    observations = package["observations"]

    header = document_header(
        title="Laboratory and Observation Report",
        case=case,
        patient_context=patient_context,
        encounter=encounter,
    )

    lines = [
        "| Date | Observation | Value | Flag status | Source |",
        "|---|---|---:|---|---|",
    ]

    for observation in sorted(
        observations,
        key=lambda item: str(item.get("date") or ""),
    ):
        description = first_nonempty(
            observation,
            "description",
            "code",
        )

        value = first_nonempty(
            observation,
            "value",
        )

        units = first_nonempty(
            observation,
            "units",
            "unit",
            default="",
        )

        value_text = f"{value} {units}".strip()

        lines.append(
            "| "
            f"{format_datetime(observation.get('date'))} | "
            f"{description} | "
            f"{value_text} | "
            f"{explicit_abnormal_status(observation)} | "
            f"{record_reference('observations', observation)} |"
        )

    if len(lines) == 2:
        lines.append("| — | No observations available | — | — | — |")

    sections = [
        header,
        "## Important Interpretation Boundary",
        "",
        (
            'Observation status is reported as "Explicitly flagged abnormal" '
            "only when an abnormal flag is present in the source data. "
            "This report does not apply external clinical reference-range "
            "interpretation."
        ),
        "",
        "## Results",
        "",
        *lines,
    ]

    return "\n".join(sections)


def medication_status(
    medication: dict[str, Any],
    encounter: dict[str, Any],
) -> str:
    """Classify medication activity relative to the encounter."""

    med_start = parse_datetime(medication.get("start"))
    med_stop = parse_datetime(medication.get("stop"))
    encounter_start = parse_datetime(encounter.get("start"))
    encounter_stop = parse_datetime(encounter.get("stop"))

    if med_start is None:
        return "Status unclear"

    if encounter_stop is None:
        encounter_stop = encounter_start

    if encounter_start is None:
        return "Status unclear"

    if med_stop and med_stop < encounter_start:
        return "Stopped before encounter"

    if med_start > encounter_stop:
        return "Started after encounter"

    if med_stop and med_stop <= encounter_stop:
        return "Stopped during encounter"

    if med_start >= encounter_start:
        return "Started during encounter"

    return "Active during encounter"


def render_medication_reconciliation(
    package: dict[str, Any],
) -> str:
    """Generate a medication reconciliation document."""

    case = package["case"]
    patient_context = package["patient_context"]
    encounter = package["encounter"]
    medications = package["medications"]

    header = document_header(
        title="Medication Reconciliation",
        case=case,
        patient_context=patient_context,
        encounter=encounter,
    )

    lines = [
        "| Medication | Start | Stop | Encounter status | Source |",
        "|---|---|---|---|---|",
    ]

    for medication in medications:
        description = first_nonempty(
            medication,
            "description",
            "code",
        )

        lines.append(
            "| "
            f"{description} | "
            f"{format_datetime(medication.get('start'))} | "
            f"{format_datetime(medication.get('stop'))} | "
            f"{medication_status(medication, encounter)} | "
            f"{record_reference('medications', medication)} |"
        )

    if len(lines) == 2:
        lines.append("| No medications found | — | — | — | — |")

    sections = [
        header,
        "## Medication Records",
        "",
        *lines,
        "",
        "## Reconciliation Boundary",
        "",
        (
            "Medication statuses are derived from structured start and stop "
            "timestamps. The document does not determine whether a medication "
            "should be continued, discontinued, or changed."
        ),
    ]

    return "\n".join(sections)


def render_discharge_summary(
    package: dict[str, Any],
) -> str:
    """Generate a structured discharge summary."""

    case = package["case"]
    patient_context = package["patient_context"]
    encounter = package["encounter"]
    conditions = package["active_conditions"]
    medications = package["medications"]
    observations = package["observations"]
    procedures = package["procedures"]
    discharge_candidates = package["discharge_candidates"]

    header = document_header(
        title="Discharge Summary",
        case=case,
        patient_context=patient_context,
        encounter=encounter,
    )

    condition_lines = render_condition_list(conditions)

    procedure_lines = [
        (f"- {first_nonempty(item, 'description', 'code')} {provenance_line('procedures', item)}")
        for item in procedures
    ]

    if not procedure_lines:
        procedure_lines.append("- No procedures documented.")

    medication_lines = [
        (
            f"- {first_nonempty(item, 'description', 'code')}; "
            f"{medication_status(item, encounter)} "
            f"{provenance_line('medications', item)}"
        )
        for item in medications
    ]

    if not medication_lines:
        medication_lines.append("- No medication records documented.")

    candidate_lines = []

    for candidate in discharge_candidates:
        candidate_lines.append(
            f"- {candidate.get('candidate_type', 'unknown')}: "
            f"{candidate.get('display', 'Not documented')} at "
            f"{format_datetime(candidate.get('timestamp'))} "
            f"[Source: {candidate.get('source_table', 'unknown')}:"
            f"{candidate.get('source_row', 'unknown')}]"
        )

    if not candidate_lines:
        candidate_lines.append("- No discharge-review candidates were generated.")

    explicit_abnormal_count = sum(
        1
        for observation in observations
        if explicit_abnormal_status(observation) != "No explicit abnormal flag found"
    )

    sections = [
        header,
        "## Encounter Summary",
        "",
        (
            f"{encounter_description(encounter)} from "
            f"{format_datetime(encounter.get('start'))} through "
            f"{format_datetime(encounter.get('stop'))}."
        ),
        "",
        "## Active Conditions",
        "",
        *condition_lines,
        "",
        "## Procedures",
        "",
        *procedure_lines,
        "",
        "## Medication Status at Encounter End",
        "",
        *medication_lines,
        "",
        "## Observation Summary",
        "",
        f"- Total encounter observations: {len(observations)}",
        (f"- Explicitly flagged abnormal observations: {explicit_abnormal_count}"),
        "",
        "## Discharge-Review Candidates",
        "",
        *candidate_lines,
        "",
        "## Limitations",
        "",
        (
            "This synthetic discharge summary is generated from structured "
            "records. It does not infer undocumented discharge diagnoses, "
            "instructions, clinical reasoning, or treatment decisions."
        ),
    ]

    return "\n".join(sections)


def render_follow_up_note(
    package: dict[str, Any],
) -> str:
    """Generate a synthetic follow-up review note."""

    case = package["case"]
    patient_context = package["patient_context"]
    encounter = package["encounter"]
    discharge_candidates = package["discharge_candidates"]

    header = document_header(
        title="Follow-Up Review Note",
        case=case,
        patient_context=patient_context,
        encounter=encounter,
    )

    review_lines = []

    for candidate in discharge_candidates:
        candidate_type = candidate.get(
            "candidate_type",
            "unknown",
        )

        display = candidate.get(
            "display",
            "Not documented",
        )

        review_lines.append(
            f"- Review candidate: {candidate_type}; "
            f"evidence: {display}; "
            f"event time: {format_datetime(candidate.get('timestamp'))}; "
            f"status: evidence review pending."
        )

    if not review_lines:
        review_lines.append("- No follow-up review candidates were identified.")

    sections = [
        header,
        "## Follow-Up Status",
        "",
        (
            "No real post-discharge clinical encounter is represented by "
            "this generated note. It is an investigation placeholder for "
            "testing follow-up reconciliation workflows."
        ),
        "",
        "## Items for Evidence Review",
        "",
        *review_lines,
        "",
        "## Required Interpretation",
        "",
        (
            "The absence of a follow-up result in the supplied dataset must "
            "be reported as 'not found in the supplied records,' not as "
            "'not performed.'"
        ),
    ]

    return "\n".join(sections)


def generate_encounter_documents(
    case_dir: Path,
    output_root: Path,
) -> DocumentGenerationResult:
    """Generate all documents for one encounter case."""

    package = load_encounter_case(case_dir)

    case_id = str(package["case"].get("case_id") or case_dir.name)

    output_dir = output_root / case_id
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    renderers = {
        "admission_note": (
            "Admission Note",
            "admission_note.md",
            render_admission_note,
            [
                "case.json",
                "patient_context.json",
                "encounter.json",
                "active_conditions.json",
                "medications.json",
            ],
        ),
        "progress_note": (
            "Progress Note",
            "progress_note.md",
            render_progress_note,
            [
                "encounter.json",
                "observations.json",
                "procedures.json",
                "medications.json",
            ],
        ),
        "lab_report": (
            "Laboratory and Observation Report",
            "lab_report.md",
            render_lab_report,
            [
                "observations.json",
            ],
        ),
        "medication_reconciliation": (
            "Medication Reconciliation",
            "medication_reconciliation.md",
            render_medication_reconciliation,
            [
                "encounter.json",
                "medications.json",
            ],
        ),
        "discharge_summary": (
            "Discharge Summary",
            "discharge_summary.md",
            render_discharge_summary,
            [
                "encounter.json",
                "active_conditions.json",
                "medications.json",
                "observations.json",
                "procedures.json",
                "discharge_candidates.json",
            ],
        ),
        "follow_up_note": (
            "Follow-Up Review Note",
            "follow_up_note.md",
            render_follow_up_note,
            [
                "encounter.json",
                "discharge_candidates.json",
            ],
        ),
    }

    documents: list[GeneratedDocument] = []

    for document_type, (
        title,
        filename,
        renderer,
        source_files,
    ) in renderers.items():
        text = renderer(package)

        write_text(
            output_dir / filename,
            text,
        )

        evidence_count = text.count("[Source:")

        documents.append(
            GeneratedDocument(
                document_type=document_type,
                filename=filename,
                title=title,
                source_files=source_files,
                evidence_count=evidence_count,
            )
        )

    document_index = {
        "case_id": case_id,
        "documents": [
            {
                "document_type": item.document_type,
                "filename": item.filename,
                "title": item.title,
                "source_files": item.source_files,
                "evidence_count": item.evidence_count,
            }
            for item in documents
        ],
    }

    write_json(
        output_dir / "document_index.json",
        document_index,
    )

    manifest = {
        "schema_version": "1.0",
        "case_id": case_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "generation_method": "deterministic_template",
        "document_count": len(documents),
        "files": [item.filename for item in documents]
        + [
            "document_index.json",
        ],
    }

    write_json(
        output_dir / "manifest.json",
        manifest,
    )

    return DocumentGenerationResult(
        case_id=case_id,
        output_dir=output_dir,
        documents=documents,
    )

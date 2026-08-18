from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from clinical_investigation.evaluation.models import (
    EvidenceSupportLabel,
    GoldCaseLabel,
    GoldFindingDisposition,
    GoldFindingLabel,
    GoldMedicationItem,
    GoldTimelineEvent,
    MedicationAccuracyLabel,
    TimelineAccuracyLabel,
)

FINAL_REPORT_FILENAME = "final_investigation_report.json"
TIMELINE_FILENAME = "canonical_timeline.json"
MEDICATION_PROFILES_FILENAME = "medication_profiles.json"


def load_json(
    path: Path,
) -> Any:
    """Load JSON from disk."""

    return json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )


def get_report_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    """Return all machine-generated findings."""

    return list(
        report.get(
            "high_priority_findings",
            [],
        )
    ) + list(
        report.get(
            "other_findings",
            [],
        )
    )


def build_gold_label_template(
    case_dir: Path,
) -> GoldCaseLabel:
    """Build an unevaluated gold-label template for one case."""

    report_path = case_dir / FINAL_REPORT_FILENAME

    if not report_path.exists():
        raise FileNotFoundError(f"Final report not found: {report_path}")

    report = load_json(report_path)

    finding_labels = [
        GoldFindingLabel(
            finding_id=str(finding["finding_id"]),
            disposition=(GoldFindingDisposition.NOT_EVALUATED),
            expected_finding_type=str(
                finding.get(
                    "finding_type",
                    "",
                )
            )
            or None,
            expected_subtype=str(
                finding.get(
                    "subtype",
                    "",
                )
            )
            or None,
            evidence_support=(EvidenceSupportLabel.NOT_EVALUATED),
            gold_evidence_ids=[],
        )
        for finding in get_report_findings(report)
    ]

    timeline_labels: list[GoldTimelineEvent] = []

    timeline_path = case_dir / TIMELINE_FILENAME

    if timeline_path.exists():
        timeline_payload = load_json(timeline_path)

        if isinstance(
            timeline_payload,
            list,
        ):
            timeline_events = timeline_payload
        elif isinstance(
            timeline_payload,
            dict,
        ):
            timeline_events = list(
                timeline_payload.get(
                    "events",
                    [],
                )
            )
        else:
            timeline_events = []

        for event in timeline_events:
            event_id = event.get("event_id")

            if event_id is None:
                continue

            timeline_labels.append(
                GoldTimelineEvent(
                    event_id=str(event_id),
                    label=(TimelineAccuracyLabel.NOT_EVALUATED),
                )
            )

    medication_labels: list[GoldMedicationItem] = []

    medication_path = case_dir / MEDICATION_PROFILES_FILENAME

    if medication_path.exists():
        medication_payload = load_json(medication_path)

        if isinstance(
            medication_payload,
            list,
        ):
            medication_profiles = medication_payload
        elif isinstance(
            medication_payload,
            dict,
        ):
            medication_profiles = list(
                medication_payload.get(
                    "profiles",
                    [],
                )
            )
        else:
            medication_profiles = []

        for profile in medication_profiles:
            medication_key = profile.get("normalized_key")

            if medication_key is None:
                continue

            medication_labels.append(
                GoldMedicationItem(
                    medication_key=str(medication_key),
                    expected_status=None,
                    expected_dose=None,
                    expected_frequency=None,
                    label=(MedicationAccuracyLabel.NOT_EVALUATED),
                )
            )

    return GoldCaseLabel(
        case_id=str(report["case_id"]),
        finding_labels=finding_labels,
        timeline_labels=timeline_labels,
        medication_labels=medication_labels,
    )

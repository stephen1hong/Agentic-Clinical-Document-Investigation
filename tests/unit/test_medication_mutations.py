"""Tests for medication document mutations."""

from pathlib import Path

from clinical_investigation.evaluation.medication_mutations import (
    mutate_dose_change,
    mutate_remove_from_discharge,
    mutate_status_flip,
)


def write_document(
    path: Path,
    text: str,
) -> None:
    """Write a Markdown fixture."""

    path.write_text(
        text,
        encoding="utf-8",
    )


def test_status_flip(
    tmp_path: Path,
) -> None:
    """Status mutation should flip active to stopped."""

    path = tmp_path / "medication.md"

    write_document(
        path,
        "- Lisinopril 10 mg active\n",
    )

    (
        line_number,
        original,
        mutated,
    ) = mutate_status_flip(
        document_path=path,
        medication_name="Lisinopril",
    )

    assert line_number == 1
    assert "active" in original
    assert "stopped" in mutated
    assert "stopped" in path.read_text(encoding="utf-8")


def test_remove_from_discharge(
    tmp_path: Path,
) -> None:
    """Discharge mutation should remove the selected line."""

    path = tmp_path / "discharge.md"

    write_document(
        path,
        ("# Discharge\n- Lisinopril 10 mg active\n- Metformin 500 mg active\n"),
    )

    (
        line_number,
        removed,
        mutated,
    ) = mutate_remove_from_discharge(
        document_path=path,
        medication_name="Lisinopril",
    )

    assert line_number == 2
    assert "Lisinopril" in removed
    assert mutated is None
    assert "Lisinopril" not in path.read_text(encoding="utf-8")


def test_dose_change(
    tmp_path: Path,
) -> None:
    """Dose mutation should change an explicit dose."""

    path = tmp_path / "medication.md"

    write_document(
        path,
        "- Lisinopril 10 mg oral daily active\n",
    )

    (
        _,
        original,
        mutated,
    ) = mutate_dose_change(
        document_path=path,
        medication_name="Lisinopril",
    )

    assert "10 mg" in original
    assert "20 mg" in mutated

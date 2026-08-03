# from pathlib import Path
# import json
# import sys
# import pandas as pd
# from rich.console import Console

import json

import pandas as pd
from rich.console import Console

from clinical_investigation.config import settings
from clinical_investigation.ingestion.synthea_csv import load_synthea_csv

# PROJECT_ROOT = Path(__file__).resolve().parents[1]
# SRC_DIR = PROJECT_ROOT / "src"

# if str(SRC_DIR) not in sys.path:
#    sys.path.insert(0, str(SRC_DIR))


console = Console()

TARGET_PATIENTS = 30
MINIMUM_MEDICATIONS = 3
MINIMUM_ENCOUNTERS = 2


def get_patient_id_column(patients: pd.DataFrame) -> str:
    for column in ("Id", "ID"):
        if column in patients.columns:
            return column

    raise ValueError("patients.csv must contain an Id or ID column")


def detect_abnormal_observations(
    observations: pd.DataFrame,
) -> pd.Series:
    """Return a Boolean mask for likely abnormal observations.

    Synthea CSV versions differ in whether an explicit abnormal flag
    is present. This function uses available status/description fields
    conservatively and can be expanded later with reference ranges.
    """

    mask = pd.Series(False, index=observations.index)

    flag_columns = [
        column
        for column in (
            "ABNORMAL",
            "FLAG",
            "INTERPRETATION",
            "STATUS",
        )
        if column in observations.columns
    ]

    abnormal_pattern = r"\b(abnormal|high|low|critical|positive)\b"

    for column in flag_columns:
        mask = mask | observations[column].astype(str).str.contains(
            abnormal_pattern,
            case=False,
            regex=True,
            na=False,
        )

    return mask


def count_by_patient(
    frame: pd.DataFrame,
    patient_column: str = "PATIENT",
) -> pd.Series:
    if patient_column not in frame.columns:
        return pd.Series(dtype="int64")

    return frame.groupby(patient_column).size()


def select_cohort(
    tables: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    patients = tables["patients"].copy()
    encounters = tables["encounters"].copy()
    medications = tables["medications"].copy()
    observations = tables["observations"].copy()

    patient_id_column = get_patient_id_column(patients)

    encounter_counts = count_by_patient(encounters)
    medication_counts = count_by_patient(medications)

    abnormal_mask = detect_abnormal_observations(observations)
    abnormal_counts = count_by_patient(observations.loc[abnormal_mask])

    cohort = patients[[patient_id_column]].copy()
    cohort = cohort.rename(columns={patient_id_column: "patient_id"})

    cohort["encounter_count"] = cohort["patient_id"].map(encounter_counts).fillna(0).astype(int)
    cohort["medication_count"] = cohort["patient_id"].map(medication_counts).fillna(0).astype(int)
    cohort["abnormal_observation_count"] = (
        cohort["patient_id"].map(abnormal_counts).fillna(0).astype(int)
    )

    cohort["has_multiple_medications"] = cohort["medication_count"] >= MINIMUM_MEDICATIONS
    cohort["has_abnormal_observations"] = cohort["abnormal_observation_count"] > 0
    cohort["has_meaningful_encounters"] = cohort["encounter_count"] >= MINIMUM_ENCOUNTERS

    cohort["selection_score"] = (
        cohort["encounter_count"].clip(upper=10)
        + 2 * cohort["medication_count"].clip(upper=10)
        + 3 * cohort["abnormal_observation_count"].clip(upper=10)
        + 5 * cohort["has_multiple_medications"].astype(int)
        + 5 * cohort["has_abnormal_observations"].astype(int)
    )

    selected = (
        cohort.sort_values(
            by=[
                "selection_score",
                "abnormal_observation_count",
                "medication_count",
                "encounter_count",
            ],
            ascending=False,
        )
        .head(TARGET_PATIENTS)
        .reset_index(drop=True)
    )

    return selected


def save_selection(selected: pd.DataFrame) -> None:
    output_dir = settings.selected_patients_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir / "selected_patient_cohort.csv"
    json_path = output_dir / "selected_patient_ids.json"

    selected.to_csv(csv_path, index=False)

    payload = {
        "patient_count": len(selected),
        "patient_ids": selected["patient_id"].tolist(),
    }

    json_path.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    console.print(f"[green]Saved cohort:[/green] {csv_path}")
    console.print(f"[green]Saved IDs:[/green] {json_path}")


def main() -> None:
    tables = load_synthea_csv(settings.synthea_csv_dir)
    selected = select_cohort(tables)

    console.print(selected.to_string(index=False))
    save_selection(selected)

    console.print()
    console.print(f"Selected patients: {len(selected)}")
    console.print(f"Multiple-medication patients: {selected['has_multiple_medications'].sum()}")
    console.print(
        "Patients with detected abnormal observations: "
        f"{selected['has_abnormal_observations'].sum()}"
    )
    console.print(
        f"Patients with meaningful encounters: {selected['has_meaningful_encounters'].sum()}"
    )


if __name__ == "__main__":
    main()

"""Configuration management for the clinical investigation platform."""

from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class DataPaths(BaseModel):
    synthea_csv: Path
    synthea_fhir: Path
    processed: Path
    selected_patients: Path
    generated_documents: Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"

    synthea_csv_dir: Path = PROJECT_ROOT / "data/raw/synthea_csv"
    synthea_fhir_dir: Path = PROJECT_ROOT / "data/raw/synthea_fhir"
    processed_data_dir: Path = PROJECT_ROOT / "data/processed"
    selected_patients_dir: Path = PROJECT_ROOT / "data/selected_patients"
    generated_documents_dir: Path = PROJECT_ROOT / "data/generated_documents"

    @property
    def patient_packages_dir(self) -> Path:
        return self.processed_data_dir / "patients"

    @property
    def encounter_cases_dir(self) -> Path:
        return self.processed_data_dir / "encounter_cases"

    @property
    def selected_encounters_dir(self) -> Path:
        return PROJECT_ROOT / "data/selected_encounters"

    @property
    def encounter_documents_dir(self) -> Path:
        return self.generated_documents_dir / "encounter_cases"

    @property
    def investigation_cases_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "investigation_cases"

    @property
    def medication_mutation_evaluation_dir(
        self,
    ) -> Path:
        """Root directory for mutation-based medication evaluation."""

        return PROJECT_ROOT / "data" / "evaluation" / "medication_mutations"

    @property
    def medication_mutation_cases_dir(
        self,
    ) -> Path:
        """Mutated investigation cases."""

        return self.medication_mutation_evaluation_dir / "cases"

    @property
    def medication_mutation_gold_dir(
        self,
    ) -> Path:
        """Gold mutation labels."""

        return self.medication_mutation_evaluation_dir / "gold"

    @property
    def medication_mutation_predictions_dir(
        self,
    ) -> Path:
        """Medication discrepancy predictions."""

        return self.medication_mutation_evaluation_dir / "predictions"

    @property
    def medication_mutation_reports_dir(
        self,
    ) -> Path:
        """Evaluation reports."""

        return self.medication_mutation_evaluation_dir / "reports"


settings = Settings()

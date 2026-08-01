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

    def data_paths(self) -> DataPaths:
        return DataPaths(
            synthea_csv=self.synthea_csv_dir,
            synthea_fhir=self.synthea_fhir_dir,
            processed=self.processed_data_dir,
            selected_patients=self.selected_patients_dir,
            generated_documents=self.generated_documents_dir,
        )


settings = Settings()

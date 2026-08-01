# Agentic Clinical Document Investigation

An agentic pipeline for investigating clinical documents — extracting structured evidence, reconciling conflicts across sources, and generating investigation reports.

## Project Structure

```
src/clinical_investigation/
├── agents/          # Agent definitions and orchestration logic
├── ingestion/       # Data ingestion from Synthea CSV/FHIR sources
├── extraction/      # Clinical entity and fact extraction
├── evidence/        # Evidence collection and scoring
├── reconciliation/  # Conflict detection and resolution across documents
├── retrieval/       # Vector/semantic retrieval over document stores
├── schemas/         # Pydantic data models
├── tools/           # Agent tools (search, lookup, compute)
├── workflows/       # End-to-end workflow orchestration
├── reporting/       # Report generation
├── evaluation/      # Metrics and evaluation harness
└── ui/              # Optional UI layer
```

## Setup

```bash
cp .env.example .env
# Fill in API keys in .env

pip install -e ".[dev]"
```

## Running

```bash
# Run a full investigation workflow (example)
python scripts/run_investigation.py --case-id <case_id>
```

## Data

Place Synthea outputs in:
- `data/raw/synthea_csv/` — CSV export
- `data/raw/synthea_fhir/` — FHIR JSON export

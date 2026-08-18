# Quick Start

This guide takes you from an installed project to the first successful clinical investigation.

## 1. Activate the Virtual Environment

From the project root:

```powershell
.\.venv\Scripts\Activate.ps1
```

Verify Python:

```powershell
python --version
```

The current validated release environment uses Python 3.12.10.

## 2. Install the Project

If the project is not already installed:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## 3. Configure Environment Variables

If required:

```powershell
Copy-Item .env.example .env
```

Add any required configuration values or API credentials to `.env`.

## 4. Verify the Release Environment

Run:

```powershell
python .\scripts\check_release_environment.py
```

Expected result:

```text
Overall status:                   PASS
Reproducible execution ready:    True
```

The current frozen release contains 20 investigation cases.

## 5. List Available Cases

```powershell
python -m clinical_investigation.cli list-cases --limit 5
```

Copy one of the returned case IDs.

## 6. Run an Investigation

```powershell
python -m clinical_investigation.cli investigate --case-id <CASE_ID>
```

Example successful output:

```text
Clinical Investigation
========================================
Case: <CASE_ID>
Findings: <N>
Validation errors: 0
Requires human review: False
Review status: not_required
Final report: ...\final_investigation_report.json
```

A case requiring human review uses:

```text
Requires human review: True
Review status: pending
```

## 7. JSON Output

Use:

```powershell
python -m clinical_investigation.cli investigate --case-id <CASE_ID> --json
```

On PowerShell, keeping the command on one line avoids line-continuation errors.

## 8. Inspect the Final Report

The final machine-generated report is persisted at:

```text
data\investigation_cases\<CASE_ID>\final_investigation_report.json
```

Inspect it with:

```powershell
Get-Content ".\data\investigation_cases\<CASE_ID>\final_investigation_report.json"
```

## 9. Optional Application Smoke Test

Run the application interface against the real production workflow:

```powershell
python .\scripts\smoke_test_application_runner.py
```

A successful run ends with:

```text
Application runner smoke test: PASS
```

## 10. Optional Application Unit Tests

```powershell
python -m pytest .\tests\unit\test_application_runner.py -v `
    --basetemp=.\tmp\pytest-10a `
    -p no:cacheprovider
```

Current baseline:

```text
4 passed
```

## Known LangGraph Warning

Some environments display:

```text
LangChainPendingDeprecationWarning
```

This is currently a non-blocking dependency warning and does not by itself indicate workflow failure.

## Next Documentation

For more detail:

```text
README.md          Project overview
OPERATOR_GUIDE.md  Operational procedures and troubleshooting
RELEASE.md         Frozen release definition
EVALUATION.md      Evaluation methodology and results
```
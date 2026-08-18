# Operator Guide

## Agentic Clinical Document Investigation Platform

This guide describes how to operate the current release of the Agentic Clinical Document Investigation Platform.

It covers:

- release-environment verification;
- listing available investigation cases;
- running investigations;
- interpreting workflow status;
- locating persisted outputs;
- understanding human-review routing;
- validating the application interface;
- troubleshooting common failures;
- protecting the frozen release baseline.

This guide assumes the project has already been installed according to `QUICKSTART.md`.

---

# 1. Operating Model

The production execution path is:

```text
CLI
 |
 v
Application Runner
 |
 v
Compiled LangGraph Workflow
 |
 v
Investigation Nodes
 |
 v
Validation
 |
 +---------------------+
 |                     |
 v                     v
Validation Passed   Human Review
 |                     |
 +----------+----------+
            |
            v
     Final Report
            |
            v
         Persist
```

The CLI and application runner are adapters over the production workflow.

They must not contain independent clinical investigation logic.

---

# 2. Activate the Project Environment

From the project root:

```powershell
.\.venv\Scripts\Activate.ps1
```

The PowerShell prompt should show:

```text
(.venv)
```

Verify Python:

```powershell
python --version
```

The current validated release environment uses:

```text
Python 3.12.10
```

The package itself declares:

```text
Python >=3.10,<3.13
```

---

# 3. Verify Release Readiness

Before operating the release, run:

```powershell
python .\scripts\check_release_environment.py
```

A healthy release environment should report:

```text
Overall status:                   PASS
Reproducible execution ready:    True
```

The checker validates:

- Python runtime compatibility;
- `pyproject.toml`;
- the `clinical_investigation` package;
- required Python dependencies;
- the investigation-case directory;
- availability of investigation cases;
- the frozen Step 9 release artifact;
- Step 9 PASS status;
- Step 9 completion;
- release readiness;
- zero release-validation issues.

If this check returns `FAIL`, do not treat the environment as release-ready until the reported failure has been investigated.

---

# 4. List Available Investigation Cases

Use:

```powershell
python -m clinical_investigation.cli list-cases
```

To show only a few cases:

```powershell
python -m clinical_investigation.cli list-cases --limit 5
```

Example:

```text
2b36a3c6-e9d6-554e-28c3-a8244a67a553__2b36a3c6-e9d6-554e-cc63-a167ac5cab80
307ab11f-ff8e-63d6-fb00-b97e91b2234e__307ab11f-ff8e-63d6-2f59-5f0578497b62
307ab11f-ff8e-63d6-fb00-b97e91b2234e__307ab11f-ff8e-63d6-6913-5d398d138394
```

The current frozen release population contains:

```text
20 investigation cases
```

---

# 5. Run One Investigation

Use:

```powershell
python -m clinical_investigation.cli investigate --case-id <CASE_ID>
```

Example:

```powershell
python -m clinical_investigation.cli investigate --case-id 2b36a3c6-e9d6-554e-28c3-a8244a67a553__2b36a3c6-e9d6-554e-cc63-a167ac5cab80
```

A successful execution produces output similar to:

```text
Clinical Investigation
========================================
Case: 2b36a3c6-e9d6-554e-28c3-a8244a67a553__2b36a3c6-e9d6-554e-cc63-a167ac5cab80
Findings: 13
Validation errors: 0
Requires human review: False
Review status: not_required
Final report: ...\final_investigation_report.json
```

---

# 6. JSON Output

For machine-readable output:

```powershell
python -m clinical_investigation.cli investigate --case-id <CASE_ID> --json
```

On PowerShell, the safest approach is to keep the command on one line.

If using multiple lines, every continued line except the last must end with a backtick:

```powershell
python -m clinical_investigation.cli investigate `
    --case-id <CASE_ID> `
    --json
```

Incorrect:

```powershell
python -m clinical_investigation.cli investigate `
    --case-id <CASE_ID>
    --json
```

In the incorrect form, PowerShell treats `--json` as a separate expression.

---

# 7. Interpreting Investigation Results

The CLI reports several important fields.

## `Findings`

Example:

```text
Findings: 13
```

A finding is a structured investigation conclusion generated after analyzing evidence, claims, timeline information, medication information, and cross-document relationships.

A finding is not simply an extracted clinical fact.

Supported finding types include:

```text
timeline_conflict
temporal_uncertainty
medication_discrepancy
contradiction
missing_follow_up
unsupported_claim
other
```

---

## `Validation errors`

Healthy execution normally reports:

```text
Validation errors: 0
```

A nonzero count means the workflow detected validation problems in the investigation state or output.

Do not interpret a case with unresolved validation errors as a clean production result.

---

## `Requires human review`

Possible values:

```text
True
False
```

This indicates whether one or more findings require human review.

---

## `Review status`

The current production contract uses:

```text
not_required
```

when no human review is necessary.

For a review-required case, the workflow uses:

```text
pending
```

Do not expect the machine workflow to use:

```text
review_required
```

as the persisted review status.

The release contract is:

```text
requires_human_review = False
review_status = not_required
```

or:

```text
requires_human_review = True
review_status = pending
```

---

# 8. Human Review Routing

After investigation synthesis, the workflow performs validation.

The routing logic is:

```text
Validation
   |
   +---- pass ----> validation_passed
   |
   +---- review --> human_review
```

Both branches eventually proceed to:

```text
final_report
    |
    v
persist_report
```

Human review routing therefore does not bypass machine report generation.

The machine-generated final report remains a distinct artifact.

Reviewer output should remain separate rather than silently replacing the original machine report.

---

# 9. Locate Investigation Outputs

Investigation cases are stored under:

```text
data\investigation_cases\<CASE_ID>\
```

For example:

```powershell
Get-ChildItem .\data\investigation_cases\<CASE_ID>
```

To recursively inspect all files for one case:

```powershell
Get-ChildItem .\data\investigation_cases\<CASE_ID> -Recurse |
    Select-Object FullName
```

The final investigation report is persisted as:

```text
data\investigation_cases\<CASE_ID>\final_investigation_report.json
```

Inspect it with:

```powershell
Get-Content .\data\investigation_cases\<CASE_ID>\final_investigation_report.json
```

For formatted JSON:

```powershell
Get-Content .\data\investigation_cases\<CASE_ID>\final_investigation_report.json |
    ConvertFrom-Json |
    ConvertTo-Json -Depth 20
```

---

# 10. Inspect an Investigation Case

To inspect the files belonging to a particular case:

```powershell
$caseId = "<CASE_ID>"

Get-ChildItem ".\data\investigation_cases\$caseId" |
    Select-Object Name, Length, LastWriteTime
```

To inspect JSON files:

```powershell
Get-ChildItem ".\data\investigation_cases\$caseId" -Filter *.json |
    Select-Object Name
```

This is preferable to assuming that every case contains exactly the same optional artifacts.

---

# 11. Application-Level Smoke Test

The application runner can be validated against the real production workflow using:

```powershell
python .\scripts\smoke_test_application_runner.py
```

This test is different from a unit test.

The smoke test executes:

```text
Application Runner
       |
       v
Actual Production LangGraph
```

A successful result ends with:

```text
Application runner smoke test: PASS
```

Use this when validating the release execution boundary.

Do not routinely run it across all cases unless a broader regression run is specifically required.

---

# 12. Application Runner Unit Tests

The application-level wrapper has dedicated unit tests:

```powershell
python -m pytest .\tests\unit\test_application_runner.py -v `
    --basetemp=.\tmp\pytest-10a `
    -p no:cacheprovider
```

The current baseline is:

```text
4 passed
```

These tests validate the application interface without executing the entire production graph.

---

# 13. Windows Pytest Temporary Directory Issue

On some Windows installations, pytest may fail with:

```text
PermissionError: [WinError 5] Access is denied
```

for a path similar to:

```text
C:\Users\<USER>\AppData\Local\Temp\pytest-of-<USER>
```

Use a local pytest temporary directory instead:

```powershell
New-Item -ItemType Directory -Force .\tmp\pytest
```

Then:

```powershell
python -m pytest `
    --basetemp=.\tmp\pytest `
    -p no:cacheprovider
```

`-p no:cacheprovider` also avoids failures caused by inability to write `.pytest_cache`.

This is an environment-level pytest issue, not necessarily an application failure.

---

# 14. Known LangGraph Warning

Execution currently may display:

```text
LangChainPendingDeprecationWarning:
The default value of `allowed_objects` will change in a future version.
```

This warning originates from the installed LangGraph package.

It is currently considered non-blocking.

If an investigation otherwise completes normally with:

```text
Validation errors: 0
```

and a valid final report is produced, this warning alone does not indicate workflow failure.

Do not suppress or modify production behavior solely to remove this warning during the frozen release.

---

# 15. Missing Case

If an invalid case ID is supplied:

```powershell
python -m clinical_investigation.cli investigate --case-id missing-case
```

the application runner should reject the request rather than create a new case implicitly.

A missing investigation case is an operational input error.

First confirm the available case IDs:

```powershell
python -m clinical_investigation.cli list-cases --limit 20
```

---

# 16. Verify the Final Report

After a successful run, confirm that the report exists:

```powershell
Test-Path ".\data\investigation_cases\<CASE_ID>\final_investigation_report.json"
```

Expected:

```text
True
```

Then inspect the report:

```powershell
Get-Content ".\data\investigation_cases\<CASE_ID>\final_investigation_report.json"
```

Operationally important consistency checks include:

```text
report case_id == requested case_id

report finding_count == workflow finding count

report review_status == workflow review_status
```

The stable application runner performs these basic checks during execution.

---

# 17. Release Acceptance Baseline

The frozen Step 9 release is the authoritative acceptance baseline.

Current release status:

```text
Step 9 status:          PASS
Step 9 complete:        True
Release ready:          True
Validation issues:      0
```

Release population:

```text
Cases:                  20
Findings:               317
Review-required:        1
Contextual:             316
Cases requiring review: 1
```

Robustness baseline:

```text
Mutation tests:         49 / 49
Failure runs:           10 / 10
Successful recoveries:  10 / 10
```

The authoritative artifact is:

```text
data\evaluation\step_9_final\step_9_release_readiness_summary.json
```

---

# 18. Protecting the Frozen Release

Step 8 and Step 9 are frozen.

Step 10 packaging work should consume the frozen release rather than modify accepted clinical logic.

During documentation, CLI, API, or demonstration work:

```text
DO:
CLI -> Application Runner -> Existing Production Workflow
```

Do not create:

```text
CLI -> separate investigation implementation
```

or:

```text
Demo -> separate clinical reasoning path
```

unless intentionally beginning a new post-release development cycle.

---

# 19. Do Not Re-run Release Evaluation Casually

The frozen Step 9 artifacts represent the accepted release baseline.

Normal operation does not require rerunning:

```text
Step 8 final evaluation
Step 9A regression
Step 9B robustness suite
Step 9C final-report acceptance
Step 9D freeze
```

Run those only when intentionally performing release regression or creating a new release candidate.

---

# 20. Common Troubleshooting

## CLI command not found

If:

```text
No module named clinical_investigation
```

verify that the virtual environment is active:

```powershell
.\.venv\Scripts\Activate.ps1
```

Then install the package:

```powershell
python -m pip install -e ".[dev]"
```

---

## Case not found

Run:

```powershell
python -m clinical_investigation.cli list-cases --limit 20
```

Copy the case ID exactly.

---

## `--json` PowerShell parser error

Use one line:

```powershell
python -m clinical_investigation.cli investigate --case-id <CASE_ID> --json
```

or include a backtick after every continued line except the final line.

---

## Pytest permission error

Use:

```powershell
python -m pytest `
    --basetemp=.\tmp\pytest `
    -p no:cacheprovider
```

---

## LangGraph pending-deprecation warning

This is currently non-blocking.

Continue investigating only if execution also produces an actual application exception, validation failure, or missing report.

---

## Release checker fails

Run:

```powershell
python .\scripts\check_release_environment.py
```

Read the `Failures` section.

Do not assume a release is reproducible if:

```text
Overall status: FAIL
```

---

# 21. Operational Health Checklist

Before a demonstration or release run:

```text
[ ] Virtual environment activated

[ ] Correct Python interpreter selected

[ ] Release environment checker returns PASS

[ ] Investigation cases are available

[ ] CLI can list cases

[ ] Selected case ID exists

[ ] Investigation executes successfully

[ ] Validation errors = 0

[ ] Review status is understood

[ ] Final report is persisted

[ ] No frozen Step 8/9 clinical logic was modified
```

---

# 22. Recommended Demo Operating Sequence

For a controlled demonstration:

### Step 1

Verify environment:

```powershell
python .\scripts\check_release_environment.py
```

### Step 2

List cases:

```powershell
python -m clinical_investigation.cli list-cases --limit 5
```

### Step 3

Choose a curated demo case.

### Step 4

Run:

```powershell
python -m clinical_investigation.cli investigate --case-id <CASE_ID>
```

### Step 5

Inspect:

```text
finding count
validation errors
human-review requirement
review status
final-report path
```

### Step 6

Open the persisted final report.

### Step 7

If the case requires human review, show the review path and reviewer artifacts separately from the machine-generated report.

---

# 23. Current Release Boundary

The current operational boundary is:

```text
Step 8
Evaluation & Refinement
        |
        v
      FROZEN

Step 9
End-to-End Acceptance
        |
        v
      FROZEN
        |
        v
Step 10A
Release Entrypoint
        |
        v
     COMPLETE
        |
        v
Step 10B
Documentation
```

Operational changes made during Step 10 should not silently invalidate the frozen Step 9 acceptance baseline.

---

# 24. Intended Operational Use

The platform is intended for research, engineering, evaluation, demonstration, and development of evidence-grounded clinical document investigation systems.

It is not intended to operate as an autonomous clinical decision-maker.

Human review remains appropriate where findings are uncertain, clinically consequential, conflicting, or explicitly routed for review.

---

# 25. Related Documentation

Start here:

```text
README.md
```

Installation and first execution:

```text
QUICKSTART.md
```

Operational procedures:

```text
OPERATOR_GUIDE.md
```

Additional release and architecture documentation will be added during the remaining Step 10 packaging work.
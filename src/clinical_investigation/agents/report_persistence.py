from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FINAL_REPORT_FILENAME = "final_investigation_report.json"


def write_json(
    path: Path,
    payload: Any,
) -> None:
    """Write deterministic formatted JSON."""

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


def persist_final_report(
    *,
    case_dir: Path,
    report: dict[str, Any],
) -> Path:
    """Persist a final investigation report for one case."""

    output_path = case_dir / FINAL_REPORT_FILENAME

    write_json(
        output_path,
        report,
    )

    return output_path

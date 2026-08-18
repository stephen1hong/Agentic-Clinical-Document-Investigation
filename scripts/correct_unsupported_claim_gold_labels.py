from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CORRECTIONS = {
    "b422562c-9370-5c7c-b3bd-837a6f238819": (
        "The lab report directly states “No observations available,” "
        "matching the extracted claim. The insufficient-evidence "
        "finding is therefore a false positive."
    ),
    "8282e36c-cb6d-52eb-83bf-5344c185bff0": (
        "The admission note directly documents 2 ML Ondansetron "
        "2 MG/ML Injection, matching the claim. The "
        "insufficient-evidence finding is therefore a false positive."
    ),
    "e114c042-635f-5a40-ad40-de36cc554937": (
        "The admission note directly documents remifentanil 2 MG "
        "Injection, matching the claim. The insufficient-evidence "
        "finding is therefore a false positive."
    ),
    "fa95ebf2-0d00-5fad-b81b-82d3daf7d841": (
        "The admission note directly documents cefazolin 2000 MG "
        "Injection, matching the claim. The insufficient-evidence "
        "finding is therefore a false positive."
    ),
    "e74fc893-848f-5702-ab50-ce2a73e1096c": (
        "The admission note directly documents lisinopril 5 MG Oral "
        "Tablet, matching the claim. The insufficient-evidence "
        "finding is therefore a false positive."
    ),
}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(
            encoding="utf-8",
        )
    )

    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")

    return payload


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]

    gold_root = project_root / "data" / "evaluation" / "gold_labels"

    corrected_ids: set[str] = set()

    for gold_path in sorted(gold_root.glob("*/gold_labels.json")):
        payload = load_json(gold_path)

        changed = False

        for label in payload.get(
            "finding_labels",
            [],
        ):
            finding_id = str(
                label.get(
                    "finding_id",
                    "",
                )
            )

            rationale = CORRECTIONS.get(finding_id)

            if rationale is None:
                continue

            label["disposition"] = "false_positive"

            label["evidence_support"] = "supported"

            label["rationale"] = rationale

            corrected_ids.add(finding_id)

            changed = True

        if changed:
            gold_path.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            print(f"Updated: {gold_path}")

    missing = set(CORRECTIONS) - corrected_ids

    print()
    print(f"Corrected labels: {len(corrected_ids)}")

    if missing:
        print("Missing finding IDs:")

        for finding_id in sorted(missing):
            print(f"  {finding_id}")

        return 1

    print("All requested corrections applied.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

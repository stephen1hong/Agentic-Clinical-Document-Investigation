from __future__ import annotations

from clinical_investigation.config import settings
from clinical_investigation.review.generation import (
    generate_reviewer_artifacts,
)


def main() -> int:
    case_dirs = sorted(path for path in settings.investigation_cases_dir.iterdir() if path.is_dir())

    if not case_dirs:
        print("No investigation cases found.")
        return 1

    total = len(case_dirs)
    completed = 0
    failed = 0

    print("=== Reviewer Artifact Generation ===")
    print(f"Cases: {total}")
    print()

    for case_dir in case_dirs:
        print(f"Generating: {case_dir.name}")

        try:
            bundle_path, report_path = generate_reviewer_artifacts(case_dir)
        except Exception as exc:
            failed += 1
            print(f"  ERROR: {type(exc).__name__}: {exc}")
            continue

        completed += 1

        print(f"  Bundle: {bundle_path.name}")
        print(f"  Report: {report_path.name}")

    print()
    print("=== Summary ===")
    print(f"Cases total: {total}")
    print(f"Cases completed: {completed}")
    print(f"Cases failed: {failed}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

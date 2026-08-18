from clinical_investigation.config import settings
from clinical_investigation.evaluation.medication_evaluation import (
    write_clean_baseline_comparison,
)


def main() -> int:
    mutation_cases_root = settings.medication_mutation_cases_dir

    clean_cases_root = settings.investigation_cases_dir

    case_dirs = sorted(
        path
        for path in mutation_cases_root.iterdir()
        if (path.is_dir() and path.name.startswith("mut-"))
    )

    if not case_dirs:
        print("No mutation cases found.")
        return 1

    passed = 0
    failed = 0

    for case_dir in case_dirs:
        try:
            output_path = write_clean_baseline_comparison(
                mutation_case_dir=(case_dir),
                clean_cases_root=(clean_cases_root),
            )

            print(f"PASS {case_dir.name}: {output_path.name}")

            passed += 1

        except Exception as exc:
            print(f"FAIL {case_dir.name}: {exc}")

            failed += 1

    print()
    print(f"Baseline comparison complete: {passed} passed, {failed} failed.")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

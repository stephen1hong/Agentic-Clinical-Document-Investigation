from clinical_investigation.investigation.medication_reconciliation import (
    normalize_medication_name,
)


def test_normalize_started_near_discharge_wrapper() -> None:
    normalized_name, normalized_key = normalize_medication_name(
        "medicationstartedneardischarge: "
        "10 ML Furosemide 10 MG/ML Injection "
        "at December 19, 2014 at 15:07 UTC"
    )

    assert normalized_name == "Furosemide ML"
    assert normalized_key == "furosemideml"


def test_normalize_stopped_near_discharge_wrapper() -> None:
    normalized_name, normalized_key = normalize_medication_name(
        "medicationstoppedneardischarge: "
        "10 ML Furosemide 10 MG/ML Injection "
        "at December 20, 2014 at 03:07 UTC"
    )

    assert normalized_name == "Furosemide ML"
    assert normalized_key == "furosemideml"


def test_wrapped_and_unwrapped_medication_share_key() -> None:
    _, wrapped_key = normalize_medication_name(
        "medicationstartedneardischarge: "
        "10 ML Furosemide 10 MG/ML Injection "
        "at December 19, 2014 at 15:07 UTC"
    )

    _, ordinary_key = normalize_medication_name("10 ML Furosemide 10 MG/ML Injection")

    assert wrapped_key == ordinary_key


def test_normal_medication_name_behavior_is_preserved() -> None:
    normalized_name, normalized_key = normalize_medication_name("lisinopril 10 MG Oral Tablet")

    assert normalized_name == "lisinopril"
    assert normalized_key == "lisinopril"

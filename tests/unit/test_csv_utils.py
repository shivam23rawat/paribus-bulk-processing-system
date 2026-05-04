"""Unit tests for CSV parsing and validation helpers."""

from app.csv_utils import CsvValidationError, parse_hospital_csv


def test_parse_hospital_csv_parses_rows_with_case_insensitive_headers():
    """Parse mixed-case headers and preserve row-level field values."""

    csv_text = (
        "NAME,ADDRESS,PHONE\n"
        "General Hospital,123 Main St,555-1234\n"
        "City Clinic,45 Oak Ave,\n"
    )

    rows = parse_hospital_csv(csv_text, max_rows=20)

    assert len(rows) == 2
    assert rows[0].row_number == 2
    assert rows[0].name == "General Hospital"
    assert rows[0].address == "123 Main St"
    assert rows[0].phone == "555-1234"
    assert rows[1].row_number == 3
    assert rows[1].phone is None


def test_parse_hospital_csv_rejects_empty_input_rows():
    """Reject a CSV file that contains only a header row."""

    csv_text = "name,address,phone\n"

    try:
        parse_hospital_csv(csv_text, max_rows=20)
    except CsvValidationError as exc:
        assert "does not contain any hospital rows" in str(exc)
    else:
        raise AssertionError("Expected CsvValidationError to be raised")

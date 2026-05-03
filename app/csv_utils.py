"""CSV parsing utilities for hospital bulk uploads.

This module contains a lightweight CSV parser that validates the header
and rows for required fields and enforces a maximum number of rows.

Functions
---------
parse_hospital_csv
    Parse and validate CSV text into a list of `HospitalCsvRow` objects.
"""

import csv
from dataclasses import dataclass
from io import StringIO
from typing import List, Optional


@dataclass
class HospitalCsvRow:
    row_number: int
    name: str
    address: str
    phone: Optional[str]


class CsvValidationError(ValueError):
    """Raised when the provided CSV is invalid.

    Notes
    -----
    This is a thin wrapper over :class:`ValueError` used to indicate CSV
    validation failures so the HTTP layer can return a proper 400 error.
    """


def parse_hospital_csv(csv_text: str, max_rows: int) -> List[HospitalCsvRow]:
    """Parse hospital CSV text and validate required fields.

    Parameters
    ----------
    csv_text : str
        CSV content as a string. UTF-8 with optional BOM is expected.
    max_rows : int
        Maximum allowed non-header rows.

    Returns
    -------
    List[HospitalCsvRow]
        A list of parsed and validated rows.

    Raises
    ------
    CsvValidationError
        If the CSV is missing headers, required columns, has invalid rows,
        or exceeds the configured row limit.
    """
    reader = csv.DictReader(StringIO(csv_text))
    raw_fieldnames = reader.fieldnames or []
    fieldnames = [field.strip().lower() for field in raw_fieldnames]

    # Create a mapping from original case to lowercase for dict access
    field_mapping = {field.strip().lower(): field.strip() for field in raw_fieldnames}

    if not fieldnames:
        raise CsvValidationError("CSV file is missing a header row")

    required_fields = {"name", "address"}
    missing_required = required_fields.difference(fieldnames)
    if missing_required:
        raise CsvValidationError(
            f"CSV is missing required columns: {', '.join(sorted(missing_required))}"
        )

    rows: List[HospitalCsvRow] = []
    for index, raw_row in enumerate(reader, start=2):
        if not raw_row:
            continue

        # Access using original case from field_mapping
        name = (raw_row.get(field_mapping.get("name", "name")) or "").strip()
        address = (raw_row.get(field_mapping.get("address", "address")) or "").strip()
        phone_key = field_mapping.get("phone", "phone")
        phone = (
            (raw_row.get(phone_key) or "").strip() or None
            if phone_key in raw_row
            else None
        )

        if not name or not address:
            raise CsvValidationError(
                f"Row {index} is missing a required name or address value"
            )

        rows.append(
            HospitalCsvRow(row_number=index, name=name, address=address, phone=phone)
        )

    if not rows:
        raise CsvValidationError("CSV file does not contain any hospital rows")

    if len(rows) > max_rows:
        raise CsvValidationError(
            f"CSV file exceeds the maximum of {max_rows} hospitals"
        )

    return rows

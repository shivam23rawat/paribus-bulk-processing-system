"""Error-scenario tests for invalid inputs and missing resources."""

from tests.conftest import create_api, override_client


def test_bulk_upload_rejects_too_many_rows():
    """Reject CSV uploads that exceed the configured row limit."""

    override_client()
    api = create_api()

    csv_rows = ["name,address,phone"]
    for index in range(21):
        csv_rows.append(f"Hospital {index},Address {index},555-000{index}")

    response = api.post(
        "/hospitals/bulk",
        files={"file": ("hospitals.csv", "\n".join(csv_rows), "text/csv")},
    )

    assert response.status_code == 400
    assert "maximum of 20 hospitals" in response.json()["detail"]


def test_validation_rejects_missing_columns():
    """Return a validation error when required CSV columns are absent."""

    override_client()
    api = create_api()

    response = api.post(
        "/hospitals/bulk/validate",
        files={
            "file": ("bad.csv", "name,phone\nGeneral Hospital,555-1234\n", "text/csv")
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["errors"]


def test_progress_returns_404_for_missing_batch():
    """Return a 404 when a batch progress lookup targets an unknown batch."""

    override_client()
    api = create_api()

    response = api.get("/hospitals/bulk/nonexistent-batch-id/progress")

    assert response.status_code == 404
    assert response.json()["detail"] == "Batch not found"

"""Integration tests for the FastAPI bulk upload endpoints."""

from tests.conftest import create_api, override_client


def test_bulk_upload_creates_and_activates_batch():
    """Submit a CSV, process it end to end, and verify the returned batch."""

    client = override_client()
    api = create_api()

    response = api.post(
        "/hospitals/bulk",
        files={
            "file": (
                "hospitals.csv",
                "name,address,phone\nGeneral Hospital,123 Main St,555-1234\nCity Clinic,45 Oak Ave,\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_hospitals"] == 2
    assert body["processed_hospitals"] == 2
    assert body["failed_hospitals"] == 0
    assert body["batch_activated"] is True
    assert body["progress_percentage"] == 100.0
    assert body["status"] == "completed"
    assert len(body["hospitals"]) == 2
    assert client.activated_batches

    progress = api.get(f"/hospitals/bulk/{body['batch_id']}/progress")
    assert progress.status_code == 200
    assert progress.json()["progress_percentage"] == 100.0

    detail = api.get(f"/hospitals/bulk/{body['batch_id']}")
    assert detail.status_code == 200
    assert detail.json()["batch_activated"] is True


def test_csv_validation_endpoint_reports_valid_csv():
    """Validate a well-formed CSV without creating downstream records."""

    override_client()
    api = create_api()

    response = api.post(
        "/hospitals/bulk/validate",
        files={
            "file": (
                "hospitals.csv",
                "name,address,phone\nGeneral Hospital,123 Main St,555-1234\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["total_hospitals"] == 1


def test_resume_retries_failed_rows_and_activates_batch():
    """Retry a partially failed batch until it completes successfully."""

    client = override_client(failing_names={"City Clinic"})
    api = create_api()

    response = api.post(
        "/hospitals/bulk",
        files={
            "file": (
                "hospitals.csv",
                "name,address,phone\nGeneral Hospital,123 Main St,555-1234\nCity Clinic,45 Oak Ave,\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["failed_hospitals"] == 1
    assert body["status"] == "partial_failed"
    batch_id = body["batch_id"]

    resume_response = api.post(f"/hospitals/bulk/{batch_id}/resume")
    assert resume_response.status_code == 200
    resume_body = resume_response.json()
    assert resume_body["failed_hospitals"] == 0
    assert resume_body["batch_activated"] is True
    assert resume_body["status"] == "completed"
    assert client.activated_batches

from typing import Any, Dict, List, Optional, Set

from fastapi.testclient import TestClient

from app.main import app, get_bulk_service, get_hospital_client
from app.settings import get_settings
from app.bulk_service import BulkProcessingService


class FakeHospitalClient:
    def __init__(self, failing_names: Optional[Set[str]] = None) -> None:
        self.created_payloads: List[Dict[str, Any]] = []
        self.activated_batches: List[str] = []
        self.failing_names: Set[str] = set(failing_names or [])
        self.fail_once: Set[str] = set(failing_names or [])

    async def create_hospital(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        self.created_payloads.append(payload)
        if payload["name"] in self.fail_once:
            self.fail_once.remove(payload["name"])
            raise RuntimeError(f"temporary failure for {payload['name']}")
        return {"id": len(self.created_payloads), "name": payload["name"]}

    async def activate_batch(self, batch_id: str) -> Dict[str, str]:
        self.activated_batches.append(batch_id)
        return {"status": "activated"}


def override_client(failing_names: Optional[Set[str]] = None) -> FakeHospitalClient:
    client = FakeHospitalClient(failing_names=failing_names)

    async def _dependency():
        yield client

    app.dependency_overrides[get_hospital_client] = _dependency
    return client


def reset_service():
    app.state.bulk_service = BulkProcessingService()


def create_api():
    reset_service()
    app.dependency_overrides[get_bulk_service] = lambda: app.state.bulk_service
    app.dependency_overrides[get_settings] = lambda: get_settings()
    return TestClient(app)


def test_bulk_upload_creates_and_activates_batch():
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

    app.dependency_overrides.clear()

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


def test_bulk_upload_rejects_too_many_rows():
    override_client()
    api = create_api()

    csv_rows = ["name,address,phone"]
    for index in range(21):
        csv_rows.append(f"Hospital {index},Address {index},555-000{index}")

    response = api.post(
        "/hospitals/bulk",
        files={"file": ("hospitals.csv", "\n".join(csv_rows), "text/csv")},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "maximum of 20 hospitals" in response.json()["detail"]


def test_csv_validation_endpoint_reports_valid_csv():
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


def test_validation_rejects_missing_columns():
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

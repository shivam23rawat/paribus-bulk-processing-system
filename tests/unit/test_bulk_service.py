"""Unit tests for the in-memory bulk processing service."""

from app.bulk_service import BulkBatchRecord, BulkHospitalRecord, BulkProcessingService
from app.csv_utils import HospitalCsvRow


def test_bulk_batch_record_reports_progress_and_summary():
    """Compute batch summary fields from mixed hospital states."""

    batch = BulkBatchRecord(
        batch_id="batch-1",
        hospitals=[
            BulkHospitalRecord(
                row=2,
                name="General Hospital",
                address="123 Main St",
                phone=None,
                status="created",
            ),
            BulkHospitalRecord(
                row=3,
                name="City Clinic",
                address="45 Oak Ave",
                phone=None,
                status="failed",
            ),
            BulkHospitalRecord(
                row=4,
                name="Rural Medical Center",
                address="789 Farm Rd",
                phone=None,
                status="pending",
            ),
        ],
    )

    assert batch.total_hospitals == 3
    assert batch.processed_hospitals == 1
    assert batch.failed_hospitals == 1
    assert batch.progress_percentage == 66.67

    summary = batch.to_summary()
    assert summary["batch_id"] == "batch-1"
    assert summary["progress_percentage"] == 66.67
    assert summary["total_hospitals"] == 3


async def test_create_batch_initializes_pending_records():
    """Create a batch with pending records from parsed CSV rows."""

    service = BulkProcessingService()
    rows = [
        HospitalCsvRow(
            row_number=2,
            name="General Hospital",
            address="123 Main St",
            phone="555-1234",
        ),
        HospitalCsvRow(
            row_number=3, name="City Clinic", address="45 Oak Ave", phone=None
        ),
    ]

    batch = await service.create_batch(rows, batch_id="batch-2")

    assert batch.batch_id == "batch-2"
    assert batch.status == "processing"
    assert batch.total_hospitals == 2
    assert all(hospital.status == "pending" for hospital in batch.hospitals)
    assert batch.hospitals[0].phone == "555-1234"
    assert batch.hospitals[1].phone is None

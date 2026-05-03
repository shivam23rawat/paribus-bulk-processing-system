"""HTTP application for the bulk processing service.

This module exposes the FastAPI application and the HTTP endpoints for
submitting CSVs, validating them, polling progress, fetching batch details,
and resuming failed batches.

The HTTP handlers are intentionally thin: they parse input, delegate to the
`BulkProcessingService`, and format Pydantic responses.
"""

import time
import uuid
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile

from .bulk_service import BulkBatchRecord, BulkProcessingService
from .csv_utils import CsvValidationError, parse_hospital_csv
from .hospital_client import HospitalDirectoryClient
from .schemas import (
    BulkBatchDetailResponse,
    BulkBatchProgress,
    BulkCreateResponse,
    BulkCsvValidationResponse,
    BulkProcessingError,
    HospitalRowResult,
)
from .settings import Settings, get_settings

app = FastAPI(title="Hospital Bulk Processing System")
app.state.bulk_service = BulkProcessingService()


async def get_hospital_client(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[HospitalDirectoryClient, None]:
    """Dependency that yields a configured :class:`HospitalDirectoryClient`.

    This is a thin wrapper to allow dependency injection in tests.
    """
    yield HospitalDirectoryClient(settings)


def get_bulk_service() -> BulkProcessingService:
    """Return the app-scoped :class:`BulkProcessingService` instance."""
    return app.state.bulk_service


def _batch_to_response(
    batch: BulkBatchRecord, processing_time_seconds: float
) -> BulkCreateResponse:
    """Convert an internal batch record to the public response model.

    Parameters
    ----------
    batch : BulkBatchRecord
        Internal batch state.
    processing_time_seconds : float
        Elapsed processing time to include in the response.
    """
    hospitals = [
        HospitalRowResult(
            row=hospital.row,
            hospital_id=hospital.hospital_id,
            name=hospital.name,
            status=hospital.status,
            error=hospital.error,
        )
        for hospital in batch.hospitals
    ]
    errors = [
        BulkProcessingError(row=hospital.row, message=hospital.error or "Unknown error")
        for hospital in batch.hospitals
        if hospital.status == "failed"
    ]
    return BulkCreateResponse(
        batch_id=batch.batch_id,
        status=batch.status,
        total_hospitals=batch.total_hospitals,
        processed_hospitals=batch.processed_hospitals,
        failed_hospitals=batch.failed_hospitals,
        processing_time_seconds=round(processing_time_seconds, 3),
        batch_activated=batch.batch_activated,
        progress_percentage=batch.progress_percentage,
        hospitals=hospitals,
        errors=errors,
    )


def _batch_to_detail_response(
    batch: BulkBatchRecord, processing_time_seconds: float = 0.0
) -> BulkBatchDetailResponse:
    """Produce a detailed batch response including timestamps."""
    response = _batch_to_response(batch, processing_time_seconds)
    return BulkBatchDetailResponse(
        **response.model_dump(),
        created_at=batch.created_at.isoformat(),
        updated_at=batch.updated_at.isoformat(),
    )


@app.get("/health")
async def health() -> dict:
    """Simple health check endpoint."""
    return {"status": "ok"}


@app.post("/hospitals/bulk/validate", response_model=BulkCsvValidationResponse)
async def validate_bulk_csv(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> BulkCsvValidationResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A CSV file is required")

    try:
        raw_bytes = await file.read()
        csv_text = raw_bytes.decode("utf-8-sig")
        rows = parse_hospital_csv(csv_text, settings.max_csv_hospitals)
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="CSV must be UTF-8 encoded"
        ) from exc
    except CsvValidationError as exc:
        return BulkCsvValidationResponse(
            valid=False,
            total_hospitals=0,
            errors=[BulkProcessingError(message=str(exc))],
        )

    return BulkCsvValidationResponse(valid=True, total_hospitals=len(rows), errors=[])


@app.post("/hospitals/bulk", response_model=BulkCreateResponse)
async def bulk_create_hospitals(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    hospital_client: HospitalDirectoryClient = Depends(get_hospital_client),
    bulk_service: BulkProcessingService = Depends(get_bulk_service),
) -> BulkCreateResponse:
    started_at = time.perf_counter()
    batch_id = str(uuid.uuid4())

    if not file.filename:
        raise HTTPException(status_code=400, detail="A CSV file is required")

    try:
        raw_bytes = await file.read()
        csv_text = raw_bytes.decode("utf-8-sig")
        rows = parse_hospital_csv(csv_text, settings.max_csv_hospitals)
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400, detail="CSV must be UTF-8 encoded"
        ) from exc
    except CsvValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    batch = await bulk_service.create_batch(rows, batch_id=batch_id)
    batch = await bulk_service.process_batch(batch.batch_id, hospital_client)
    return _batch_to_response(batch, time.perf_counter() - started_at)


@app.get("/hospitals/bulk/{batch_id}/progress", response_model=BulkBatchProgress)
async def get_bulk_progress(
    batch_id: str, bulk_service: BulkProcessingService = Depends(get_bulk_service)
) -> BulkBatchProgress:
    batch = await bulk_service.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    return BulkBatchProgress(**batch.to_summary())


@app.get("/hospitals/bulk/{batch_id}", response_model=BulkBatchDetailResponse)
async def get_bulk_batch(
    batch_id: str, bulk_service: BulkProcessingService = Depends(get_bulk_service)
) -> BulkBatchDetailResponse:
    batch = await bulk_service.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    return _batch_to_detail_response(batch)


@app.post("/hospitals/bulk/{batch_id}/resume", response_model=BulkBatchDetailResponse)
async def resume_bulk_batch(
    batch_id: str,
    hospital_client: HospitalDirectoryClient = Depends(get_hospital_client),
    bulk_service: BulkProcessingService = Depends(get_bulk_service),
) -> BulkBatchDetailResponse:
    batch = await bulk_service.get_batch(batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    if batch.failed_hospitals == 0 and not batch.batch_activated:
        batch = await bulk_service.process_batch(
            batch_id, hospital_client, only_failed=True
        )
    else:
        batch = await bulk_service.resume_batch(batch_id, hospital_client)

    return _batch_to_detail_response(batch)

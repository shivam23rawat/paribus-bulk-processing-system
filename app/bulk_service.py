"""In-memory batch management used by the bulk processing endpoints.

This module implements a small, thread-safe-in-asyncio in-memory store for
tracking batch progress and supporting resume semantics. It's intentionally
simple and not durable so it is easy to replace with a database or cache in
the future.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

import httpx

from .csv_utils import HospitalCsvRow


def _utc_now() -> datetime:
    """Return the current UTC time with timezone information.

    Returns
    -------
    datetime
        Current UTC timestamp.
    """
    return datetime.now(timezone.utc)


@dataclass
class BulkHospitalRecord:
    """Representation of a single hospital within a batch.

    Attributes
    ----------
    row : int
        The source CSV row number.
    name : str
        Hospital name.
    address : str
        Hospital address.
    phone : Optional[str]
        Optional phone string.
    hospital_id : Optional[int]
        Downstream hospital id once created.
    status : str
        Processing status for the row (e.g. 'pending', 'created', 'failed').
    error : Optional[str]
        Error message if the row failed to process.
    attempts : int
        Number of attempts made to create this row.
    """

    row: int
    name: str
    address: str
    phone: Optional[str]
    hospital_id: Optional[int] = None
    status: str = "pending"
    error: Optional[str] = None
    attempts: int = 0


@dataclass
class BulkBatchRecord:
    """Aggregate record for a submitted batch.

    Attributes
    ----------
    batch_id : str
        Identifier for the batch.
    hospitals : List[BulkHospitalRecord]
        List of hospital records in the batch.
    created_at : datetime
        Timestamp when the batch was created.
    updated_at : datetime
        Timestamp for the last update to the batch.
    status : str
        Overall batch status (queued/processing/completed/failed/etc.).
    batch_activated : bool
        Whether the downstream batch activation has completed.
    """

    batch_id: str
    hospitals: List[BulkHospitalRecord]
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    status: str = "queued"
    batch_activated: bool = False

    @property
    def total_hospitals(self) -> int:
        """Return the total number of hospitals in the batch."""
        return len(self.hospitals)

    @property
    def processed_hospitals(self) -> int:
        """Count hospitals that have been created (regardless of activation)."""
        return sum(
            1
            for hospital in self.hospitals
            if hospital.status in {"created", "created_and_activated"}
        )

    @property
    def failed_hospitals(self) -> int:
        """Count hospitals that are currently marked as failed."""
        return sum(1 for hospital in self.hospitals if hospital.status == "failed")

    @property
    def progress_percentage(self) -> float:
        """Compute a simple completed-percentage for the batch.

        Returns
        -------
        float
            Completed percentage rounded to two decimal places.
        """
        if not self.hospitals:
            return 0.0
        completed = sum(
            1
            for hospital in self.hospitals
            if hospital.status in {"created", "created_and_activated", "failed"}
        )
        return round((completed / len(self.hospitals)) * 100.0, 2)

    def to_summary(self) -> dict:
        """Return a serializable summary of the batch for progress endpoints."""
        return {
            "batch_id": self.batch_id,
            "status": self.status,
            "total_hospitals": self.total_hospitals,
            "processed_hospitals": self.processed_hospitals,
            "failed_hospitals": self.failed_hospitals,
            "progress_percentage": self.progress_percentage,
            "batch_activated": self.batch_activated,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class BulkProcessingService:
    """In-memory service that stores batches and processes them.

    This class is purposely simple: it stores batch state in a dictionary and
    uses an asyncio lock to protect concurrent access from multiple
    request handlers. It exposes methods to create batches, process them, and
    resume failed rows.
    """

    def __init__(self) -> None:
        self._batches: Dict[str, BulkBatchRecord] = {}
        self._lock = asyncio.Lock()

    async def create_batch(
        self, rows: Iterable[HospitalCsvRow], batch_id: str
    ) -> BulkBatchRecord:
        """Create a new batch record from parsed CSV rows.

        Parameters
        ----------
        rows : Iterable[HospitalCsvRow]
            Parsed CSV rows.
        batch_id : str
            Identifier to assign to the batch.

        Returns
        -------
        BulkBatchRecord
            The created batch object.
        """
        batch = BulkBatchRecord(
            batch_id=batch_id,
            hospitals=[
                BulkHospitalRecord(
                    row=row.row_number,
                    name=row.name,
                    address=row.address,
                    phone=row.phone,
                )
                for row in rows
            ],
            status="processing",
        )
        async with self._lock:
            self._batches[batch_id] = batch
        return batch

    async def get_batch(self, batch_id: str) -> Optional[BulkBatchRecord]:
        """Retrieve a batch by id.

        Returns None if the batch is not present.
        """
        async with self._lock:
            return self._batches.get(batch_id)

    async def process_batch(
        self, batch_id: str, hospital_client, only_failed: bool = False
    ) -> BulkBatchRecord:
        """Process (or re-process) a batch's rows.

        Parameters
        ----------
        batch_id : str
            Identifier of the batch to process.
        hospital_client : Any
            Downstream client implementing `create_hospital` and
            `activate_batch` coroutine methods.
        only_failed : bool, optional
            If True, only process rows previously marked as failed.

        Returns
        -------
        BulkBatchRecord
            Updated batch state after processing.

        Raises
        ------
        KeyError
            If the batch does not exist.
        """
        batch = await self.get_batch(batch_id)
        if batch is None:
            raise KeyError(batch_id)

        batch.status = "processing"
        batch.updated_at = _utc_now()

        if only_failed:
            candidate_rows = [
                hospital for hospital in batch.hospitals if hospital.status == "failed"
            ]
        else:
            candidate_rows = [
                hospital
                for hospital in batch.hospitals
                if hospital.status == "pending" or hospital.status == "failed"
            ]

        for hospital in candidate_rows:
            if hospital.status == "created":
                continue

            hospital.attempts += 1
            hospital.status = "processing"
            hospital.error = None
            payload = {
                "name": hospital.name,
                "address": hospital.address,
                "creation_batch_id": batch.batch_id,
            }
            if hospital.phone:
                payload["phone"] = hospital.phone

            try:
                created = await hospital_client.create_hospital(payload)
            except (
                httpx.HTTPStatusError
            ) as exc:  # pragma: no cover - downstream failure path
                hospital.status = "failed"
                error_detail = f"HTTP {exc.response.status_code}"
                try:
                    error_detail += f": {exc.response.text}"
                except Exception:
                    pass
                hospital.error = error_detail
                batch.updated_at = _utc_now()
                continue
            except Exception as exc:  # pragma: no cover - downstream failure path
                hospital.status = "failed"
                hospital.error = f"{type(exc).__name__}: {str(exc)}"
                batch.updated_at = _utc_now()
                continue

            hospital.hospital_id = created.get("id")
            hospital.name = created.get("name", hospital.name)
            hospital.status = "created"
            hospital.error = None
            batch.updated_at = _utc_now()

        if (
            batch.failed_hospitals == 0
            and batch.processed_hospitals == batch.total_hospitals
        ):
            try:
                await hospital_client.activate_batch(batch.batch_id)
                batch.batch_activated = True
                for hospital in batch.hospitals:
                    if hospital.status == "created":
                        hospital.status = "created_and_activated"
                batch.status = "completed"
            except Exception:  # pragma: no cover - activation failure
                batch.status = "completed_but_not_activated"
        elif batch.failed_hospitals > 0 and batch.processed_hospitals > 0:
            batch.status = "partial_failed"
        else:
            batch.status = "failed"

        batch.updated_at = _utc_now()
        return batch

    async def create_and_process_batch(
        self, rows: Iterable[HospitalCsvRow], batch_id: str, hospital_client
    ) -> BulkBatchRecord:
        """Convenience helper to create and immediately process a batch."""
        await self.create_batch(rows, batch_id=batch_id)
        return await self.process_batch(batch_id, hospital_client, only_failed=False)

    async def resume_batch(self, batch_id: str, hospital_client) -> BulkBatchRecord:
        """Resume processing for a batch by retrying only failed rows."""
        return await self.process_batch(batch_id, hospital_client, only_failed=True)

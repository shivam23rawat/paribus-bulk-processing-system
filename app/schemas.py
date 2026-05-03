"""Response schemas used by the bulk processing API.

These Pydantic models define the JSON shapes returned by endpoints and are
designed to be minimal while providing useful information for clients.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class HospitalRowResult(BaseModel):
    """Result for a single CSV row after processing.

    Attributes
    ----------
    row : int
        CSV row number (1-based with header counted where applicable).
    hospital_id : Optional[int]
        Downstream hospital ID assigned by the Hospital Directory API.
    name : str
        Hospital name.
    status : str
        Processing status ("pending", "created", "failed", etc.).
    error : Optional[str]
        Error message if the row failed processing.
    """

    row: int
    hospital_id: Optional[int] = None
    name: str
    status: str
    error: Optional[str] = None


class BulkProcessingError(BaseModel):
    """Simple error model for reporting CSV or row failures."""

    row: Optional[int] = None
    message: str


class BulkBatchProgress(BaseModel):
    """Summary progress response for a batch."""

    batch_id: str
    status: str
    total_hospitals: int
    processed_hospitals: int
    failed_hospitals: int
    progress_percentage: float = Field(ge=0, le=100)
    batch_activated: bool
    created_at: str
    updated_at: str


class BulkCsvValidationResponse(BaseModel):
    """Response for CSV validation requests."""

    valid: bool
    total_hospitals: int
    errors: List[BulkProcessingError] = []


class BulkCreateResponse(BaseModel):
    """Response returned after submitting a bulk create request.

    Includes the batch identifier and per-row results.
    """

    batch_id: str
    status: str
    total_hospitals: int
    processed_hospitals: int
    failed_hospitals: int
    processing_time_seconds: float = Field(ge=0)
    batch_activated: bool
    progress_percentage: float = Field(ge=0, le=100)
    hospitals: List[HospitalRowResult]
    errors: List[BulkProcessingError] = []


class BulkBatchDetailResponse(BulkCreateResponse):
    """Detailed batch response that adds timestamps."""

    created_at: Optional[str] = None
    updated_at: Optional[str] = None

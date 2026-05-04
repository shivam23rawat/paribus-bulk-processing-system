"""Response schemas used by the bulk processing API.

These Pydantic models define the JSON shapes returned by endpoints and are
designed to be minimal while providing useful information for clients.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


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

    row: int = Field(
        description="CSV row number, starting at 1 for the header-adjusted data row."
    )
    hospital_id: Optional[int] = Field(
        default=None,
        description="Downstream hospital identifier returned by the Directory API.",
    )
    name: str = Field(description="Hospital name from the CSV input.")
    status: str = Field(description="Processing state for the row.")
    error: Optional[str] = Field(
        default=None, description="Error message if the row failed."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "row": 2,
                "hospital_id": 123,
                "name": "General Hospital",
                "status": "created_and_activated",
                "error": None,
            }
        }
    )


class BulkProcessingError(BaseModel):
    """Simple error model for reporting CSV or row failures."""

    row: Optional[int] = Field(
        default=None,
        description="CSV row number associated with the error, when available.",
    )
    message: str = Field(description="Human-readable error message.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "row": 3,
                "message": "HTTP 404: Not Found",
            }
        }
    )


class BulkBatchProgress(BaseModel):
    """Summary progress response for a batch."""

    batch_id: str = Field(description="Unique identifier for the batch.")
    status: str = Field(description="Current batch processing state.")
    total_hospitals: int = Field(description="Total number of hospitals in the batch.")
    processed_hospitals: int = Field(
        description="Number of rows successfully created so far."
    )
    failed_hospitals: int = Field(description="Number of rows that failed processing.")
    progress_percentage: float = Field(ge=0, le=100)
    batch_activated: bool = Field(
        description="Whether the downstream batch activation completed."
    )
    created_at: str = Field(description="Timestamp when the batch was created.")
    updated_at: str = Field(description="Timestamp when the batch was last updated.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "batch_id": "a20c4988-1d52-4a25-930b-788f25cbd7c9",
                "status": "completed",
                "total_hospitals": 3,
                "processed_hospitals": 3,
                "failed_hospitals": 0,
                "progress_percentage": 100.0,
                "batch_activated": True,
                "created_at": "2026-05-04T03:15:30.802405+00:00",
                "updated_at": "2026-05-04T03:15:58.735775+00:00",
            }
        }
    )


class BulkCsvValidationResponse(BaseModel):
    """Response for CSV validation requests."""

    valid: bool = Field(description="Whether the CSV passed validation.")
    total_hospitals: int = Field(
        description="Number of hospital rows detected in the CSV."
    )
    errors: List[BulkProcessingError] = Field(
        default_factory=list, description="Validation errors, if any."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "valid": True,
                "total_hospitals": 2,
                "errors": [],
            }
        }
    )


class BulkCreateResponse(BaseModel):
    """Response returned after submitting a bulk create request.

    Includes the batch identifier and per-row results.
    """

    batch_id: str = Field(description="Unique identifier for the batch.")
    status: str = Field(description="Current batch processing state.")
    total_hospitals: int = Field(description="Total number of hospitals submitted.")
    processed_hospitals: int = Field(
        description="Number of rows successfully processed."
    )
    failed_hospitals: int = Field(description="Number of rows that failed processing.")
    processing_time_seconds: float = Field(ge=0)
    batch_activated: bool = Field(description="Whether batch activation succeeded.")
    progress_percentage: float = Field(ge=0, le=100)
    hospitals: List[HospitalRowResult] = Field(description="Per-row hospital results.")
    errors: List[BulkProcessingError] = Field(
        default_factory=list, description="Errors encountered while processing."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "batch_id": "a20c4988-1d52-4a25-930b-788f25cbd7c9",
                "status": "completed",
                "total_hospitals": 3,
                "processed_hospitals": 3,
                "failed_hospitals": 0,
                "processing_time_seconds": 27.935,
                "batch_activated": True,
                "progress_percentage": 100.0,
                "hospitals": [
                    {
                        "row": 2,
                        "hospital_id": 1,
                        "name": "General Hospital",
                        "status": "created_and_activated",
                        "error": None,
                    }
                ],
                "errors": [],
            }
        }
    )


class BulkBatchDetailResponse(BulkCreateResponse):
    """Detailed batch response that adds timestamps."""

    created_at: Optional[str] = Field(
        default=None, description="Timestamp when the batch was created."
    )
    updated_at: Optional[str] = Field(
        default=None, description="Timestamp when the batch was last updated."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "batch_id": "a20c4988-1d52-4a25-930b-788f25cbd7c9",
                "status": "completed",
                "total_hospitals": 3,
                "processed_hospitals": 3,
                "failed_hospitals": 0,
                "processing_time_seconds": 0.0,
                "batch_activated": True,
                "progress_percentage": 100.0,
                "hospitals": [
                    {
                        "row": 2,
                        "hospital_id": 1,
                        "name": "General Hospital",
                        "status": "created_and_activated",
                        "error": None,
                    }
                ],
                "errors": [],
                "created_at": "2026-05-04T03:15:30.802405+00:00",
                "updated_at": "2026-05-04T03:15:58.735775+00:00",
            }
        }
    )

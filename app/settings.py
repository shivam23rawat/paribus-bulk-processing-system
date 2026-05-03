"""Application settings.

This module centralizes configuration values that the service uses. Values
are read from environment variables by default so the application can be
configured at deployment time without code changes.
"""

import os
from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Container for runtime configuration values.

    Parameters
    ----------
    hospital_directory_api_base_url : str
        Base URL of the downstream Hospital Directory API.
    max_csv_hospitals : int
        Maximum number of hospitals allowed in a single CSV upload.
    downstream_timeout_seconds : float
        HTTP timeout for calls to the downstream API.
    """

    hospital_directory_api_base_url: str = Field(
        default_factory=lambda: os.getenv(
            "HOSPITAL_DIRECTORY_API_BASE_URL", "https://hospital-directory.onrender.com"
        )
    )
    max_csv_hospitals: int = Field(
        default_factory=lambda: int(os.getenv("MAX_CSV_HOSPITALS", "20"))
    )
    downstream_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("DOWNSTREAM_TIMEOUT_SECONDS", "30.0"))
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    Returns
    -------
    Settings
        The application settings instance populated from environment
        variables.
    """
    return Settings()

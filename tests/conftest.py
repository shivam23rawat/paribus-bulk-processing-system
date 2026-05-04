"""Shared test fixtures and helpers for the bulk processing test suite.

This module provides a fake downstream client plus reusable FastAPI test
application setup used by the unit, integration, and error scenario tests.
"""

from typing import Any, Dict, List, Optional, Set

import pytest
from fastapi.testclient import TestClient

from app.bulk_service import BulkProcessingService
from app.main import app, get_bulk_service, get_hospital_client
from app.settings import get_settings


class FakeHospitalClient:
    """Minimal downstream client double used to isolate API tests.

    Parameters
    ----------
    failing_names : Optional[Set[str]], optional
        Hospital names that should fail once before succeeding on retry.
    """

    def __init__(self, failing_names: Optional[Set[str]] = None) -> None:
        self.created_payloads: List[Dict[str, Any]] = []
        self.activated_batches: List[str] = []
        self.failing_names: Set[str] = set(failing_names or [])
        self.fail_once: Set[str] = set(failing_names or [])

    async def create_hospital(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Pretend to create a downstream hospital record.

        The method records the payload so tests can assert on the request body
        and optionally raises once to exercise retry paths.
        """

        self.created_payloads.append(payload)
        if payload["name"] in self.fail_once:
            self.fail_once.remove(payload["name"])
            raise RuntimeError(f"temporary failure for {payload['name']}")
        return {"id": len(self.created_payloads), "name": payload["name"]}

    async def activate_batch(self, batch_id: str) -> Dict[str, str]:
        """Record downstream batch activation attempts.

        Returns
        -------
        Dict[str, str]
            A small success payload matching the production client shape.
        """

        self.activated_batches.append(batch_id)
        return {"status": "activated"}


def override_client(failing_names: Optional[Set[str]] = None) -> FakeHospitalClient:
    """Override the FastAPI dependency with a fake downstream client."""

    client = FakeHospitalClient(failing_names=failing_names)

    async def _dependency():
        yield client

    # Each test gets a deterministic downstream client through dependency injection.
    app.dependency_overrides[get_hospital_client] = _dependency
    return client


def create_api() -> TestClient:
    """Create a fresh TestClient backed by a new in-memory batch service."""

    app.state.bulk_service = BulkProcessingService()
    app.dependency_overrides[get_bulk_service] = lambda: app.state.bulk_service
    app.dependency_overrides[get_settings] = lambda: get_settings()
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_app_state() -> None:
    """Reset dependency overrides and batch state around each test."""

    # Tests rely on isolated application state so one scenario cannot leak into another.
    app.dependency_overrides.clear()
    app.state.bulk_service = BulkProcessingService()
    yield
    app.dependency_overrides.clear()
    app.state.bulk_service = BulkProcessingService()

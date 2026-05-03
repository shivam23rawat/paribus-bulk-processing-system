"""HTTP client wrapper for the Hospital Directory API.

This small helper centralizes calls to the downstream API so the rest of the
application does not need to manage `httpx.AsyncClient` usage or the base
URL/timeout configuration.
"""

from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx

from .settings import Settings


class HospitalDirectoryClient:
    """Client to interact with the external Hospital Directory API.

    Parameters
    ----------
    settings : Settings
        Application settings object used to obtain the downstream base URL
        and timeouts.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def create_hospital(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a single hospital record in the downstream API.

        Parameters
        ----------
        payload : dict
            The JSON payload sent to `POST /hospitals/` on the downstream
            service.

        Returns
        -------
        dict
            The parsed JSON response from the downstream API.

        Raises
        ------
        httpx.HTTPStatusError
            If the downstream API returns a non-2xx response.
        """
        async with httpx.AsyncClient(
            base_url=str(self._settings.hospital_directory_api_base_url),
            timeout=self._settings.downstream_timeout_seconds,
        ) as client:
            response = await client.post("/hospitals/", json=payload)
        response.raise_for_status()
        return response.json()

    async def activate_batch(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """Activate all hospitals in a batch.

        Parameters
        ----------
        batch_id : str
            UUID identifying the created batch.

        Returns
        -------
        Optional[dict]
            Parsed JSON from the downstream activation endpoint, if any.

        Raises
        ------
        httpx.HTTPStatusError
            If the downstream activation call fails.
        """
        async with httpx.AsyncClient(
            base_url=str(self._settings.hospital_directory_api_base_url),
            timeout=self._settings.downstream_timeout_seconds,
        ) as client:
            response = await client.patch(
                f"/hospitals/batch/{quote(batch_id, safe='')}/activate"
            )
        response.raise_for_status()
        if response.content:
            return response.json()
        return None

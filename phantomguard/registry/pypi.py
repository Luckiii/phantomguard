from __future__ import annotations

from datetime import datetime

import httpx

from phantomguard.registry.models import RegistryLookupResult

PYPI_JSON_URL = "https://pypi.org/pypi/{name}/json"


def _earliest_release_date(payload: dict) -> datetime | None:
    timestamps: list[datetime] = []
    for files in payload.get("releases", {}).values():
        for file_info in files:
            raw = file_info.get("upload_time_iso_8601")
            if raw:
                timestamps.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    return min(timestamps) if timestamps else None


class PyPiClient:
    def __init__(self, client: httpx.Client | None = None, timeout: float = 5.0) -> None:
        self._client = client or httpx.Client(timeout=timeout)

    def check_exists(self, name: str) -> RegistryLookupResult:
        url = PYPI_JSON_URL.format(name=name)
        try:
            response = self._client.get(url)
        except httpx.TimeoutException:
            return RegistryLookupResult(name=name, exists=None, status_code=None, error="timeout")
        except httpx.RequestError as exc:
            return RegistryLookupResult(
                name=name, exists=None, status_code=None, error=f"network error: {exc}"
            )

        if response.status_code == 200:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            return RegistryLookupResult(
                name=name,
                exists=True,
                status_code=200,
                first_release_at=_earliest_release_date(payload),
            )
        if response.status_code == 404:
            return RegistryLookupResult(name=name, exists=False, status_code=404)
        return RegistryLookupResult(
            name=name,
            exists=None,
            status_code=response.status_code,
            error=f"unexpected status {response.status_code}",
        )

    def close(self) -> None:
        self._client.close()

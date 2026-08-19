from __future__ import annotations

from datetime import datetime

import httpx

from phantomguard.registry.models import RegistryLookupResult

NPM_REGISTRY_URL = "https://registry.npmjs.org/{name}"


def _created_date(payload: dict) -> datetime | None:
    raw = payload.get("time", {}).get("created")
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


class NpmClient:
    def __init__(self, client: httpx.Client | None = None, timeout: float = 5.0) -> None:
        self._client = client or httpx.Client(timeout=timeout)

    def check_exists(self, name: str) -> RegistryLookupResult:
        url = NPM_REGISTRY_URL.format(name=name)
        try:
            response = self._client.get(url)
        except httpx.TimeoutException:
            return RegistryLookupResult(
                name=name, exists=None, status_code=None, error="timeout", ecosystem="npm"
            )
        except httpx.RequestError as exc:
            return RegistryLookupResult(
                name=name,
                exists=None,
                status_code=None,
                error=f"network error: {exc}",
                ecosystem="npm",
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
                first_release_at=_created_date(payload),
                ecosystem="npm",
            )
        if response.status_code == 404:
            return RegistryLookupResult(name=name, exists=False, status_code=404, ecosystem="npm")
        return RegistryLookupResult(
            name=name,
            exists=None,
            status_code=response.status_code,
            error=f"unexpected status {response.status_code}",
            ecosystem="npm",
        )

    def close(self) -> None:
        self._client.close()

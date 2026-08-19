from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class RegistryLookupResult(BaseModel):
    name: str
    exists: bool | None
    status_code: int | None
    error: str | None = None
    first_release_at: datetime | None = None
    ecosystem: str = "pypi"

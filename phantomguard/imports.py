from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class ImportedName(BaseModel):
    module: str
    raw: str
    lineno: int
    source_file: Path = Path("<string>")
    ecosystem: str = "pypi"

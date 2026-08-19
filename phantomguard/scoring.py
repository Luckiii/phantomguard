from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel

from phantomguard.db.known_hallucinations import HallucinatedName, find
from phantomguard.extractor_multi import extract_all_imports_from_path
from phantomguard.registry.npm import NpmClient
from phantomguard.registry.pypi import PyPiClient, RegistryLookupResult


class Verdict(str, Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    BLOCK = "BLOCK"


_REGISTRY_LABELS = {"pypi": "PyPI", "npm": "npm"}


def _registry_label(ecosystem: str) -> str:
    return _REGISTRY_LABELS.get(ecosystem, ecosystem)


class Signal(BaseModel):
    name: str
    points: int
    detail: str


class ImportCheckResult(BaseModel):
    name: str
    ecosystem: str
    verdict: Verdict
    reason: str
    score: int
    signals: list[Signal]
    source_files: list[Path]


class ScanResult(BaseModel):
    target: Path
    results: list[ImportCheckResult]

    @property
    def has_block(self) -> bool:
        return any(r.verdict is Verdict.BLOCK for r in self.results)


def compute_signals(lookup: RegistryLookupResult, known: HallucinatedName | None) -> list[Signal]:
    signals: list[Signal] = []

    if lookup.exists is False:
        signals.append(
            Signal(
                name="not_in_registry",
                points=100,
                detail=f"'{lookup.name}' not found on {_registry_label(lookup.ecosystem)}",
            )
        )

    if known is not None:
        signals.append(
            Signal(
                name="known_hallucination",
                points=80,
                detail=f"matches known hallucinated name (observed {known.times_observed}x)",
            )
        )

    if lookup.exists is True and lookup.first_release_at is not None:
        age_days = (datetime.now(timezone.utc) - lookup.first_release_at).days
        if age_days < 7:
            signals.append(
                Signal(
                    name="very_new_package",
                    points=40,
                    detail=f"first released {age_days} day(s) ago",
                )
            )
        elif age_days < 30:
            signals.append(
                Signal(
                    name="new_package",
                    points=20,
                    detail=f"first released {age_days} day(s) ago",
                )
            )

    return signals


def decide_verdict(lookup: RegistryLookupResult, signals: list[Signal]) -> tuple[Verdict, str]:
    if lookup.exists is None:
        return Verdict.WARN, f"could not verify '{lookup.name}': {lookup.error}"

    score = sum(s.points for s in signals)
    if score >= 70:
        verdict = Verdict.BLOCK
    elif score >= 30:
        verdict = Verdict.WARN
    else:
        verdict = Verdict.ALLOW

    if signals:
        reason = "; ".join(s.detail for s in signals) + f" (score {score})"
    else:
        reason = f"'{lookup.name}' found on {_registry_label(lookup.ecosystem)}, no risk signals fired"

    return verdict, reason


def run_scan(
    path: Path,
    pypi_client: PyPiClient,
    npm_client: NpmClient,
    conn: sqlite3.Connection,
) -> ScanResult:
    imports = extract_all_imports_from_path(path)
    clients: dict[str, PyPiClient | NpmClient] = {"pypi": pypi_client, "npm": npm_client}

    source_files_by_key: dict[tuple[str, str], list[Path]] = {}
    for imported in imports:
        key = (imported.module, imported.ecosystem)
        source_files_by_key.setdefault(key, []).append(imported.source_file)

    results: list[ImportCheckResult] = []
    for (name, ecosystem), source_files in source_files_by_key.items():
        client = clients[ecosystem]
        lookup = client.check_exists(name)
        known = find(conn, name, ecosystem=ecosystem)
        signals = compute_signals(lookup, known)
        verdict, reason = decide_verdict(lookup, signals)
        score = sum(s.points for s in signals)
        results.append(
            ImportCheckResult(
                name=name,
                ecosystem=ecosystem,
                verdict=verdict,
                reason=reason,
                score=score,
                signals=signals,
                source_files=source_files,
            )
        )

    return ScanResult(target=path, results=results)

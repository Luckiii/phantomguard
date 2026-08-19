from __future__ import annotations

import json
import sqlite3

from pydantic import BaseModel


class HallucinatedName(BaseModel):
    name: str
    ecosystem: str
    first_observed_at: str
    last_observed_at: str
    times_observed: int = 1
    observed_by_models: list[str] = []
    pattern_type: str | None = None
    source_of_confusion: str | None = None
    currently_registered: bool = False
    is_malicious: bool | None = None
    confidence: float | None = None
    notes: str | None = None


# Seeded from the public, documented incidents named in docs/phantomguard-mvp-proposal.md
# §7 and §1. `react-codeshift` is directly sourced and dated from §1's citation. The other
# two proposal-named incidents ("unused-imports", "huggingface-cli") are listed there without
# a specific ecosystem/date/source-of-confusion, so their metadata below is a best-effort,
# lower-confidence inference (not independently verified) — flagged in `notes`.
SEED_HALLUCINATED_NAMES: list[HallucinatedName] = [
    HallucinatedName(
        name="react-codeshift",
        ecosystem="npm",
        first_observed_at="2026-01-01",
        last_observed_at="2026-01-31",
        times_observed=237,
        pattern_type="conflation",
        source_of_confusion="jscodeshift + react-codemod",
        currently_registered=True,
        is_malicious=None,
        confidence=1.0,
        notes=(
            "Spread through 237 repositories via AI-generated agent instructions in "
            "January 2026, installed by autonomous agents rather than humans copy-pasting. "
            "See proposal.md §1."
        ),
    ),
    HallucinatedName(
        name="huggingface-cli",
        ecosystem="pypi",
        first_observed_at="2026-08-19",
        last_observed_at="2026-08-19",
        times_observed=1,
        pattern_type="conflation",
        source_of_confusion="huggingface_hub's console-script entry point is named huggingface-cli",
        currently_registered=False,
        is_malicious=None,
        confidence=0.5,
        notes=(
            "Named in proposal.md §7 as a documented public incident, but without a specific "
            "date or source citation there — ecosystem/pattern inferred, not independently "
            "verified. Verify before relying on this entry for enforcement."
        ),
    ),
    HallucinatedName(
        name="unused-imports",
        ecosystem="pypi",
        first_observed_at="2026-08-19",
        last_observed_at="2026-08-19",
        times_observed=1,
        pattern_type="fabrication",
        source_of_confusion=None,
        currently_registered=False,
        is_malicious=None,
        confidence=0.5,
        notes=(
            "Named in proposal.md §7 as a documented public incident, but without a specific "
            "date, ecosystem, or source citation there — inferred, not independently verified. "
            "Verify before relying on this entry for enforcement."
        ),
    ),
]


def seed(conn: sqlite3.Connection, entries: list[HallucinatedName] | None = None) -> None:
    for entry in entries if entries is not None else SEED_HALLUCINATED_NAMES:
        conn.execute(
            """
            INSERT OR IGNORE INTO hallucinated_names (
                name, ecosystem, first_observed_at, last_observed_at, times_observed,
                observed_by_models, pattern_type, source_of_confusion,
                currently_registered, is_malicious, confidence, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.name,
                entry.ecosystem,
                entry.first_observed_at,
                entry.last_observed_at,
                entry.times_observed,
                json.dumps(entry.observed_by_models),
                entry.pattern_type,
                entry.source_of_confusion,
                int(entry.currently_registered),
                None if entry.is_malicious is None else int(entry.is_malicious),
                entry.confidence,
                entry.notes,
            ),
        )
    conn.commit()


def find(conn: sqlite3.Connection, name: str, ecosystem: str = "pypi") -> HallucinatedName | None:
    row = conn.execute(
        """
        SELECT name, ecosystem, first_observed_at, last_observed_at, times_observed,
               observed_by_models, pattern_type, source_of_confusion,
               currently_registered, is_malicious, confidence, notes
        FROM hallucinated_names
        WHERE name = ? AND ecosystem = ?
        """,
        (name, ecosystem),
    ).fetchone()
    if row is None:
        return None
    return HallucinatedName(
        name=row[0],
        ecosystem=row[1],
        first_observed_at=row[2],
        last_observed_at=row[3],
        times_observed=row[4],
        observed_by_models=json.loads(row[5]) if row[5] else [],
        pattern_type=row[6],
        source_of_confusion=row[7],
        currently_registered=bool(row[8]),
        is_malicious=None if row[9] is None else bool(row[9]),
        confidence=row[10],
        notes=row[11],
    )


def ensure_seeded(conn: sqlite3.Connection) -> None:
    count = conn.execute("SELECT COUNT(*) FROM hallucinated_names").fetchone()[0]
    if count == 0:
        seed(conn)

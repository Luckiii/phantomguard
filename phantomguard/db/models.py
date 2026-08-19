from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".phantomguard" / "known_hallucinations.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS hallucinated_names (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    ecosystem TEXT NOT NULL,
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    times_observed INTEGER DEFAULT 1,
    observed_by_models TEXT,
    pattern_type TEXT,
    source_of_confusion TEXT,
    currently_registered INTEGER DEFAULT 0,
    is_malicious INTEGER,
    confidence REAL,
    notes TEXT,
    UNIQUE(name, ecosystem)
);
"""


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn

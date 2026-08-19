import sqlite3

from phantomguard.db.known_hallucinations import (
    SEED_HALLUCINATED_NAMES,
    find,
    seed,
)
from phantomguard.db.models import connect


def test_connect_creates_hallucinated_names_table():
    conn = connect(":memory:")
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "hallucinated_names" in tables


def test_connect_is_idempotent():
    conn = connect(":memory:")
    connect(":memory:")  # separate in-memory db, just proving no exception on repeat schema init
    conn.execute("SELECT 1 FROM hallucinated_names")


def test_find_returns_none_when_not_present():
    conn = connect(":memory:")
    assert find(conn, "requests", ecosystem="pypi") is None


def test_seed_then_find_returns_entry():
    conn = connect(":memory:")
    seed(conn)
    assert len(SEED_HALLUCINATED_NAMES) > 0
    first = SEED_HALLUCINATED_NAMES[0]
    found = find(conn, first.name, ecosystem=first.ecosystem)
    assert found is not None
    assert found.name == first.name
    assert found.ecosystem == first.ecosystem


def test_seed_is_idempotent_no_duplicate_rows():
    conn = connect(":memory:")
    seed(conn)
    seed(conn)
    count = conn.execute("SELECT COUNT(*) FROM hallucinated_names").fetchone()[0]
    assert count == len(SEED_HALLUCINATED_NAMES)


def test_find_is_ecosystem_scoped():
    conn = connect(":memory:")
    seed(conn)
    npm_only = [e for e in SEED_HALLUCINATED_NAMES if e.ecosystem == "npm"]
    if npm_only:
        assert find(conn, npm_only[0].name, ecosystem="pypi") is None

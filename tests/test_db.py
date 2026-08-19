import sqlite3

from phantomguard.db.known_hallucinations import (
    SEED_HALLUCINATED_NAMES,
    find,
    record_observation,
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


def test_record_observation_inserts_new_name():
    conn = connect(":memory:")
    record_observation(conn, "totally-fake-pkg", ecosystem="pypi", model="claude-fable-5", observed_at="2026-08-20")
    found = find(conn, "totally-fake-pkg", ecosystem="pypi")
    assert found is not None
    assert found.times_observed == 1
    assert found.observed_by_models == ["claude-fable-5"]
    assert found.first_observed_at == "2026-08-20"
    assert found.last_observed_at == "2026-08-20"


def test_record_observation_increments_existing_name():
    conn = connect(":memory:")
    record_observation(conn, "totally-fake-pkg", ecosystem="pypi", model="claude-fable-5", observed_at="2026-08-20")
    record_observation(conn, "totally-fake-pkg", ecosystem="pypi", model="claude-fable-5", observed_at="2026-08-21")
    found = find(conn, "totally-fake-pkg", ecosystem="pypi")
    assert found.times_observed == 2
    assert found.last_observed_at == "2026-08-21"
    assert found.first_observed_at == "2026-08-20"


def test_record_observation_dedupes_model_list_but_tracks_new_models():
    conn = connect(":memory:")
    record_observation(conn, "totally-fake-pkg", ecosystem="pypi", model="claude-fable-5", observed_at="2026-08-20")
    record_observation(conn, "totally-fake-pkg", ecosystem="pypi", model="claude-fable-5", observed_at="2026-08-21")
    record_observation(conn, "totally-fake-pkg", ecosystem="pypi", model="gpt-5", observed_at="2026-08-22")
    found = find(conn, "totally-fake-pkg", ecosystem="pypi")
    assert sorted(found.observed_by_models) == ["claude-fable-5", "gpt-5"]
    assert found.times_observed == 3

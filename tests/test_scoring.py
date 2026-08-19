import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from phantomguard.db.known_hallucinations import seed
from phantomguard.db.models import connect
from phantomguard.registry.npm import NpmClient
from phantomguard.registry.pypi import PyPiClient, RegistryLookupResult
from phantomguard.scoring import Verdict, compute_signals, decide_verdict, run_scan

FIXTURES = Path(__file__).parent / "fixtures"


def _db() -> sqlite3.Connection:
    return connect(":memory:")


def test_compute_signals_fires_not_in_registry_for_missing_package():
    lookup = RegistryLookupResult(name="totally-fake-pkg", exists=False, status_code=404)
    signals = compute_signals(lookup, known=None)
    assert [s.name for s in signals] == ["not_in_registry"]
    assert signals[0].points == 100


def test_compute_signals_no_signals_for_established_package():
    lookup = RegistryLookupResult(
        name="requests",
        exists=True,
        status_code=200,
        first_release_at=datetime(2011, 1, 1, tzinfo=timezone.utc),
    )
    assert compute_signals(lookup, known=None) == []


def test_compute_signals_fires_very_new_package_under_7_days():
    lookup = RegistryLookupResult(
        name="brand-new",
        exists=True,
        status_code=200,
        first_release_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    signals = compute_signals(lookup, known=None)
    assert [s.name for s in signals] == ["very_new_package"]
    assert signals[0].points == 40


def test_compute_signals_fires_new_package_between_7_and_30_days():
    lookup = RegistryLookupResult(
        name="somewhat-new",
        exists=True,
        status_code=200,
        first_release_at=datetime.now(timezone.utc) - timedelta(days=15),
    )
    signals = compute_signals(lookup, known=None)
    assert [s.name for s in signals] == ["new_package"]
    assert signals[0].points == 20


def test_compute_signals_no_age_signal_when_first_release_unknown():
    lookup = RegistryLookupResult(name="requests", exists=True, status_code=200, first_release_at=None)
    assert compute_signals(lookup, known=None) == []


def test_decide_verdict_allow_when_no_signals():
    lookup = RegistryLookupResult(name="requests", exists=True, status_code=200)
    verdict, reason = decide_verdict(lookup, signals=[])
    assert verdict is Verdict.ALLOW
    assert "requests" in reason


def test_decide_verdict_block_when_score_at_least_70():
    lookup = RegistryLookupResult(name="totally-fake-pkg", exists=False, status_code=404)
    signals = compute_signals(lookup, known=None)
    verdict, reason = decide_verdict(lookup, signals)
    assert verdict is Verdict.BLOCK
    assert "not found" in reason


def test_compute_signals_not_in_registry_detail_names_npm_for_npm_lookup():
    lookup = RegistryLookupResult(
        name="evilpkg", exists=False, status_code=404, ecosystem="npm"
    )
    signals = compute_signals(lookup, known=None)
    assert "npm" in signals[0].detail
    assert "PyPI" not in signals[0].detail


def test_decide_verdict_allow_reason_names_npm_for_npm_lookup():
    lookup = RegistryLookupResult(name="react", exists=True, status_code=200, ecosystem="npm")
    verdict, reason = decide_verdict(lookup, signals=[])
    assert verdict is Verdict.ALLOW
    assert "npm" in reason
    assert "PyPI" not in reason


def test_decide_verdict_warn_when_score_between_30_and_70():
    lookup = RegistryLookupResult(
        name="somewhat-new",
        exists=True,
        status_code=200,
        first_release_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    signals = compute_signals(lookup, known=None)  # very_new_package = 40
    verdict, reason = decide_verdict(lookup, signals)
    assert verdict is Verdict.WARN


def test_decide_verdict_warn_when_lookup_failed():
    lookup = RegistryLookupResult(name="numpy", exists=None, status_code=None, error="timeout")
    verdict, reason = decide_verdict(lookup, signals=[])
    assert verdict is Verdict.WARN
    assert "timeout" in reason


def _mock_client() -> PyPiClient:
    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.split("/")[2]
        if name == "requests":
            return httpx.Response(200, json={"info": {"name": "requests"}, "releases": {}})
        return httpx.Response(404)

    return PyPiClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def _mock_npm_client() -> NpmClient:
    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.lstrip("/")
        if name == "react":
            return httpx.Response(200, json={"time": {"created": "2013-05-29T00:00:00.000Z"}})
        return httpx.Response(404)

    return NpmClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_run_scan_blocks_hallucinated_fixture():
    result = run_scan(FIXTURES / "hallucinated_example.py", _mock_client(), _mock_npm_client(), _db())
    verdicts = {r.name: r.verdict for r in result.results}
    assert verdicts["definitely_not_a_real_package_xyz123"] is Verdict.BLOCK


def test_run_scan_allows_clean_fixture():
    result = run_scan(FIXTURES / "clean_example.py", _mock_client(), _mock_npm_client(), _db())
    verdicts = {r.name: r.verdict for r in result.results}
    assert verdicts == {"requests": Verdict.ALLOW}


def test_run_scan_dedups_repeated_import_across_files(tmp_path: Path):
    (tmp_path / "a.py").write_text("import requests\n")
    (tmp_path / "b.py").write_text("import requests\n")
    result = run_scan(tmp_path, _mock_client(), _mock_npm_client(), _db())
    assert len(result.results) == 1
    assert len(result.results[0].source_files) == 2


def test_run_scan_blocks_known_hallucinated_name_even_if_now_registered(tmp_path: Path):
    from phantomguard.db.known_hallucinations import HallucinatedName

    (tmp_path / "a.py").write_text("import phantomevilpkg\n")

    def handler(request: httpx.Request) -> httpx.Response:
        # simulate a slopsquatter having registered the name after it was flagged
        return httpx.Response(200, json={"info": {"name": "phantomevilpkg"}, "releases": {}})

    client = PyPiClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    conn = _db()
    seed(
        conn,
        entries=[
            HallucinatedName(
                name="phantomevilpkg",
                ecosystem="pypi",
                first_observed_at="2026-01-01",
                last_observed_at="2026-01-01",
            )
        ],
    )

    result = run_scan(tmp_path, client, _mock_npm_client(), conn)
    assert result.results[0].verdict is Verdict.BLOCK
    assert "known" in result.results[0].reason.lower()


def test_run_scan_blocks_hallucinated_js_import(tmp_path: Path):
    (tmp_path / "a.js").write_text("import evilpkg from 'evilpkg';\n")
    result = run_scan(tmp_path, _mock_client(), _mock_npm_client(), _db())
    verdicts = {r.name: r.verdict for r in result.results}
    assert verdicts["evilpkg"] is Verdict.BLOCK
    assert result.results[0].ecosystem == "npm"


def test_run_scan_allows_clean_js_import(tmp_path: Path):
    (tmp_path / "a.js").write_text("import react from 'react';\n")
    result = run_scan(tmp_path, _mock_client(), _mock_npm_client(), _db())
    verdicts = {r.name: r.verdict for r in result.results}
    assert verdicts["react"] is Verdict.ALLOW


def test_run_scan_keeps_same_name_separate_across_ecosystems(tmp_path: Path):
    # "requests" exists on PyPI (mocked ALLOW) but not on npm (mocked BLOCK) —
    # the two ecosystems must not be merged into a single dedup bucket.
    (tmp_path / "a.py").write_text("import requests\n")
    (tmp_path / "b.js").write_text("import requests from 'requests';\n")
    result = run_scan(tmp_path, _mock_client(), _mock_npm_client(), _db())
    verdicts = {(r.name, r.ecosystem): r.verdict for r in result.results}
    assert verdicts[("requests", "pypi")] is Verdict.ALLOW
    assert verdicts[("requests", "npm")] is Verdict.BLOCK

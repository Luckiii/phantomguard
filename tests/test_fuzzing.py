from pathlib import Path

import httpx

from phantomguard.db.known_hallucinations import find
from phantomguard.db.models import connect
from phantomguard.registry.npm import NpmClient
from phantomguard.registry.pypi import PyPiClient

from fuzzing.run_fuzz import CorpusEntry, load_corpus, run_fuzz


class FakeGenerator:
    def __init__(self, responses):
        self._responses = iter(responses)

    def generate(self, prompt: str) -> str:
        return next(self._responses)


def _pypi_all_404() -> PyPiClient:
    return PyPiClient(client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))))


def _npm_all_404() -> NpmClient:
    return NpmClient(client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))))


def _pypi_requests_exists() -> PyPiClient:
    def handler(request: httpx.Request) -> httpx.Response:
        name = request.url.path.split("/")[2]
        if name == "requests":
            return httpx.Response(200, json={"info": {"name": "requests"}, "releases": {}})
        return httpx.Response(404)

    return PyPiClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_run_fuzz_flags_nonexistent_import():
    corpus = [CorpusEntry(prompt="write a script", language="python")]
    generator = FakeGenerator(["import definitely_fake_pkg_xyz\n"])
    conn = connect(":memory:")

    report = run_fuzz(
        corpus,
        generator,
        _pypi_all_404(),
        _npm_all_404(),
        conn,
        model_name="claude-fable-5",
        repeats=1,
        observed_at="2026-08-20",
    )

    assert "definitely_fake_pkg_xyz" in report.flagged_names
    found = find(conn, "definitely_fake_pkg_xyz", ecosystem="pypi")
    assert found is not None
    assert found.observed_by_models == ["claude-fable-5"]


def test_run_fuzz_does_not_flag_real_package():
    corpus = [CorpusEntry(prompt="write a script", language="python")]
    generator = FakeGenerator(["import requests\n"])
    conn = connect(":memory:")

    report = run_fuzz(
        corpus,
        generator,
        _pypi_requests_exists(),
        _npm_all_404(),
        conn,
        model_name="claude-fable-5",
        repeats=1,
        observed_at="2026-08-20",
    )

    assert report.flagged_names == []
    assert find(conn, "requests", ecosystem="pypi") is None


def test_run_fuzz_repeats_generation_per_prompt():
    corpus = [CorpusEntry(prompt="write a script", language="python")]
    generator = FakeGenerator(["import os\n"] * 3)
    conn = connect(":memory:")

    report = run_fuzz(
        corpus,
        generator,
        _pypi_all_404(),
        _npm_all_404(),
        conn,
        model_name="claude-fable-5",
        repeats=3,
        observed_at="2026-08-20",
    )

    assert report.total_generations == 3


def test_run_fuzz_dispatches_js_prompts_to_npm():
    corpus = [CorpusEntry(prompt="write a react component", language="javascript")]
    generator = FakeGenerator(["import evilpkg from 'evilpkg';\n"])
    conn = connect(":memory:")

    report = run_fuzz(
        corpus,
        generator,
        _pypi_all_404(),
        _npm_all_404(),
        conn,
        model_name="claude-fable-5",
        repeats=1,
        observed_at="2026-08-20",
    )

    assert "evilpkg" in report.flagged_names
    assert find(conn, "evilpkg", ecosystem="npm") is not None
    assert find(conn, "evilpkg", ecosystem="pypi") is None


def test_run_fuzz_repeated_observation_increments_times_observed():
    corpus = [CorpusEntry(prompt="write a script", language="python")]
    generator = FakeGenerator(["import definitely_fake_pkg_xyz\n"] * 2)
    conn = connect(":memory:")

    run_fuzz(
        corpus,
        generator,
        _pypi_all_404(),
        _npm_all_404(),
        conn,
        model_name="claude-fable-5",
        repeats=2,
        observed_at="2026-08-20",
    )

    found = find(conn, "definitely_fake_pkg_xyz", ecosystem="pypi")
    assert found.times_observed == 2


def test_load_corpus_reads_json_file(tmp_path: Path):
    corpus_file = tmp_path / "prompts.json"
    corpus_file.write_text(
        '[{"prompt": "write a CSV parser", "language": "python"}]', encoding="utf-8"
    )

    corpus = load_corpus(corpus_file)

    assert len(corpus) == 1
    assert corpus[0].prompt == "write a CSV parser"
    assert corpus[0].language == "python"

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from phantomguard.db.known_hallucinations import ensure_seeded, record_observation
from phantomguard.db.models import connect
from phantomguard.extractor import extract_imports
from phantomguard.extractor_js import extract_js_imports
from phantomguard.registry.npm import NpmClient
from phantomguard.registry.pypi import PyPiClient
from fuzzing.generator import AnthropicCodeGenerator, CodeGenerator

DEFAULT_CORPUS_PATH = Path(__file__).parent / "corpus" / "prompts.json"


class CorpusEntry(BaseModel):
    prompt: str
    language: str = "python"


class FuzzReport(BaseModel):
    total_generations: int
    flagged_names: list[str]


def load_corpus(path: Path = DEFAULT_CORPUS_PATH) -> list[CorpusEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [CorpusEntry(**entry) for entry in raw]


def run_fuzz(
    corpus: list[CorpusEntry],
    generator: CodeGenerator,
    pypi_client: PyPiClient,
    npm_client: NpmClient,
    conn: sqlite3.Connection,
    model_name: str,
    repeats: int = 5,
    observed_at: str | None = None,
) -> FuzzReport:
    observed_at = observed_at or datetime.now(timezone.utc).date().isoformat()
    clients = {"pypi": pypi_client, "npm": npm_client}

    total_generations = 0
    flagged_names: list[str] = []

    for entry in corpus:
        for _ in range(repeats):
            code = generator.generate(entry.prompt)
            total_generations += 1

            if entry.language == "python":
                imports = extract_imports(code, filename="<fuzz>")
            else:
                imports = extract_js_imports(code, filename="<fuzz>")

            for imported in imports:
                client = clients[imported.ecosystem]
                lookup = client.check_exists(imported.module)
                if lookup.exists is False:
                    record_observation(
                        conn,
                        imported.module,
                        ecosystem=imported.ecosystem,
                        model=model_name,
                        observed_at=observed_at,
                    )
                    flagged_names.append(imported.module)

    return FuzzReport(total_generations=total_generations, flagged_names=flagged_names)


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "ANTHROPIC_API_KEY is not set. The self-fuzz pipeline is a maintainer-run "
            "job that calls the Anthropic API and incurs real cost — set the key "
            "explicitly to confirm you intend to run it."
        )

    corpus = load_corpus()
    generator = AnthropicCodeGenerator()
    pypi_client = PyPiClient()
    npm_client = NpmClient()
    conn = connect()
    ensure_seeded(conn)

    try:
        report = run_fuzz(corpus, generator, pypi_client, npm_client, conn, model_name=generator.model)
    finally:
        pypi_client.close()
        npm_client.close()
        conn.close()

    print(f"Generated {report.total_generations} samples; flagged {len(report.flagged_names)} names:")
    for name in report.flagged_names:
        print(f"  - {name}")


if __name__ == "__main__":
    main()

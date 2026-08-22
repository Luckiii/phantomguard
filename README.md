# PhantomGuard

Catches AI-hallucinated ("slopsquatted") package names before they get installed.

**Status: M4/M5 — Self-fuzz pipeline + MCP server.** `phantomguard scan <path> [<path> ...]`
extracts Python and JS/TS imports, checks each against the PyPI or npm
registry (as appropriate) and a local known-hallucination database, scores
the result, and prints `ALLOW` / `WARN` / `BLOCK` with a reason. The
known-hallucination database can now be grown over time by a maintainer-run
fuzz pipeline, and the same checks are exposed as an MCP tool for
MCP-compatible agents (Cursor, Windsurf, etc.). M3 (LLM necessity-rationale
layer) was deliberately skipped — see "Scope" below.

## Install

```
pip install phantomguard-cli
```

That's it — no API key, no config. This installs the `phantomguard` command
(the PyPI *distribution name* is `phantomguard-cli`, since plain
`phantomguard` collided with PyPI's name-similarity check; the command you
actually run is still `phantomguard`).

<details>
<summary>Contributing to PhantomGuard itself (dev install)</summary>

```
uv venv .venv
uv pip install -e ".[dev]" -p .venv
```

(or `pip install -e ".[dev]"` in any virtualenv)

Two extras add optional, maintainer-only capability, neither needed for
normal use:

- `.[fuzz]` — installs the `anthropic` SDK, needed only to run the self-fuzz
  pipeline (see below).
- `.[mcp]` — installs the `mcp` SDK, needed only to run the MCP server (see
  below).

</details>

## Usage

```
phantomguard scan ./path/to/project
phantomguard scan ./path/to/project --explain
phantomguard scan file1.py file2.js file3.ts   # multiple files/dirs at once
```

Python (`.py`) files are checked against PyPI; JS/TS (`.js`/`.jsx`/`.mjs`/`.cjs`/`.ts`/`.tsx`)
files are checked against npm. Each result line shows which registry it was checked against:

```
ALLOW [pypi] requests: 'requests' found on PyPI, no risk signals fired
ALLOW [npm] react: 'react' found on npm, no risk signals fired
BLOCK [npm] definitely-not-a-real-npm-package-xyz123: 'definitely-not-a-real-npm-package-xyz123' not found on npm (score 100)
```

With `--explain`, each line is followed by the individual signals that fired
and their point contribution:

```
BLOCK [pypi] definitely_not_a_real_package_xyz123: 'definitely_not_a_real_package_xyz123' not found on PyPI (score 100)
    - not_in_registry (+100): 'definitely_not_a_real_package_xyz123' not found on PyPI
```

Exit code is `1` if any import is `BLOCK`ed, otherwise `0`.

## Integrations

**pre-commit** — add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/Luckiii/phantomguard
    rev: v0.1.1
    hooks:
      - id: phantomguard
```

**GitHub Actions** — add a step using the composite action in this repo:

```yaml
- uses: Luckiii/phantomguard@v0.1.1
  with:
    path: .
    explain: "false"
```

Both wrap the same CLI, so behavior is identical to running `phantomguard scan`
locally. Neither requires any API key — see "Scope" below.

## Risk scoring (M1)

```
score = 0
if not exists_in_registry:      score += 100
if matches_known_hallucination: score += 80
if age_days < 7:                score += 40
elif age_days < 30:             score += 20

verdict = BLOCK if score >= 70 else WARN if score >= 30 else ALLOW
```

This is a subset of the full formula in `docs/phantomguard-mvp-proposal.md` §8.
Signals requiring a new dependency or external API — download counts,
maintainer counts, install-script inspection — are still deferred. Both
PyPI's and npm's JSON APIs give us existence and release history for their
respective ecosystems, which is what this scoring is based on. Cross-registry
confusion (a name that exists on one registry but not the other) is not yet
implemented as its own signal.

The known-hallucination database is a local SQLite file (default
`~/.phantomguard/known_hallucinations.db`, schema in
`phantomguard/db/models.py`), auto-created and seeded on first run from
`phantomguard/db/known_hallucinations.py`. It currently has 3 seed entries
from the public incidents named in the proposal doc; two of those
(`unused-imports`, `huggingface-cli`) have inferred rather than independently
verified metadata — see the `notes` field on each entry.

## Self-fuzz pipeline (M4)

`fuzzing/run_fuzz.py` is a maintainer-run job, not something end users ever
run: it feeds a corpus of coding prompts (`fuzzing/corpus/prompts.json`) to
an LLM (Anthropic), extracts the imports from each generated sample, checks
them against PyPI/npm, and logs any nonexistent name into the
known-hallucination database with `times_observed` and `observed_by_models`
tracking. The pipeline logic (`run_fuzz`) is fully unit-tested with a fake
generator and mocked registries — no network or API cost in `pytest`.

Running it for real requires the `fuzz` extra and an API key:

```
uv pip install -e ".[fuzz]" -p .venv
ANTHROPIC_API_KEY=sk-... .venv/Scripts/python.exe -m fuzzing.run_fuzz
```

This has **not been run yet** — no real fuzz campaign has executed, so the
seed database still only contains the 3 manually-sourced incidents from M1.
Running it for real costs real API money; do that deliberately, not as a
side effect of installing the package.

## MCP server (M5)

`phantomguard-mcp` exposes a single tool, `check_dependency(name, ecosystem)`,
returning the same ALLOW/WARN/BLOCK verdict as the CLI, for any MCP-compatible
client (Cursor, Windsurf, etc.) to call during planning. Requires the `mcp`
extra:

```
uv pip install -e ".[mcp]" -p .venv
phantomguard-mcp
```

Add it to an MCP client's config by pointing at the `phantomguard-mcp`
command (stdio transport). No demo GIF or MCP-directory submission yet —
those are manual follow-ups once the package is published.

## Try it

```
phantomguard scan ./tests/fixtures/hallucinated_example.py   # -> BLOCK
phantomguard scan ./tests/fixtures/clean_example.py           # -> ALLOW
phantomguard scan ./tests/fixtures/hallucinated_example.js    # -> BLOCK (npm)
phantomguard scan ./tests/fixtures/clean_example.js           # -> ALLOW (npm)
```

## Tests

```
pytest
```

All tests run against a mocked PyPI registry (`httpx.MockTransport`) and an
in-memory SQLite database — no live network calls or filesystem state in CI.

## Scope

Built so far: M0 (registry-checker CLI), M1 (risk scoring + seeded
hallucination DB), M2 (npm/JS support, pre-commit hook, GitHub Action), M4
(self-fuzz pipeline — built and tested, not yet run for real), and M5 (MCP
server core — built and tested; packaging polish like a demo GIF and MCP
directory submission still pending).

**M3 (LLM-based necessity/rationale layer) was deliberately skipped**, not
just deferred. The deterministic ALLOW/WARN/BLOCK from M0–M2 is the actual
security mechanism; M3 was scoped as advisory-only text that never changes
the verdict, so it added complexity and an API-key dependency without adding
real detection. If a "why is this risky" explanation is wanted later for
Claude Code users specifically, the better approach is a `SKILL.md` that lets
the already-running Claude reason about a WARN inline — using the
subscription the user already has, at zero extra cost — rather than a
separate LLM call from the CLI.

The core tool (M0/M1/M2) has no API-key requirement and never will, since
it's meant to be installed by anyone as a plugin/hook/pre-commit check at
zero cost. M4's fuzz pipeline and M5's MCP server both need optional extras
(`anthropic`, `mcp`) that only the maintainer or an MCP-client user installs,
never the average CLI/hook/pre-commit user. M6 (auth analyzer) is explicitly
out of scope — see `CLAUDE.md` and `docs/phantomguard-mvp-proposal.md` for
the full roadmap.

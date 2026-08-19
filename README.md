# PhantomGuard

Catches AI-hallucinated ("slopsquatted") package names before they get installed.

**Status: M2 — Multi-ecosystem + integrations.** `phantomguard scan <path> [<path> ...]`
extracts Python and JS/TS imports, checks each against the PyPI or npm
registry (as appropriate) and a local known-hallucination database, scores
the result, and prints `ALLOW` / `WARN` / `BLOCK` with a reason.

## Install

```
uv venv .venv
uv pip install -e ".[dev]" -p .venv
```

(or `pip install -e ".[dev]"` in any virtualenv)

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
  - repo: https://github.com/<yourname>/phantomguard
    rev: v0.1.0
    hooks:
      - id: phantomguard
```

**GitHub Actions** — add a step using the composite action in this repo:

```yaml
- uses: <yourname>/phantomguard@v0.1.0
  with:
    path: .
    explain: "false"
```

Both wrap the same CLI (`pip install phantomguard` under the hood), so
behavior is identical to running `phantomguard scan` locally. Neither
requires any API key — see "Scope" below.

> Not yet published to PyPI, so `pip install phantomguard` in the action
> doesn't resolve yet — both integrations are wired and testable in principle,
> but won't work end-to-end for outside users until a release is published.

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
hallucination DB), and M2 (npm/JS support, pre-commit hook, GitHub Action).

Not yet built: necessity checker (M3), self-fuzz pipeline (M4), MCP server
(M5). M3's LLM-based rationale layer will be **strictly opt-in** — it only
runs if an `ANTHROPIC_API_KEY` is set, and its absence never changes the
deterministic ALLOW/WARN/BLOCK verdict. The core tool (everything above) has
no API-key requirement and never will, since it's meant to be installed by
anyone as a plugin/hook/pre-commit check at zero cost. M6 (auth analyzer) is
explicitly out of scope for now — see `CLAUDE.md` and
`docs/phantomguard-mvp-proposal.md` for the full roadmap.

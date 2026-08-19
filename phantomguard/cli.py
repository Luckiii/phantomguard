from __future__ import annotations

import sqlite3
from pathlib import Path

import typer

from phantomguard.db.known_hallucinations import ensure_seeded
from phantomguard.db.models import connect
from phantomguard.registry.npm import NpmClient
from phantomguard.registry.pypi import PyPiClient
from phantomguard.scoring import run_scan

app = typer.Typer()


@app.callback()
def main() -> None:
    """PhantomGuard - catch AI-hallucinated package names before they get installed."""


def _make_pypi_client() -> PyPiClient:
    return PyPiClient()


def _make_npm_client() -> NpmClient:
    return NpmClient()


def _make_db_connection() -> sqlite3.Connection:
    conn = connect()
    ensure_seeded(conn)
    return conn


@app.command()
def scan(
    paths: list[Path] = typer.Argument(..., exists=True, help="Files or directories to scan"),
    explain: bool = typer.Option(
        False, "--explain", help="Show which risk signals fired for each import"
    ),
) -> None:
    pypi_client = _make_pypi_client()
    npm_client = _make_npm_client()
    conn = _make_db_connection()
    try:
        has_block = False
        for path in paths:
            result = run_scan(path, pypi_client, npm_client, conn)
            has_block = has_block or result.has_block
            for item in result.results:
                typer.echo(f"{item.verdict.value} [{item.ecosystem}] {item.name}: {item.reason}")
                if explain:
                    if item.signals:
                        for signal in item.signals:
                            typer.echo(f"    - {signal.name} (+{signal.points}): {signal.detail}")
                    else:
                        typer.echo("    - no risk signals fired")
    finally:
        pypi_client.close()
        npm_client.close()
        conn.close()

    if has_block:
        raise typer.Exit(code=1)

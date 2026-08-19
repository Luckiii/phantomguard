from __future__ import annotations

import sqlite3

from mcp.server.mcpserver import MCPServer

from phantomguard.db.known_hallucinations import ensure_seeded, find
from phantomguard.db.models import connect
from phantomguard.registry.npm import NpmClient
from phantomguard.registry.pypi import PyPiClient
from phantomguard.scoring import compute_signals, decide_verdict

server = MCPServer("phantomguard")


def check_dependency_core(
    name: str,
    ecosystem: str | None,
    pypi_client: PyPiClient,
    npm_client: NpmClient,
    conn: sqlite3.Connection,
) -> dict:
    ecosystem = ecosystem or "pypi"
    client = pypi_client if ecosystem == "pypi" else npm_client

    lookup = client.check_exists(name)
    known = find(conn, name, ecosystem=ecosystem)
    signals = compute_signals(lookup, known)
    verdict, reason = decide_verdict(lookup, signals)

    return {
        "name": name,
        "ecosystem": ecosystem,
        "verdict": verdict.value,
        "reason": reason,
        "score": sum(s.points for s in signals),
    }


@server.tool()
def check_dependency(name: str, ecosystem: str = "pypi") -> dict:
    """Check whether a package name is real/registered or a likely AI-hallucinated
    (slopsquatted) name, on PyPI (ecosystem="pypi") or npm (ecosystem="npm")."""
    pypi_client = PyPiClient()
    npm_client = NpmClient()
    conn = connect()
    ensure_seeded(conn)
    try:
        return check_dependency_core(name, ecosystem, pypi_client, npm_client, conn)
    finally:
        pypi_client.close()
        npm_client.close()
        conn.close()


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()

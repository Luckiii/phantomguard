from __future__ import annotations

import re
from pathlib import Path

from phantomguard.imports import ImportedName

_SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules", "dist", "build"}
_JS_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}

_NODE_BUILTINS = {
    "assert", "async_hooks", "buffer", "child_process", "cluster", "console",
    "constants", "crypto", "dgram", "diagnostics_channel", "dns", "domain",
    "events", "fs", "http", "http2", "https", "inspector", "module", "net",
    "os", "path", "perf_hooks", "process", "punycode", "querystring",
    "readline", "repl", "stream", "string_decoder", "sys", "timers", "tls",
    "trace_events", "tty", "url", "util", "v8", "vm", "wasi", "worker_threads",
    "zlib", "assert/strict",
}

_IMPORT_SPEC_PATTERN = re.compile(
    r"""require\(\s*['"]([^'"]+)['"]\s*\)"""
    r"""|from\s+['"]([^'"]+)['"]"""
    r"""|^\s*import\s+['"]([^'"]+)['"]""",
    re.MULTILINE,
)


def _top_level_package(spec: str) -> str:
    parts = spec.split("/")
    if spec.startswith("@") and len(parts) >= 2:
        return "/".join(parts[:2])
    return parts[0]


def _is_relative_or_absolute_path(spec: str) -> bool:
    return spec.startswith(".") or spec.startswith("/")


def _is_node_builtin(spec: str) -> bool:
    name = spec[5:] if spec.startswith("node:") else spec
    return name in _NODE_BUILTINS


def extract_js_imports(source: str, filename: str = "<string>") -> list[ImportedName]:
    results: list[ImportedName] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        for match in _IMPORT_SPEC_PATTERN.finditer(line):
            spec = next(g for g in match.groups() if g is not None)
            if _is_relative_or_absolute_path(spec) or _is_node_builtin(spec):
                continue
            results.append(
                ImportedName(
                    module=_top_level_package(spec),
                    raw=spec,
                    lineno=lineno,
                    source_file=Path(filename),
                    ecosystem="npm",
                )
            )
    return results


def extract_js_imports_from_file(path: Path) -> list[ImportedName]:
    return extract_js_imports(path.read_text(encoding="utf-8"), filename=str(path))


def extract_js_imports_from_path(path: Path) -> list[ImportedName]:
    if path.is_file():
        return extract_js_imports_from_file(path)

    results: list[ImportedName] = []
    for suffix in _JS_SUFFIXES:
        for js_file in path.rglob(f"*{suffix}"):
            if _SKIP_DIRS & set(js_file.parts):
                continue
            results.extend(extract_js_imports_from_file(js_file))
    return results

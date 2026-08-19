from __future__ import annotations

import ast
import sys
from pathlib import Path

from phantomguard.imports import ImportedName

_SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", "node_modules"}


def _top_level(dotted: str) -> str:
    return dotted.split(".", 1)[0]


def extract_imports(source: str, filename: str = "<string>") -> list[ImportedName]:
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return []

    results: list[ImportedName] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = _top_level(alias.name)
                if top in sys.stdlib_module_names:
                    continue
                results.append(
                    ImportedName(
                        module=top,
                        raw=alias.name,
                        lineno=node.lineno,
                        source_file=Path(filename),
                        ecosystem="pypi",
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0 or node.module is None:
                continue
            top = _top_level(node.module)
            if top in sys.stdlib_module_names:
                continue
            results.append(
                ImportedName(
                    module=top,
                    raw=node.module,
                    lineno=node.lineno,
                    source_file=Path(filename),
                    ecosystem="pypi",
                )
            )
    return results


def extract_imports_from_file(path: Path) -> list[ImportedName]:
    return extract_imports(path.read_text(encoding="utf-8"), filename=str(path))


def extract_imports_from_path(path: Path) -> list[ImportedName]:
    if path.is_file():
        return extract_imports_from_file(path)

    results: list[ImportedName] = []
    for py_file in path.rglob("*.py"):
        if _SKIP_DIRS & set(py_file.parts):
            continue
        results.extend(extract_imports_from_file(py_file))
    return results

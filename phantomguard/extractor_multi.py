from __future__ import annotations

from pathlib import Path

from phantomguard.extractor import _SKIP_DIRS as _PY_SKIP_DIRS
from phantomguard.extractor import extract_imports_from_file as _extract_python_file
from phantomguard.extractor_js import _JS_SUFFIXES
from phantomguard.extractor_js import _SKIP_DIRS as _JS_SKIP_DIRS
from phantomguard.extractor_js import extract_js_imports_from_file as _extract_js_file
from phantomguard.imports import ImportedName

_SKIP_DIRS = _PY_SKIP_DIRS | _JS_SKIP_DIRS


def _extract_file(path: Path) -> list[ImportedName]:
    if path.suffix == ".py":
        return _extract_python_file(path)
    if path.suffix in _JS_SUFFIXES:
        return _extract_js_file(path)
    return []


def extract_all_imports_from_path(path: Path) -> list[ImportedName]:
    if path.is_file():
        return _extract_file(path)

    results: list[ImportedName] = []
    for file in path.rglob("*"):
        if not file.is_file():
            continue
        if _SKIP_DIRS & set(file.parts):
            continue
        results.extend(_extract_file(file))
    return results

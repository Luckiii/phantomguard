from pathlib import Path

import pytest

from phantomguard.extractor import extract_imports, extract_imports_from_path


def names(source: str) -> list[str]:
    return [i.module for i in extract_imports(source)]


def test_filters_stdlib_import():
    assert names("import os\n") == []


def test_filters_stdlib_submodule_import():
    assert names("import os.path\n") == []


def test_extracts_top_level_name_for_plain_import():
    assert names("import requests\n") == ["requests"]


def test_extracts_top_level_name_for_dotted_third_party_import():
    assert names("import requests.exceptions\n") == ["requests"]


def test_extracts_from_import():
    assert names("from foo import bar\n") == ["foo"]


def test_skips_relative_from_import():
    assert names("from . import x\n") == []


def test_skips_relative_dotted_from_import():
    assert names("from .relative import y\n") == []


def test_extracts_multiple_names_from_single_import_statement():
    assert sorted(names("import a.b, c.d\n")) == ["a", "c"]


def test_syntax_error_source_returns_empty_without_raising():
    assert extract_imports("def broken(:\n") == []


def test_extract_imports_from_path_walks_directory(tmp_path: Path):
    (tmp_path / "a.py").write_text("import requests\n")
    (tmp_path / "b.py").write_text("import os\nimport numpy\n")
    found = sorted(i.module for i in extract_imports_from_path(tmp_path))
    assert found == ["numpy", "requests"]


def test_extract_imports_from_path_skips_venv_dirs(tmp_path: Path):
    venv_dir = tmp_path / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "installed.py").write_text("import some_vendored_thing\n")
    (tmp_path / "real.py").write_text("import requests\n")
    found = sorted(i.module for i in extract_imports_from_path(tmp_path))
    assert found == ["requests"]

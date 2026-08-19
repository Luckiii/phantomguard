from pathlib import Path

from phantomguard.extractor_multi import extract_all_imports_from_path


def test_dispatches_python_file_by_extension(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("import requests\n")
    found = extract_all_imports_from_path(f)
    assert [(i.module, i.ecosystem) for i in found] == [("requests", "pypi")]


def test_dispatches_js_file_by_extension(tmp_path: Path):
    f = tmp_path / "a.js"
    f.write_text("import react from 'react';\n")
    found = extract_all_imports_from_path(f)
    assert [(i.module, i.ecosystem) for i in found] == [("react", "npm")]


def test_dispatches_mixed_directory(tmp_path: Path):
    (tmp_path / "a.py").write_text("import requests\n")
    (tmp_path / "b.js").write_text("import react from 'react';\n")
    found = extract_all_imports_from_path(tmp_path)
    pairs = sorted((i.module, i.ecosystem) for i in found)
    assert pairs == [("react", "npm"), ("requests", "pypi")]


def test_unrecognized_extension_is_ignored(tmp_path: Path):
    (tmp_path / "notes.txt").write_text("import requests\n")
    found = extract_all_imports_from_path(tmp_path)
    assert found == []

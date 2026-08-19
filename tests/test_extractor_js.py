from pathlib import Path

from phantomguard.extractor_js import extract_js_imports, extract_js_imports_from_path


def names(source: str) -> list[str]:
    return [i.module for i in extract_js_imports(source)]


def test_extracts_require():
    assert names("const x = require('lodash');\n") == ["lodash"]


def test_extracts_require_double_quotes():
    assert names('const x = require("lodash");\n') == ["lodash"]


def test_extracts_es_import_from():
    assert names("import React from 'react';\n") == ["react"]


def test_extracts_bare_import():
    assert names("import 'some-polyfill';\n") == ["some-polyfill"]


def test_extracts_named_import():
    assert names("import { useState } from 'react';\n") == ["react"]


def test_resolves_submodule_to_top_level_package():
    assert names("import debounce from 'lodash/debounce';\n") == ["lodash"]


def test_resolves_scoped_package_submodule_to_scope_plus_name():
    assert names("import { Component } from '@angular/core/testing';\n") == ["@angular/core"]


def test_skips_relative_imports():
    assert names("import x from './local-module';\n") == []
    assert names("import y from '../parent-module';\n") == []


def test_skips_node_builtins():
    assert names("import fs from 'fs';\nconst path = require('path');\n") == []


def test_skips_node_prefixed_builtins():
    assert names("import fs from 'node:fs';\n") == []


def test_extracts_multiple_distinct_imports():
    source = "import React from 'react';\nconst axios = require('axios');\n"
    assert sorted(names(source)) == ["axios", "react"]


def test_marks_ecosystem_as_npm():
    imports = extract_js_imports("import React from 'react';\n")
    assert imports[0].ecosystem == "npm"


def test_extract_js_imports_from_path_walks_directory(tmp_path: Path):
    (tmp_path / "a.js").write_text("import React from 'react';\n")
    (tmp_path / "b.ts").write_text("import axios from 'axios';\n")
    (tmp_path / "c.py").write_text("import requests\n")  # not a JS file, ignored
    found = sorted(i.module for i in extract_js_imports_from_path(tmp_path))
    assert found == ["axios", "react"]


def test_extract_js_imports_from_path_skips_node_modules(tmp_path: Path):
    nm = tmp_path / "node_modules" / "somepkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("import fakevendored from 'fakevendored';\n")
    (tmp_path / "real.js").write_text("import react from 'react';\n")
    found = sorted(i.module for i in extract_js_imports_from_path(tmp_path))
    assert found == ["react"]

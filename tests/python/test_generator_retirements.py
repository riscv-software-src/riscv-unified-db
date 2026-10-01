# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
from ruamel.yaml import YAML

ROOT = Path(__file__).parents[2]
RETIRED_JOBS = {
    "regress-ext-explorer",
    "regress-gen-isa-manual",
    "regress-gen-instruction-appendix",
    "regress-cfg-manual",
    "regress-gen-profile",
    "regress-profile-extensions",
    "build-isa-explorer-csr",
    "build-isa-explorer-ext",
    "build-isa-explorer-inst",
    "build-isa-explorer-spreadsheet",
    "build-html-isa-manual",
    "build-html-cfg-isa-manual",
    "build-instruction-appendix",
    "build-profile",
}


@pytest.mark.parametrize("command", ["manual", "isa-explorer"])
def test_retired_generator_is_rejected_before_runtime_setup(command: str, tmp_path: Path) -> None:
    result = subprocess.run(
        ["bash", str(ROOT / "bin/generate"), command],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert f"Invalid subcommand: {command}" in result.stdout
    assert not result.stderr


def test_retired_jobs_are_absent_from_registry_and_generated_workflow() -> None:
    yaml = YAML(typ="safe")
    definitions = yaml.load(ROOT / "tools/test/regress-tests.yaml")["tests"]
    workflow = yaml.load(ROOT / ".github/workflows/regress.yml")["jobs"]
    assert not RETIRED_JOBS.intersection(definitions)
    assert not RETIRED_JOBS.intersection(workflow)
    assert not RETIRED_JOBS.intersection(workflow["regress-complete"]["needs"])
    assert {
        "regress-gen-ext-pdf",
        "regress-gen-c-header",
        "regress-gen-sverilog",
        "regress-gen-go",
        "regress-cpp-unit",
        "regress-schema-docs",
        "regress-python-config-headers",
        "regress-python-profile-configs",
    } <= definitions.keys()


def test_pages_downloads_only_retained_artifacts() -> None:
    yaml = YAML(typ="safe")
    steps = yaml.load(ROOT / ".github/workflows/pages.yml")["jobs"]["pages"]["steps"]
    downloads = {
        step["with"]["name"]
        for step in steps
        if step.get("uses", "").startswith("actions/download-artifact@")
    }
    assert downloads == {"reuse-manifest", "resolved-spec", "udb-api", "idl-doc", "docs-site"}


def test_retired_aliases_and_editor_launches_are_removed() -> None:
    rakefile = (ROOT / "Rakefile").read_text(encoding="utf-8")
    launches = (ROOT / ".vscode/launch.json").read_text(encoding="utf-8")
    for retired in (
        "isa_explorer",
        "html_manual",
        "gen/profile/pdf",
        "profile_release_pdf",
        "portfolios",
    ):
        assert retired not in rakefile
        assert retired not in launches


def test_retired_workbook_dependencies_are_absent_from_typing_inputs() -> None:
    requires = (ROOT / "sorbet/tapioca/require.rb").read_text(encoding="utf-8")
    lockfile = (ROOT / "Gemfile.lock").read_text(encoding="utf-8")
    for gem in ("write_xlsx", "nkf"):
        assert f'require "{gem}"' not in requires
        assert f"    {gem} (" not in lockfile
        assert not list((ROOT / "sorbet/rbi/gems").glob(f"{gem}@*.rbi"))


def test_site_showcase_does_not_advertise_retired_generators() -> None:
    showcase = (ROOT / "doc/src/pages/index.tsx").read_text(encoding="utf-8")
    for retired in ("prm-pdf", "isa-explorer", "manual generation"):
        assert retired not in showcase
    assert "Extension documentation and PDF generation" in showcase


def test_landing_page_retains_data_and_docs_without_retired_product_links(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "retirement_pages_index", ROOT / "tools/scripts/gen_pages_index.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    (schema_dir / "index.json").write_text(
        json.dumps({"schemas": {"inst_schema.json": ["v0.1"]}}), encoding="utf-8"
    )
    output = module.render_index(tmp_path, ROOT / "tools/scripts/pages.html.template")
    for retained in (
        "/resolved_spec/index.yaml",
        "/resolved_spec/resolved_spec.tar.gz",
        "/docs-preview/",
        "/htmls/udb_api_doc/index.html",
        "/idl.html",
        "/schemas/inst_schema.json/v0.1/inst_schema.json",
    ):
        assert retained in output
    for retired in ("/manual/html/", "/isa_explorer/", "/pdfs/", "/example_cfg/html/"):
        assert retired not in output
    assert "@@" not in output

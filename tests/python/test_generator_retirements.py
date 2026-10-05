# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

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


def test_retired_jobs_are_absent_from_workflow() -> None:
    yaml = YAML(typ="safe")
    workflow = yaml.load(ROOT / ".github/workflows/regress.yml")["jobs"]
    assert not RETIRED_JOBS.intersection(workflow)
    assert not RETIRED_JOBS.intersection(workflow["regress-complete"]["needs"])


def test_pages_downloads_only_retained_artifacts() -> None:
    yaml = YAML(typ="safe")
    steps = yaml.load(ROOT / ".github/workflows/pages.yml")["jobs"]["pages"]["steps"]
    downloads = {
        step["with"]["name"]
        for step in steps
        if step.get("uses", "").startswith("actions/download-artifact@")
    }
    assert downloads == {"reuse-manifest", "resolved-spec", "docs-site"}


def test_retired_aliases_and_editor_launches_are_removed() -> None:
    assert not (ROOT / "Rakefile").exists()
    launches = (ROOT / ".vscode/launch.json").read_text(encoding="utf-8")
    for retired in (
        "isa_explorer",
        "html_manual",
        "gen/profile/pdf",
        "profile_release_pdf",
        "portfolios",
    ):
        assert retired not in launches


def test_retired_ruby_typing_inputs_are_absent() -> None:
    assert not any(path.is_file() for path in (ROOT / "sorbet").rglob("*"))
    assert not (ROOT / "Gemfile.lock").exists()


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

# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Shared fixtures and execution-layer policy for the Python test suite."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from functools import cache
from pathlib import Path

import pytest

from udb import Configuration, Database
from udb.schema import SchemaStore

ROOT = Path(__file__).parents[1]

SLOW_TESTS = {
    "tests/python/test_config_headers.py": {"test_generated_sources_compile_and_lint"},
    "tests/python/test_configured_prose_oracle.py": {
        "test_all_frozen_scalar_outputs_and_error_outcomes",
        "test_all_native_source_outputs_and_error_outcomes",
        "test_cache_boundary_corpus_kills_review_mutations",
        "test_corrections_are_precise_and_independently_reproduced",
        "test_exact_source_inventory",
        "test_extended_whitespace_is_exact_raw_tilt",
        "test_from_architecture_is_the_documented_declaration_projection",
        "test_independent_valid_mc100_witness_separates_defects_from_synthetic_shapes",
        "test_original_raw_archive_has_not_been_rewritten",
        "test_raw_parity_is_separate_from_substitutions_and_errors",
        "test_real_database_input_projection_matches_ruby",
        "test_real_structured_exception_name_consumer",
        "test_supplemental_real_ruby_scalar_captures",
        "test_supplemental_native_source_outputs",
        "test_templated_names_are_selected_from_database_not_rendered_captures",
    },
    "tests/python/test_extension_pdf.py": {
        "test_actual_official_complete_zba_pdf_compares_native_source",
        "test_actual_official_pdf_text_metadata_and_rendered_page",
        "test_actual_official_qc_csr_theme_and_declared_float_include",
    },
    "tests/python/test_generic_codegen_consumers.py": {
        "test_c_all_instruction_csr_cause_consumer",
        "test_go_complete_real_obj_package_adaptor",
        "test_sv_complete_decode_package_lints",
    },
    "tests/python/test_idl_architecture_real.py": {
        "test_actual_architecture_bodies_and_unavailable_coverage"
    },
    "tests/python/test_idl_condition_runtime.py": {
        "test_real_runtime_architecture_is_valid_without_idl_deferrals"
    },
    "tests/python/test_idl_conditions.py": {"test_live_database_translation_matches_frozen_ruby"},
    "tests/python/test_idl_environment.py": {
        "test_idl_environment_builds_for_real_configs",
        "test_rv32_sxlen_invariant_prohibits_64_bit_supervisor_extensions",
    },
    "tests/python/test_idl_environment_fixes.py": {
        "test_real_bootstrap_has_genuine_encoding_size_and_resource_safe_symbolic_arrays",
        "test_real_csr_structural_regressions",
    },
    "tests/python/test_idl_passes_real.py": {"test_real_database_passes_match_ruby"},
    "tests/python/test_layouts.py": {
        "test_all_layouts_reproduce_every_tracked_output_byte_for_byte",
        "test_cli_check_reports_drift_without_rewriting",
    },
    "tests/python/test_qc_layouts.py": {
        "test_every_qc_output_matches_genuine_native_bytes_and_semantics",
        "test_qc_plan_regenerates_only_owned_files_and_check_never_writes",
        "test_qc_bundled_resources_generate_without_any_repository_source",
        "test_qc_and_standard_collections_preserve_all_standard_bytes",
        "test_qc_tracked_outputs_are_exactly_the_current_layout_plan",
        "test_readonly_qc_outputs_are_excluded_from_eof_rewriting",
        "test_every_qc_output_validates_against_unchanged_current_schema",
    },
}

PACKAGE_FILES = {
    "tests/python/test_distribution.py",
    "tests/python/test_qc_layout_packaging.py",
}

IDL_CONFIG_TEST = "tests/python/test_idl_architecture_real.py"
IDL_CONFIGURATIONS = ("_", "rv32", "rv64", "qc_iu")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-goldens",
        action="store_true",
        help="replace reviewed golden files with current Python output",
    )
    parser.addoption(
        "--config",
        choices=IDL_CONFIGURATIONS,
        help="select one real-spec IDL configuration",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    require_tools = os.environ.get("UDB_REQUIRE_TOOLS") == "1"
    selected_config = config.getoption("--config")
    deselected: list[pytest.Item] = []
    for item in items:
        relative = Path(str(item.path)).resolve().relative_to(ROOT).as_posix()
        if relative == IDL_CONFIG_TEST and selected_config is not None:
            callspec = getattr(item, "callspec", None)
            if callspec is not None and callspec.params.get("name") != selected_config:
                deselected.append(item)
                continue
        original_name = getattr(item, "originalname", item.name.split("[", 1)[0])
        if original_name in SLOW_TESTS.get(relative, ()):
            item.add_marker(pytest.mark.slow)
        if relative in PACKAGE_FILES:
            item.add_marker(pytest.mark.package)
        for marker in item.iter_markers("needs_tool"):
            tool = str(marker.args[0])
            if shutil.which(tool) is not None:
                continue
            message = f"required external tool is unavailable: {tool}"
            if require_tools:
                raise pytest.UsageError(message)
            item.add_marker(pytest.mark.skip(reason=message))
    if deselected:
        items[:] = [item for item in items if item not in deselected]
        config.hook.pytest_deselected(items=deselected)


@pytest.fixture(scope="session")
def database() -> Database:
    return Database.bundled()


@pytest.fixture(scope="session")
def resolved(database: Database):
    return database.resolve()


@pytest.fixture(scope="session")
def configured(resolved) -> Callable[[str], object]:
    @cache
    def load(name: str):
        configuration = (
            Configuration.from_file(ROOT / "cfgs/mc100-32-full-example.yaml")
            if name == "full"
            else Configuration.builtin(name)
        )
        return resolved.configure(configuration)

    return load


@pytest.fixture(scope="session")
def configured_custom() -> Callable[[str], object]:
    @cache
    def load(name: str):
        configuration = Configuration.from_file(ROOT / "cfgs" / f"{name}.yaml")
        if configuration.overlay is None:
            database = Database.bundled().resolve()
        else:
            database = Database.bundled().resolve(
                overlays=(ROOT / "spec/custom/isa" / configuration.overlay,)
            )
        return database.configure(configuration)

    return load


@pytest.fixture(scope="session")
def schema_store() -> SchemaStore:
    root = Database.bundled().schemas_root
    assert root is not None
    return SchemaStore(root)


@pytest.fixture(scope="session")
def golden(request: pytest.FixtureRequest):
    update = request.config.getoption("--update-goldens")

    def compare(path: Path, content: bytes | str) -> None:
        payload = content.encode() if isinstance(content, str) else content
        if update:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        assert path.read_bytes() == payload

    return compare

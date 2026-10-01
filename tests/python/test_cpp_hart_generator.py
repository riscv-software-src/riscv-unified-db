# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from capture_cpp_hart_metadata import interface

from udb import Configuration, Database
from udb.cpp_hart import (
    CONFIG_ARTIFACTS,
    SHARED_ARTIFACTS,
    CppGenerationError,
    CppHartGenerator,
    RuntimeResources,
)
from udb.cpp_hart.__main__ import main
from udb.cpp_hart.catalog import Catalog
from udb.cpp_hart.context import Context
from udb.cpp_hart.generator import _unavailable, build_type
from udb.cpp_hart.resources import package_mapping, standalone_cmake

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures" / "cpp_hart"


@pytest.fixture(scope="module")
def database():
    return Database.from_path(ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas").resolve()


@pytest.fixture(scope="module")
def architecture(database):
    return database.configure(Configuration.from_file(FIXTURES / "cpp-smoke.yaml"))


@pytest.fixture(scope="module")
def plan(architecture):
    return CppHartGenerator([architecture], resources=RuntimeResources.from_path(ROOT)).plan()


def _contents(plan):
    return {str(file.path): file.content for file in plan.outputs}


def test_complete_artifact_set_and_provenance(plan):
    contents = _contents(plan)
    assert set(SHARED_ARTIFACTS) <= contents.keys()
    assert {f"include/udb/cfgs/cpp-smoke/{name}" for name in CONFIG_ARTIFACTS} <= contents.keys()
    assert {
        "CMakeLists.txt",
        ".toolchain/check_cxx.cmake",
        ".toolchain/.build-elfutils.sh",
        "include/udb/bits.hpp",
        "src/iss.cpp",
        "cfgs/cpp-smoke.json",
    } <= contents.keys()
    manifest = json.loads(contents["cpp-hart-manifest.json"])
    assert manifest["configurations"] == ["cpp-smoke"]
    assert manifest["unavailable"] == []
    assert set(manifest["outputs"]) == contents.keys() - {"cpp-hart-manifest.json"}
    for name, details in manifest["outputs"].items():
        assert details["sha256"] == hashlib.sha256(contents[name]).hexdigest()
    assert "schemas/config_schema.json" in manifest["inputs"]
    assert "cpp-smoke/idl/source/isa/globals.isa" in manifest["inputs"]
    assert all(
        str(dependency).startswith(".cpp_hart_inputs/")
        for file in plan.outputs
        for dependency in file.dependencies
    )


def test_safe_repeatable_writer(plan, tmp_path):
    changed = plan.apply(tmp_path)
    assert len(changed) == len(plan.outputs)
    assert plan.apply(tmp_path) == ()
    assert plan.apply(tmp_path, check=True) == ()
    path = tmp_path / "include/udb/enum.hxx"
    path.write_text("stale")
    assert path.relative_to(tmp_path) in plan.apply(tmp_path, check=True)
    assert path.read_text() == "stale"
    plan.apply(tmp_path)
    assert path.read_bytes() == _contents(plan)["include/udb/enum.hxx"]
    assert (tmp_path / ".toolchain/.build-elfutils.sh").stat().st_mode & 0o777 == 0o755


def test_explicit_resources_are_byte_exact(plan):
    contents = _contents(plan)
    for output, original, _, _ in RuntimeResources.from_path(ROOT).files():
        if str(output) != "CMakeLists.txt":
            assert contents[str(output)] == original


def test_source_generation_is_offline(architecture, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("source generation attempted an external process")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    # No package discovery occurs when the caller supplies source architectures
    # and the declared resource root.
    from udb.cpp_hart import resources

    monkeypatch.setattr(resources, "package_data_root", forbidden)
    generated = CppHartGenerator([architecture], resources=RuntimeResources.from_path(ROOT)).plan()
    assert len(generated.outputs) >= 70


def test_standalone_cmake_preserves_explicit_repository_override():
    original = (ROOT / "backends/cpp_hart_gen/CMakeLists.txt").read_bytes()
    text = standalone_cmake(original, ("rv32", "rv64")).decode()
    assert 'set(CONFIG_LIST "rv32;rv64")' in text
    assert 'if(NOT DEFINED UDB_ROOT OR UDB_ROOT STREQUAL "")' in text
    assert 'set(UDB_ROOT "${CMAKE_CURRENT_LIST_DIR}")' in text
    assert 'get_filename_component(UDB_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)' in text
    assert (ROOT / "backends/cpp_hart_gen/CMakeLists.txt").read_bytes() == original
    debug = standalone_cmake(original, ("rv32",), "Debug").decode()
    assert "SET(CMAKE_BUILD_TYPE Debug" in debug
    assert "IF(NOT CMAKE_BUILD_TYPE)" in debug
    with pytest.raises(CppGenerationError, match="Unrecognized"):
        standalone_cmake(b"not the declared CMake contract", ("rv32",))
    with pytest.raises(CppGenerationError, match="build-type"):
        standalone_cmake(
            original.replace(b"SET(CMAKE_BUILD_TYPE RelWithDebInfo", b"changed"), ("rv32",)
        )
    with pytest.raises(CppGenerationError, match="Unsupported"):
        standalone_cmake(original, ("rv32",), "../../escape")


def test_package_mapping_does_not_duplicate_static_sources():
    mapping = package_mapping(ROOT)
    assert ROOT / "backends/cpp_hart_gen/cpp/include/udb/bits.hpp" in mapping
    assert all(
        str(destination).startswith("udb/_data/cpp_hart/")
        or str(destination) == "udb/cpp_hart/NOTICE"
        for destination in mapping.values()
    )
    assert len(set(mapping.values())) == len(mapping)


def test_asset_manifest_isolated_from_runtime_dependencies():
    script = """
import importlib.util
from pathlib import Path
import sys
root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("cpp_assets", root / "src/udb/cpp_hart/asset_manifest.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert len(module.package_mapping(root)) >= 55
"""
    result = subprocess.run(
        [sys.executable, "-S", "-c", script, str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_runtime_source_alias_is_rejected_before_writes(architecture, tmp_path):
    for _, content, _, origin in RuntimeResources.from_path(ROOT).files():
        target = tmp_path / origin
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    license_file = tmp_path / "LICENSE-BSD-3-Clause-Clear.txt"
    original = license_file.read_bytes()
    generator = CppHartGenerator([architecture], resources=RuntimeResources.from_path(tmp_path))
    with pytest.raises(CppGenerationError, match="aliases runtime source"):
        generator.generate(tmp_path)
    assert license_file.read_bytes() == original


def test_bundled_runtime_assets_are_independent_of_checkout(tmp_path, monkeypatch):
    from udb.cpp_hart import resources

    data = tmp_path / "_data"
    for source, destination in package_mapping(ROOT).items():
        if str(destination).startswith("udb/_data/"):
            target = tmp_path / destination.relative_to("udb")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    monkeypatch.setattr(resources, "package_data_root", lambda: data)
    original = {name: content for name, content, _, _ in RuntimeResources.from_path(ROOT).files()}
    copied = {name: content for name, content, _, _ in RuntimeResources.bundled().files()}
    assert copied == original


def test_empty_all_selection_is_explicit(tmp_path, capsys):
    assert (
        main(
            [
                "--config",
                "all",
                "--configs-directory",
                str(tmp_path),
                "--out",
                str(tmp_path / "out"),
            ]
        )
        == 2
    )
    assert "No configurations selected" in capsys.readouterr().err


def test_invalid_or_missing_inputs_are_explicit(architecture, tmp_path):
    resources = RuntimeResources.from_path(ROOT)
    with pytest.raises(TypeError):
        CppHartGenerator([], resources=resources)
    with pytest.raises(CppGenerationError, match="unique"):
        CppHartGenerator([architecture, architecture], resources=resources, build_name="both")
    with pytest.raises(CppGenerationError, match="Missing explicit"):
        RuntimeResources.from_path(tmp_path / "absent")
    with pytest.raises(CppGenerationError, match="lack"):
        tuple(RuntimeResources.from_path(tmp_path).files())
    with pytest.raises(CppGenerationError, match="Invalid C\\+\\+"):
        CppHartGenerator([architecture], resources=resources, build_name="../../escape")
    with pytest.raises(CppGenerationError, match="Build type"):
        CppHartGenerator([architecture], resources=resources, build_type="weird")
    assert build_type("FAST_DEBUG") == "RelWithDebInfo"
    assert build_type("asan") == "Asan"


def test_native_instruction_field_interfaces(plan, architecture):
    oracle = json.loads((FIXTURES / "cpp-smoke-oracle.json").read_text())
    observed = interface(
        _contents(plan)["include/udb/cfgs/cpp-smoke/inst.hxx"].decode(), prefix="CppSmoke_"
    )
    expected = {
        f"CppSmoke_{record.name.replace('.', '_').capitalize()}_Inst"
        for record in architecture.possible_instructions
    }
    assert set(observed["classes"]) == expected
    old = oracle["observations"]["inst.hxx"]
    for name in expected:
        assert observed["decode_fields"][name] == [
            tuple(field) for field in old["decode_fields"][name]
        ]
    assert set(old["classes"]) - expected == set(oracle["classified_native_extra_instructions"])
    assert oracle["classification"] == "native-full-config-positive-only-SAT"


def test_native_shared_and_csr_class_interfaces(plan):
    oracle = json.loads((FIXTURES / "cpp-smoke-oracle.json").read_text())
    contents = _contents(plan)
    for artifact in ("db_data.hxx", "csrs.hxx", "structs.hxx", "hart.hxx", "csr_container.hxx"):
        path = (
            f"include/udb/{artifact}"
            if artifact == "db_data.hxx"
            else f"include/udb/cfgs/cpp-smoke/{artifact}"
        )
        observed = set(interface(contents[path].decode(), prefix="CppSmoke_")["classes"])
        old = set(oracle["observations"][artifact]["classes"])
        differences = oracle["classified_interfaces"][artifact]
        assert observed - old == set(differences["python_extra"])
        assert old - observed == set(differences["native_extra"])


def test_catalog_shares_parameter_definitions_across_full_and_partial(database, architecture):
    other = database.configure(Configuration.builtin("rv32"))
    first = Context(architecture)
    second = Context(other)
    shared = Catalog([first, second])
    assert len(shared.parameters) == len(first.parameters)
    assert [enum.name for enum in shared.enum_types] == [
        enum.name for enum in Catalog([first]).enum_types
    ]


def test_multiple_real_configurations_share_artifacts_without_namespace_aliasing(
    database, architecture, tmp_path
):
    data = architecture.configuration.to_dict()
    data["name"] = "cpp-second"
    second = database.configure(Configuration(data))
    generator = CppHartGenerator(
        [architecture, second], resources=RuntimeResources.from_path(ROOT), build_name="both"
    )
    plan = generator.plan()
    contents = _contents(plan)
    assert len(contents) == 98
    for name in ("cpp-smoke", "cpp-second"):
        assert {f"include/udb/cfgs/{name}/{file}" for file in CONFIG_ARTIFACTS} <= contents.keys()
    factory = contents["include/udb/hart_factory.hxx"].decode()
    assert "CppSmoke_Hart" in factory and "CppSecond_Hart" in factory
    manifest = json.loads(contents["cpp-hart-manifest.json"])
    assert manifest["configurations"] == ["cpp-smoke", "cpp-second"]
    assert manifest["unavailable"] == []
    plan.apply(tmp_path)
    assert (tmp_path / "cfgs/cpp-second.json").is_file()


def test_mixed_full_width_configurations_preserve_per_hart_width(database, architecture, tmp_path):
    data = architecture.configuration.to_dict()
    data["name"] = "cpp-wide"
    data["params"].update(MXLEN=64, MTVAL_WIDTH=64, PHYS_ADDR_WIDTH=56)
    wide = database.configure(Configuration(data))
    plan = CppHartGenerator(
        [architecture, wide], resources=RuntimeResources.from_path(ROOT), build_name="widths"
    ).plan()
    contents = _contents(plan)
    assert len(contents) == 98
    manifest = json.loads(contents["cpp-hart-manifest.json"])
    assert manifest["configurations"] == ["cpp-smoke", "cpp-wide"]
    assert manifest["unavailable"] == []
    for name, mxlen in (("cpp-smoke", 32), ("cpp-wide", 64)):
        hart = contents[f"include/udb/cfgs/{name}/hart.hxx"].decode()
        assert f"static constexpr unsigned MXLEN = {mxlen};" in hart
        assert "using XReg = Bits<MXLEN>" in hart
        config = json.loads(contents[f"cfgs/{name}.json"])
        assert config["params"]["MXLEN"] == mxlen
    plan.apply(tmp_path)


def test_real_configuration_namespace_collisions_are_rejected(database, architecture):
    first_data = architecture.configuration.to_dict()
    second_data = dict(first_data)
    first_data["name"] = "cpp-collision"
    second_data["name"] = "cpp_collision"
    first = database.configure(Configuration(first_data))
    second = database.configure(Configuration(second_data))
    generator = CppHartGenerator(
        [first, second], resources=RuntimeResources.from_path(ROOT), build_name="both"
    )
    with pytest.raises(CppGenerationError, match="collide"):
        generator.plan()


@pytest.mark.parametrize(("selector", "count"), [("_", 22), ("rv32", 11), ("rv64", 22)])
def test_genuine_unavailable_operations_retain_configuration_attribution(database, selector, count):
    context = Context(database.configure(Configuration.builtin(selector)))
    for instruction in context.instructions:
        if "operation()" in instruction.instruction:
            continue
        for xlen in context.xlens:
            if (instruction.name, xlen) in context.encodings:
                assert context.operation(instruction.name, xlen) is None
    assert len(context.unavailable) == count
    observed = _unavailable([context])
    assert len(observed) == count
    for item in observed:
        assert item["configuration"] == selector
        assert item["behavior"] == "operation()"
        assert item["source"].endswith("#/operation()")


def test_csr_field_compilation_is_cached_per_semantic_context(architecture, monkeypatch):
    context = Context(architecture)
    original = context.compiler.compile_field
    calls = []

    def compile_field(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(context.compiler, "compile_field", compile_field)
    csr, field = next(
        (record.name, field.name)
        for record, descriptor in context.csrs
        for field in context.fields(record, descriptor)
        if field.defined_in_base(32) and "reset_value()" in record["fields"][field.name]
    )
    first = context.field_body(csr, field, "reset_value()", 32)
    first_text = first.cpp()
    second = context.field_body(csr, field, "reset_value()", 32)
    assert second is first
    assert second.cpp() == first_text
    assert len(calls) == 1


def test_real_partial_function_enum_cast_is_native_source(database):
    context = Context(database.configure(Configuration.builtin("rv32")))
    definition = context.table.get("canonical_gpaddr?").func_def_ast
    _, body = context.function(definition)
    text = body.cpp()
    assert "SatpMode{" in text
    assert "UserTypeName(" not in text
    assert "IdlSource(" not in text

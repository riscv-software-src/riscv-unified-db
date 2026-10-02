# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import importlib.util
from pathlib import Path

from udb import Database

REPOSITORY_ROOT = Path(__file__).parents[2]
BUILD_HOOK_SPEC = importlib.util.spec_from_file_location(
    "hatch_build", REPOSITORY_ROOT / "hatch_build.py"
)
assert BUILD_HOOK_SPEC is not None and BUILD_HOOK_SPEC.loader is not None
BUILD_HOOK = importlib.util.module_from_spec(BUILD_HOOK_SPEC)
BUILD_HOOK_SPEC.loader.exec_module(BUILD_HOOK)
package_data = BUILD_HOOK.package_data


def test_editable_install_finds_bundled_data() -> None:
    assert Database.bundled().extension("Zvkg").name == "Zvkg"


def test_package_data_contains_raw_sources_and_schemas() -> None:
    mappings = package_data(REPOSITORY_ROOT)
    destinations = {destination.as_posix() for destination in mappings.values()}

    assert "udb/_data/isa/inst/Zaamo/amoadd.w.yaml" in destinations
    assert "udb/_data/isa/inst/Zalrsc/lr.w.yaml" in destinations
    assert "udb/_data/isa/csr/Zihpm/mhpmcounter3.yaml" in destinations
    assert "udb/_data/isa/csr/stvec.yaml" in destinations
    assert "udb/_data/isa/exception_code/IllegalInstruction.yaml" in destinations
    assert "udb/_data/isa/isa/globals.isa" in destinations
    assert "udb/_data/isa/prose/interrupts.adoc" in destinations
    assert "udb/_data/schemas/inst_schema.json" in destinations
    assert "udb/_data/layouts/inst/Zaamo/amoadd.SIZE.AQRL.layout" in destinations
    assert "udb/extension_docs/assets/manifest.json" in destinations
    assert "udb/extension_docs/assets/fonts/JetBrainsMono-Regular.ttf" in destinations
    assert "udb/extension_docs/assets/images/wavedrom/float-csr.adoc" in destinations
    assert "udb/extension_docs/templates/header.adoc" in destinations
    assert "udb/_data/cpp_hart/runtime/CMakeLists.txt" in destinations
    assert "udb/_data/cpp_hart/runtime/cpp/include/udb/bits.hpp" in destinations
    assert "udb/_data/cpp_hart/runtime/cpp/test/test_bits_properties_small.cpp" in destinations
    assert "udb/_data/cpp_hart/runtime/cpp/test/bits-tests.cmake" in destinations
    assert "udb/_data/cpp_hart/runtime/cpp/test/bits_property.hpp" in destinations
    assert not any(destination.endswith(".erb") for destination in destinations)

# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).parents[2]
BACKEND = ROOT / "backends/cpp_hart_gen"


def test_native_bits_no_longer_authors_test_source() -> None:
    tests = BACKEND / "cpp/test"
    assert not (tests / "gen_test_bits.rb").exists()
    assert not list(tests.glob("test_bits_random_*.cpp"))
    cmake = (tests / "CMakeLists.txt").read_text()
    assert 'include("${CMAKE_CURRENT_LIST_DIR}/bits-tests.cmake")' in cmake
    module = (tests / "bits-tests.cmake").read_text()
    for source in tests.glob("test_bits_properties_*.cpp"):
        assert source.name in module
    assert "test_bits_runtime_defects" in module
    assert "gen_test_bits" not in module and "test_bits_random_0" not in module
    assert "check_cxx_source_compiles(" in module
    assert "set(CMAKE_REQUIRED_LIBRARIES gmpxx gmp)" in module
    assert "find_library(" not in module


def test_native_bits_task_does_not_depend_on_hart_generation() -> None:
    commands = (ROOT / "tools/dev/tasks.toml").read_text()
    assert '["test:native-bits"]' in commands
    assert "tools.dev.native.cli test native-bits" in commands
    assert "./do" not in commands and "ruby" not in commands
    workflow = YAML(typ="safe").load(ROOT / ".github/workflows/regress.yml")
    steps = workflow["jobs"]["native-bits"]["steps"]
    assert any(step.get("run") == "mise run test:native-bits" for step in steps)

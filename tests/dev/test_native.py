# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tools.dev.common import DevError
from tools.dev.native import commands

ROOT = Path(__file__).resolve().parents[2]


def test_native_task_tree_is_discoverable() -> None:
    result = subprocess.run(
        ["mise", "tasks", "--no-header", "--name-only"],
        cwd=ROOT,
        env={**os.environ, "MISE_AUTO_INSTALL": "0"},
        check=True,
        capture_output=True,
        text=True,
    )
    names = set(result.stdout.splitlines())
    assert {
        "build:cpp-hart",
        "build:iss",
        "build:renode-hart",
        "build:softfloat-tests",
        "build:riscv-tests",
        "test:cpp-hart",
        "test:riscv-tests",
        "test:riscv-vector-tests",
        "test:softfloat",
        "test:native-bits",
        "test:llvm",
    } <= names


def test_cpp_generation_uses_final_installed_cli_spelling(tmp_path: Path) -> None:
    options = commands.NativeOptions(
        configs=("rv32", "cfgs/custom.yaml"),
        build_name="combo",
        build_type="fast-debug",
        jobs=3,
    )
    command = commands.generation_command(options, tmp_path)
    rendered = " ".join(command.argv)
    assert command.argv[0].endswith(".venv/bin/udb")
    assert " generate cpp-hart " in f" {rendered} "
    assert " -c rv32 -c cfgs/custom.yaml " in f" {rendered} "
    assert f" -o {tmp_path}/gen/cpp-hart/combo_fast-debug " in f" {rendered} "
    assert " --build-name combo " in f" {rendered} "
    assert " --build-type RelWithDebInfo " in f" {rendered} "


def test_multiple_configs_require_build_name() -> None:
    options = commands.NativeOptions(configs=("rv32", "rv64"))
    with pytest.raises(DevError, match="build-name"):
        options.resolved_build_name()


def test_cpp_build_and_test_plans_construct_expected_targets(tmp_path: Path) -> None:
    options = commands.NativeOptions(configs=("rv64",), jobs=2)
    build = commands.cpp_build_plan("iss", options, tmp_path)
    assert build[0] == commands.generation_command(options, tmp_path)
    assert "iss" in build[-1].argv
    tests = commands.cpp_test_plan("cpp-hart", options, tmp_path)
    flattened = [" ".join(command.argv) for command in tests]
    assert any("test_bits_random" in command for command in flattened)
    assert any(command.startswith("ctest --test-dir") for command in flattened)


def test_native_bits_plan_is_independent_and_honors_jobs(tmp_path: Path) -> None:
    plan = commands.native_bits_plan(build_type="debug", jobs=2, root=tmp_path)
    flattened = [" ".join(command.argv) for command in plan]
    assert all("generate cpp-hart" not in command for command in flattened)
    assert flattened[0].startswith("cmake -S ")
    assert "--target test_bits_random test_bits_directed -j 2" in flattened[1]
    assert "ctest --test-dir" in flattened[2] and "-j 2" in flattened[2]


def test_riscv_test_build_uses_selected_width_and_toolchain_prefix(tmp_path: Path) -> None:
    plan = commands.riscv_tests_build_plan(
        xlen=32,
        build_type="release",
        jobs=4,
        root=tmp_path,
    )
    make = " ".join(plan[-1].argv)
    assert "XLEN=32" in make
    assert "BUILD_TYPE=Release" in make
    assert "RISCV_PREFIX=riscv32-unknown-elf-" in make
    assert "-j4" in make


def test_riscv_test_execution_expands_after_build(tmp_path: Path) -> None:
    options = commands.NativeOptions(configs=("rv32",), jobs=2)
    plan = commands.riscv_test_plan(options, timeout=15, root=tmp_path)
    assert plan[-1].argv[:2] == ("bash", "-c")
    script = plan[-1].argv[2]
    assert "rv32{ui,um,uc,si,uf}-p-*" in script
    assert "timeout 15" in script

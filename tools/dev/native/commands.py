# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .. import container
from ..common import ROOT, DevError, udb_command

BUILD_TYPES = {
    "debug": "Debug",
    "fast-debug": "RelWithDebInfo",
    "release": "Release",
    "asan": "Asan",
}


@dataclass(frozen=True)
class Command:
    argv: tuple[str, ...]
    cwd: Path = ROOT
    env: dict[str, str] = field(default_factory=dict)
    toolchain: bool = False
    timeout: int | None = None


@dataclass(frozen=True)
class NativeOptions:
    configs: tuple[str, ...] = ()
    build_name: str | None = None
    build_type: str = "fast-debug"
    jobs: int = os.cpu_count() or 1
    ignore_undefined: bool = False

    def resolved_build_name(self) -> str:
        if not self.configs:
            raise DevError("at least one -c/--config is required", 2)
        if len(self.configs) > 1 and not self.build_name:
            raise DevError("--build-name is required with multiple configurations", 2)
        name = self.build_name or Path(self.configs[0]).stem
        return f"{name}_{self.build_type}"


def source_dir(options: NativeOptions, root: Path = ROOT) -> Path:
    return root / "gen/cpp-hart" / options.resolved_build_name()


def generation_command(options: NativeOptions, root: Path = ROOT) -> Command:
    output = source_dir(options, root)
    command = udb_command("generate", "cpp-hart")
    for config in options.configs:
        command.extend(("-c", config))
    command.extend(
        (
            "-o",
            str(output),
            "--build-name",
            options.build_name or Path(options.configs[0]).stem,
            "--build-type",
            BUILD_TYPES[options.build_type],
            "-j",
            str(options.jobs),
        )
    )
    return Command(tuple(command), root)


def _toolchain_mode(root: Path) -> str:
    if os.environ.get("UDB_TOOLCHAIN_NONE") == "1":
        return "none"
    if os.environ.get("UDB_TOOLCHAIN_CONTAINER") == "1":
        return "container"
    preference = (
        (root / ".toolchain-local").read_text(encoding="utf-8")
        if (root / ".toolchain-local").is_file()
        else ""
    )
    if "UDB_TOOLCHAIN_NONE=1" in preference:
        return "none"
    if "UDB_TOOLCHAIN_CONTAINER=1" in preference:
        return "container"
    return "native"


def _cxx_compiler(root: Path) -> str:
    if _toolchain_mode(root) == "container":
        return "g++"
    return shutil.which("g++") or shutil.which("clang++") or "g++"


def configure_command(options: NativeOptions, root: Path = ROOT) -> Command:
    source = source_dir(options, root)
    compiler = _cxx_compiler(root)
    configs = ";".join(Path(config).stem for config in options.configs)
    return Command(
        (
            "cmake",
            "-S",
            str(source),
            "-B",
            str(source / "build"),
            f"-DCMAKE_CXX_COMPILER={compiler}",
            f"-DCONFIG_LIST={configs}",
            f"-DCMAKE_BUILD_TYPE={BUILD_TYPES[options.build_type]}",
            f"-DIGNOREUNDEFINED={'YES' if options.ignore_undefined else 'NO'}",
            f"-DUDB_ROOT={root}",
        ),
        root,
        toolchain=True,
    )


def cmake_build_command(options: NativeOptions, *targets: str, root: Path = ROOT) -> Command:
    return Command(
        (
            "cmake",
            "--build",
            str(source_dir(options, root) / "build"),
            "--target",
            *targets,
            "-j",
            str(options.jobs),
        ),
        root,
        toolchain=True,
    )


def cpp_build_plan(kind: str, options: NativeOptions, root: Path = ROOT) -> list[Command]:
    target = {
        "cpp-hart": "hart",
        "iss": "iss",
        "renode-hart": "hart_renode",
        "softfloat-tests": "test_softfloat_fp",
    }[kind]
    if kind == "softfloat-tests":
        options = NativeOptions(
            configs=("rv64",),
            build_name=options.build_name,
            build_type="debug",
            jobs=options.jobs,
            ignore_undefined=options.ignore_undefined,
        )
    return [
        generation_command(options, root),
        configure_command(options, root),
        cmake_build_command(options, target, root=root),
    ]


def cpp_test_plan(kind: str, options: NativeOptions, root: Path = ROOT) -> list[Command]:
    if kind == "cpp-hart":
        return [
            generation_command(options, root),
            configure_command(options, root),
            cmake_build_command(
                options,
                "test_bits_directed",
                "test_bits_random",
                "test_softfloat_fp",
                "test_regfile",
                "test_util",
                root=root,
            ),
            Command(
                (
                    "ctest",
                    "--test-dir",
                    str(source_dir(options, root) / "build"),
                    "-j",
                    str(options.jobs),
                    "--output-on-failure",
                ),
                root,
                toolchain=True,
            ),
        ]
    if kind == "softfloat":
        fixed = NativeOptions(
            configs=("rv64",),
            build_name=options.build_name,
            build_type="debug",
            jobs=options.jobs,
            ignore_undefined=options.ignore_undefined,
        )
        return [
            *cpp_build_plan("softfloat-tests", fixed, root),
            Command(
                (str(source_dir(fixed, root) / "build/test_softfloat_fp"),),
                root,
                toolchain=True,
            ),
        ]
    raise DevError(f"unknown C++ test kind: {kind}", 2)


def native_bits_plan(
    *, build_type: str = "debug", jobs: int = 1, root: Path = ROOT
) -> list[Command]:
    build = root / "gen/native-bits"
    compiler = _cxx_compiler(root)
    return [
        Command(
            (
                "cmake",
                "-S",
                str(root / "backends/cpp_hart_gen/cpp/test"),
                "-B",
                str(build),
                f"-DCMAKE_CXX_COMPILER={compiler}",
                f"-DCMAKE_BUILD_TYPE={BUILD_TYPES[build_type]}",
            ),
            root,
            toolchain=True,
        ),
        Command(
            (
                "cmake",
                "--build",
                str(build),
                "--target",
                "test_bits_random",
                "test_bits_directed",
                "-j",
                str(jobs),
            ),
            root,
            toolchain=True,
        ),
        Command(
            (
                "ctest",
                "--test-dir",
                str(build),
                "-j",
                str(jobs),
                "--output-on-failure",
            ),
            root,
            toolchain=True,
        ),
    ]


def riscv_tests_build_plan(
    *, xlen: int, build_type: str, jobs: int, root: Path = ROOT
) -> list[Command]:
    return [
        Command(("git", "submodule", "update", "--init", "ext/riscv-tests"), root),
        Command(
            ("git", "submodule", "update", "--init", "--recursive"),
            root / "ext/riscv-tests",
        ),
        Command(
            (
                "make",
                f"XLEN={xlen}",
                f"BUILD_TYPE={BUILD_TYPES[build_type]}",
                f"RISCV_PREFIX=riscv{xlen}-unknown-elf-",
                f"-j{jobs}",
            ),
            root / "tests/isa",
            toolchain=True,
        ),
    ]


def vector_test_plan(options: NativeOptions, root: Path = ROOT) -> list[Command]:
    config = options.configs[0]
    xlen = 32 if Path(config).stem == "rv32" else 64
    iss = source_dir(options, root) / "build/iss"
    tests = (
        "vsetivli",
        "vsetvl",
        "vsetvli_rs1_eq_zero",
        "vsetvli_vl_lt_vlmax",
        "vle8",
        "vmv_v_i",
        "vadd.vv",
    )
    commands = [
        *cpp_build_plan("iss", options, root),
        *riscv_tests_build_plan(
            xlen=xlen,
            build_type=options.build_type,
            jobs=options.jobs,
            root=root,
        ),
    ]
    commands.extend(
        Command(
            (
                str(iss),
                "-m",
                Path(config).stem,
                "-c",
                str(root / "cfgs" / f"{Path(config).stem}.yaml"),
                str(root / f"tests/isa/rv{xlen}uv-p-{test}"),
            ),
            root,
            toolchain=True,
        )
        for test in tests
    )
    return commands


def riscv_test_plan(options: NativeOptions, *, timeout: int, root: Path = ROOT) -> list[Command]:
    config = Path(options.configs[0]).stem
    xlen = 32 if config == "rv32" else 64
    iss = source_dir(options, root) / "build/iss"
    commands = [
        *cpp_build_plan("iss", options, root),
        *riscv_tests_build_plan(
            xlen=xlen,
            build_type=options.build_type,
            jobs=options.jobs,
            root=root,
        ),
    ]
    script = f"""
set -eu
for test in {root}/ext/riscv-tests/isa/{config}{{ui,um,uc,si,uf}}-p-*; do
  [ -e "$test" ] || continue
  timeout {timeout} {iss} -m {config} \
    -c {root}/cfgs/{config}-riscv-tests.yaml "$test"
done
"""
    commands.append(Command(("bash", "-c", script), root, toolchain=True))
    return commands


def llvm_plan(root: Path = ROOT) -> list[Command]:
    build = root / "ext/llvm-project/build"
    return [
        Command(
            (
                "cmake",
                "-S",
                str(root / "ext/llvm-project/llvm"),
                "-B",
                str(build),
                "-DCMAKE_BUILD_TYPE=Release",
            ),
            root,
            toolchain=True,
        ),
        Command(
            ("cmake", "--build", str(build), "--target", "llvm-tblgen"),
            root,
            toolchain=True,
        ),
    ]


def _toolchain_prefix(root: Path, cwd: Path) -> list[str]:
    mode = _toolchain_mode(root)
    if mode == "none":
        raise DevError("the selected task requires a configured C++ toolchain", 3)
    if mode != "container":
        return []
    runtime = container.find_runtime()
    if runtime is None:
        raise DevError("the configured container toolchain runtime is unavailable", 3)
    return [
        runtime,
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{root}:{root}",
        "-w",
        str(cwd),
        container.image_name(root),
    ]


def execute(plan: list[Command], root: Path = ROOT) -> int:
    for command in plan:
        argv = (
            [*_toolchain_prefix(root, command.cwd), *command.argv]
            if command.toolchain
            else list(command.argv)
        )
        try:
            result = subprocess.run(
                argv,
                cwd=command.cwd,
                env={**os.environ, **command.env},
                check=False,
                timeout=command.timeout,
            )
        except subprocess.TimeoutExpired:
            return 124
        if result.returncode:
            return result.returncode
    return 0

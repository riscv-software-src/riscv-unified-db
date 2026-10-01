# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import os
import shlex

from ..common import DevError, entrypoint
from .commands import (
    NativeOptions,
    cpp_build_plan,
    cpp_test_plan,
    execute,
    llvm_plan,
    native_bits_plan,
    riscv_test_plan,
    riscv_tests_build_plan,
    vector_test_plan,
)


def _jobs(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _options() -> NativeOptions:
    configs = tuple(shlex.split(os.environ.get("usage_config", "")))
    build_type = os.environ.get("usage_build_type") or "fast-debug"
    jobs = _jobs(os.environ.get("usage_jobs") or str(os.cpu_count() or 1))
    return NativeOptions(
        configs=configs,
        build_name=os.environ.get("usage_build_name") or None,
        build_type=build_type,
        jobs=jobs,
        ignore_undefined=os.environ.get("usage_ignore_undefined") == "true",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "test"))
    parser.add_argument(
        "kind",
        choices=(
            "cpp-hart",
            "iss",
            "renode-hart",
            "softfloat-tests",
            "riscv-tests",
            "riscv-vector-tests",
            "softfloat",
            "native-bits",
            "llvm",
        ),
    )
    args = parser.parse_args(argv)
    options = _options()
    if args.kind == "native-bits":
        return execute(
            native_bits_plan(
                build_type=os.environ.get("usage_build_type") or "debug",
                jobs=options.jobs,
            )
        )
    if args.kind == "llvm":
        return execute(llvm_plan())
    if args.kind == "riscv-tests" and args.action == "build":
        xlen_text = os.environ.get("usage_xlen")
        if xlen_text not in {"32", "64"}:
            raise DevError("--xlen 32|64 is required", 2)
        return execute(
            riscv_tests_build_plan(
                xlen=int(xlen_text),
                build_type=options.build_type,
                jobs=options.jobs,
            )
        )
    if args.kind == "riscv-tests":
        if options.configs not in {("rv32",), ("rv64",)}:
            raise DevError("test:riscv-tests requires exactly -c rv32 or -c rv64", 2)
        timeout = int(os.environ.get("usage_timeout") or 10)
        return execute(riscv_test_plan(options, timeout=timeout))
    if args.kind == "riscv-vector-tests":
        if options.configs not in {("rv32",), ("rv64",)}:
            raise DevError("test:riscv-vector-tests requires exactly -c rv32 or -c rv64", 2)
        return execute(vector_test_plan(options))
    if args.action == "build":
        return execute(cpp_build_plan(args.kind, options))
    return execute(cpp_test_plan(args.kind, options))


if __name__ == "__main__":
    raise SystemExit(entrypoint(main))

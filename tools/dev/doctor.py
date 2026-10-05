# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from . import container
from .common import ROOT, entrypoint


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    required: bool = True


def _command_check(
    name: str, command: list[str], *, cwd: Path = ROOT, required: bool = True
) -> Check:
    try:
        result = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)
    except OSError as error:
        return Check(name, "fail" if required else "warn", str(error), required)
    output = (result.stdout or result.stderr).splitlines()
    detail = output[0] if output else f"exit {result.returncode}"
    return Check(
        name,
        "pass" if result.returncode == 0 else ("fail" if required else "warn"),
        detail,
        required,
    )


def _mise_tool_checks(root: Path = ROOT) -> list[Check]:
    config = tomllib.loads((root / ".mise.toml").read_text(encoding="utf-8"))
    tools = config.get("tools", {})
    checks = []
    for tool, pin in tools.items():
        binary = "gh" if tool == "github-cli" else tool
        try:
            resolved = subprocess.run(
                ["mise", "which", binary],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            checks.append(Check(f"mise-tool:{tool}", "fail", str(error)))
            continue
        path = resolved.stdout.strip()
        if resolved.returncode or not path:
            checks.append(Check(f"mise-tool:{tool}", "fail", f"{tool} {pin} is not installed"))
            continue
        checks.append(
            _command_check(
                f"mise-tool:{tool}",
                [path, "--version"],
                cwd=root,
            )
        )
    return checks


def _toolchain_mode(root: Path) -> tuple[str, bool]:
    if os.environ.get("UDB_TOOLCHAIN_NONE") == "1":
        return "none", True
    if os.environ.get("UDB_TOOLCHAIN_CONTAINER") == "1":
        return "container", True
    preference_path = root / ".toolchain-local"
    preference = preference_path.read_text(encoding="utf-8") if preference_path.is_file() else ""
    if "UDB_TOOLCHAIN_NONE=1" in preference:
        return "none", True
    if "UDB_TOOLCHAIN_CONTAINER=1" in preference:
        return "container", True
    return "native", bool(preference)


def _native_cxx_requirements_check(root: Path, compiler: str, *, required: bool) -> Check:
    source = root / "gen/doctor-cxx-check"
    build = source / "build"
    shutil.rmtree(source, ignore_errors=True)
    source.mkdir(parents=True)
    (source / "CMakeLists.txt").write_text(
        "\n".join(
            (
                "cmake_minimum_required(VERSION 3.12)",
                "project(cxx_check CXX)",
                f'include("{root / ".toolchain/check_cxx.cmake"}")',
                "",
            )
        ),
        encoding="utf-8",
    )
    try:
        cmake = subprocess.run(
            ["mise", "which", "cmake"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        cmake_binary = cmake.stdout.strip() if cmake.returncode == 0 else "cmake"
        result = subprocess.run(
            [
                cmake_binary or "cmake",
                "-S",
                str(source),
                "-B",
                str(build),
                f"-DCMAKE_CXX_COMPILER={compiler}",
                "--log-level=ERROR",
                "-Wno-dev",
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        return Check("cxx-requirements", "fail" if required else "warn", str(error), required)
    finally:
        shutil.rmtree(source, ignore_errors=True)
    return Check(
        "cxx-requirements",
        "pass" if result.returncode == 0 else ("fail" if required else "warn"),
        "C++23, concepts, and constexpr from_chars"
        if result.returncode == 0
        else "compiler lacks required C++23 features",
        required,
    )


def collect_checks(root: Path = ROOT) -> list[Check]:
    mise = _command_check("mise", ["mise", "--version"], cwd=root)
    checks = [
        _command_check("git", ["git", "--version"], cwd=root),
        mise,
        _command_check(
            "python-environment",
            [
                "uv",
                "sync",
                "--check",
            ],
            cwd=root,
        )
        if (root / ".venv").is_dir()
        else Check("python-environment", "fail", ".venv is missing"),
        Check(
            "node-dependencies",
            "pass" if (root / "node_modules").is_dir() else "fail",
            "node_modules present"
            if (root / "node_modules").is_dir()
            else "node_modules is missing",
        ),
    ]
    if mise.status == "pass":
        checks.extend(_mise_tool_checks(root))
    else:
        checks.append(Check("mise-tools", "fail", "mise is unavailable"))

    git_dir = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        check=False,
        capture_output=True,
        text=True,
    )
    hook = Path(git_dir.stdout.strip()) / "hooks" / "pre-commit"
    checks.append(
        Check(
            "pre-commit-hook",
            "pass" if hook.is_file() else "warn",
            "installed" if hook.is_file() else "not installed",
            False,
        )
    )

    mode, explicitly_selected = _toolchain_mode(root)
    if mode == "none":
        checks.append(Check("toolchain", "warn", "disabled by .toolchain-local", False))
    elif mode == "container":
        runtime = container.find_runtime()
        checks.append(
            Check(
                "toolchain",
                "pass" if runtime else "fail",
                f"container runtime: {runtime}" if runtime else "container runtime is unavailable",
            )
        )
    else:
        compiler = shutil.which("g++") or shutil.which("clang++")
        required = explicitly_selected
        checks.append(
            Check(
                "toolchain",
                "pass" if compiler else ("fail" if required else "warn"),
                compiler or "native compiler unavailable",
                required,
            )
        )
        if compiler:
            checks.append(_native_cxx_requirements_check(root, compiler, required=required))

    renderer = shutil.which("asciidoctor-pdf")
    checks.append(
        Check(
            "pdf-renderer",
            "pass" if renderer else "warn",
            renderer or "asciidoctor-pdf is needed only by PDF regressions",
            False,
        )
    )
    workflow = root / ".github" / "workflows" / "regress.yml"
    checks.append(Check("workflow", "pass" if workflow.is_file() else "fail", str(workflow)))
    return checks


def doctor(output_format: str, root: Path = ROOT) -> int:
    checks = collect_checks(root)
    if output_format == "json":
        print(json.dumps({"checks": [asdict(check) for check in checks]}, sort_keys=True))
    else:
        symbols = {"pass": "✓", "warn": "!", "fail": "✗"}
        for check in checks:
            print(f"{symbols[check.status]} {check.name}: {check.detail}")
        passed = sum(check.status == "pass" for check in checks)
        warnings = sum(check.status == "warn" for check in checks)
        failures = sum(check.status == "fail" for check in checks)
        print(f"{passed} passed, {failures} failed, {warnings} warnings")
    return 1 if any(check.required and check.status == "fail" for check in checks) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    return doctor(args.format)


if __name__ == "__main__":
    raise SystemExit(entrypoint(main))

# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from . import container
from .common import ROOT


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str
    required: bool = True


def _command_check(name: str, command: list[str], *, required: bool = True) -> Check:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
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


def collect_checks(root: Path = ROOT) -> list[Check]:
    checks = [
        _command_check("git", ["git", "--version"]),
        _command_check("mise", ["mise", "--version"]),
        _command_check(
            "python-environment",
            [
                "uv",
                "sync",
                "--locked",
                "--check",
            ],
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

    preference = (
        (root / ".toolchain-local").read_text(encoding="utf-8")
        if (root / ".toolchain-local").exists()
        else ""
    )
    if "UDB_TOOLCHAIN_NONE=1" in preference:
        checks.append(Check("toolchain", "warn", "disabled by .toolchain-local", False))
    elif "UDB_TOOLCHAIN_CONTAINER=1" in preference:
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
        checks.append(
            Check(
                "toolchain",
                "pass" if compiler else "warn",
                compiler or "native compiler unavailable",
                bool(preference),
            )
        )

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
    checks.append(
        Check("generated-workflow", "pass" if workflow.is_file() else "fail", str(workflow))
    )
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
    raise SystemExit(main())

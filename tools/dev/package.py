# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from .common import ROOT, DevError, entrypoint, python_command


def build_command(output: Path, *, wheel_only: bool = False, sdist_only: bool = False) -> list[str]:
    if wheel_only and sdist_only:
        raise DevError("--wheel-only and --sdist-only are mutually exclusive", 2)
    command = python_command("-m", "build", "--outdir", str(output))
    if wheel_only:
        command.append("--wheel")
    if sdist_only:
        command.append("--sdist")
    return command


def build(output: Path, *, wheel_only: bool, sdist_only: bool) -> int:
    output.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        build_command(output, wheel_only=wheel_only, sdist_only=sdist_only),
        cwd=ROOT,
        check=False,
    ).returncode


def check(*, rebuild_sdist: bool) -> int:
    dist = ROOT / "dist"
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if not wheels or not sdists:
        raise DevError("dist/ must contain a wheel and source archive; run package build", 2)
    check_root = ROOT / "gen/package-check"
    shutil.rmtree(check_root, ignore_errors=True)
    commands: list[list[str]] = [
        python_command("-m", "venv", "--system-site-packages", str(check_root / "wheel")),
        [
            str(check_root / "wheel/bin/python"),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            str(wheels[-1]),
        ],
        [
            str(check_root / "wheel/bin/python"),
            str(ROOT / "tools/test/check_python_install.py"),
        ],
    ]
    for command in commands:
        status = subprocess.run(command, cwd=ROOT, check=False).returncode
        if status:
            return status
    if rebuild_sdist:
        rebuild_commands = [
            python_command(
                "-m",
                "venv",
                "--system-site-packages",
                str(check_root / "sdist"),
            ),
            [
                str(check_root / "sdist/bin/python"),
                "-m",
                "pip",
                "wheel",
                "--no-index",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(check_root / "rebuilt"),
                str(sdists[-1]),
            ],
        ]
        for command in rebuild_commands:
            status = subprocess.run(command, cwd=ROOT, check=False).returncode
            if status:
                return status
        rebuilt = sorted((check_root / "rebuilt").glob("*.whl"))
        if not rebuilt:
            raise DevError("source archive rebuild produced no wheel", 3)
        rebuilt_commands = [
            python_command(
                "-m",
                "venv",
                "--system-site-packages",
                str(check_root / "rebuilt-wheel"),
            ),
            [
                str(check_root / "rebuilt-wheel/bin/python"),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                str(rebuilt[-1]),
            ],
            [
                str(check_root / "rebuilt-wheel/bin/python"),
                str(ROOT / "tools/test/check_python_install.py"),
            ],
        ]
        for command in rebuilt_commands:
            status = subprocess.run(command, cwd=ROOT, check=False).returncode
            if status:
                return status
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(os.environ.get("usage_output") or ROOT / "dist"),
    )
    build_parser.add_argument(
        "--wheel-only",
        action="store_true",
        default=os.environ.get("usage_wheel_only") == "true",
    )
    build_parser.add_argument(
        "--sdist-only",
        action="store_true",
        default=os.environ.get("usage_sdist_only") == "true",
    )
    check_parser = commands.add_parser("check")
    check_parser.add_argument("--rebuild-sdist", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "build":
        return build(
            args.output,
            wheel_only=args.wheel_only,
            sdist_only=args.sdist_only,
        )
    return check(
        rebuild_sdist=args.rebuild_sdist or os.environ.get("usage_rebuild_sdist") == "true"
    )


if __name__ == "__main__":
    raise SystemExit(entrypoint(main))

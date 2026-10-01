# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import os
import subprocess

from .common import ROOT, DevError, entrypoint, python_command, udb_command


def build_commands(target: str) -> list[list[str]]:
    if target == "site":
        return [["aube", "-C", "doc", "--frozen-lockfile", "build"]]
    if target == "schemas":
        return [
            udb_command(
                "generate",
                "schema-docs",
                "-o",
                str(ROOT / "doc/docs/schemas"),
                "--replace-current",
            )
        ]
    if target == "idl":
        return [
            [
                "asciidoctor",
                "-a",
                "toc=left",
                "-o",
                str(ROOT / "gen/docs/idl.html"),
                str(ROOT / "doc/idl.adoc"),
            ]
        ]
    if target == "pages":
        return [
            *build_commands("site"),
            python_command(
                str(ROOT / "tools/scripts/gen_schema_index.py"),
                str(ROOT / "_site/schemas"),
                str(ROOT / "_site/schemas/index.json"),
            ),
            python_command(str(ROOT / "tools/scripts/gen_pages_index.py")),
        ]
    if target == "api":
        raise DevError("Python API-reference generation is deferred by the Stage 6 design", 3)
    raise DevError(f"unknown docs target: {target}", 2)


def build(target: str) -> int:
    for command in build_commands(target):
        status = subprocess.run(command, cwd=ROOT, check=False).returncode
        if status:
            return status
    return 0


def serve(target: str, *, port: int) -> int:
    directory = ROOT / ("doc/build" if target == "site" else "gen/docs/api")
    if not directory.is_dir():
        status = build(target)
        if status:
            return status
    return subprocess.run(
        python_command("-m", "http.server", str(port), "--directory", str(directory)),
        cwd=ROOT,
        check=False,
    ).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build")
    build_parser.add_argument(
        "target",
        nargs="?",
        choices=("site", "pages", "idl", "schemas", "api"),
        default=os.environ.get("usage_target"),
    )
    serve_parser = commands.add_parser("serve")
    serve_parser.add_argument(
        "target",
        nargs="?",
        choices=("site", "api"),
        default=os.environ.get("usage_target"),
    )
    serve_parser.add_argument("--port", type=int, default=int(os.environ.get("usage_port") or 8000))
    args = parser.parse_args(argv)
    if not args.target:
        parser.error("TARGET is required")
    if args.command == "build":
        return build(args.target)
    return serve(args.target, port=args.port)


if __name__ == "__main__":
    raise SystemExit(entrypoint(main))

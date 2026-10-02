# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import os
import subprocess

from .common import ROOT, DevError, entrypoint, python_command, udb_command


def package_command(repository: str | None, artifacts: list[str] | None = None) -> list[str]:
    if not repository:
        raise DevError("release package requires --repository NAME_OR_URL", 2)
    option = "--publish-url" if "://" in repository else "--index"
    return ["uv", "publish", option, repository, *(artifacts or ["dist/*"])]


def release_package(repository: str | None) -> int:
    package_command(repository)
    artifacts = sorted(str(path) for path in (ROOT / "dist").glob("*") if path.is_file())
    if not artifacts:
        raise DevError("dist/ contains no package artifacts; run build:package first", 2)
    return subprocess.run(
        package_command(repository, artifacts),
        cwd=ROOT,
        check=False,
    ).returncode


def release_schemas(*, check_only: bool) -> int:
    status = subprocess.run(
        udb_command("generate", "schema-bundle", "-o", str(ROOT / "gen/schemas")),
        cwd=ROOT,
        check=False,
    ).returncode
    if status:
        return status
    command = python_command(str(ROOT / "tools/scripts/publish_schemas.py"))
    if check_only:
        command.append("--check-only")
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    package_parser = commands.add_parser("package")
    package_parser.add_argument("--repository")
    schemas_parser = commands.add_parser("schemas")
    schemas_parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "package":
        return release_package(args.repository or os.environ.get("usage_repository"))
    return release_schemas(
        check_only=args.check_only or os.environ.get("usage_check_only") == "true"
    )


if __name__ == "__main__":
    raise SystemExit(entrypoint(main))

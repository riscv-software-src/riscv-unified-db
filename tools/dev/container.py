# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path

from .common import ROOT, DevError, entrypoint


def image_name(root: Path = ROOT) -> str:
    digest = hashlib.sha256((root / ".toolchain" / "Dockerfile").read_bytes()).hexdigest()[:16]
    return f"ghcr.io/riscv/udb-toolchain:{digest}"


def find_runtime() -> str | None:
    return shutil.which("docker") or shutil.which("podman")


def image_exists(runtime: str, image: str) -> bool:
    result = subprocess.run(
        [runtime, "images", "--format", "{{.Repository}}:{{.Tag}}"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and image in result.stdout.splitlines()


def command_for(action: str, *, force: bool = False, root: Path = ROOT) -> list[str] | None:
    runtime = find_runtime()
    if runtime is None:
        raise DevError("no container runtime found (Docker or Podman is required)")
    image = image_name(root)
    exists = image_exists(runtime, image)

    if action in {"build", "pull"} and exists and not force:
        return None
    if action == "build":
        return [
            runtime,
            "build",
            "-t",
            image,
            "-f",
            str(root / ".toolchain" / "Dockerfile"),
            str(root / ".toolchain"),
        ]
    if action == "pull":
        return [runtime, "pull", image]
    if action == "remove":
        return [runtime, "rmi", image] if exists else None
    raise DevError(f"unknown container action: {action}", 2)


def execute(action: str, *, force: bool = False, root: Path = ROOT) -> int:
    command = command_for(action, force=force, root=root)
    if command is None:
        print(f"Toolchain image already in requested state: {image_name(root)}")
        return 0
    return subprocess.run(command, cwd=root, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "pull", "remove"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    return execute(args.action, force=args.force)


if __name__ == "__main__":
    raise SystemExit(entrypoint(main))

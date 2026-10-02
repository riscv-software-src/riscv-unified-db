# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

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


def _venv_executable(environment: Path, name: str) -> Path:
    directory = "Scripts" if os.name == "nt" else "bin"
    suffix = ".exe" if os.name == "nt" else ""
    return environment / directory / f"{name}{suffix}"


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> int:
    return subprocess.run(command, cwd=cwd, env=env, check=False).returncode


def _uv_executable() -> str:
    executable = shutil.which("uv")
    if executable is None:
        raise DevError("uv is required for offline package acceptance", 2)
    return executable


def _installed_environment(environment: Path) -> dict[str, str]:
    clean = os.environ.copy()
    clean["PATH"] = str(_venv_executable(environment, "python").parent)
    clean["PYTHONNOUSERSITE"] = "1"
    for name in ("PYTHONHOME", "PYTHONPATH", "RUBYLIB", "RUBYOPT", "BUNDLE_GEMFILE"):
        clean.pop(name, None)
    return clean


def _check_installed_wheel(wheel: Path, root: Path, acceptance: Path) -> int:
    root.mkdir(parents=True)
    environment = root / "environment"
    status = _run(
        [
            _uv_executable(),
            "venv",
            "--offline",
            "--no-config",
            "--python",
            sys.executable,
            str(environment),
        ],
        cwd=root,
    )
    if status:
        return status
    python = _venv_executable(environment, "python")
    status = _run(
        [
            _uv_executable(),
            "pip",
            "install",
            "--offline",
            "--no-config",
            "--strict",
            "--python",
            str(python),
            str(wheel),
        ],
        cwd=root,
    )
    if status:
        return status
    work = root / "work"
    work.mkdir()
    return _run(
        [
            str(python),
            "-I",
            str(acceptance / "installed_smoke.py"),
            "--root",
            str(root / "output"),
            "--full-config",
            str(acceptance / "full-config.yaml"),
        ],
        cwd=work,
        env=_installed_environment(environment),
    )


def _check_artifacts(
    wheel: Path,
    sdist: Path,
    *,
    rebuild_sdist: bool,
    check_root: Path,
) -> int:
    acceptance = check_root / "acceptance"
    acceptance.mkdir(parents=True)
    shutil.copy2(ROOT / "tests/package/installed_smoke.py", acceptance)
    shutil.copy2(
        ROOT / "cfgs/mc100-32-full-example.yaml",
        acceptance / "full-config.yaml",
    )
    status = _check_installed_wheel(wheel.resolve(), check_root / "wheel", acceptance)
    if status:
        return status
    if rebuild_sdist:
        sdist_root = check_root / "sdist"
        sdist_root.mkdir()
        status = _run(
            [
                _uv_executable(),
                "build",
                "--offline",
                "--no-config",
                "--wheel",
                "--out-dir",
                str(sdist_root / "rebuilt"),
                str(sdist.resolve()),
            ],
            cwd=sdist_root,
        )
        if status:
            return status
        rebuilt = sorted((sdist_root / "rebuilt").glob("*.whl"))
        if not rebuilt:
            raise DevError("source archive rebuild produced no wheel", 3)
        status = _check_installed_wheel(
            rebuilt[-1].resolve(),
            check_root / "rebuilt-wheel",
            acceptance,
        )
        if status:
            return status
    return 0


def check(*, rebuild_sdist: bool, dist: Path | None = None) -> int:
    dist = ROOT / "dist" if dist is None else dist
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if not wheels or not sdists:
        raise DevError("dist/ must contain a wheel and source archive; run package build", 2)
    with TemporaryDirectory(prefix="udb-package-check-") as directory:
        return _check_artifacts(
            wheels[-1],
            sdists[-1],
            rebuild_sdist=rebuild_sdist,
            check_root=Path(directory),
        )


def test() -> int:
    status = _run(
        python_command("-m", "pytest", "-q", "-m", "package"),
        cwd=ROOT,
    )
    if status:
        return status
    test_root = ROOT / "gen/package-test"
    shutil.rmtree(test_root, ignore_errors=True)
    artifacts = test_root / "artifacts"
    artifacts.mkdir(parents=True)
    status = _run(
        [
            _uv_executable(),
            "build",
            "--offline",
            "--no-config",
            "--python",
            sys.executable,
            "--out-dir",
            str(artifacts),
            str(ROOT),
        ],
        cwd=test_root,
    )
    if status:
        return status
    return check(rebuild_sdist=True, dist=artifacts)


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
    commands.add_parser("test")
    args = parser.parse_args(argv)
    if args.command == "build":
        return build(
            args.output,
            wheel_only=args.wheel_only,
            sdist_only=args.sdist_only,
        )
    if args.command == "check":
        return check(
            rebuild_sdist=args.rebuild_sdist or os.environ.get("usage_rebuild_sdist") == "true"
        )
    return test()


if __name__ == "__main__":
    raise SystemExit(entrypoint(main))

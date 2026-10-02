# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from pathlib import Path
from types import SimpleNamespace

from tools.dev import bootstrap, clean, container, doctor

ROOT = Path(__file__).resolve().parents[2]


def test_setup_plan_excludes_ruby_and_bundler() -> None:
    selected, commands = bootstrap.setup_commands(root=ROOT, toolchain="none")
    flattened = "\n".join(" ".join(command) for command in commands)
    assert selected == "none"
    assert "mise install" not in flattened
    assert "uv sync" not in flattened
    assert "bundle" not in flattened
    assert flattened == "prek install --prepare-hooks"


def test_toolchain_auto_selection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(container, "find_runtime", lambda: "/usr/bin/docker")
    assert bootstrap.choose_toolchain("auto", tmp_path) == "container"
    (tmp_path / ".toolchain-local").write_text("UDB_TOOLCHAIN_NONE=1\n", encoding="utf-8")
    assert bootstrap.choose_toolchain("auto", tmp_path) == "none"


def test_clean_and_clobber_preserve_toolchain(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        clean.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0)
    )
    for relative in (*clean.CLEAN_PATHS, *clean.CLOBBER_PATHS):
        path = tmp_path / relative
        path.mkdir(parents=True)
        (path / "owned").write_text("x", encoding="utf-8")
    (tmp_path / ".toolchain-local").write_text("UDB_TOOLCHAIN_NONE=1\n", encoding="utf-8")

    clean.clobber(tmp_path)

    assert not any(
        (tmp_path / relative).exists() for relative in (*clean.CLEAN_PATHS, *clean.CLOBBER_PATHS)
    )
    assert (tmp_path / ".toolchain-local").is_file()


def test_clean_constructs_legacy_isa_make_commands(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run(command, **_kwargs):
        calls.append(tuple(command))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(clean.subprocess, "run", fake_run)

    assert clean.clean(tmp_path) == 0
    assert calls == [
        ("make", "-C", str(tmp_path / "tests/isa"), "clean"),
        ("make", "-C", str(tmp_path / "tests/isa"), "XLEN=32", "clean"),
    ]


def test_container_command_construction(monkeypatch, tmp_path: Path) -> None:
    toolchain = tmp_path / ".toolchain"
    toolchain.mkdir()
    (toolchain / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    monkeypatch.setattr(container, "find_runtime", lambda: "/usr/bin/docker")
    monkeypatch.setattr(container, "image_exists", lambda _runtime, _image: False)

    command = container.command_for("build", root=tmp_path)

    assert command is not None
    assert command[:2] == ["/usr/bin/docker", "build"]
    assert container.image_name(tmp_path) in command


def test_doctor_json_and_failure_status(monkeypatch, capsys) -> None:
    checks = [
        doctor.Check("ok", "pass", "ready"),
        doctor.Check("optional", "warn", "missing", False),
        doctor.Check("bad", "fail", "broken"),
    ]
    monkeypatch.setattr(doctor, "collect_checks", lambda _root: checks)

    assert doctor.doctor("json", ROOT) == 1
    payload = json.loads(capsys.readouterr().out)
    assert [check["name"] for check in payload["checks"]] == ["ok", "optional", "bad"]


def test_doctor_checks_non_ruby_mise_tools(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".mise.toml").write_text(
        '[tools]\nruby = "3.4.10"\nuv = "0.12.10"\n"github-cli" = "2.100.0"\n',
        encoding="utf-8",
    )
    calls: list[tuple[str, ...]] = []

    def fake_run(command, **_kwargs):
        calls.append(tuple(command))
        if command[:2] == ["mise", "which"]:
            return subprocess.CompletedProcess(command, 0, f"/mise/{command[2]}\n", "")
        return subprocess.CompletedProcess(command, 0, f"{command[0]} 1.0\n", "")

    monkeypatch.setattr(doctor.subprocess, "run", fake_run)

    checks = doctor._mise_tool_checks(tmp_path)

    assert [check.name for check in checks] == ["mise-tool:uv", "mise-tool:github-cli"]
    assert ("mise", "which", "uv") in calls
    assert ("mise", "which", "gh") in calls
    assert all("ruby" not in command for command in calls)


def test_doctor_compiles_cxx_requirements_with_shared_check(monkeypatch, tmp_path: Path) -> None:
    shared = tmp_path / ".toolchain/check_cxx.cmake"
    shared.parent.mkdir()
    shared.write_text("# shared requirements\n", encoding="utf-8")
    cmake_lists = ""
    calls: list[tuple[str, ...]] = []

    def fake_run(command, **_kwargs):
        nonlocal cmake_lists
        calls.append(tuple(command))
        if command == ["mise", "which", "cmake"]:
            return subprocess.CompletedProcess(command, 0, "/mise/cmake\n", "")
        cmake_lists = (tmp_path / "gen/doctor-cxx-check/CMakeLists.txt").read_text()
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(doctor.subprocess, "run", fake_run)

    check = doctor._native_cxx_requirements_check(tmp_path, "/usr/bin/g++", required=True)

    assert check.status == "pass"
    assert f'include("{shared}")' in cmake_lists
    assert any("-DCMAKE_CXX_COMPILER=/usr/bin/g++" in command for command in calls)
    assert not (tmp_path / "gen/doctor-cxx-check").exists()


def test_mise_includes_developer_tasks_without_bin_dev() -> None:
    config = tomllib.loads((ROOT / ".mise.toml").read_text(encoding="utf-8"))
    assert config["task_config"]["includes"] == ["tools/dev/tasks.toml"]
    assert not (ROOT / "bin/dev").exists()
    assert not (ROOT / "tools/dev/cli.py").exists()


def test_core_tasks_are_discoverable_without_dependency_install() -> None:
    result = subprocess.run(
        ["mise", "tasks", "--no-header", "--name-only"],
        cwd=ROOT,
        env={**os.environ, "MISE_AUTO_INSTALL": "0"},
        check=True,
        capture_output=True,
        text=True,
    )
    names = set(result.stdout.splitlines())
    assert {"setup", "doctor", "clean", "clobber", "container:build"} <= names

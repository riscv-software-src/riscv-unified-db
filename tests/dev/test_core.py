# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
import os
import subprocess
import tomllib
from pathlib import Path

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


def test_clean_and_clobber_preserve_toolchain(tmp_path: Path) -> None:
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

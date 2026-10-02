# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from tools.dev import author, docs, fixtures, generate, package, quality, release
from tools.dev.common import DevError

ROOT = Path(__file__).resolve().parents[2]


def task_names() -> set[str]:
    result = subprocess.run(
        ["mise", "tasks", "--no-header", "--name-only"],
        cwd=ROOT,
        env={**os.environ, "MISE_AUTO_INSTALL": "0"},
        check=True,
        capture_output=True,
        text=True,
    )
    return set(result.stdout.splitlines())


def test_step9_task_tree_is_discoverable() -> None:
    expected = {
        "gen:all",
        "gen:quick",
        "gen:profile-configs",
        "gen:schema-docs",
        "gen:idl-grammar",
        "fixtures:list",
        "fixtures:refresh",
        "author:rvtest",
        "check",
        "check:data",
        "check:encodings",
        "check:csrs",
        "check:idl",
        "check:layouts",
        "check:schema-versions",
        "lint",
        "fmt",
        "test",
        "test:slow",
        "test:slow:idl",
        "test:slow:prose",
        "test:package",
        "check:all",
        "check:pre-commit",
        "test:java",
        "test:vscode",
        "docs:build",
        "docs:serve",
        "artifact:reuse-manifest",
        "artifact:resolved-unconfigured",
        "build:package",
        "build:wheel",
        "build:sdist",
        "package:check",
        "release:package",
        "release:schemas",
    }
    assert expected <= task_names()


def test_developer_tasks_use_uv_environment() -> None:
    source = (ROOT / "tools/dev/tasks.toml").read_text(encoding="utf-8")
    assert ".venv/bin/python" not in source
    assert "PYTHONPATH" not in source
    assert "UV_NO_SYNC" not in source
    assert "uv run --locked" not in source


def test_fixture_registry_marks_ruby_oracles_frozen(capsys) -> None:
    assert fixtures.list_fixtures("json") == 0
    entries = {entry["name"]: entry for entry in json.loads(capsys.readouterr().out)}
    assert entries["config-headers"]["refreshable"]
    assert entries["generic-codegen"]["refreshable"]
    for name in (
        "extension-documents",
        "instruction-table",
        "query-reports",
        "schema-docs",
    ):
        assert not entries[name]["refreshable"]
        assert "frozen" in entries[name]["detail"]


def test_fixture_commands_use_final_python_cli() -> None:
    commands = fixtures.commands_for("config-headers", check=True)
    flattened = [" ".join(command) for command in commands]
    assert any("udb generate config-c-header" in command for command in flattened)
    assert any("udb generate config-sv-header" in command for command in flattened)
    assert all(command.endswith("--check") for command in flattened)
    assert all("mise exec" not in command for command in flattened)


def test_generate_commands_and_api_deferment() -> None:
    assert "udb generate profile-configs" in " ".join(
        generate.leaf_command("profile-configs", check=True)
    )
    assert generate.leaf_command("idl-grammar", check=True)[-1] == "--check"
    with pytest.raises(DevError, match="deferred"):
        docs.build_commands("api")


def test_author_rvtest_creates_both_widths_and_refuses_overwrite(tmp_path: Path) -> None:
    for xlen in (32, 64):
        template = tmp_path / "tools/scripts" / f"new-rvtest-{xlen}-template.S"
        template.parent.mkdir(parents=True, exist_ok=True)
        template.write_text("TEST __INSTR__\n", encoding="utf-8")
        directory = tmp_path / f"tests/isa/rv{xlen}uv"
        directory.mkdir(parents=True)
        (directory / "Makefrag").write_text(f"rv{xlen}uv_sc_tests = old\n", encoding="utf-8")
    assert author.create_rvtest("new.inst", tmp_path) == 0
    for xlen in (32, 64):
        assert (tmp_path / f"tests/isa/rv{xlen}uv/new.inst.S").read_text(
            encoding="utf-8"
        ) == "TEST new.inst\n"
        assert "new.inst old" in (tmp_path / f"tests/isa/rv{xlen}uv/Makefrag").read_text(
            encoding="utf-8"
        )
    with pytest.raises(DevError, match="refusing to overwrite"):
        author.create_rvtest("new.inst", tmp_path)


def test_package_and_release_command_contracts(tmp_path: Path) -> None:
    command = package.build_command(tmp_path, wheel_only=True)
    assert command[-1] == "--wheel"
    assert command[:3] == [os.sys.executable, "-m", "build"]
    with pytest.raises(DevError, match="mutually exclusive"):
        package.build_command(tmp_path, wheel_only=True, sdist_only=True)
    with pytest.raises(DevError, match="requires --repository"):
        release.package_command(None)
    named = release.package_command("testpypi", ["dist/example.whl"])
    assert named[-1] == "dist/example.whl"
    assert "--index" in named
    url = release.package_command("https://packages.example/upload")
    assert "--publish-url" in url


def test_quality_commands_are_non_nested_and_checkable(monkeypatch) -> None:
    monkeypatch.setattr(
        quality,
        "selected_files",
        lambda _files, _all: ["tools/dev/quality.py", "bin/setup", ".mise.toml"],
    )
    lint = quality.lint_commands([], True)
    fmt = quality.format_commands([], True, check=True)
    flattened = [" ".join(command) for command in [*lint, *fmt]]
    assert any("ruff check" in command for command in flattened)
    assert any("shellcheck" in command for command in flattened)
    assert any("prettier --check" in command for command in flattened)
    assert all("mise exec" not in command for command in flattened)

# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Installed Typer command-tree and process-boundary contracts."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from udb.cli import app
from udb.cli import main as cli_main
from udb.cli_output import write_generated_source
from udb.commands.common import CliState, _progress_enabled

RUNNER = CliRunner()
REPOSITORY_ROOT = Path(__file__).parents[2]

LEAF_HELP = (
    ("list",),
    ("show",),
    ("inspect", "extension"),
    ("inspect", "parameter"),
    ("inspect", "extensions"),
    ("inspect", "parameters"),
    ("inspect", "csrs"),
    ("inspect", "encoding"),
    ("validate", "data"),
    ("validate", "cfg"),
    ("validate", "encodings"),
    ("validate", "csrs"),
    ("validate", "idl"),
    ("resolve",),
    ("idl", "compile"),
    ("idl", "eval"),
    ("idl", "check", "instruction"),
    ("generate", "schema-bundle"),
    ("generate", "profile-configs"),
    ("generate", "config-c-header"),
    ("generate", "config-sv-header"),
    ("generate", "c-encoding"),
    ("generate", "sv-decode"),
    ("generate", "go-encoding"),
    ("generate", "instruction-table"),
    ("generate", "extension-document"),
    ("generate", "schema-docs"),
    ("author", "layouts"),
    ("render", "pdf"),
)


def test_root_help_is_rich_grouped_and_has_completion() -> None:
    result = RUNNER.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Explore, validate, and generate artifacts" in result.stdout
    for group in ("Architecture", "Validation", "IDL", "Generation", "Authoring", "Rendering"):
        assert group in result.stdout
    assert "--install-completion" in result.stdout
    assert "--show-completion" in result.stdout
    assert "Examples:" in result.stdout


@pytest.mark.parametrize("command", LEAF_HELP)
def test_every_leaf_has_help(command: tuple[str, ...]) -> None:
    result = RUNNER.invoke(app, [*command, "--help"])

    assert result.exit_code == 0, result.output
    assert "Usage:" in result.stdout
    assert "--help" in result.stdout


def test_final_tree_has_no_transitional_commands() -> None:
    result = RUNNER.invoke(app, ["--help"])

    for removed in ("validate-cfg", "generate-layouts", "schemas", "disasm"):
        assert not re.search(rf"\b{re.escape(removed)}\b", result.stdout)


def test_udb_is_the_only_installed_or_repository_user_entrypoint() -> None:
    metadata = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["scripts"] == {"udb": "udb.cli:main"}
    for wrapper in ("udb", "idlc", "udb-gen", "generate"):
        assert not (REPOSITORY_ROOT / "bin" / wrapper).exists()


def test_version_and_usage_exit_codes() -> None:
    version = RUNNER.invoke(app, ["--version"])
    invalid = RUNNER.invoke(app, ["not-a-command"])

    assert version.exit_code == 0
    assert version.stdout.startswith("udb ")
    assert invalid.exit_code == 2


def test_process_boundary_usage_errors_are_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["not-a-command"]) == 2

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "Error: No such command 'not-a-command'.\n"


def test_progress_policy_respects_tty_quiet_and_terminal_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("udb.commands.common.sys.stderr.isatty", lambda: True)
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")

    assert _progress_enabled(CliState())
    assert not _progress_enabled(CliState(quiet=True))
    monkeypatch.setenv("NO_COLOR", "1")
    assert not _progress_enabled(CliState())
    monkeypatch.delenv("NO_COLOR")
    monkeypatch.setenv("TERM", "dumb")
    assert not _progress_enabled(CliState())


def test_global_options_must_precede_the_command() -> None:
    result = RUNNER.invoke(app, ["list", "extension", "--view", "raw"])

    assert result.exit_code == 2
    assert "No such option" in result.output


def test_non_database_commands_reject_database_options() -> None:
    result = RUNNER.invoke(app, ["--database", "missing", "idl", "eval", "1"])

    assert result.exit_code == 2
    assert "does not accept database options" in result.stderr
    assert "Traceback" not in result.stderr


def test_idl_errors_use_data_error_exit_code() -> None:
    result = RUNNER.invoke(
        app,
        ["idl", "check", "instruction", "-"],
        input="X[missing] = 15;\n",
    )

    assert result.exit_code == 2
    assert "no symbol named 'missing'" in result.stderr
    assert "internal error" not in result.stderr


def test_expected_negative_and_internal_exit_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("broken invariant")

    monkeypatch.setattr("udb.commands.query_impl.run_list", fail)
    normal = RUNNER.invoke(app, ["list", "extension"])
    debug = RUNNER.invoke(app, ["--debug", "list", "extension"])

    assert normal.exit_code == 4
    assert "internal error: broken invariant" in normal.stderr
    assert "Traceback" not in normal.stderr
    assert debug.exit_code == 4
    assert "Traceback" in debug.stderr


def test_atomic_output_and_check_drift(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "nested" / "artifact.txt"

    assert not write_generated_source(
        "first\n",
        output,
        artifact="test artifact",
        create_parents=True,
    )
    assert output.read_bytes() == b"first\n"
    assert not write_generated_source(
        "first\n",
        output,
        artifact="test artifact",
        check=True,
    )
    assert write_generated_source(
        "second\n",
        output,
        artifact="test artifact",
        check=True,
    )
    assert capsys.readouterr().out == f"{output}\n"
    assert output.read_bytes() == b"first\n"


def test_subprocess_help_is_clean_when_piped() -> None:
    environment = dict(os.environ)
    source_root = str(Path(__file__).parents[2] / "src")
    environment["PYTHONPATH"] = source_root
    completed = subprocess.run(
        [sys.executable, "-m", "udb", "--help"],
        check=False,
        capture_output=True,
        env=environment,
    )

    assert completed.returncode == 0
    assert b"Usage:" in completed.stdout
    assert b"\x1b[" not in completed.stdout + completed.stderr

# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Full native table comparisons against frozen, unmodified Ruby artifacts."""

import socket
import subprocess
from pathlib import Path

import pytest

from udb import Configuration, Database
from udb.instruction_table import render_instruction_table

FIXTURES = Path(__file__).parent / "fixtures/instruction_table"
ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize(
    ("config", "fixture"),
    [
        ("_", "native-all-stdout.txt"),
        ("rv32", "native-rv32-stdout.txt"),
        ("rv64", "native-rv64-stdout.txt"),
        ("cfgs/mc100-32-full-example.yaml", "native-full-stdout.txt"),
    ],
)
def test_bundled_complete_table_against_native_ruby(config, fixture):
    database = Database.bundled().resolve()
    configuration = (
        Configuration.from_file(ROOT / config)
        if config.endswith(".yaml")
        else Configuration.builtin(config)
    )
    architecture = database.configure(configuration)
    actual = render_instruction_table(architecture)
    # No normalization of semantic rows, provenance, whitespace, or ordering.
    assert actual.encode() == (FIXTURES / fixture).read_bytes()
    assert len([line for line in actual.splitlines() if not line.startswith("#")]) == 1400


def test_bundled_complete_file_table_against_genuine_integration_fixture():
    actual = render_instruction_table(Database.bundled(), file_name="test_table.txt")
    assert actual.encode() == (FIXTURES / "legacy-all-file.txt").read_bytes()


def test_source_tree_complete_table_matches_bundled_and_ruby():
    source = Database.from_path(ROOT / "spec/std/isa", schemas_path=ROOT / "spec/schemas").resolve()
    actual = render_instruction_table(source, file_name="test_table.txt")
    assert actual.encode() == (FIXTURES / "legacy-all-file.txt").read_bytes()


def test_default_source_uses_only_bundled_resources(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("generation must not open a checkout or run Ruby")

    monkeypatch.setattr(Database, "from_path", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    actual = render_instruction_table()
    assert actual.encode() == (FIXTURES / "native-all-stdout.txt").read_bytes()

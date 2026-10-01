# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import LiteralScalarString

from udb import ArchitectureCheck, ArchitectureCheckStatus, ArchitectureDiagnostic, Configuration
from udb.architecture import ConfiguredArchitecture
from udb.cli import main


def write_yaml(path, data):
    with path.open("w", encoding="utf-8") as stream:
        YAML().dump(data, stream)


@pytest.fixture
def inputs(tmp_path: Path):
    source = tmp_path / "isa"
    documents = {
        "ext/A.yaml": {
            "kind": "extension",
            "name": "A",
            "versions": [{"version": "1.0.0", "state": "ratified"}],
        },
        "param/MXLEN.yaml": {
            "kind": "parameter",
            "name": "MXLEN",
            "definedBy": True,
            "schema": {"type": "integer", "enum": [32, 64]},
        },
        "param/P.yaml": {
            "kind": "parameter",
            "name": "P",
            "definedBy": True,
            "schema": {"type": "integer", "minimum": 0, "maximum": 2},
            "requirements": {"idl()": LiteralScalarString("-> P > 0;")},
        },
    }
    for relative, document in documents.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        write_yaml(path, document)
    config = tmp_path / "configuration.yaml"
    config.write_text(
        json.dumps(
            {
                "$schema": "config_schema.json#",
                "kind": "architecture configuration",
                "type": "partially configured",
                "name": "example",
                "description": "CLI test",
                "params": {"MXLEN": 32, "P": 1},
                "mandatory_extensions": [],
            }
        ),
        encoding="utf-8",
    )
    return source, config


@pytest.mark.parametrize("value, exit_code, status", [(1, 0, "valid"), (0, 1, "unsat")])
def test_cli_checks_real_idl_constraints(inputs, capsys, value, exit_code, status):
    source, config = inputs
    data = json.loads(config.read_text(encoding="utf-8"))
    data["params"]["P"] = value
    config.write_text(json.dumps(data), encoding="utf-8")
    before = config.read_bytes()

    assert main(["--database", str(source), "validate", "cfg", "-c", str(config)]) == exit_code

    output = capsys.readouterr()
    assert output.out == f"example: {status}\n"
    assert ("unsatisfiable:" in output.err) is (exit_code == 1)
    assert config.read_bytes() == before


def test_cli_applies_explicit_overlay(inputs, tmp_path, capsys):
    source, config = inputs
    overlay = tmp_path / "overlay"
    (overlay / "param").mkdir(parents=True)
    write_yaml(
        overlay / "param" / "P.yaml",
        {"requirements": {"idl()": LiteralScalarString("-> P > 1;")}},
    )
    assert (
        main(
            [
                "--database",
                str(source),
                "--overlay",
                str(overlay),
                "validate",
                "cfg",
                "-c",
                str(config),
            ]
        )
        == 1
    )
    assert capsys.readouterr().out == "example: unsat\n"


def test_cli_reports_invalid_idl(inputs, capsys):
    source, config = inputs
    path = source / "param" / "P.yaml"
    document = YAML().load(path.read_text(encoding="utf-8"))
    document["requirements"] = {"idl()": LiteralScalarString("-> missing_parameter;")}
    write_yaml(path, document)

    assert main(["--database", str(source), "validate", "cfg", "-c", str(config)]) == 1
    output = capsys.readouterr()
    assert "invalid-idl-condition:" in output.err
    assert "param/P.yaml" in output.err
    assert "missing_parameter" in output.err


def test_cli_never_treats_deferred_as_success(inputs, capsys, monkeypatch):
    source, config = inputs
    monkeypatch.setattr(
        ConfiguredArchitecture,
        "check",
        lambda self: ArchitectureCheck(
            ArchitectureCheckStatus.DEFERRED,
            (ArchitectureDiagnostic("solver-unknown", "could not decide validity"),),
        ),
    )
    assert main(["--database", str(source), "validate", "cfg", "-c", str(config)]) == 2
    output = capsys.readouterr()
    assert output.out == "example: deferred\n"
    assert "solver-unknown: could not decide validity" in output.err


@pytest.mark.parametrize("malformed", [False, True])
def test_cli_reports_missing_or_malformed_configuration(inputs, capsys, malformed):
    source, config = inputs
    if malformed:
        config.write_text("name: invalid\n", encoding="utf-8")
    else:
        config.unlink()
    assert main(["--database", str(source), "validate", "cfg", "-c", str(config)]) == 2
    assert str(config) in capsys.readouterr().err


def test_cli_accepts_bundled_configuration_name(inputs, capsys, monkeypatch):
    source, config = inputs
    configuration = Configuration.from_file(config)
    names = []

    def builtin(name):
        names.append(name)
        return configuration

    monkeypatch.setattr(Configuration, "builtin", builtin)
    assert main(["--database", str(source), "validate", "cfg", "-c", "rv32"]) == 0
    assert names == ["rv32"]
    assert capsys.readouterr().out == "example: valid\n"

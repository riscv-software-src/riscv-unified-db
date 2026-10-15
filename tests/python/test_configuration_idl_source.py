# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from udb.configuration import Configuration, ConfigurationError

TEXT = """\
$schema: config_schema.json#
kind: architecture configuration
name: traced
description: Source capture
type: partially configured
mandatory_extensions: []
requirements:
  idl(): |
    -> true;
"""


def test_configuration_keeps_original_yaml_for_idl_mapping() -> None:
    config = Configuration.from_yaml(TEXT, source="custom-config.yaml")
    assert config.source_text == TEXT
    span = config.sources.at("requirements", "idl()")
    assert span is not None
    assert span.source == "custom-config.yaml"
    assert span.start_line == 8
    assert span.start_column == 10


def test_configuration_source_snapshot_survives_removed_file(tmp_path: Path) -> None:
    path = tmp_path / "custom.yaml"
    path.write_text(TEXT, encoding="utf-8")
    config = Configuration.from_file(path)
    path.unlink()
    assert config.source_text == TEXT
    assert config.sources.document == str(path)


def test_source_text_is_immutable_nonsemantic_metadata() -> None:
    captured = Configuration.from_yaml(TEXT)
    plain = Configuration(captured.to_dict())
    assert plain.source_text is None
    assert captured == plain
    assert "source_text" not in captured.to_dict()
    assert "source_text" not in repr(captured)
    with pytest.raises(FrozenInstanceError):
        captured.source_text = "changed"


@pytest.mark.parametrize("name", ["_", "rv32", "rv64"])
def test_bundled_configuration_retains_its_source(name: str) -> None:
    config = Configuration.builtin(name)
    assert isinstance(config.source_text, str)
    assert config.source_text
    assert config.sources.document == f"configs/{name}.yaml"


def test_invalid_explicit_source_text_is_rejected() -> None:
    config = Configuration.from_yaml(TEXT)
    with pytest.raises(ConfigurationError, match="source_text must be a string"):
        Configuration(config.to_dict(), source_text=7)

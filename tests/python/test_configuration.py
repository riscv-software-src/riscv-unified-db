# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from copy import deepcopy
from pathlib import Path

import pytest

from udb.configuration import Configuration, ConfigurationError, ConfigurationKind, Presence


def partial(**changes):
    return {
        "$schema": "config_schema.json#",
        "kind": "architecture configuration",
        "type": "partially configured",
        "name": "test",
        "description": "A test configuration",
        "mandatory_extensions": [{"name": "I", "version": ">= 2.1"}],
        **changes,
    }


def test_config_is_immutable_and_round_trips():
    data = partial(params={"MXLEN": 64, "EXAMPLE": [1, 2]}, requirements={"xlen": 64})
    original = deepcopy(data)
    config = Configuration(data)
    data["params"]["EXAMPLE"].append(3)
    assert config.params["EXAMPLE"] == (1, 2)
    with pytest.raises(TypeError):
        config.params["MXLEN"] = 32
    assert config.to_dict() == original
    assert Configuration(config.to_dict()) == config
    assert config.extensions[0].presence is Presence.MANDATORY
    assert config.kind is ConfigurationKind.PARTIAL


@pytest.mark.parametrize("name,width", [("_", None), ("rv32", 32), ("rv64", 64)])
def test_generic_configs_match_repository(name, width):
    root = Path(__file__).parents[2]
    bundled = Configuration.builtin(name)
    assert bundled.to_dict() == Configuration.from_file(root / "cfgs" / f"{name}.yaml").to_dict()
    assert bundled.mxlen == width


def test_full_config_requires_width_and_exact_versions():
    data = partial()
    del data["mandatory_extensions"]
    data.update(type="fully configured", params={}, implemented_extensions=[["I", "= 2.1"]])
    with pytest.raises(ConfigurationError, match="require MXLEN"):
        Configuration(data)
    data["params"]["MXLEN"] = 32
    config = Configuration(data)
    assert not config.additional_extensions
    assert str(config.extensions[0].requirements[0]) == "= 2.1.0"
    data["implemented_extensions"] = [{"name": "I", "version": ">= 2.1"}]
    with pytest.raises(ConfigurationError):
        Configuration(data)


def test_optional_prohibited_and_external_declarations():
    config = Configuration(
        partial(
            non_mandatory_extensions=[{"name": "M", "version": [">= 2.0", "< 3.0"]}],
            prohibited_extensions=[{"name": "V", "version": ">= 0"}],
            additional_extensions=False,
            arch_overlay="missing-overlay",
            compatible=["missing-config"],
        )
    )
    assert [item.presence for item in config.extensions] == [
        Presence.MANDATORY,
        Presence.OPTIONAL,
        Presence.PROHIBITED,
    ]
    assert len(config.extensions[1].requirements) == 2
    assert config.overlay == "missing-overlay"
    assert config.compatible == ("missing-config",)
    assert not config.additional_extensions


@pytest.mark.parametrize(
    "params,requirements,width",
    [
        ({"UXLEN": 64}, True, 64),
        ({"UXLEN": [32, 64]}, True, 64),
        ({"UXLEN": 32}, True, None),
        (
            {},
            {"param": {"anyOf": [{"name": "UXLEN", "equal": 64}, {"name": "SXLEN", "equal": 64}]}},
            64,
        ),
        (
            {},
            {"param": {"anyOf": [{"name": "UXLEN", "equal": 64}, {"name": "SXLEN", "equal": 32}]}},
            None,
        ),
    ],
)
def test_partial_width_inference(params, requirements, width):
    data = partial(params=params)
    if requirements is not True:
        data["requirements"] = requirements
    assert Configuration(data).mxlen == width


@pytest.mark.parametrize(
    "changes",
    [
        {"params": {"MXLEN": True}},
        {"params": {"MXLEN": 128}},
        {"params": {"P": {"nested": 1}}},
        {"params": {"P": [[1]]}},
        {"params": {"P": 1.5}},
        {
            "mandatory_extensions": [
                {"name": "I", "version": ">= 0"},
                {"name": "I", "version": "= 2.1"},
            ]
        },
    ],
)
def test_invalid_config_values(changes):
    with pytest.raises(ConfigurationError):
        Configuration(partial(**changes))


def test_config_errors_have_source_and_yaml_location():
    with pytest.raises(ConfigurationError, match=r"example\.yaml"):
        Configuration.from_yaml("name: [broken", source="example.yaml")
    text = """$schema: config_schema.json#
kind: architecture configuration
type: partially configured
name: test
description: test
mandatory_extensions: []
params:
  MXLEN: 128
"""
    with pytest.raises(ConfigurationError, match=r"example\.yaml:8:10"):
        Configuration.from_yaml(text, source="example.yaml")

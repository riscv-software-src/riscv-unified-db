# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from udb import Configuration, ConfigurationError, SchemaStore

IDL = {"idl()": "-> true;", "reason": "An IDL leaf in a YAML tree"}
PARAMETER = {"param": {"name": "P", "lessThan": 3}}


def configuration(requirements):
    return Configuration(
        {
            "$schema": "config_schema.json#",
            "kind": "architecture configuration",
            "type": "partially configured",
            "name": "mixed-conditions",
            "description": "Mixed ordinary and IDL conditions",
            "mandatory_extensions": [{"name": "Xbase", "version": ">= 1"}],
            "requirements": requirements,
        },
        schema_store=SchemaStore(Path(__file__).parents[2] / "spec" / "schemas"),
    )


@pytest.mark.parametrize("operator", ["allOf", "anyOf", "oneOf", "noneOf"])
def test_logical_conditions_accept_mixed_idl_and_yaml_leaves(operator):
    requirements = {operator: [deepcopy(IDL), deepcopy(PARAMETER)]}
    original = deepcopy(requirements)

    result = configuration(requirements)

    assert result.to_dict()["requirements"] == original
    assert requirements == original


@pytest.mark.parametrize(
    "requirements",
    [
        {"not": IDL},
        {"if": IDL, "then": PARAMETER},
        {"if": PARAMETER, "then": IDL},
        {"not": {"if": IDL, "then": {"oneOf": [PARAMETER, False]}}},
        {"allOf": [{"anyOf": [IDL, PARAMETER]}, {"not": False}]},
    ],
)
def test_nested_negation_and_implication_accept_idl(requirements):
    assert configuration(requirements).to_dict()["requirements"] == requirements


@pytest.mark.parametrize(
    "leaf",
    [
        {"idl()": 3},
        {"idl()": "-> true;", "unknown": True},
        {"idl()": "-> true;", "reason": False},
        {"unknown": True},
    ],
)
def test_mixed_conditions_still_reject_invalid_children(leaf):
    with pytest.raises(ConfigurationError, match="schema validation failed"):
        configuration({"allOf": [deepcopy(IDL), {"not": leaf}]})

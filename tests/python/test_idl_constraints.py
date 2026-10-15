# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from __future__ import annotations

from pathlib import Path

import pytest
from idl_semantics_helpers import run_semantic_case
from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]
YAML_LOADER = YAML(typ="safe")
GOOD = YAML_LOADER.load((ROOT / "tools/ruby-gems/idlc/test/idl/constraints.yaml").read_text())[
    "tests"
]
BAD = YAML_LOADER.load((ROOT / "tools/ruby-gems/idlc/test/idl/constraint_errors.yaml").read_text())[
    "tests"
]


def _setup(parameters):
    variables = []
    for name, value in (parameters or {}).items():
        if isinstance(value, bool):
            type_spec = "Boolean"
        elif isinstance(value, int):
            type_spec = f"Bits<{max(1, value.bit_length())}>"
        elif isinstance(value, str):
            type_spec = "String"
        elif isinstance(value, list):
            first = value[0]
            subtype = (
                "Boolean" if isinstance(first, bool) else f"Bits<{max(1, first.bit_length())}>"
            )
            type_spec = {"array": subtype, "width": len(value)}
        else:
            raise TypeError(f"unsupported constraint parameter {name}: {value!r}")
        variables.append({"name": name, "type": type_spec, "value": value})
    return {"vars": variables}


@pytest.mark.parametrize("entry", GOOD, ids=[f"constraint_{index}" for index in range(len(GOOD))])
def test_constraint_results(entry):
    result = run_semantic_case(
        {
            "root": "constraint_body",
            "text": entry["c"],
            "setup": _setup(entry.get("p")),
            "observe": {"constraint_satisfied": True},
        }
    )
    if entry["r"] is None:
        assert result["error"] == "type"
    else:
        assert result["ok"] is True
        assert result["satisfied"] is entry["r"]


@pytest.mark.parametrize("entry", BAD, ids=[f"bad_constraint_{index}" for index in range(len(BAD))])
def test_bad_constraints_are_rejected(entry):
    result = run_semantic_case(
        {
            "root": "constraint_body",
            "text": entry["c"],
            "setup": _setup(entry.get("p")),
            "observe": {"constraint_satisfied": True},
        }
    )
    if entry.get("r") is None:
        assert result["ok"] is False
        assert result["error"] == "type"
    else:
        assert result["satisfied"] is entry["r"]

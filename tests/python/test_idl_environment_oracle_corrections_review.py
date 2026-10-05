# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Catalog proofs may refine unknown versions, never other Ruby observations."""

from copy import deepcopy

import pytest
from idl_environment_oracle_corrections import corrected_environment_expectation

from udb import ObjectNotFoundError, ResolvedDatabase


def database():
    return ResolvedDatabase(
        {
            "ext/Xtest.yaml": {
                "kind": "extension",
                "name": "Xtest",
                "versions": [
                    {"version": "1.0.0", "state": "ratified"},
                    {"version": "2.0.0", "state": "ratified"},
                ],
            }
        }
    )


def test_refinement_is_exact_and_preserves_input_and_all_other_observations():
    frozen = {
        "extensions": {
            "Xtest": {
                "implemented": None,
                "implemented_version": {
                    "= 1.0.0": None,
                    ">= 2.0.0": None,
                    ">= 3.0.0": None,
                    "= 4.0.0": True,
                    "= 2.0.0": False,
                },
            }
        },
        "other": {"values": [1, 2, None]},
    }
    before = deepcopy(frozen)
    expected = corrected_environment_expectation(database(), frozen)
    assert frozen == before
    assert expected["extensions"]["Xtest"]["implemented_version"]["= 1.0.0"] is None
    assert expected["extensions"]["Xtest"]["implemented_version"][">= 2.0.0"] is None
    assert expected["extensions"]["Xtest"]["implemented_version"][">= 3.0.0"] is False
    assert expected["extensions"]["Xtest"]["implemented_version"]["= 4.0.0"] is True
    assert expected["extensions"]["Xtest"]["implemented_version"]["= 2.0.0"] is False
    expected["extensions"]["Xtest"]["implemented_version"][">= 3.0.0"] = None
    assert expected == frozen
    expected["other"]["values"].append(3)
    assert frozen == before


def test_unknown_extension_is_explicit_not_a_silent_correction():
    with pytest.raises(ObjectNotFoundError):
        corrected_environment_expectation(
            database(), {"extensions": {"missing": {"implemented_version": {">= 3.0.0": None}}}}
        )

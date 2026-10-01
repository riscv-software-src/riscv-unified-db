# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

from dataclasses import FrozenInstanceError

import pytest

from udb import Configuration, ResolvedDatabase
from udb.query_reports import InstructionMatcher, MatchingError, parse_encoding, possible_xlens


def small_database():
    return ResolvedDatabase(
        {
            "ext/I.yaml": {"kind": "extension", "name": "I", "versions": [{"version": "1.0"}]},
            "ext/X.yaml": {"kind": "extension", "name": "X", "versions": [{"version": "1.0"}]},
            "param/MXLEN.yaml": {
                "kind": "parameter",
                "name": "MXLEN",
                "definedBy": True,
                "schema": {"enum": [32, 64], "type": "integer"},
            },
            "inst/I/add.yaml": {
                "kind": "instruction",
                "name": "add",
                "definedBy": {"extension": {"name": "I"}},
                "assembly": "xd, imm",
                "encoding": {
                    "match": "-00000000------1",
                    "variables": [
                        {"name": "imm", "location": "15|6-4", "sign_extend": True, "left_shift": 1},
                        {"name": "xd", "location": "3-1", "not": [0], "alias": "rd"},
                    ],
                },
            },
            "inst/X/alias.yaml": {
                "kind": "instruction",
                "name": "alias",
                "definedBy": {"allOf": [{"extension": {"name": "X"}}, {"xlen": 64}]},
                "encoding": {
                    "match": "---------------1",
                    "variables": [{"name": "bits", "location": "15-1"}],
                },
            },
            "inst/X/wide.yaml": {
                "kind": "instruction",
                "name": "wide",
                "definedBy": {"extension": {"name": "X"}},
                "encoding": {
                    "match": "-------------------------------1",
                    "variables": [{"name": "bits", "location": "31-1"}],
                },
            },
        }
    )


@pytest.mark.parametrize("text", ["0x", "", " 13", "13\n", "-1", "0xz", "1_3", "+13", "0b10x"])
def test_malformed_hex(text):
    with pytest.raises(MatchingError):
        parse_encoding(text)


def test_hex_is_not_decimal_and_prefix_optional():
    assert [parse_encoding(text) for text in ("13", "0x13", "0X13")] == [19] * 3
    assert parse_encoding("0b10") == 0xB10
    for value in (-1, True, None, 1.2):
        with pytest.raises(MatchingError):
            parse_encoding(value)


def test_complete_structured_match_signed_scattered_fields_and_ambiguity():
    result = InstructionMatcher(small_database()).match(0x8031, width=16)
    assert [(part.xlen, [item.name for item in part.matches]) for part in result.results] == [
        (32, ["add"]),
        (64, ["add", "alias"]),
    ]
    match = result.results[0].matches[0]
    assert (match.mask, match.fixed_value, match.length, match.assembly) == (
        0x7F81,
        1,
        16,
        "xd, imm",
    )
    assert [
        (
            field.name,
            field.encoded_value,
            field.value,
            field.width,
            field.sign_extend,
            field.left_shift,
            field.alias,
            field.excluded,
        )
        for field in match.variables
    ] == [
        ("imm", 11, -10, 5, True, 1, None, False),
        ("xd", 0, 0, 3, False, 0, "rd", True),
    ]
    assert match.constraint_violations == ("xd",)
    assert not result.results[0].ambiguous and result.results[1].ambiguous
    with pytest.raises(FrozenInstanceError):
        match.name = "changed"


def test_legacy_mask_policy_and_explicit_width():
    matcher = InstructionMatcher(small_database())
    assert [item.name for item in matcher.match(1).results[1].matches] == ["add", "alias", "wide"]
    assert matcher.match(1).render() == matcher.match((1 << 40) | 1).render()
    assert [item.name for item in matcher.match(1, width=32).results[0].matches] == ["wide"]
    with pytest.raises(MatchingError, match="does not fit"):
        matcher.match(1 << 16, width=16)
    for width in (0, 8, 64, True):
        with pytest.raises(MatchingError):
            matcher.match(1, width=width)
    assert (
        matcher.match(0).render() == "RV32:\n  Illegal Instruction\nRV64:\n  Illegal Instruction\n"
    )


def test_configured_selection_is_explicit_not_catalog_default():
    database = small_database()
    config = Configuration(
        {
            "$schema": "config_schema.json#",
            "kind": "architecture configuration",
            "type": "fully configured",
            "name": "full",
            "description": "matching fixture",
            "implemented_extensions": [["I", "1.0"]],
            "params": {"MXLEN": 64},
        }
    )
    matcher = InstructionMatcher(database.configure(config))
    assert [item.name for item in matcher.match(1).results[0].matches] == ["add", "alias", "wide"]
    assert [item.name for item in matcher.match(1, selection="possible").results[0].matches] == [
        "add"
    ]
    assert [item.name for item in matcher.match(1, selection="mandatory").results[0].matches] == [
        "add"
    ]
    with pytest.raises(MatchingError, match="configuration filtering"):
        InstructionMatcher(database).match(1, selection="possible")
    with pytest.raises(MatchingError, match="not a possible"):
        matcher.match(1, xlen=32)


def test_effective_privilege_xlens_not_just_mxlen():
    documents = {path: dict(data) for path, data in small_database().documents.items()}
    for extension, parameters in (("S", ["SXLEN"]), ("U", ["UXLEN"]), ("H", ["VSXLEN", "VUXLEN"])):
        documents[f"ext/{extension}.yaml"] = {
            "kind": "extension",
            "name": extension,
            "versions": [{"version": "1.0"}],
        }
        for parameter in parameters:
            documents[f"param/{parameter}.yaml"] = {
                "kind": "parameter",
                "name": parameter,
                "definedBy": {"extension": {"name": extension}},
                "schema": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 2,
                    "items": {"type": "integer", "enum": [32, 64]},
                },
            }
    database = ResolvedDatabase(documents)

    def config(kind, *, extensions=None, params=None, **extra):
        return Configuration(
            {
                "$schema": "config_schema.json#",
                "kind": "architecture configuration",
                "name": "privilege",
                "description": "effective-mode fixture",
                "type": kind,
                (
                    "implemented_extensions"
                    if kind == "fully configured"
                    else "mandatory_extensions"
                ): extensions or [],
                "params": {"MXLEN": 64, **(params or {})},
                **extra,
            }
        )

    assert possible_xlens(database.configure(config("partially configured"))) == (32, 64)
    assert possible_xlens(database.configure(config("fully configured"))) == (64,)
    assert possible_xlens(
        database.configure(
            config(
                "fully configured",
                extensions=[["U", "1.0"]],
                params={"UXLEN": [32, 64]},
            )
        )
    ) == (32, 64)
    assert possible_xlens(
        database.configure(
            config(
                "fully configured",
                extensions=[["U", "1.0"]],
                params={"UXLEN": [64]},
            )
        )
    ) == (64,)
    assert possible_xlens(
        database.configure(
            config(
                "partially configured",
                params={"MXLEN": 32},
            )
        )
    ) == (32,)
    assert possible_xlens(
        database.configure(
            config(
                "partially configured",
                prohibited_extensions=[{"name": name} for name in ("S", "U", "H")],
            )
        )
    ) == (64,)

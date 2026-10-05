# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Black-box differential tests for IDL expression type-checking/evaluation
(``udb.idl.ast`` semantic methods: ``type_check``/``type``/``value``/``values``).

Every expectation in ``tests/python/data/idl/expressions.json`` is a reviewed, frozen capture from
the retired implementation. Nothing here talks to Ruby at test time, and the capture has no
refresh command.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from udb.idl import parser
from udb.idl.ast import UnknownLiteral
from udb.idl.errors import IdlInternalError, IdlSyntaxError, IdlTypeError, IdlValueUnknown
from udb.idl.symbols import EnumDef, IdlEnvironment, SymbolTable, Var
from udb.idl.types import BitfieldType, StructType, Type, TypeKind

DATA_FILE = Path(__file__).parent / "data" / "idl" / "expressions.json"
IDL_DATA_DIR = DATA_FILE.parent

# The oracle stamps the Ruby AST's source label with "[EXPRESSION]" (Idl::Compiler#compile_expression
# hard-codes this); passing the same label to the Python parser makes error messages -- which embed
# "In file <label>" -- byte-identical instead of merely equal-modulo-label.
EXPRESSION_LABEL = "[EXPRESSION]"


def _load_cases() -> list[dict[str, Any]]:
    doc = json.loads(DATA_FILE.read_text())
    cases = doc["cases"]
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "duplicate case ids in expressions.json"
    return cases


CASES = _load_cases()
OK_CASES = [c for c in CASES if c["expect"]["ok"]]
ERROR_CASES = [c for c in CASES if not c["expect"]["ok"]]

# Cases where Python intentionally differs from a confirmed Ruby bug (see
# doc/python-migration-bugfixes.md). Maps case id -> the *fully corrected* expectation (not a
# partial merge, since some corrections flip "ok" itself and drop the error-schema fields), so
# the test documents exactly what differs and why.
RUBY_BUG_CORRECTIONS: dict[str, dict[str, Any]] = {
    # Ruby bug entry 26: ConcatenationExpressionAst#type's `is_const` local is initialized to
    # `true` and never updated from each element's `e_type.const?`, so Ruby always reports
    # concatenation's qualifiers as `[:const]` even when an operand is a non-const variable.
    # `{a, 1'b1}` with non-const `a` should NOT be const.
    "adv:concat_const_var": {
        "ok": True,
        "type": "Bits<4>",
        "kind": "bits",
        "width": 4,
        "qualifiers": [],
        "value": "11",
        "value_known": True,
        "to_idl": "{a,1'b1}",
        "warnings": "",
    },
    # Ruby bug entry 27: division/modulo by zero raises an uncaught Ruby `ZeroDivisionError`
    # instead of a catchable value error, so `4 / 0` crashes the compiler outright.
    "adv:div_by_zero_known": {
        "ok": True,
        "type": "const known Bits<3>",
        "kind": "bits",
        "width": 3,
        "qualifiers": ["const", "known"],
        "value": None,
        "value_known": False,
        "to_idl": "(4 / 0)",
        "warnings": "",
    },
    "adv:mod_by_zero_known": {
        "ok": True,
        "type": "const known Bits<3>",
        "kind": "bits",
        "width": 3,
        "qualifiers": ["const", "known"],
        "value": None,
        "value_known": False,
        "to_idl": "(4 % 0)",
        "warnings": "",
    },
    # Ruby bug entry 27 (continued): `&&`/`||`'s `type`/`type_check` eagerly evaluate both
    # operands' values to look for a short circuit, so even a short-circuited zero divisor
    # crashes -- e.g. `false && (1 / 0 == 0)` should short-circuit on `false` without ever
    # evaluating the zero-divisor rhs.
    "adv:logical_and_shortcircuit_false": {
        "ok": True,
        "type": "const Boolean",
        "kind": "boolean",
        "width": None,
        "qualifiers": ["const"],
        "value": False,
        "value_known": True,
        "to_idl": "(false && (((1 / 0) == 0)))",
        "warnings": "",
    },
    "adv:logical_or_shortcircuit_true": {
        "ok": True,
        "type": "const Boolean",
        "kind": "boolean",
        "width": None,
        "qualifiers": ["const"],
        "value": True,
        "value_known": True,
        "to_idl": "(true || (((1 / 0) == 0)))",
        "warnings": "",
    },
    # Ruby bug entry 28: `IntLiteralAst#type` only treats a lowercase `x` as an unknown bit when
    # deciding the `:known` qualifier, so `4'bX011` (uppercase) is reported `known` even though
    # `unsigned_value`/`value` (which are case-insensitive) compute a genuinely partial value.
    "adv:lit_unknown_bits_upper_x": {
        "ok": True,
        "type": "const Bits<4>",
        "kind": "bits",
        "width": 4,
        "qualifiers": ["const"],
        "value": "4'bx011",
        "value_known": True,
        "to_idl": "4'bX011",
        "warnings": "",
    },
    # Ruby bug entry 18: the basic-decimal branch of `IntLiteralAst#width` reads the wrong regex
    # capture group and drops the sign bit for signed decimal literals (`63s` has width 6 instead
    # of 7); Python adds the sign bit for every signed form.
    "adv:lit_signed_decimal": {
        "ok": True,
        "type": "signed const known Bits<7>",
        "kind": "bits",
        "width": 7,
        "qualifiers": ["const", "known", "signed"],
        "value": "63",
        "value_known": True,
        "to_idl": "63s",
        "warnings": "",
    },
    "adv:lit_signed_decimal_neg": {
        "ok": True,
        "type": "signed const known Bits<2>",
        "kind": "bits",
        "width": 2,
        "qualifiers": ["const", "known", "signed"],
        "value": "-1",
        "value_known": True,
        "to_idl": "-1s",
        "warnings": "",
    },
    # Ruby bug entry 30: `IntLiteralAst#value` for a verilog-style explicit-width signed literal
    # additionally requires `unsigned_value.bit_length > (width - 1)` before computing the
    # negative two's-complement value; that condition is always true whenever the sign bit is
    # set, so Ruby's `value()` never actually returns a negative value for such a literal.
    "adv:lit_verilog_signed_overflow": {
        "ok": True,
        "type": "signed const known Bits<8>",
        "kind": "bits",
        "width": 8,
        "qualifiers": ["const", "known", "signed"],
        "value": "-56",
        "value_known": True,
        "to_idl": "8'sd200",
        "warnings": "",
    },
    "adv:unary_neg_signed": {
        "ok": True,
        "type": "signed const known Bits<4>",
        "kind": "bits",
        "width": 4,
        "qualifiers": ["const", "known", "signed"],
        "value": "1",
        "value_known": True,
        "to_idl": "-(4'shf)",
        "warnings": "",
    },
    # Ruby bug entry 19: `ArrayIncludesAst#to_idl` emits `$array_size(a, 1)` for
    # `$array_includes?(a, 1)`, which does not reparse to the same call.
    "adv:array_includes_enum": {
        "ok": True,
        "type": "Boolean",
        "kind": "boolean",
        "width": None,
        "qualifiers": [],
        "value": True,
        "value_known": True,
        "to_idl": "$array_includes?($enum_to_a(PrivilegeMode), 1)",
        "warnings": "",
    },
    "adv:array_includes_missing": {
        "ok": True,
        "type": "Boolean",
        "kind": "boolean",
        "width": None,
        "qualifiers": [],
        "value": False,
        "value_known": True,
        "to_idl": "$array_includes?($enum_to_a(PrivilegeMode), 7)",
        "warnings": "",
    },
    # Ruby bug entry 18 (continued): since `(-1s)`'s width is corrected from 1 to 2, the type
    # error message for comparing it against an unsigned literal necessarily differs in the
    # type name it embeds, even though the underlying "not comparable" diagnosis is identical.
    "adv:signed_lt_negative": {
        "ok": False,
        "error": "type",
        "message": (
            "In file [EXPRESSION]\nOn line 1\nIn the code:\n\n"
            "  0: **HERE** >> (-1s) < 1 << **HERE**\n\n"
            "A type error occurred\n"
            "  (-1s) (type = signed const known Bits<2>) and 1 (type = const known Bits<1>) "
            "are not comparable\n"
        ),
    },
}


def _enum_def(spec: dict[str, Any]) -> EnumDef:
    elements = spec["elements"]
    return EnumDef(
        name=spec["name"],
        element_names=tuple(elements.keys()),
        element_values=tuple(elements.values()),
    )


def _bind(symtab: SymbolTable, name: str, value: Any) -> None:
    """Bind ``name`` in a pushed scope, mirroring the oracle's Ruby ``bind`` helper."""
    if isinstance(value, bool):
        symtab.add(name, Var(name, Type(TypeKind.BOOLEAN), value))
    elif isinstance(value, int):
        width = value.bit_length() or 1
        symtab.add(name, Var(name, Type(TypeKind.BITS, width=width), value))
    elif isinstance(value, str):
        symtab.add(name, Var(name, Type(TypeKind.STRING), value))
    elif isinstance(value, dict) and "bitfield" in value:
        spec = value["bitfield"]
        fields = spec["fields"]
        bf = BitfieldType(
            spec["name"],
            spec["width"],
            tuple(fields.keys()),
            tuple(range(lo, hi + 1) for lo, hi in fields.values()),
        )
        symtab.add(name, Var(name, bf, value["value"]))
    elif isinstance(value, dict) and "struct" in value:
        spec = value["struct"]
        members = spec["members"]
        st = StructType(
            spec["name"],
            tuple(Type(TypeKind.BITS, width=w) for w in members.values()),
            tuple(members.keys()),
        )
        symtab.add(name, Var(name, st, value["value"]))
    else:
        raise TypeError(f"unsupported parameter {name}: {value!r}")


def _build_symtab(case: dict[str, Any]) -> SymbolTable:
    builtin_enums = tuple(_enum_def(spec) for spec in case.get("enums", []))
    symtab = SymbolTable(IdlEnvironment(builtin_enums=builtin_enums))
    params = case.get("params", {})
    if params:
        symtab.push(None)
        for name, value in params.items():
            _bind(symtab, name, value)
    return symtab


def _encode(value: Any) -> Any:
    """Mirror the oracle's Ruby ``encode``: integers (not bools) become decimal strings.

    ``UnknownLiteral`` values fall through Ruby's ``encode`` unchanged (it is neither
    ``Integer``, ``Array``, nor ``Hash``), and are then serialized by ``JSON.generate``'s
    default ``Object#to_json`` fallback, which calls ``#to_s``. Python does that
    stringification explicitly here.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, UnknownLiteral):
        return str(value)
    if isinstance(value, list):
        return [_encode(v) for v in value]
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    return value


def _width_field(t: Type) -> Any:
    if t.kind != TypeKind.BITS:
        return None
    width = t.width
    return width if isinstance(width, int) else str(width)


def _evaluate(case: dict[str, Any]) -> dict[str, Any]:
    """Run one case through the Python implementation, producing the oracle's result schema."""
    symtab = _build_symtab(case)
    try:
        node = parser.parse_expression(case["text"], label=EXPRESSION_LABEL)
        node.type_check(symtab, strict=False)
        t = node.type(symtab)

        known = True
        value: Any = None
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                value = node.value(symtab)
            except IdlValueUnknown:
                known = False
            warning_text = "".join(str(w.message) for w in caught)

        return {
            "ok": True,
            "type": str(t),
            "kind": str(t.kind),
            "width": _width_field(t),
            "qualifiers": sorted(q.value for q in t.qualifiers),
            "value": _encode(value) if known else None,
            "value_known": known,
            "to_idl": node.to_idl(),
            "warnings": warning_text,
        }
    except IdlTypeError as e:
        return {"ok": False, "error": "type", "message": e.message}
    except IdlInternalError as e:
        return {"ok": False, "error": "internal", "message": e.message}
    except IdlSyntaxError as e:
        return {"ok": False, "error": "syntax", "message": str(e)}


@pytest.mark.parametrize("case", OK_CASES, ids=[c["id"] for c in OK_CASES])
def test_ok_case_matches_ruby_oracle(case: dict[str, Any]) -> None:
    actual = _evaluate(case)
    expected = RUBY_BUG_CORRECTIONS.get(case["id"], case["expect"])
    assert actual == expected


@pytest.mark.parametrize("case", ERROR_CASES, ids=[c["id"] for c in ERROR_CASES])
def test_error_case_matches_ruby_oracle(case: dict[str, Any]) -> None:
    actual = _evaluate(case)
    expected = RUBY_BUG_CORRECTIONS.get(case["id"], case["expect"])
    if expected["ok"] is False:
        assert actual["ok"] is False
        assert actual["error"] == expected["error"]
        assert actual["message"] == expected["message"]
    else:
        assert actual == expected


def _yaml_entries(filename: str) -> list[dict[str, Any]]:
    document = YAML(typ="safe").load((IDL_DATA_DIR / filename).read_text(encoding="utf-8"))
    return document["tests"]


def _bind_fixture_value(symtab: SymbolTable, name: str, value: Any) -> None:
    if isinstance(value, bool):
        symtab.add(name, Var(name, Type(TypeKind.BOOLEAN), value))
    elif isinstance(value, int):
        symtab.add(name, Var(name, Type(TypeKind.BITS, width=value.bit_length() or 1), value))
    elif isinstance(value, str):
        symtab.add(name, Var(name, Type(TypeKind.STRING), value))
    else:
        raise TypeError(f"Unexpected fixture value for {name}: {value!r}")


def _run_expression_fixture(entries: list[dict[str, Any]]) -> None:
    for index, entry in enumerate(entries):
        symtab = SymbolTable(IdlEnvironment())
        if "p" in entry:
            symtab.push(None)
            for name, value in entry["p"].items():
                _bind_fixture_value(symtab, name, value)

        expression = parser.parse_expression(entry["e"], label=EXPRESSION_LABEL)
        expression.type_check(symtab, strict=False)
        expected = parser.parse_expression(entry["="], label=EXPRESSION_LABEL)
        expected.type_check(symtab, strict=False)

        assert expression.value(symtab) == expected.value(symtab), (
            f"entry {index} ({entry.get('d', entry['e'])!r})"
        )


def test_literals_fixture_self_consistency() -> None:
    _run_expression_fixture(_yaml_entries("literals.yaml"))


def test_expressions_fixture_self_consistency() -> None:
    _run_expression_fixture(_yaml_entries("expressions.yaml"))


# --- Regressions from the slice 14 cross-family review ---------------------------------------


def _eval(text: str, symtab: SymbolTable) -> tuple[str, Any]:
    node = parser.parse_expression(text, label=EXPRESSION_LABEL)
    node.type_check(symtab, strict=False)
    return str(node.type(symtab)), node.value(symtab)


def test_id_type_follows_the_current_scope() -> None:
    # Ruby's IdAst#type never memoizes, so a shadowing binding changes the type of a reused AST.
    node = parser.parse_expression("a + 1", label=EXPRESSION_LABEL)
    symtab = SymbolTable(IdlEnvironment())
    symtab.push(None)
    symtab.add("a", Var("a", Type(TypeKind.BITS, width=2), 2))
    assert (str(node.type(symtab)), node.value(symtab)) == ("Bits<2>", 3)
    symtab.push(None)
    symtab.add("a", Var("a", Type(TypeKind.BITS, width=8), 128))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert (str(node.type(symtab)), node.value(symtab)) == ("Bits<8>", 129)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Ruby's Integer#<< and #>> reverse direction for a negative count.
        ("$signed(8'd255) << $signed(8'd255)", -1),
        ("$signed(8'd254) >> $signed(8'd255)", -4),
        # Ruby's Integer#[] returns 0 for a negative bit index.
        ("8'd255[$signed(8'd255)]", 0),
        # Ruby's arithmetic-shift masking with a negative count, reproduced exactly.
        ("$signed(8'd255) >>> $signed(8'd255)", -2),
        ("8'd128 >>> $signed(8'd255)", -256),
    ],
)
def test_negative_shift_amounts_follow_ruby(text: str, expected: int) -> None:
    symtab = SymbolTable(IdlEnvironment())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert _eval(text, symtab)[1] == expected


@pytest.mark.parametrize(
    "text",
    [
        *(
            f"4'b10x1 {op} 4'd1"
            for op in ["+", "-", "*", "/", "%", "^", ">>", ">>>", "<", ">", ">="]
        ),
        *(f"4'd1 {op} 4'b10x1" for op in ["+", "&", "|", "<", "<=", ">>>"]),
    ],
)
def test_unknown_bit_operands_give_an_unknown_value(text: str) -> None:
    # Ruby crashes on each of these (bug-log entry 31).
    symtab = SymbolTable(IdlEnvironment())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with pytest.raises(IdlValueUnknown):
            _eval(text, symtab)


def test_shifting_unknown_bits_truncates_both_masks() -> None:
    # Ruby crashes in Rvalue#truncate (bug-log entry 32).
    symtab = SymbolTable(IdlEnvironment())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert _eval("4'b10x1 << 4'd4", symtab)[1] == 0


def test_unsized_unknown_bit_literal_evaluates_to_its_partial_value() -> None:
    # Ruby crashes here (bug-log entry 29); Python returns the partially-known value, exactly as it
    # does for the sized literal 4'b10x1.
    symtab = SymbolTable(IdlEnvironment())
    unsized = parser.parse_expression("'b10x1", label=EXPRESSION_LABEL)
    sized = parser.parse_expression("4'b10x1", label=EXPRESSION_LABEL)
    assert isinstance(unsized.value(symtab), UnknownLiteral)
    assert unsized.value(symtab) == sized.value(symtab)

# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""The single adaptation layer for Python/Ruby IDL semantic observations.

Every assumption about the public API belongs here, not in test modules.
The contract is ``doc/stage4-idl.md``:

* semantic methods live on AST nodes and accept an explicit ``SymbolTable``;
* methods are named ``type_check``, ``type``, ``value``, ``values``,
  ``execute``, ``return_type``, ``return_value``, ``return_values`` and
  ``const_eval``;
* unknown values raise ``IdlValueUnknown``;
* semantic failures raise ``IdlTypeError``/``IdlInternalError``;
* function definitions additionally expose ``add_symbol``,
  ``semantic_arguments`` and qualifier predicates.

If the implementation chooses a different spelling for a semantic helper,
adapt it here. Tests outside this module use only the functions exported by
``__all__``.
"""

from __future__ import annotations

import contextlib
import copy
import io
import warnings
from dataclasses import dataclass
from typing import Any

from udb.idl import (
    FunctionDef,
    IdlInternalError,
    IdlSyntaxError,
    IdlTypeError,
    IdlValueUnknown,
    Isa,
    parse_constraint_body,
    parse_expression,
    parse_for_loop,
    parse_function_body,
    parse_isa,
)
from udb.idl.symbols import IdlEnvironment, SymbolTable, Var
from udb.idl.types import VOID_TYPE, WIDTH_UNKNOWN, Qualifier, Type, TypeKind, XregType

__all__ = [
    "RUBY_BUG_CORRECTIONS",
    "assert_case_matches",
    "compile_constraint",
    "compile_expression",
    "compile_for_loop",
    "compile_func_body",
    "compile_isa",
    "make_symtab",
    "run_semantic_case",
    "type_to_str",
]


RUBY_BUG_CORRECTIONS: dict[str, dict[str, Any]] = {
    **{
        f"adv_loop_sum_{limit}": {
            "expect_patch": {"return_values": {"known": True, "value": [str(limit)]}},
            "ruby_bug": "Statement review F3: replay uses stale assignment Var bindings",
        }
        for limit in range(1, 13)
    },
    **{
        f"adv_reassign_bits_{width}": {
            "expect_patch": {"return_values": {"known": True, "value": [str(width)]}},
            "symbol_value_patch": {"x": {"known": True, "value": str(width)}},
            "ruby_bug": "Statement review F3: replay uses stale assignment Var bindings",
        }
        for width in range(2, 18)
    },
    "adv_uninitialized_then_assign": {
        "expect_patch": {"return_values": {"known": True, "value": ["3"]}},
        "ruby_bug": "Statement review F3: replay uses stale assignment Var bindings",
    },
    "adv_multi_declaration": {
        "expect_patch": {"return_values": {"known": True, "value": ["6"]}},
        "ruby_bug": "Statement review F3: replay uses stale assignment Var bindings",
    },
    "adv_nested_loops": {
        "expect_patch": {"return_values": {"known": True, "value": ["6"]}},
        "ruby_bug": "Statement review F3: replay uses stale assignment Var bindings",
    },
    "adv_conditional_assignment_true": {
        "expect_patch": {"return_values": {"known": True, "value": ["7"]}},
        "ruby_bug": "Statement review F3: replay uses stale assignment Var bindings",
    },
    "ruby_type__primitive_types_bits__bits_literal_c_style_signed": {
        "expect_patch": {
            "type": {
                "text": "signed const known Bits<5>",
                "kind": "bits",
                "width": "5",
                "qualifiers": ["const", "known", "signed"],
            }
        },
        "ruby_bug": "Migration entry 18: decimal signed literals lose the sign bit",
    },
    "ruby_type__operators_concat_replic_extended__replication_with_concatenation": {
        "expect_patch": {
            "type": {
                "text": "known Bits<8>",
                "kind": "bits",
                "width": "8",
                "qualifiers": ["known"],
            }
        },
        "ruby_bug": "Migration entry 26: concatenation incorrectly forces the const qualifier",
    },
    "ruby_type__operators_concat_replic_extended__concatenation_with_extraction": {
        "expect_patch": {
            "type": {
                "text": "known Bits<8>",
                "kind": "bits",
                "width": "8",
                "qualifiers": ["known"],
            }
        },
        "ruby_bug": "Migration entry 26: concatenation incorrectly forces the const qualifier",
    },
    "adv_truncation_warning_unary": {
        "expect_patch": {
            "value": {"known": True, "value": "-8"},
            "warnings": (
                "In file [EXPRESSION]\nOn line 1\n  A value was truncated\n"
                "  -4'sd8 is truncated due to insufficient bit width (from 8 to -8).\n"
                "  Perhaps you want to use a widening operator (`+, `-, `*, `<<)?\n"
            ),
        },
        "ruby_bug": "Migration entry 30: explicit-width signed literals never return negative values",
    },
    "adv_duplicate_same_scope": {
        "expect": {
            "ok": False,
            "error": "type",
            "class": "Idl::AstNode::TypeError",
            "message": (
                "In file adv_duplicate_same_scope\nOn line 1\nIn the code:\n\n"
                "  0: Bits<8> x = 1; **HERE** >> Bits<8> x = 2 << **HERE**;\n\n"
                "A type error occurred\n  Variable 'x' is already declared in this scope"
            ),
        },
        "python_policy": "Same-scope declarations are rejected; outer-scope shadowing is legal",
    },
    "adv_csr_address": {
        "expect_patch": {"to_idl": "CSR[mockcsr].address()"},
        "ruby_bug": "Ruby drops the CSR[] wrapper in CsrFunctionCallAst#to_idl (ast.rb:9719)",
    },
    "adv_csr_field_ro": {
        "expect_patch": {"const_eval": True},
        "ruby_bug": (
            "CsrFieldReadExpressionAst#const_eval? is `!@value.nil?`, but @value is never "
            "assigned in the class (ast.rb ~9334), so it always reports false even for a "
            "known RO field whose value() succeeds"
        ),
    },
    "adv_csr_sw_read": {
        "expect_patch": {"to_idl": "CSR[mockcsr].sw_read()"},
        "ruby_bug": "Ruby drops the CSR[] wrapper in CsrFunctionCallAst#to_idl (ast.rb:9719)",
    },
    "post_decrement_assignment_rhs": {
        "root": "function_body",
        "text": "Bits<8> i = 3; Bits<8> a = 0; a = i--;",
        "error": IdlTypeError,
        "message": "Post-decrement is not a valid assignment right-hand side",
        "ruby_bug": "Ruby crashes in ast.rb:2845 while lowering `a = i--;`",
    },
    "wrong_function_argument_type": {
        "root": "isa",
        "text": (
            "%version: 1.0\n"
            "function f { arguments Boolean a description { f } body { } }\n"
            "function c { description { c } body { f(1); } }\n"
        ),
        "error": IdlTypeError,
        "message_contains": "Wrong type for argument number 1",
        "ruby_bug": (
            "Ruby passes five arguments to FunctionType#argument_type at ast.rb:7874 "
            "while formatting this diagnostic"
        ),
    },
}


@dataclass(frozen=True)
class _RegisterFile:
    name: str
    register_length: str
    registers: tuple[object, ...]


@dataclass(frozen=True)
class _CsrField:
    name: str
    field_width: int
    reset_value: object
    field_type: str
    bases: tuple[int, ...]
    exists: bool

    @property
    def defined_in_all_bases(self) -> bool:
        return set(self.bases) == {32, 64}

    @property
    def defined_in_base32(self) -> bool:
        return 32 in self.bases

    @property
    def defined_in_base64(self) -> bool:
        return 64 in self.bases

    @property
    def base64_only(self) -> bool:
        return self.bases == (64,)

    @property
    def base32_only(self) -> bool:
        return self.bases == (32,)

    def width(self, _xlen: int | None = None) -> int:
        return self.field_width

    def type(self, _xlen: int | None = None) -> str:
        return self.field_type


@dataclass(frozen=True)
class _Csr:
    name: str
    address: int
    max_length: int
    value: object
    fields: tuple[_CsrField, ...]

    def length(self, _base: int | None = None) -> int:
        return self.max_length


def _type_from_spec(spec: Any, mxlen: int | None) -> Type:
    if isinstance(spec, dict):
        return Type(
            TypeKind.ARRAY,
            width=spec["width"],
            sub_type=_type_from_spec(spec["array"], mxlen),
        )
    text = str(spec).strip()
    qualifiers: list[Qualifier] = []
    for word, qualifier in (
        ("const", Qualifier.CONST),
        ("signed", Qualifier.SIGNED),
        ("global", Qualifier.GLOBAL),
        ("known", Qualifier.KNOWN),
    ):
        if text.startswith(f"{word} "):
            qualifiers.append(qualifier)
            text = text.removeprefix(f"{word} ")
    if text.startswith("Bits<") and text.endswith(">"):
        raw_width = text[5:-1]
        width: int | str = WIDTH_UNKNOWN if raw_width == "unknown" else int(raw_width)
        return Type(TypeKind.BITS, width=width, max_width=mxlen or 64, qualifiers=qualifiers)
    if text == "XReg":
        result: Type = XregType(mxlen or 64)
        for qualifier in qualifiers:
            result = result.qualify(qualifier)
        return result
    aliases = {
        "U32": Type(TypeKind.BITS, width=32, qualifiers=qualifiers),
        "U64": Type(TypeKind.BITS, width=64, qualifiers=qualifiers),
        "Boolean": Type(TypeKind.BOOLEAN, qualifiers=qualifiers),
        "String": Type(TypeKind.STRING, qualifiers=qualifiers),
        "void": VOID_TYPE,
        "Void": VOID_TYPE,
    }
    try:
        return aliases[text]
    except KeyError:
        raise AssertionError(f"unsupported test type spec: {spec!r}") from None


def make_symtab(setup: dict[str, Any] | None = None) -> SymbolTable:
    setup = setup or {}
    mxlen = setup.get("mxlen")
    register_files = tuple(
        _RegisterFile(
            rf["name"],
            f"return {rf['width']};",
            tuple(object() for _ in range(rf.get("count", 32))),
        )
        for rf in setup.get("register_files", ())
    )
    csrs = tuple(
        _Csr(
            csr["name"],
            csr["address"],
            csr.get("length", 32),
            csr.get("value"),
            tuple(
                _CsrField(
                    field["name"],
                    field["width"],
                    field.get("value"),
                    field.get("type", "RW" if field.get("value") is None else "RO"),
                    tuple(field.get("bases", (32, 64))),
                    field.get("exists", True),
                )
                for field in csr.get("fields", ())
            ),
        )
        for csr in setup.get("csrs", ())
    )
    possible_xlens = tuple(setup.get("possible_xlens", (32, 64)))
    env = IdlEnvironment(
        mxlen=mxlen,
        possible_xlens_cb=lambda: possible_xlens,
        register_files=register_files,
        csrs=csrs,
    )
    symtab = SymbolTable(env)
    for variable in setup.get("vars", ()):
        if variable.get("scope", "global") == "local" and symtab.levels == 1:
            symtab.push()
        symtab.add_unique(
            variable["name"],
            Var(
                variable["name"],
                _type_from_spec(variable["type"], mxlen),
                variable.get("value"),
            ),
        )
    return symtab


def compile_expression(text: str, symtab: SymbolTable):
    node = parse_expression(text, label="[EXPRESSION]")
    node.type_check(symtab, strict=False)
    return node


def compile_func_body(
    text: str,
    symtab: SymbolTable,
    *,
    return_type: Type | None = None,
    strict: bool = False,
    label: str = "<idl>",
):
    node = parse_function_body(text, label=label)
    check_symtab = symtab.deep_clone()
    check_symtab.push(node)
    if return_type is not None:
        check_symtab.add("__expected_return_type", return_type)
    node.type_check(check_symtab, strict=strict)
    return node


def compile_for_loop(text: str, symtab: SymbolTable, *, strict: bool = False):
    node = parse_for_loop(text, label="[LOOP]")
    node.type_check(symtab, strict=strict)
    return node


def compile_constraint(text: str, symtab: SymbolTable, *, strict: bool = False):
    node = parse_constraint_body(text)
    node.type_check(symtab, strict=strict)
    return node


def compile_isa(
    text: str, symtab: SymbolTable, *, strict: bool = False, label: str = "<idl>"
) -> Isa:
    node = parse_isa(text, label=label)
    node.type_check(symtab, strict=strict)
    return node


def type_to_str(type_: Type) -> str:
    return str(type_)


def _type_facts(type_: Type) -> dict[str, Any]:
    width = None
    if type_.kind in {
        TypeKind.BITS,
        TypeKind.ARRAY,
        TypeKind.BITFIELD,
        TypeKind.CSR,
        TypeKind.ENUM,
    }:
        width = str(type_.width)
    return {
        "text": type_to_str(type_),
        "kind": type_.kind.value,
        "width": width,
        "qualifiers": sorted(qualifier.value for qualifier in type_.qualifiers),
    }


def _encode(value: Any) -> Any:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode(item) for key, item in value.items()}
    return str(value)


def _observe(call) -> dict[str, Any]:
    try:
        return {"known": True, "value": _encode(call())}
    except IdlValueUnknown as exc:
        return {"known": False, "reason": exc.reason}


def _function_facts(function: FunctionDef, symtab: SymbolTable) -> dict[str, Any]:
    function_symtab = symtab.deep_clone()
    function_symtab.push(function)
    # ``semantic_arguments`` is deliberately isolated here because the
    # syntax node already has an ``arguments`` property.
    arguments = function.semantic_arguments(function_symtab)
    for type_, name in arguments:
        function_symtab.add(name, Var(name, type_))
    return {
        "name": function.name,
        "arguments": [[_type_facts(type_), name] for type_, name in arguments],
        "return_type": _type_facts(function.return_type(function_symtab)),
        "const_eval": function.const_eval(symtab),
        "builtin": function.builtin,
        "generated": function.generated,
        "external": function.external,
    }


def run_semantic_case(case: dict[str, Any]) -> dict[str, Any]:
    """Run one corpus case and return the Ruby-oracle-shaped observation."""

    warnings_buffer = io.StringIO()
    try:
        symtab = make_symtab(case.get("setup"))
        return_type = (
            None
            if case.get("return_type") is None
            else _type_from_spec(case["return_type"], case.get("setup", {}).get("mxlen"))
        )
        with (
            contextlib.redirect_stderr(warnings_buffer),
            warnings.catch_warnings(record=True) as captured_warnings,
        ):
            warnings.simplefilter("always")
            match case["root"]:
                case "function_body":
                    node = compile_func_body(
                        case["text"],
                        symtab,
                        return_type=return_type,
                        strict=case.get("strict", False),
                        label=case.get("id", "<idl>"),
                    )
                case "expression":
                    node = compile_expression(case["text"], symtab)
                    if case.get("strict"):
                        node.type_check(symtab, strict=True)
                case "for_loop":
                    node = compile_for_loop(case["text"], symtab, strict=case.get("strict", False))
                case "constraint_body":
                    node = compile_constraint(
                        case["text"], symtab, strict=case.get("strict", False)
                    )
                case "isa":
                    node = compile_isa(
                        case["text"],
                        symtab,
                        strict=case.get("strict", False),
                        label=case.get("id", "<idl>"),
                    )
                case other:
                    raise AssertionError(f"unsupported semantic test root: {other}")

            observe = case.get("observe", {})
            result: dict[str, Any] = {
                "ok": True,
                "ast_class": f"{type(node).__name__}Ast",
                "to_idl": (
                    "\n".join(definition.to_idl() for definition in node.definitions)
                    if isinstance(node, Isa)
                    else node.to_idl()
                ),
                "warnings": warnings_buffer.getvalue(),
            }
            if observe.get("const_eval"):
                result["const_eval"] = node.const_eval(symtab)
            if observe.get("type"):
                result["type"] = _type_facts(node.type(symtab))
            if observe.get("value"):
                result["value"] = _observe(lambda: node.value(symtab))
            if observe.get("values"):
                result["values"] = _observe(lambda: node.values(symtab))
            if observe.get("constraint_satisfied"):
                result["satisfied"] = node.satisfied(symtab)
            if observe.get("functions"):
                result["functions"] = [
                    _function_facts(function, symtab)
                    for function in node.definitions
                    if isinstance(function, FunctionDef)
                ]

            eval_symtab = symtab.deep_clone()
            if case["root"] == "function_body":
                eval_symtab.push(node)
                if return_type is not None:
                    eval_symtab.add("__expected_return_type", return_type)
            if observe.get("return"):
                result["return_type"] = _type_facts(node.return_type(eval_symtab))
                result["return_value"] = _observe(lambda: node.return_value(eval_symtab))
                result["return_values"] = _observe(lambda: node.return_values(eval_symtab))
            elif observe.get("execute"):
                result["execute"] = _observe(lambda: node.execute(eval_symtab))

            symbols: dict[str, Any] = {}
            for name in observe.get("symbols", ()):
                symbol = eval_symtab.get(name) or symtab.get(name)
                if symbol is None:
                    symbols[name] = None
                elif isinstance(symbol, Var):
                    symbols[name] = {
                        "type": _type_facts(symbol.type),
                        "value": (
                            {"known": False, "reason": ""}
                            if symbol.value is None
                            else {"known": True, "value": _encode(symbol.value)}
                        ),
                        "const_eval": symbol.const_eval,
                        "for_loop_iter": symbol.for_loop_iter,
                    }
                elif isinstance(symbol, Type):
                    symbols[name] = {"type": _type_facts(symbol)}
                else:
                    symbols[name] = {"class": type(symbol).__name__}
            if observe.get("symbols"):
                result["symbols"] = symbols
            warning_messages = dict.fromkeys(str(warning.message) for warning in captured_warnings)
            result["warnings"] = warnings_buffer.getvalue() + "".join(warning_messages)
            return result
    except IdlTypeError as exc:
        return {
            "ok": False,
            "error": "type",
            "class": "Idl::AstNode::TypeError",
            "message": str(exc).strip(),
        }
    except IdlInternalError as exc:
        return {
            "ok": False,
            "error": "internal",
            "class": "Idl::AstNode::InternalError",
            "message": str(exc).strip(),
        }
    except IdlValueUnknown as exc:
        return {
            "ok": False,
            "error": "value_unknown",
            "class": type(exc).__name__,
            "message": str(exc).strip(),
        }
    except IdlSyntaxError as exc:
        return {
            "ok": False,
            "error": "syntax",
            "class": "SyntaxError",
            "message": str(exc).strip(),
        }


def assert_case_matches(case: dict[str, Any]) -> None:
    correction = RUBY_BUG_CORRECTIONS.get(case["id"], {})
    expected = copy.deepcopy(correction.get("expect", case["expect"]))
    expected.update(correction.get("expect_patch", {}))
    for name, value in correction.get("symbol_value_patch", {}).items():
        expected["symbols"][name]["value"] = value
    assert run_semantic_case(case) == expected

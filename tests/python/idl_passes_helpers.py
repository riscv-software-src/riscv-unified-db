# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Single adaptation layer for the slice-17 IDL analysis-pass contract.

Every black-box test calls through this module, which binds the standalone
Python passes without changing the oracle corpus or assertions. Synthetic
environments are constructed from the frozen setup records. Real sources are
compiled through slice 16's ordinary architecture compiler and owned contexts.

The proposed standalone API in :mod:`udb.idl.passes` is:

* ``prune(node, symtab, *, forced_type=None) -> Node``
* ``reachable_functions(node, symtab, *, cache=None) -> tuple[FunctionDef, ...]``
* ``reachable_exceptions(node, symtab, *, cache=None) -> int``
* ``referenced_csrs(node) -> frozenset[str]``
* ``source_registers(node, symtab) -> frozenset[RegisterRef]``
* ``destination_registers(node, symtab) -> frozenset[RegisterRef]``
* ``return_values(body, symtab) -> tuple[ConditionalReturnValue, ...]``
* ``to_adoc(node, *, indent=0, indent_spaces=2) -> str``
* ``to_option_adoc(node) -> str``

``RegisterRef`` is proposed as an immutable record with ``file`` and ``index``
fields, where ``index`` is either an integer or a generated expression string.
``ConditionalReturnValue`` is proposed as an immutable record containing the
returned expression node and a tuple of condition nodes.

All semantic passes take an explicit ``SymbolTable`` when they need semantic
state. No compiler or architecture global is permitted. Unknown values and
complex register selection use UDB exceptions rather than printing or exiting.

The real-database helper uses ``udb.idl_architecture.ArchitectureCompiler``;
compiler/source integration failures remain explicit, without synthetic
fallbacks or fabricated architecture observations.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

__all__ = [
    "analyze_real_sample",
    "assert_case_matches",
    "destination_registers",
    "prune",
    "reachable_exceptions",
    "reachable_functions",
    "referenced_csrs",
    "return_values",
    "run_synthetic_case",
    "source_registers",
    "to_adoc",
    "to_option_adoc",
]


_MISSING = (
    "Slice 17 IDL analysis passes are not implemented. Bind the proposed "
    "udb.idl.passes API in tests/python/idl_passes_helpers.py."
)


def _passes():
    try:
        from udb.idl import passes
    except ImportError as error:
        raise NotImplementedError(_MISSING) from error
    return passes


def prune(node: Any, symtab: Any, *, forced_type: Any | None = None) -> Any:
    """Return a semantically equivalent tree with known values and paths folded."""

    function = getattr(_passes(), "prune", None)
    if function is None:
        raise NotImplementedError(_MISSING)
    return function(node, symtab, forced_type=forced_type)


def reachable_functions(
    node: Any,
    symtab: Any,
    *,
    cache: dict[Any, tuple[Any, ...]] | None = None,
) -> tuple[Any, ...]:
    """Return unique direct and transitive callees reachable from ``node``."""

    function = getattr(_passes(), "reachable_functions", None)
    if function is None:
        raise NotImplementedError(_MISSING)
    return tuple(function(node, symtab, cache=cache))


def reachable_exceptions(
    node: Any,
    symtab: Any,
    *,
    cache: dict[Any, int] | None = None,
) -> int:
    """Return the exception-code bit mask reachable from ``node``."""

    function = getattr(_passes(), "reachable_exceptions", None)
    if function is None:
        raise NotImplementedError(_MISSING)
    return int(function(node, symtab, cache=cache))


def referenced_csrs(node: Any) -> frozenset[str]:
    """Return names of statically referenced CSRs, excluding numeric handles."""

    function = getattr(_passes(), "referenced_csrs", None)
    if function is None:
        raise NotImplementedError(_MISSING)
    return frozenset(function(node))


def source_registers(node: Any, symtab: Any) -> frozenset[Any]:
    """Return register-file elements read by ``node``."""

    function = getattr(_passes(), "source_registers", None)
    if function is None:
        raise NotImplementedError(_MISSING)
    return frozenset(function(node, symtab))


def destination_registers(node: Any, symtab: Any) -> frozenset[Any]:
    """Return register-file elements written by ``node``."""

    function = getattr(_passes(), "destination_registers", None)
    if function is None:
        raise NotImplementedError(_MISSING)
    return frozenset(function(node, symtab))


def return_values(node: Any, symtab: Any) -> tuple[Any, ...]:
    """Return each possible value and the path conditions under which it returns."""

    function = getattr(_passes(), "return_values", None)
    if function is None:
        raise NotImplementedError(_MISSING)
    return tuple(function(node, symtab))


def to_adoc(node: Any, *, indent: int = 0, indent_spaces: int = 2) -> str:
    """Render normal IDL documentation AsciiDoc."""

    function = getattr(_passes(), "to_adoc", None)
    if function is None:
        raise NotImplementedError(_MISSING)
    return str(function(node, indent=indent, indent_spaces=indent_spaces))


def to_option_adoc(node: Any) -> str:
    """Render implementation-option conditional AsciiDoc."""

    function = getattr(_passes(), "to_option_adoc", None)
    if function is None:
        raise NotImplementedError(_MISSING)
    return str(function(node))


def _record(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    result = {}
    for name in ("file", "index", "expression", "conditions"):
        if hasattr(value, name):
            result[name] = getattr(value, name)
    if result:
        return result
    raise TypeError(f"Cannot serialize pass result {value!r}")


def _type_from_spec(text: str, mxlen: int | None = None):
    from udb.idl.types import WIDTH_UNKNOWN, Qualifier, Type, TypeKind

    qualifiers = []
    while text.split()[0] in {"const", "global", "signed", "known"}:
        qualifier, text = text.split(" ", 1)
        qualifiers.append(Qualifier(qualifier))
    match = re.fullmatch(r"Bits<(\d+|unknown)>", text)
    if match:
        width = WIDTH_UNKNOWN if match[1] == "unknown" else int(match[1])
        return Type(TypeKind.BITS, width=width, qualifiers=qualifiers)
    if text == "XReg":
        return Type(TypeKind.BITS, width=mxlen or WIDTH_UNKNOWN, qualifiers=qualifiers)
    kind = {"Boolean": TypeKind.BOOLEAN, "String": TypeKind.STRING, "void": TypeKind.VOID}
    return Type(kind[text], qualifiers=qualifiers)


@dataclass(frozen=True)
class _CsrField:
    spec: Mapping[str, Any]

    @property
    def name(self):
        return self.spec["name"]

    @property
    def defined_in_all_bases(self):
        return sorted(self.spec.get("bases", (32, 64))) == [32, 64]

    def defined_in_base(self, xlen):
        return xlen in self.spec.get("bases", (32, 64))

    @property
    def defined_in_base32(self):
        return self.defined_in_base(32)

    @property
    def defined_in_base64(self):
        return self.defined_in_base(64)

    @property
    def base64_only(self):
        return self.spec.get("bases", (32, 64)) == [64]

    @property
    def base32_only(self):
        return self.spec.get("bases", (32, 64)) == [32]

    def location(self, base=None):
        lsb = self.spec.get("lsb", 0)
        return range(lsb, lsb + self.width(base))

    def width(self, base=None):
        return self.spec["width"]

    def type(self, base=None):
        return self.spec.get("type", "RW" if self.spec.get("value") is None else "RO")

    @property
    def exists(self):
        return self.spec.get("exists", True)

    @property
    def reset_value(self):
        value = self.spec.get("value")
        return "UNDEFINED_LEGAL" if value is None else value


@dataclass(frozen=True)
class _Csr:
    spec: Mapping[str, Any]

    @property
    def name(self):
        return self.spec["name"]

    @property
    def address(self):
        return self.spec["address"]

    @property
    def value(self):
        return self.spec.get("value")

    @property
    def max_length(self):
        return self.spec.get("length", 32)

    @property
    def fields(self):
        return tuple(_CsrField(field) for field in self.spec.get("fields", ()))

    def length(self, base=None):
        return self.max_length

    def dynamic_length(self):
        return False


def run_synthetic_case(case: Mapping[str, Any]) -> dict[str, Any]:
    """Compile one frozen synthetic input and return canonical pass observations.

    Construct the parser root and synthetic ``IdlEnvironment`` described by
    ``case["setup"]``, then serialize the pass observations in the Ruby oracle's
    canonical shape. Keeping construction here prevents tests from depending
    on parser or symbol-table convenience APIs.
    """

    from udb.idl import ast, parse
    from udb.idl.symbols import IdlEnvironment, SymbolTable, Var

    @dataclass(frozen=True)
    class _RegisterFile:
        name: str
        register_length: str
        registers: tuple[object, ...]

    setup = case.get("setup") or {}
    register_files = tuple(
        _RegisterFile(
            item["name"],
            f"return {item['width']};",
            tuple(range(item["count"])),
        )
        for item in setup.get("register_files", ())
    )
    possible_xlens = tuple(setup.get("possible_xlens", ()))
    symtab = SymbolTable(
        IdlEnvironment(
            mxlen=setup.get("mxlen"),
            possible_xlens_cb=(lambda: possible_xlens) if possible_xlens else None,
            register_files=register_files,
            csrs=tuple(_Csr(item) for item in setup.get("csrs", ())),
        )
    )

    for item in setup.get("vars", ()):
        var_type = _type_from_spec(item["type"], setup.get("mxlen"))
        if item["name"] and item["name"][0].isupper():
            var_type = var_type.make_const()
        symtab.add(item["name"], Var(item["name"], var_type, item.get("value")))

    root = "function_body" if case["root"] == "function_body_syntax" else case["root"]
    node = parse(case["text"], root)
    if isinstance(node, ast.Isa):
        node.add_global_symbols(symtab)
        if case.get("target"):
            node = symtab.get(case["target"]).body
    return {"passes": _observations(node, symtab, case)}


def _register_records(refs, symtab, *, decode_getters=False):
    from udb.idl.symbols import Var

    records = [_record(ref) for ref in refs]
    if decode_getters:
        for record in records:
            index = record["index"]
            binding = symtab.get(index) if isinstance(index, str) else None
            if isinstance(binding, Var) and binding.decode_var:
                record["index"] = f"{index}()"
    return sorted(records, key=lambda ref: (ref["file"], str(ref["index"])))


def _observations(node, symtab, case, *, decode_getters=False):
    from udb.idl import IdlValueUnknown

    setup = case.get("setup") or {}
    observations: dict[str, Any] = {}
    for pass_name in case["passes"]:
        try:
            if pass_name == "prune":
                forced = (
                    _type_from_spec(case["forced_type"], setup.get("mxlen"))
                    if case.get("forced_type")
                    else None
                )
                pruned = prune(node, symtab, forced_type=forced)
                value = {
                    "ast_class": type(pruned).__name__ + "Ast",
                    "to_idl": pruned.to_idl(),
                }
            elif pass_name == "referenced_csrs":
                value = sorted(referenced_csrs(node))
            elif pass_name == "source_registers":
                value = _register_records(
                    source_registers(node, symtab), symtab, decode_getters=decode_getters
                )
            elif pass_name == "destination_registers":
                value = _register_records(
                    destination_registers(node, symtab), symtab, decode_getters=decode_getters
                )
            elif pass_name == "return_values":
                value = [
                    {
                        "expression": item.expression.to_idl(),
                        "conditions": [condition.to_idl() for condition in item.conditions],
                    }
                    for item in return_values(node, symtab)
                ]
            elif pass_name == "adoc":
                value = to_adoc(node)
            elif pass_name == "option_adoc":
                value = to_option_adoc(node)
            elif pass_name == "reachable_functions":
                value = sorted(function.name for function in reachable_functions(node, symtab))
            elif pass_name == "reachable_functions_shared":
                cache = {}
                value = {
                    target: sorted(
                        function.name
                        for function in reachable_functions(
                            symtab.get(target).body, symtab, cache=cache
                        )
                    )
                    for target in case["shared_targets"]
                }
            elif pass_name == "reachable_exceptions":
                mask = reachable_exceptions(node, symtab)
                value = {
                    "mask": mask,
                    "codes": [code for code in range(mask.bit_length()) if mask & (1 << code)],
                }
            else:
                raise NotImplementedError(
                    f"Synthetic adapter for {pass_name!r} is not implemented yet"
                )
            observations[pass_name] = {"ok": True, "value": value}
        except IdlValueUnknown:
            observations[pass_name] = {
                "error": "Idl::ComplexRegDetermination",
                "error_class": "Idl::ComplexRegDetermination",
                "ok": False,
            }
    return observations


def _instruction_xlens(architecture, record):
    from udb.encoding import instruction_encodings
    from udb.idl_environment import possible_xlens

    encoding_xlens = {encoding.xlen for encoding in instruction_encodings(architecture, record)}
    return tuple(
        xlen
        for xlen in possible_xlens(architecture)
        if xlen in encoding_xlens and record.data.get("base") in (None, xlen)
    )


def analyze_real_sample(
    architecture: Any,
    sample: Mapping[str, Any],
) -> dict[str, Any] | list[dict[str, Any]]:
    """Analyze one real instruction, CSR body, field body, or ISA function.

    Preserve explicit instruction XLEN entries and the oracle's decode-getter
    spelling without changing standalone pass expression indices.
    """

    from udb.idl_architecture import ArchitectureCompiler

    compiler = ArchitectureCompiler(architecture)
    pass_names = (
        "adoc",
        "destination_registers",
        "prune",
        "reachable_exceptions",
        "reachable_functions",
        "referenced_csrs",
        "return_values",
        "source_registers",
    )
    if sample.get("body") in ("field_type", "field_reset"):
        pass_names += ("option_adoc",)

    def observe(compiled):
        return _observations(
            compiled.ast,
            compiled.symtab,
            {"passes": pass_names},
            decode_getters=True,
        )

    if sample["kind"] == "instruction":
        record = compiler.database.instruction(sample["name"])
        return [
            {
                "ok": True,
                "value": {
                    "xlen": xlen,
                    "passes": observe(
                        compiler.compile_instruction(sample["name"], effective_xlen=xlen)
                    ),
                },
            }
            for xlen in _instruction_xlens(architecture, record)
        ]
    if sample["kind"] == "function":
        return observe(compiler.compile_function(sample["name"]))
    if sample["kind"] == "csr":
        if "field" in sample:
            behavior = {
                "field_type": "type()",
                "field_reset": "reset_value()",
                "field_sw_write": "sw_write(csr_value)",
            }[sample["body"]]
            compiled = compiler.compile_field(
                sample["csr"], sample["field"], behavior, effective_xlen=sample["xlen"]
            )
        else:
            compiled = compiler.compile_csr(
                sample["csr"], f"{sample['body']}()", effective_xlen=sample["xlen"]
            )
        return observe(compiled)
    raise ValueError(f"Unsupported real sample kind {sample['kind']!r}")


def assert_case_matches(case: Mapping[str, Any]) -> None:
    """Assert one synthetic case against its frozen Ruby observation."""

    actual = run_synthetic_case(case)
    assert actual == case.get("python_expect", case["expect"])

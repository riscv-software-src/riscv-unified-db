# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""C++ names and representation of the ordinary compiler's types."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

from udb.idl.types import WIDTH_UNKNOWN, Type, TypeKind


class CppGenerationError(ValueError):
    """An input cannot be represented by the retained native interface."""


def identifier(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9-]*", name):
        raise CppGenerationError(f"Invalid C++ configuration identifier: {name!r}")
    return name.replace("-", "_")


def names(configuration: str, kind: str, *extras: str) -> str:
    prefix = "".join(part[:1].upper() + part[1:] for part in identifier(configuration).split("_"))
    suffix = {
        "cfg": "",
        "hart": "_Hart",
        "params": "_Params",
        "csr_container": "_CsrContainer",
    }
    if kind in suffix:
        return prefix + suffix[kind]
    if kind == "param":
        return extras[0] + "_Parameter"
    if kind == "struct":
        return prefix + "_" + extras[0] + "_Struct"
    if kind in {"csr", "inst", "csr_field"}:
        text = extras[0].replace(".", "_").capitalize()
        if kind == "csr_field":
            text += "_" + extras[1].capitalize()
        return prefix + "_" + text + {"csr": "_Csr", "inst": "_Inst", "csr_field": "_Field"}[kind]
    raise CppGenerationError(f"Unknown generated symbol kind: {kind}")


def literal(value: object) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, int):
        return f"-{-value}_sb" if value < 0 else f"{value}_b"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True) + "sv"
    if isinstance(value, Sequence):
        return "{" + ", ".join(literal(item) for item in value) + "}"
    raise CppGenerationError(f"Unsupported C++ constant: {value!r}")


def cpp_type(dtype: Type, *, const: bool = False, constexpr_value: object = None) -> str:
    kind = dtype.kind
    if kind in (TypeKind.ENUM, TypeKind.BITFIELD):
        result = dtype.name
    elif kind is TypeKind.ENUM_REF:
        result = dtype.enum_class.name
    elif kind is TypeKind.STRUCT:
        result = f"__UDB_STRUCT({dtype.name})"
    elif kind is TypeKind.BITS:
        signed = str(dtype.is_signed).lower()
        if dtype.width == WIDTH_UNKNOWN:
            capacity = dtype.max_width or "BitsInfinitePrecision"
            family = "_RuntimeBits" if dtype.is_known else "_PossiblyUnknownRuntimeBits"
            result = f"{family}<{capacity}, {signed}>"
        else:
            family = "_Bits" if dtype.is_known else "_PossiblyUnknownBits"
            result = f"{family}<{dtype.width}, {signed}>"
    elif kind is TypeKind.BOOLEAN:
        result = "bool"
    elif kind is TypeKind.STRING:
        result = "std::string_view" if constexpr_value is not None else "std::string"
    elif kind is TypeKind.ARRAY:
        subtype = cpp_type(dtype.sub_type, constexpr_value=constexpr_value)
        size = dtype.width
        if constexpr_value is not None:
            size = len(constexpr_value)
        result = (
            f"std::vector<{subtype}>" if size == WIDTH_UNKNOWN else f"std::array<{subtype}, {size}>"
        )
    elif kind is TypeKind.TUPLE:
        result = "std::tuple<" + ", ".join(cpp_type(item) for item in dtype.tuple_types) + ">"
    elif kind is TypeKind.VOID:
        result = "void"
    else:
        raise CppGenerationError(f"Unsupported C++ type: {dtype}")
    return ("const " if const and dtype.is_const else "") + result

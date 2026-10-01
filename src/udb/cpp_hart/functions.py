# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Reachable global IDL function declarations and template definitions."""

from udb.idl.passes import constexpr, written
from udb.idl.types import WIDTH_UNKNOWN, TypeKind

from .emitter import Emitter
from .instructions import macros


def _signature(context, function, compiled, *, definition):
    emitter = Emitter(compiled.symtab)
    semantic = function.semantic_arguments(compiled.symtab)
    templates = []
    args = []
    initializers = []
    for index, (dtype, name) in enumerate(semantic):
        if dtype.kind is TypeKind.BITS:
            prefix = f"_Arg{index}BitsType"
            templates += [
                f"template <unsigned, bool> class {prefix}",
                f"unsigned {prefix}N",
                f"bool {prefix}Signed",
            ]
            typ = f"{prefix}<{prefix}N, {prefix}Signed>"
            args.append(f"const {typ}& _{name}")
            if dtype.width == WIDTH_UNKNOWN:
                unknown_type = f"_PossiblyUnknownRuntimeBits<BitsInfinitePrecision, {prefix}Signed>"
                known_type = f"_RuntimeBits<BitsInfinitePrecision, {prefix}Signed>"
                initializer = f"_{name}, {emitter.expression(dtype.width_ast)}"
            else:
                unknown_type = f"_PossiblyUnknownBits<{dtype.width}, {prefix}Signed>"
                known_type = f"_Bits<{dtype.width}, {prefix}Signed>"
                initializer = f"_{name}"
            initializers.append(
                f"using __Arg{index}BitsType = std::conditional_t<{typ}::PossiblyUnknown, {unknown_type}, {known_type}>;\n__Arg{index}BitsType {name}{{{initializer}}};"
            )
        else:
            arg_type = emitter.type_name(function.arguments[index].type_name)
            mutable = written(function.body, compiled.symtab, name)
            args.append(f"{'' if mutable else 'const '}{arg_type}{'' if mutable else '&'} {name}")
    template = "template <" + ", ".join(templates) + ">\n" if templates else ""
    returns = [emitter.type_name(node) for node in function.return_types]
    ret = (
        returns[0]
        if len(returns) == 1
        else "std::tuple<" + ", ".join(returns) + ">"
        if returns
        else "void"
    )
    const = constexpr(function, context.table)
    qualifiers = ("constexpr" if definition else "static constexpr") if const else ""
    noreturn = "[[noreturn]] " if function.name.startswith("raise") else ""
    scope = context.symbol("hart") + "<SocType>::" if definition else ""
    name = function.name.replace("?", "_Q_")
    signature = f"{template}{noreturn}{qualifiers} {ret} {scope}{name}({', '.join(args)})"
    return signature, "\n".join(initializers)


def function_headers(context):
    prototypes = [
        f"#define __UDB_CONST_GLOBAL(name) {context.symbol('hart')}::name",
        "#define __UDB_MUTABLE_GLOBAL(name) name",
        f"#define __UDB_STRUCT(name) {context.symbol('cfg')}_ ## name ## _Struct",
        f"#define __UDB_STATIC_PARAM(name) {context.symbol('params')}::name.value()",
        "#define __UDB_CONSTEXPR_FUNC_CALL",
    ]
    macro, undef = macros(context, parent="this", hart=True)
    definitions = [
        '#pragma once\n#include <type_traits>\n#include "udb/hart.hpp"',
        macro,
        "namespace udb {",
    ]
    for function in context.functions:
        if function.builtin or function.generated:
            continue
        compiled, body = context.function(function)
        proto, _ = _signature(context, function, compiled, definition=False)
        signature, initializers = _signature(context, function, compiled, definition=True)
        prototypes.append(proto + ";")
        definitions.append(
            f"template <SocModel SocType>\n{signature} {{\n{initializers}\n{body.cpp(2)}\n}}"
        )
    prototypes.append(
        "#undef __UDB_CONST_GLOBAL\n#undef __UDB_MUTABLE_GLOBAL\n#undef __UDB_STRUCT\n#undef __UDB_STATIC_PARAM\n#undef __UDB_CONSTEXPR_FUNC_CALL"
    )
    definitions += ["}", undef]
    return "\n".join(prototypes) + "\n", "\n".join(definitions) + "\n"

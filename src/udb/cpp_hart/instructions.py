# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Instruction classes and decoder, using public encoding descriptors/passes."""

import json

from udb.idl.errors import IdlValueUnknown
from udb.idl.parser import parse_expression
from udb.idl.passes import (
    DecodeEncoding,
    DecodeGenerator,
    DecodeVariable,
    control_flow,
    destination_registers,
    source_registers,
)

from .conditions import condition_cpp


def macros(context, *, parent="m_parent", hart=False):
    target = f"{context.symbol('hart')}<SocType>"
    definitions = {
        "__UDB_FUNC_CALL": f"{parent}->",
        "__UDB_CONSTEXPR_FUNC_CALL": f"{target}::",
        "__UDB_CSR_BY_ADDR(addr)": f"(*({parent}->csr(addr)))",
        "__UDB_CSR_BY_NAME(name)": f"{parent}->m_csrs.name",
        "__UDB_ENCODING": "this->_encoding()"
        if not hart
        else f"Bits<{context.largest_encoding}>{{{parent}->m_cur_inst ? {parent}->m_cur_inst->encoding() : 0x13}}",
        "__UDB_RUNTIME_PARAM(name)": f"{parent}->params().name.value()",
        "__UDB_STATIC_PARAM(name)": f"{context.symbol('params')}::name.value()",
        "__UDB_STRUCT(name)": f"{context.symbol('cfg')}_ ## name ## _Struct",
        "__UDB_SET_PC(pc)": f"{parent}->set_next_pc(pc)",
        "__UDB_PC": f"{parent}->m_pc",
        "__UDB_MUTABLE_GLOBAL(name)": f"{parent}->name",
        "__UDB_CONST_GLOBAL(name)": f"{target}::name",
        "__UDB_XLEN": f"{parent}->xlen().to_defined()",
        "__UDB_HART": parent,
    }
    return (
        "\n".join(f"#define {name} {value}" for name, value in definitions.items()),
        "\n".join(f"#undef {name.split('(')[0]}" for name in definitions),
    )


def _branches(context, instruction, operation, *, default):
    parts = []
    for xlen in context.xlens:
        if (instruction.name, xlen) not in context.encodings:
            continue
        body = context.operation(instruction.name, xlen)
        cpp = operation(body, xlen) if body is not None else default
        parts.append((xlen, cpp))
    if len(parts) == 1:
        return parts[0][1]
    return "\n".join(
        f"{'if' if i == 0 else 'else if'} constexpr (XLEN == {xlen}) {{\n{cpp}\n}}"
        for i, (xlen, cpp) in enumerate(parts)
    )


def _extract(field):
    expressions = []
    for bits in field.ranges:
        if bits.width == 1:
            expressions.append(f"this->m_encoding.template at<{bits.low}>()")
        else:
            expressions.append(f"this->m_encoding.template extract<{bits.high}, {bits.low}>()")
    if field.left_shift:
        expressions.append(f"Bits<{field.left_shift}>{{0}}")
    return "concat(" + ", ".join(expressions) + ")" if len(expressions) > 1 else expressions[0]


def _assembly(instruction, encoding):
    fmt = (instruction.assembly or "").replace("{", "{{").replace("}", "}}")
    args = []
    for field in encoding.variables:
        fmt = fmt.replace(field.name, "{}")
        if field.name[0] in "xr":
            args.append(f"Reg({field.name}()).to_string()")
        elif field.name[0] == "f":
            args.append(f"Reg({field.name}(), true).to_string()")
        else:
            args.append(f"{field.name}()")
    return json.dumps("{} " + fmt), ", ".join(["m_name", *reversed(args)])


def _registers(body, pass_function):
    try:
        refs = pass_function(body.ast, body.emitter.symtab)
    except IdlValueUnknown:
        return "throw ComplexRegDetermination();"
    items = []
    for ref in sorted(refs, key=lambda item: (item.file, str(item.index))):
        if isinstance(ref.index, int):
            items.append(f"{{Reg::{ref.file}{ref.index}}}")
        else:
            expression = body.emitter.expression(parse_expression(ref.index))
            base = {"X": 0, "F": 32, "V": 64}[ref.file]
            items.append(f"{{Reg::from_rf_index({expression}, {base}u)}}")
    return "return {" + ", ".join(items) + "};"


def instruction_headers(context):
    macro, undef = macros(context)
    out = [
        '#pragma once\n#include "udb/bits.hpp"\n#include "udb/util.hpp"\n#include "udb/xregister.hpp"\n#include "udb/inst.hpp"\n#include "udb/cpp_exceptions.hpp"',
        f'#include "udb/cfgs/{context.name}/structs.hxx"',
        "#ifdef assert\n#undef assert\n#endif\nnamespace udb {",
        macro,
    ]
    impl = ["#pragma once\nnamespace udb {"]
    unavailable = 'm_parent->assert(false, "There is no operation() defined for this instruction");'
    for instruction in context.instructions:
        encodings = [
            context.encodings[(instruction.name, xlen)]
            for xlen in context.xlens
            if (instruction.name, xlen) in context.encodings
        ]
        if not encodings:
            continue
        length = encodings[0].length
        cls = context.symbol("inst", instruction.name)
        hart = context.symbol("hart")
        out.append(f"""
template <unsigned XLEN, SocModel SocType>
class {cls} : public InstWithKnownLength<XLEN, {length}> {{
  void* operator new(size_t) = delete;
public:
  void* operator new(std::size_t, void* p) throw() {{ return p; }}
  void operator delete(void* ptr);
  using XReg = Bits<{context.mxlen}>;
  static constexpr unsigned EncodingLength = {length};
  {cls}({hart}<SocType>* parent, XReg pc, Bits<{length}> encoding)
    : InstWithKnownLength<XLEN, {length}>(pc, encoding), m_parent(parent) {{}}
  virtual ~{cls}() {{}}
  {hart}<SocType>* parent() {{ return m_parent; }}
  bool control_flow() const override {{
{_branches(context, instruction, lambda body, xlen: "return " + str(control_flow(body.ast, body.emitter.symtab.global_clone())).lower() + ";", default="return false;")}
  }}
""")
        for encoding in encodings:
            for field in encoding.variables:
                constraint = f" requires (_XLEN == {encoding.xlen})" if len(encodings) > 1 else ""
                template = "template <unsigned _XLEN = XLEN>\n" if len(encodings) > 1 else ""
                out.append(
                    f"{template}Bits<{field.width}> {field.name}() const{constraint} {{ return {_extract(field)}; }}"
                )
                if field.alias:
                    out.append(
                        f"{template}Bits<{field.width}> {field.alias}() const{constraint} {{ return {field.name}(); }}"
                    )
        execute = _branches(
            context, instruction, lambda body, xlen: body.cpp(), default=unavailable
        )
        disassemble = []
        for encoding in encodings:
            fmt, args = _assembly(instruction, encoding)
            disassemble.append(
                f"if constexpr (XLEN == {encoding.xlen}) return fmt::format({fmt}, {args});"
            )
        src = _branches(
            context,
            instruction,
            lambda body, xlen: _registers(body, source_registers),
            default=unavailable + "\n__builtin_unreachable();",
        )
        dst = _branches(
            context,
            instruction,
            lambda body, xlen: _registers(body, destination_registers),
            default=unavailable + "\n__builtin_unreachable();",
        )
        out.append(f"""
  void execute() override {{ {execute} }}
  constexpr static std::string_view m_name = "{instruction.name}";
  const std::string_view& name() override {{ return m_name; }}
  std::string disassemble(bool use_abi_reg_names = false) const override {{
    {" ".join(disassemble)}
    udb_assert(false, "Not defined"); __builtin_unreachable();
  }}
  std::vector<Reg> srcRegs() const override {{ {src} }}
  std::vector<Reg> dstRegs() const override {{ {dst} }}
private:
  {hart}<SocType>* const m_parent;
}};
""")
        impl.append(
            f"template <unsigned XLEN, SocModel SocType>\nvoid {cls}<XLEN, SocType>::operator delete(void* ptr) {{ {hart}<SocType>::inst_allocator.free(reinterpret_cast<InstBase*>(ptr)); }}"
        )
    return "\n".join(out + [undef, "}"]) + "\n", "\n".join(impl + ["}"]) + "\n"


def decode(context):
    generator = DecodeGenerator(instruction_class=lambda name: context.symbol("inst", name))
    branches = []
    for xlen in context.xlens:
        records = []
        for instruction in context.instructions:
            encoding = context.encodings.get((instruction.name, xlen))
            if encoding is None:
                continue
            variables = tuple(
                DecodeVariable(
                    field.name,
                    tuple(range(bits.low, bits.high + 1) for bits in field.ranges),
                    field.exclusions,
                )
                for field in encoding.variables
            )
            hint = instruction.instruction.get("hintOf")
            if isinstance(hint, dict):
                hint = hint.get("name")
            condition = condition_cpp(context.condition(instruction.instruction), context)
            records.append(
                DecodeEncoding(instruction.name, encoding.match, variables, hint, condition)
            )
        code = generator.generate(records, xlen)
        branches.append(f"if (xlen() == {xlen}_b) {{\n{code}\n}}" if context.multi else code)
    return "\n".join(branches)

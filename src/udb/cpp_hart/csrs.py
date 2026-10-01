# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""CSR storage, views, software semantics and dependency-ordered reset."""

from graphlib import TopologicalSorter

from udb.conditions import XlenTerm
from udb.idl.errors import IdlValueUnknown
from udb.idl.passes import referenced_csrs

from .conditions import condition_cpp
from .emitter import Emitter
from .instructions import macros
from .types import CppGenerationError, literal


def _field_dynamic(context, field):
    return context.multi and Emitter._field_dynamic(field)


def _csr_dynamic(context, csr):
    return context.multi and Emitter._csr_dynamic(csr)


def _bases(context, descriptor):
    return tuple(base for base in context.xlens if descriptor.defined_in_base(base))


def _branch(bases, code, dynamic):
    if not dynamic:
        return code(bases[0])
    return "\n".join(
        f"{'if' if index == 0 else 'else if'} (xlen == {base}_b) {{\n{code(base)}\n}}"
        for index, base in enumerate(bases)
    )


def _location(field, base):
    bits = field.location(base)
    return bits.stop - 1, bits.start, len(bits)


def _field_header(context, record, field):
    name = context.symbol("csr_field", record.name, field.name)
    hart = context.symbol("hart")
    bases = _bases(context, field)
    width = max(field.width(base) for base in bases)
    dynamic = _field_dynamic(context, field)
    locations = []
    if dynamic:
        for base in bases:
            high, low, _ = _location(field, base)
            locations.append(f"m_location_{base}({high}, {low})")
        location = "xlen == 32_b ? m_location_32 : m_location_64"
        storage = "const CsrFieldLocation m_location_32;\nconst CsrFieldLocation m_location_64;"
    else:
        high, low, _ = _location(field, bases[0])
        locations.append(f"m_location({high}, {low})")
        location = "m_location"
        storage = "const CsrFieldLocation m_location;"

    def extract(base):
        _, low, count = _location(field, base)
        return f"return (csr_value & 0x{((1 << count) - 1) << low:x}_b) >> {low}_b;"

    extract_cpp = _branch(bases, extract, context.multi and len(bases) > 1)
    write_cpp = _branch(
        bases, lambda base: f"m_value = value & 0x{(1 << field.width(base)) - 1:x}_b;", dynamic
    )
    param = "const PossiblyUnknownBits<8>& xlen" if dynamic else ""
    extra = ", xlen" if dynamic else ""
    location_param = "const Bits<8>& xlen" if dynamic else ""
    return f"""
template <SocModel SocType>
class {name} : public CsrFieldBase {{
public:
  using ValueType = PossiblyUnknownBits<{width}>;
  {name}({hart}<SocType>* hart) : m_hart(hart), {", ".join(locations)} {{}}
  const CsrFieldLocation location(const Bits<8>& xlen) const override {{ return {location}; }}
  const CsrFieldLocation _location({location_param}) const {{ return {location}; }}
  void reset() override;
  PossiblyUnknownBits<MAX_POSSIBLE_XLEN> hw_read(const Bits<8>& xlen) const override {{ return m_value; }}
  ValueType _hw_read() const {{ return m_value; }}
  PossiblyUnknownBits<MAX_POSSIBLE_XLEN> extract(const PossiblyUnknownBits<MAX_POSSIBLE_XLEN>& csr_value, const Bits<8>& xlen) const override {{ {extract_cpp} }}
  void hw_write(const PossiblyUnknownBits<MAX_POSSIBLE_XLEN>& value, const Bits<8>& xlen) override {{ _hw_write(value{extra}); }}
  void _hw_write(const ValueType& value{", " + param if param else ""}) {{ {write_cpp} }}
  CsrFieldType type(const Bits<8>& xlen) const override;
private:
  {hart}<SocType>* m_hart;
  {storage}
  ValueType m_value;
}};
"""


def _field_impl(context, record, field):
    name = context.symbol("csr_field", record.name, field.name)
    bases = _bases(context, field)
    data = record["fields"][field.name]

    def access(base):
        if "type" in data:
            return "return CsrFieldType::" + data["type"].replace("-", "") + ";"
        try:
            value = field.type(base)
        except IdlValueUnknown:
            return context.field_body(record.name, field.name, "type()", base).cpp()
        return "return CsrFieldType::" + value.replace("-", "") + ";"

    type_cpp = _branch(bases, access, context.multi and len(bases) > 1)
    extra = ", m_hart->xlen().to_defined()" if _field_dynamic(context, field) else ""
    try:
        reset = field.reset_value
        reset_cpp = (
            "m_value = ValueType{};"
            if reset in ("UNDEFINED_LEGAL", "UNDEFINED_LEGAL_DETERMINISTIC")
            else f"_hw_write({literal(reset)}{extra});"
        )
    except IdlValueUnknown:
        body = context.field_body(record.name, field.name, "reset_value()", bases[0])
        width = max(field.width(base) for base in bases)
        reset_cpp = f"auto value = [this]() -> PossiblyUnknownBits<{width + 1}> {{\n{body.cpp()}\n}}();\n_hw_write(value{extra});"
    return f"""
template <SocModel SocType>
CsrFieldType {name}<SocType>::type(const Bits<8>& xlen) const {{ {type_cpp} }}
template <SocModel SocType>
void {name}<SocType>::reset() {{ {reset_cpp} }}
"""


def _views(context, record, csr):
    out = []
    name = context.symbol("csr", record.name) + "View"
    out.append(f"template <unsigned XLEN> class {name};")
    for base in _bases(context, csr):
        length = csr.length(base)
        fields = [field for field in csr.fields if field.defined_in_base(base)]
        init = ", ".join(f"{field.name}(*this)" for field in fields)
        init = ", " + init if init else ""
        members = "\n".join(
            f"BitfieldMember<{length}, {field.location(base).start}, {field.width(base)}> {field.name};"
            for field in fields
        )
        out.append(f"""
template <> class {name}<{base}> : public Bitfield<{length}> {{
public:
  {name}() = default;
  {name}(const PossiblyUnknownBits<{length}>& value) : Bitfield<{length}>(value){init} {{}}
  {members}
}};
""")
    return "\n".join(out)


def _csr_header(context, record, csr, fields):
    name, hart = context.symbol("csr", record.name), context.symbol("hart")
    dynamic = _csr_dynamic(context, csr)
    bases = _bases(context, csr)
    xlen_param = "const Bits<8>& xlen" if dynamic else ""
    extra = ", xlen" if dynamic else ""
    call = "xlen" if dynamic else ""
    width = csr.max_length
    indirect = "indirect_address" in record
    addr_type = "Indirect" if indirect else "Direct"
    address = (
        f"return {record['address']};"
        if not indirect
        else f'throw CsrAddressTypeError("{record.name} is not direct addressible.");'
    )
    indirect_address = (
        f"return {record['indirect_address']};"
        if indirect
        else f'throw CsrAddressTypeError("{record.name} is not indirect.");'
    )
    indirect_slot = (
        f"return {record['indirect_slot']};"
        if indirect
        else f'throw CsrAddressTypeError("{record.name} is not indirect.");'
    )
    address_static = (
        f"static constexpr Bits<12> _address() {{ return {record['address']}_b; }}"
        if "address" in record
        else ""
    )
    declarations, friends, resets, members = [], [], [], []
    for field in fields:
        cls = context.symbol("csr_field", record.name, field.name)
        friends.append(f"friend class {cls}<SocType>;")
        resets.append(f"m_{field.name}.reset();")
        declarations.append(f"{cls}<SocType>& {field.name}() {{ return m_{field.name}; }}")
        members.append(f"{cls}<SocType> m_{field.name};")

    def read(base):
        terms = []
        for field in fields:
            if not field.defined_in_base(base):
                continue
            value = f"m_{field.name}._hw_read()"
            if _field_dynamic(context, field):
                value = f"({value} & 0x{(1 << field.width(base)) - 1:x}_b)"
            terms.append(f"({value}.template widening_sll<{field.location(base).start}>())")
        return "return " + (" | ".join(terms) or "0_b") + ";"

    defined = condition_cpp(context.condition(record), context, parent="m_parent")
    return f"""
template <SocModel SocType>
class {name} : public CsrBase {{
  {" ".join(friends)}
public:
  template <unsigned XLEN> using View = {name}View<XLEN>;
  using ValueType = PossiblyUnknownBits<{width}>;
  {name}({hart}<SocType>* parent);
  CsrAddressType address_type() const override {{ return CsrAddressType::{addr_type}; }}
  unsigned address() const override {{ {address} }}
  uint64_t indirect_address() const override {{ {indirect_address} }}
  uint8_t indirect_slot() const override {{ {indirect_slot} }}
  {address_static}
  const std::string name() const override {{ return "{record.name}"; }}
  PrivilegeMode mode() const override {{ return PrivilegeMode::{record.get("priv_mode", "M")}; }}
  bool writable() const override {{ return {str(record.get("writable", True)).lower()}; }}
  bool defined() override {{ return {defined}; }}
  void reset() override {{ if (defined()) {{ {" ".join(resets)} }} }}
  PossiblyUnknownBits<MAX_POSSIBLE_XLEN> hw_read(const Bits<8>& xlen) const override {{ return _hw_read({call}); }}
  ValueType _hw_read({xlen_param}) const {{ {_branch(bases, read, dynamic)} }}
  PossiblyUnknownBits<MAX_POSSIBLE_XLEN> sw_read(const Bits<8>& xlen) const override {{ return _sw_read({call}); }}
  ValueType _sw_read({xlen_param}) const;
  void hw_write(const PossiblyUnknownBits<MAX_POSSIBLE_XLEN>& value, const Bits<8>& xlen) override {{ _hw_write(value{extra}); }}
  void _hw_write(const ValueType& value{", const PossiblyUnknownBits<8>& xlen" if dynamic else ""});
  bool sw_write(const PossiblyUnknownBits<MAX_POSSIBLE_XLEN>& value, const Bits<8>& xlen) override {{ return _sw_write(value{extra}); }}
  bool _sw_write(const ValueType& value{", " + xlen_param if dynamic else ""});
  bool implemented_without_Q_(const ExtensionName&) const override;
  {" ".join(declarations)}
private:
  {hart}<SocType>* m_parent;
  {" ".join(members)}
}};
"""


def _csr_impl(context, record, csr, fields):
    name, hart = context.symbol("csr", record.name), context.symbol("hart")
    scope = name + "<SocType>"
    dynamic = _csr_dynamic(context, csr)
    bases = _bases(context, csr)
    xlen_param = "const Bits<8>& xlen" if dynamic else ""
    init = ", ".join(["m_parent(parent)", *(f"m_{field.name}(parent)" for field in fields)])

    def read(base):
        if "sw_read()" in record:
            return context.csr_body(record.name, base).cpp()
        return "return _hw_read(" + ("xlen" if dynamic else "") + ");"

    def hw_write(base):
        out = []
        for field in fields:
            if field.defined_in_base(base):
                high, low, _ = _location(field, base)
                extra = ", xlen" if _field_dynamic(context, field) else ""
                out.append(
                    f"m_{field.name}._hw_write(value.template extract<{high}, {low}>(){extra});"
                )
        return "\n".join(out)

    def sw_write(base):
        out = [f"View<{base}> csr_value(value);"]
        for field in fields:
            if not field.defined_in_base(base):
                continue
            extra = ", xlen" if _field_dynamic(context, field) else ""
            if "sw_write(csr_value)" in record["fields"][field.name]:
                body = context.field_body(record.name, field.name, "sw_write(csr_value)", base)
                out.append(
                    f"{{ auto wr_val = [this, &csr_value = std::as_const(csr_value)]() -> PossiblyUnknownBits<{field.width(base)}> {{\n{body.cpp()}\n}}(); m_{field.name}._hw_write(wr_val{extra}); }}"
                )
            else:
                out.append(f"m_{field.name}._hw_write(csr_value.{field.name}{extra});")
        return "\n".join(out)

    return f"""
template <SocModel SocType>
{scope}::{name}({hart}<SocType>* parent) : CsrBase(), {init} {{}}
template <SocModel SocType>
typename {scope}::ValueType {scope}::_sw_read({xlen_param}) const {{ {_branch(bases, read, dynamic)} }}
template <SocModel SocType>
void {scope}::_hw_write(const ValueType& value{", const PossiblyUnknownBits<8>& xlen" if dynamic else ""}) {{ {_branch(bases, hw_write, dynamic)} }}
template <SocModel SocType>
bool {scope}::_sw_write(const ValueType& value{", " + xlen_param if dynamic else ""}) {{ {_branch(bases, sw_write, dynamic)} return true; }}
template <SocModel SocType>
bool {scope}::implemented_without_Q_(const ExtensionName& ext) const {{ return true; }}
"""


def csr_headers(context):
    header = [
        '#pragma once\n#include "udb/util.hpp"\n#include "udb/bits.hpp"\n#include "udb/bitfield.hpp"\n#include "udb/csr.hpp"\n#include "udb/cpp_exceptions.hpp"\n#include "udb/version.hpp"\nnamespace udb {',
        f"template <SocModel SocType> class {context.symbol('hart')};",
    ]
    impl = [
        f'#pragma once\n#include "udb/cfgs/{context.name}/structs.hxx"\n#include "udb/cfgs/{context.name}/params.hxx"\nusing namespace std::literals;\nnamespace udb {{'
    ]
    for record, csr in context.csrs:
        fields = context.fields(record, csr)
        header += [_field_header(context, record, field) for field in fields]
        header += [_views(context, record, csr), _csr_header(context, record, csr, fields)]
        macro, undef = macros(context, parent="m_hart", hart=True)
        impl += [macro, *(_field_impl(context, record, field) for field in fields), undef]
        macro, undef = macros(context, parent="m_parent", hart=True)
        impl += [macro, _csr_impl(context, record, csr, fields), undef]
    header += [
        "}",
        f'#include "udb/cfgs/{context.name}/hart.hxx"\n#include "udb/inst.hpp"\n#include "udb/cfgs/{context.name}/csrs_impl.hxx"',
    ]
    impl.append("}")
    return "\n".join(header) + "\n", "\n".join(impl) + "\n"


def _mentions_xlen(condition):
    if isinstance(condition, XlenTerm):
        return True
    children = getattr(condition, "children", ())
    child = getattr(condition, "child", None)
    if child is not None:
        children = (*children, child)
    return any(_mentions_xlen(child) for child in children)


def csr_container(context):
    graph = {}
    members = []
    initializers = []
    name = context.symbol("csr_container")
    for record, csr in context.csrs:
        deps = set()
        fields = context.fields(record, csr)
        if _mentions_xlen(context.condition(record)) or any(
            _field_dynamic(context, field) for field in fields
        ):
            deps.update(("misa", "mstatus"))
        for field in fields:
            if "reset_value()" in record["fields"][field.name]:
                body = context.field_body(
                    record.name, field.name, "reset_value()", _bases(context, field)[0]
                )
                deps.update(referenced_csrs(body.ast))
        deps.discard(record.name)
        graph[record.name] = deps
        member = record.name.replace(".", "_")
        members.append(f"{context.symbol('csr', record.name)}<SocType> {member};")
        initializers.append(f"{member}(parent)")
    missing = {dep for deps in graph.values() for dep in deps if dep not in graph}
    if missing:
        raise CppGenerationError(f"CSR reset references unavailable CSRs: {sorted(missing)}")
    reset = "\n".join(
        f"{csr.replace('.', '_')}.reset();" for csr in TopologicalSorter(graph).static_order()
    )
    return f"""#pragma once
#include "udb/cfgs/{context.name}/csrs.hxx"
namespace udb {{
template <SocModel SocType> class {context.symbol("hart")};
template <SocModel SocType> struct {name} {{
  {" ".join(members)}
  {name}({context.symbol("hart")}<SocType>* parent){" : " + ", ".join(initializers) if initializers else ""} {{}}
  void reset() {{ {reset} }}
}};
}}
"""

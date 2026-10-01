# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Retained generated hart interface, register storage and native entry points."""

from udb.idl import ast
from udb.idl.parser import parse_function_body
from udb.idl.symbols import Var
from udb.idl.types import WIDTH_UNKNOWN, Type, TypeKind

from .emitter import Emitter
from .instructions import decode, macros
from .types import CppGenerationError, cpp_type


def _register_expression(context, text, width=None):
    body = parse_function_body(text)
    table = context.compiler.global_symbol_table
    if width is not None:
        table.push(body)
        table.add("value", Var("value", Type(TypeKind.BITS, width=width)))
    if len(body.stmts) != 1 or not isinstance(body.stmts[0], ast.ReturnStatement):
        raise CppGenerationError(f"Register descriptor must be a return expression: {text!r}")
    expression = body.stmts[0].return_value_nodes[0]
    expression.type_check(table)
    return Emitter(table).expression(expression)


def _registers(context):
    out, storage, initializers, resets = [], [], [], []
    for record in context.database.objects("register_file"):
        name = record.name.lower()
        entries = record.get("registers", ())
        width, capacity = context.register_width(record.name)
        runtime = width == WIDTH_UNKNOWN
        capacity = capacity if runtime else width
        typ = (
            f"PossiblyUnknownRuntimeBits<{capacity}>"
            if runtime
            else f"PossiblyUnknownBits<{width}>"
        )
        setter = (
            f"_PossiblyUnknownRuntimeBits<{capacity}, false>"
            if runtime
            else f"_PossiblyUnknownBits<{width}, false>"
        )
        if runtime:
            expr = parse_function_body(record["register_length()"]).stmts[0].return_value_nodes[0]
            if isinstance(expr, ast.Id) and context.table.get(expr.name).param:
                width_expr = f"m_params.{expr.name}.has_value() ? static_cast<uint64_t>(m_params.{expr.name}.value().get()) : {capacity}"
            else:
                width_expr = _register_expression(context, record["register_length()"]) + ".get()"
            initializers.append(
                f"m_{name}regs{{"
                + ", ".join(f"{typ}{{WidthArg({width_expr})}}" for _ in entries)
                + "}"
            )
        for index, entry in enumerate(entries):
            if "reset_value" in entry:
                resets.append(
                    f"m_{name}regs[{index}] = {context.expression(entry['reset_value'])};"
                )
        read_cases, write_cases = [], []
        for index, entry in enumerate(entries):
            if "arch_read()" in entry:
                expression = _register_expression(context, entry["arch_read()"])
                if runtime:
                    expression = f"{typ}({expression}, WidthArg(m_{name}regs[{index}].width()))"
                else:
                    expression = f"{typ}({expression})"
                read_cases.append(f"case {index}: return {expression};")
            if "arch_write(value)" in entry:
                write_cases.append(
                    f"case {index}: to_store = {_register_expression(context, entry['arch_write(value)'], capacity)}; break;"
                )
        read = (
            "switch (num) {" + " ".join(read_cases) + f"default: return m_{name}regs[num]; }}"
            if read_cases
            else f"return m_{name}regs[num];"
        )
        write = (
            "auto to_store = value; switch (static_cast<unsigned>(num.get())) {"
            + " ".join(write_cases)
            + f"default: break; }} m_{name}regs[static_cast<unsigned>(num.get())] = to_store;"
            if write_cases
            else f"m_{name}regs[static_cast<unsigned>(num.get())] = value;"
        )
        convert = (
            f"static_cast<uint64_t>(_{name}reg(num).get().get_ui())"
            if runtime or capacity > 64
            else f"_{name}reg(num).get()"
        )
        setter_val = (
            f"{typ}{{Bits<64>{{value}}, WidthArg(m_{name}regs[num].width())}}"
            if runtime
            else f"Bits<{width}>{{value}}"
        )
        out.append(f"""
uint64_t {name}reg(unsigned num) const override {{
  if (num >= {len(entries)}) throw std::out_of_range("{record.name} register indices are 0 - {len(entries) - 1}, inclusive");
  return {convert};
}}
{typ} _{name}reg(unsigned num) const {{ {read} }}
template <template <unsigned, bool> class BitsClass, unsigned N, bool Signed>
  requires (BitsType<BitsClass<N, Signed>>)
{typ} _{name}reg(const BitsClass<N, Signed>& num) const {{ return _{name}reg(static_cast<unsigned>(num.get())); }}
void set_{name}reg(unsigned num, uint64_t value) override {{
  if (num >= {len(entries)}) throw std::out_of_range("{record.name} register indices are 0 - {len(entries) - 1}, inclusive");
  _set_{name}reg(Bits<8>{{num}}, {setter_val});
}}
template <template <unsigned, bool> class IdxType, unsigned IdxN, bool IdxSigned>
  requires (BitsType<IdxType<IdxN, IdxSigned>>)
void _set_{name}reg(const IdxType<IdxN, IdxSigned>& num, const {setter}& value) {{ {write} }}
""")
        storage.append(f"std::array<{typ}, {len(entries)}> m_{name}regs;")
    return "\n".join(out), "\n".join(storage), initializers, "\n".join(resets)


def _csr_lookup(context):
    handle = context.symbol("struct", "Csr")
    indirect = any("indirect_address" in record for record, _ in context.csrs)
    lookup = (
        """auto csr = m_csr_indirect_addr_map.find(std::make_tuple(target_mode, csr_indirect_addr.to_defined(), window_slot));
if (csr == m_csr_indirect_addr_map.end()) { csr_handle.valid = false; return csr_handle; }
csr_handle.valid = csr->second->defined();
csr_handle.name = csr->second->name();
csr_handle.addr_type = CsrAddressType::Indirect;
csr_handle.address = csr_indirect_addr;
csr_handle.indirect_slot = window_slot;
csr_handle.mode = csr->second->mode();
csr_handle.writable = csr->second->writable();
return csr_handle;"""
        if indirect
        else "csr_handle.valid = false; return csr_handle;"
    )
    out = [
        f"""
{handle} direct_csr_lookup(const PossiblyUnknownBits<12>& addr) {{
  {handle} result;
  auto csr = m_csr_addr_map.find(addr);
  if (csr == m_csr_addr_map.end()) {{ result.valid = false; return result; }}
  result.valid = csr->second->defined(); result.name = csr->second->name();
  result.addr_type = CsrAddressType::Direct; result.address = addr; result.indirect_slot = 0_b;
  result.mode = csr->second->mode(); result.writable = csr->second->writable();
  return result;
}}
{handle} indirect_csr_lookup(const PrivilegeMode& target_mode, const PossiblyUnknownBits<64>& csr_indirect_addr, const Bits<4>& window_slot) {{
  {handle} csr_handle;
  udb_assert(window_slot > 0_b && window_slot <= 6_b, "Indirect slots must be between 1-6, inclusive");
  {lookup}
}}
"""
    ]
    for action in ("hw_read", "sw_read", "sw_write"):
        write = action == "sw_write"
        ret = "void" if write else "PossiblyUnknownBits<64>"
        args = f", const PossiblyUnknownBits<{context.mxlen}>& value" if write else ""
        call = f"csr->second->{action}(" + ("value, " if write else "") + "xlen().to_defined());"
        call = call if write else "return " + call
        alternative = (
            f"""
auto csr = m_csr_indirect_addr_map.find(std::make_tuple(csr_handle.mode, csr_handle.address.to_defined(), csr_handle.indirect_slot.to_defined()));
udb_assert(csr != m_csr_indirect_addr_map.end(), "CSR not found");
{call}
"""
            if indirect
            else 'udb_assert(false, "There are no indirect CSRs"); __builtin_unreachable();'
        )
        out.append(f"""
{ret} csr_{action}(const {handle}& csr_handle{args}) {{
  if (csr_handle.addr_type == CsrAddressType::Direct) {{
    auto csr = m_csr_addr_map.find(csr_handle.address);
    udb_assert(csr != m_csr_addr_map.end(), "CSR not found");
    {call}
  }} else {{ {alternative} }}
}}
""")
    return "\n".join(out)


def hart_header(context):
    hart, params, container = (
        context.symbol("hart"),
        context.symbol("params"),
        context.symbol("csr_container"),
    )
    reg_methods, reg_storage, reg_init, reg_resets = _registers(context)
    friends, sizes, lengths = [], [], []
    for instruction in context.instructions:
        cls = context.symbol("inst", instruction.name)
        friends.append(f"template <unsigned XLEN, SocModel _SocType> friend class {cls};")
        for xlen in context.xlens:
            if (instruction.name, xlen) in context.encodings:
                sizes.append(f"sizeof({cls}<{xlen}, SocType>)")
                lengths.append(f"{cls}<{xlen}, SocType>::EncodingLength")
    for record, csr in context.csrs:
        friends.append(f"friend class {context.symbol('csr', record.name)}<SocType>;")
        for field in context.fields(record, csr):
            friends.append(
                f"friend class {context.symbol('csr_field', record.name, field.name)}<SocType>;"
            )
    globals_, reset_globals = [], []
    for name, dtype, immutable, initializer in context.globals():
        typ = cpp_type(dtype)
        if immutable:
            globals_.append(f"static constexpr {typ} {name} = {initializer};")
        else:
            globals_.append(f"static {typ} {name};")
            if initializer:
                reset_globals.append(f"{name} = {initializer};")
    addr_map, name_map, indirect_map = [], [], []
    for record, _ in context.csrs:
        member = "m_csrs." + record.name.replace(".", "_")
        name_map.append(f'{{"{record.name}", &{member}}}')
        if record.get("address") is not None:
            addr_map.append(f"{{PossiblyUnknownBits<12>{{{record['address']}_b, 0_b}}, &{member}}}")
        if "indirect_address" in record:
            indirect_map.append(
                f"{{std::make_tuple(PrivilegeMode::{record['priv_mode']}, Bits<64>{{{record['indirect_address']}_b}}, Bits<4>{{{record['indirect_slot']}_b}}), &{member}}}"
            )
    init = [
        "HartBase<SocType>(hart_id, soc, cfg)",
        "m_params(cfg)",
        *reg_init,
        "m_csrs(this)",
        "m_csr_addr_map{" + ", ".join(addr_map) + "}",
    ]
    if indirect_map:
        init.append("m_csr_indirect_addr_map{" + ", ".join(indirect_map) + "}")
    init.append("m_csr_name_map{" + ", ".join(name_map) + "}")
    macro, undef = macros(context, parent="this", hart=True)
    cached = context.symbol("struct", "CachedTranslationResult")
    cached_ctor = (
        "result(this)" if context.table.get("CachedTranslationResult").is_runtime else "result"
    )
    return f"""#pragma once
#include <cstdint>
#include <deque>
#include <map>
#include <tuple>
#include <unordered_map>
#include "udb/defines.hpp"
#if !defined(JSON_ASSERT)
#define JSON_ASSERT(cond) udb_assert(cond, "JSON assert");
#endif
#include <nlohmann/json-schema.hpp>
#include "udb/hart.hpp"
#include "udb/cfgs/{context.name}/params.hxx"
#include "udb/cfgs/{context.name}/csr_container.hxx"
#include "udb/cfgs/{context.name}/structs.hxx"
#include "udb/enum.hxx"
#include "udb/bitfield.hxx"
#include "udb/util.hpp"
#include "udb/inst.hpp"
#include "udb/bb_cache.hpp"
namespace udb {{ template <SocModel SocType> class {hart}; }}
#include "udb/cfgs/{context.name}/inst.hxx"
namespace udb {{
template <SocModel SocType> class {hart} : public HartBase<SocType> {{
  {" ".join(friends)}
  friend class InstBase;
  static constexpr size_t __MAX_INST_CPP_SIZE = std::max({{{", ".join(sizes)}}});
  static constexpr unsigned __MAX_INST_ENCODING_SIZE = std::max({{{", ".join(lengths)}}});
  static inline PoolAllocator<InstBase, __MAX_INST_CPP_SIZE> inst_allocator;
public:
  {" ".join(globals_)}
  #include "udb/cfgs/{context.name}/func_prototypes.hxx"
  static constexpr unsigned MXLEN = {context.mxlen};
  using XReg = Bits<MXLEN>;
  {macro}
  {hart}(uint64_t hart_id, SocType& soc, const Config& cfg) : {", ".join(init)} {{ {reg_resets} }}
  void reset(uint64_t reset_pc) override {{
    HartBase<SocType>::reset(reset_pc); m_pc = Bits<MXLEN>{{reset_pc}};
    {" ".join(reset_globals)}
    m_csrs.reset();
  }}
  {undef}
  bool implemented_version_Q_(const ExtensionName& ext, const VersionRequirement& req) const override {{
    auto it = this->m_cfg.implemented_exts_hash().find(ext);
    return it != this->m_cfg.implemented_exts_hash().end() && req.satisfied_by(it->second.version);
  }}
  template <ExtensionName ext, TemplateString ver> bool _implemented_version_Q_() const {{
    constexpr VersionRequirement req(ver.sv()); return implemented_version_Q_(ext, req);
  }}
  bool implemented_Q_(const ExtensionName& ext) const override {{ return this->m_cfg.implemented_exts_hash().find(ext) != this->m_cfg.implemented_exts_hash().end(); }}
  template <ExtensionName ext> bool _implemented_Q_() const {{ return implemented_Q_(ext); }}
  bool implemented_csr_Q_(const Bits<12>& addr) {{ return m_csr_addr_map.count(addr) == 1; }}
  {_csr_lookup(context)}
  void set_pc(uint64_t pc) override {{ m_pc = Bits<MXLEN>{{pc}}; }}
  void set_next_pc(uint64_t pc) override {{ m_next_pc = Bits<MXLEN>{{pc}}; }}
  template <template <unsigned, bool> class BitsClass, unsigned N, bool Signed>
    requires (BitsType<BitsClass<N, Signed>>)
  void set_next_pc(const BitsClass<N, Signed>& pc) {{ m_next_pc = pc.to_defined(); }}
  uint64_t pc() const override {{ return m_pc.get(); }}
  void advance_pc() override {{ m_pc = m_next_pc; }}
  unsigned mxlen() override {{ return MXLEN; }}
  {reg_methods}
  void printState(FILE* out = stdout) const override;
  CsrBase* csr(unsigned addr) override {{ auto it = m_csr_addr_map.find(Bits<12>{{addr}}); return it == m_csr_addr_map.end() ? nullptr : it->second; }}
  const CsrBase* csr(unsigned addr) const override {{ auto it = m_csr_addr_map.find(Bits<12>{{addr}}); return it == m_csr_addr_map.end() ? nullptr : it->second; }}
  CsrBase* csr(const std::string& name) override {{ auto it = m_csr_name_map.find(name); return it == m_csr_name_map.end() ? nullptr : it->second; }}
  const CsrBase* csr(const std::string& name) const override {{ auto it = m_csr_name_map.find(name); return it == m_csr_name_map.end() ? nullptr : it->second; }}
  const {params}& params() const {{ return m_params; }}
  InstBase* _decode(const XReg& pc, const Bits<{context.largest_encoding}>& encoding) {{
    InstBase* inst = inst_allocator.allocate();
    if (!_decode(pc, encoding, inst)) {{ inst_allocator.free(inst); return nullptr; }} return inst;
  }}
  bool _decode(const XReg& pc, const Bits<{context.largest_encoding}>& encoding, InstBase* obj);
  uint64_t fetch() override {{ return _fetch().get(); }}
  void execute_instruction(const Bits<32>& encoding) {{
    InstBase* inst = reinterpret_cast<InstBase*>(m_execute_instruction_storage.data());
    if (!_decode(m_pc, encoding, inst)) {{ raise(ExceptionCode{{ExceptionCode::IllegalInstruction}}, mode(), encoding); return; }}
    inst->execute();
  }}
  PossiblyUnknownBits<INSTR_ENC_SIZE.get()> _fetch();
  void ifence() override {{ m_bb_cache.invalidate(); HartBase<SocType>::ifence(); this->m_exit_requested = true; }}
  {cached} cached_translation(const PossiblyUnknownBits<64>& vaddr, const MemoryOperation& op) const {{ {cached} {cached_ctor}; result.valid = false; return result; }}
  {container}<SocType>& _csrContainer() {{ return m_csrs; }}
  int run_one() override {{ return _run_one(); }} int _run_one();
  int run_bb() override {{ return _run_bb(); }} int _run_bb();
  int run_n(uint64_t n) override {{ return _run_n(n); }} int _run_n(uint64_t n);
  void set_mmode_ext_int() {{ m_csrs.mip.MEIP()._hw_write(1_b); refresh_pending_interrupts(); }}
  void clear_mmode_ext_int() {{ m_csrs.mip.MEIP()._hw_write(0_b); refresh_pending_interrupts(); }}
  void set_smode_ext_int() {{ pending_smode_external_interrupt = true; refresh_pending_interrupts(); }}
  void clear_smode_ext_int() {{ pending_smode_external_interrupt = false; refresh_pending_interrupts(); }}
  TranslateResult translate_native(uint64_t vaddr, MemoryOperation op, PrivilegeMode mode_, uint64_t encoding) override {{
    auto result = translate(Bits<64>{{vaddr}}, op, mode_, Bits<64>{{encoding}});
    return TranslateResult{{result.paddr.get()}};
  }}
  PrivilegeMode _get_mode() override {{ return current_mode; }}
  void _set_mode(const PrivilegeMode& mode_) override {{ current_mode = mode_; }}
private:
  XReg m_pc; XReg m_next_pc; InstBase* m_cur_inst = nullptr;
  {params} m_params;
  {reg_storage}
  {container}<SocType> m_csrs;
  std::unordered_map<PossiblyUnknownBits<12>, CsrBase*> m_csr_addr_map;
  {"std::map<std::tuple<PrivilegeMode, Bits<64>, Bits<4>>, CsrBase*> m_csr_indirect_addr_map;" if indirect_map else ""}
  std::map<std::string, CsrBase*> m_csr_name_map;
  alignas(InstBase) std::array<uint8_t, __MAX_INST_CPP_SIZE> m_run_one_inst_storage;
  alignas(InstBase) std::array<uint8_t, __MAX_INST_CPP_SIZE> m_execute_instruction_storage;
  BasicBlockCache<__MAX_INST_CPP_SIZE> m_bb_cache;
}};
}}
#include "udb/cfgs/{context.name}/hart_impl.hxx"
#include "udb/cfgs/{context.name}/idl_funcs_impl.hxx"
#include "udb/cfgs/{context.name}/inst_impl.hxx"
"""


def hart_implementation(context):
    hart = context.symbol("hart")
    out = [
        '#pragma once\n#include <memory>\n#include <fmt/core.h>\n#include "udb/inst.hpp"\nusing namespace std::literals;\nnamespace udb {'
    ]
    for name, dtype, immutable, _ in context.globals():
        if not immutable:
            out.append(f"template <SocModel SocType>\n{cpp_type(dtype)} {hart}<SocType>::{name};")
    printing = []
    for record in context.database.objects("register_file"):
        name = record.name.lower()
        width, _capacity = context.register_width(record.name)
        value = (
            f"static_cast<uint64_t>(_{name}reg(i).get().get_ui())"
            if width == WIDTH_UNKNOWN or width > 64
            else f"_{name}reg(i).get()"
        )
        printing.append(
            f'fmt::print(out, "{record.name} registers:\\n"); for (unsigned i = 0; i < {len(record["registers"])}; i++) fmt::print(out, "{name}{{}}: {{:#x}}\\n", i, {value});'
        )
    macro, undef = macros(context, parent="this", hart=True)
    out += [
        f'template <SocModel SocType>\nvoid {hart}<SocType>::printState(FILE* out) const {{ fmt::print(out, "Hart %u:\\n", this->m_hart_id); fmt::print(out, "PC: {{:#x}}\\n", m_pc.get()); {" ".join(printing)} }}',
        macro,
    ]
    out.append(
        f"template <SocModel SocType>\nPossiblyUnknownBits<{hart}<SocType>::INSTR_ENC_SIZE.get()> {hart}<SocType>::_fetch() {{\n{context.fetch().cpp()}\n}}"
    )
    out.append(
        f"template <SocModel SocType>\nbool {hart}<SocType>::_decode(const XReg& pc, const Bits<{context.largest_encoding}>& encoding, InstBase* inst) {{\n{decode(context)}\nreturn false;\n}}"
    )
    out += [undef, runtime(context), "}"]
    return "\n".join(out) + "\n"


def runtime(context):
    """The existing ISS stop/notification/basic-block protocol, without tool calls."""
    hart = context.symbol("hart")
    catch_one = """catch (const AbortPreExecute&) { return StopReason::Exception; }
catch (const AbortInstruction&) { advance_pc(); return StopReason::Exception; }
catch (const WfiException&) { advance_pc(); return StopReason::Wfi; }
catch (const PauseException&) { advance_pc(); return StopReason::Pause; }
catch (const UnpredictableBehaviorException&) { advance_pc(); return StopReason::UnpredictableBehavior; }
catch (const ExitEvent& e) { advance_pc(); this->m_exit_code = e.code(); this->m_exit_reason = e.what(); return e.code() == 0 ? StopReason::ExitSuccess : StopReason::ExitFailure; }"""
    catch_bb = catch_one.replace("advance_pc();", "current_bb->invalidate(); advance_pc();")
    fetch_decode = """Bits<INSTR_ENC_SIZE.get()> enc;
this->Notify(PREFETCH_EVENT, (void*)&m_pc);
enc = _fetch(); this->Notify(FETCH_EVENT, (void*)&enc);
"""
    failure = """if (!_decode(m_pc, enc, m_cur_inst)) {
  try { raise(ExceptionCode{ExceptionCode::IllegalInstruction}, mode(), m_params.REPORT_ENCODING_IN_MTVAL_ON_ILLEGAL_INSTRUCTION.value() ? enc : decltype(enc){0}); }
  catch (const AbortInstruction&) { return StopReason::Exception; }
}
this->Notify(DECODE_EVENT, (void*)m_cur_inst);"""
    execute = """m_next_pc = m_pc + Bits<MXLEN>{m_cur_inst->enc_len()};
this->Notify(PREEXECUTE_EVENT, (void*)m_cur_inst);
m_cur_inst->execute();
this->Notify(EXECUTE_EVENT, (void*)m_cur_inst);
advance_pc();"""
    return f"""
template <SocModel SocType> int {hart}<SocType>::_run_one() {{
  try {{
    {fetch_decode}
    m_cur_inst = reinterpret_cast<InstBase*>(m_run_one_inst_storage.data());
    {failure}
    {execute}
    if (this->m_exit_requested) this->m_exit_requested = false;
  }} {catch_one}
  return StopReason::InstLimitReached;
}}
template <SocModel SocType> int {hart}<SocType>::_run_bb() {{
  auto current_bb = m_bb_cache.get(m_pc.get());
  try {{
    if (current_bb->start_pc() == m_pc.get()) {{
      current_bb->reset();
      const auto size = current_bb->size();
      for (unsigned b = 0; b < size; b++) {{
        m_cur_inst = current_bb->pop();
        {execute}
        if (this->m_exit_requested) {{ this->m_exit_requested = false; break; }}
      }}
    }} else {{
      current_bb->recycle(m_pc.get());
      do {{
        {fetch_decode}
        m_cur_inst = current_bb->alloc_inst();
        {failure}
        {execute}
        if (this->m_exit_requested) {{ this->m_exit_requested = false; break; }}
      }} while (!(current_bb->full() || m_cur_inst->control_flow()));
    }}
  }} {catch_bb}
  return StopReason::InstLimitReached;
}}
template <SocModel SocType> int {hart}<SocType>::_run_n(uint64_t n) {{
  while (n > 0) {{
    if (n >= decltype(m_bb_cache)::MAX_BASIC_BLOCK_SIZE) {{
      auto before = this->m_num_inst_exec;
      auto reason = _run_bb();
      if (reason != StopReason::InstLimitReached) return reason;
      n -= this->m_num_inst_exec - before;
    }} else {{
      auto reason = _run_one();
      if (reason != StopReason::InstLimitReached) return reason;
      n--;
    }}
  }}
  return StopReason::InstLimitReached;
}}
"""

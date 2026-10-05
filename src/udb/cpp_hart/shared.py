# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

"""Configuration-independent database, enum, bitfield and factory interfaces."""

from .conditions import condition_cpp
from .emitter import Emitter
from .types import cpp_type, literal


def enums(context):
    header = [
        '#pragma once\n#include <cstdint>\n#include <concepts>\n#include <string>\n#include "udb/bits.hpp"\nnamespace udb {'
    ]
    source = ['#include "udb/enum.hxx"\n#include "udb/cpp_exceptions.hpp"\nnamespace udb {']
    types = (
        context.enum_types
        if hasattr(context, "enum_types")
        else (enum.type(context.table) for enum in context.global_ast.enums)
    )
    for dtype in types:
        typ = "uint32_t" if dtype.width <= 32 else "uint64_t"
        name = dtype.name
        members = "\n".join(
            f"static constexpr {typ} {key} = {value};"
            for key, value in zip(dtype.element_names, dtype.element_values, strict=True)
        )
        header.append(f"""
struct {name} {{
  using ValueType = {typ};
  {members}
  constexpr {name}() = default;
  constexpr {name}(const {typ}& value) : m_value(value) {{}}
  template <BitsType BitsClass>
  constexpr {name}(const BitsClass& value) : m_value(value.get()) {{}}
  static const {name} from_s(const std::string_view& value);
  {typ} m_value;
  constexpr {typ} value() const {{ return m_value; }}
  constexpr uint32_t size() const {{ return {len(dtype.element_names)}; }}
  template <std::integral T> constexpr operator T() const {{ return m_value; }}
  template <std::integral T> constexpr {name}& operator<<(const T& rhs) {{ m_value << rhs; return *this; }}
  template <std::integral T> constexpr bool operator==(const T& rhs) const {{ return m_value == rhs; }}
  constexpr bool operator==(const {name}& rhs) const {{ return m_value == rhs.m_value; }}
  constexpr bool operator!=(const {name}& rhs) const {{ return m_value != rhs.m_value; }}
  constexpr bool operator<(const {name}& rhs) const {{ return m_value < rhs.m_value; }}
}};
const std::string to_s(const {name}& value);
template <std::integral T> constexpr T operator<<(const T& lhs, const {name}& rhs) {{ return lhs << rhs.value(); }}
template <std::integral T> constexpr bool operator==(const T& lhs, const {name}& rhs) {{ return lhs == rhs.value(); }}
""")
        tests = "\n".join(
            f'if (value == "{member}") return {name}::{member};' for member in dtype.element_names
        )
        # Aliased enum values require one case per value, preserving the first name.
        seen = set()
        cases = "\n".join(
            f'case {value}: return "{member}";'
            for member, value in zip(dtype.element_names, dtype.element_values, strict=True)
            if value not in seen and not seen.add(value)
        )
        source.append(f"""
const {name} {name}::from_s(const std::string_view& value) {{
  {tests}
  throw DbError("Bad enum value");
}}
const std::string to_s(const {name}& value) {{
  switch (value.value()) {{ {cases} }}
  return "Unknown";
}}
""")
    return "\n".join(header + ["}"]) + "\n", "\n".join(source + ["}"]) + "\n"


def bitfields(context):
    out = ['#pragma once\n#include "udb/bits.hpp"\n#include "udb/bitfield.hpp"\nnamespace udb {']
    items = (
        context.bitfield_items
        if hasattr(context, "bitfield_items")
        else ((node, context.table) for node in context.global_ast.bitfields)
    )
    for bitfield, table in items:
        dtype = bitfield.type(table)
        name, width = dtype.name, bitfield.size.value(table)
        field_names = tuple(field.field_name for field in bitfield.bitfield_fields)
        field_ranges = tuple(dtype.range(name) for name in field_names)
        initializers = ", ".join(f"{key}(*this)" for key in field_names)
        members = "\n".join(
            f"BitfieldMember<{width}, {bits.start}, {len(bits)}> {key};"
            for key, bits in zip(field_names, field_ranges, strict=True)
        )
        out.append(f"""
class {name} : public Bitfield<{width}> {{
public:
  {name}() : {initializers} {{}}
  template <template <unsigned, bool> class BitsClass>
  {name}(const BitsClass<{width}, false>& value) : Bitfield<{width}>(value), {initializers} {{}}
  {name}(const {name}& other) : Bitfield<{width}>(static_cast<PossiblyUnknownBits<{width}>>(other)), {initializers} {{}}
  {name}& operator=(const {name}& other) {{
    this->m_value = static_cast<PossiblyUnknownBits<{width}>>(other); return *this;
  }}
  {members}
}};
""")
    return "\n".join(out + ["}"]) + "\n"


DB_HEADER = """#pragma once
#include <any>
#include <array>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
#include <fmt/ranges.h>
#include <nlohmann/json.hpp>
#include "udb/bits.hpp"
#include "udb/enum.hxx"
#include "udb/version.hpp"
using namespace std::literals;
namespace udb {
template <unsigned N, bool Signed> void to_json(nlohmann::json& j, const _Bits<N, Signed>& b) { j = nlohmann::json{b.get()}; }
template <unsigned N, bool Signed> void to_json(nlohmann::json& j, const _PossiblyUnknownBits<N, Signed>& b) { j = nlohmann::json{b.get()}; }
template <unsigned N, bool Signed> void from_json(const nlohmann::json& j, _Bits<N, Signed>& b) { b = _Bits<N, Signed>{j.get<typename _Bits<N, Signed>::StorageType>()}; }
template <unsigned N, bool Signed> void from_json(const nlohmann::json& j, _PossiblyUnknownBits<N, Signed>& b) { b = _PossiblyUnknownBits<N, Signed>{_Bits<N, Signed>{j.get<typename _Bits<N, Signed>::StorageType>()}, 0_b}; }
class SatisfiedResult {
public:
  enum class Type { Yes, Maybe, No };
  SatisfiedResult() = delete;
  constexpr SatisfiedResult(const Type& result) : m_result(result) {}
  constexpr SatisfiedResult(const SatisfiedResult&) = default;
  constexpr SatisfiedResult(SatisfiedResult&&) = default;
  SatisfiedResult operator&&(const SatisfiedResult& rhs) const {
    if (m_result == Type::No || rhs.m_result == Type::No) return Type::No;
    if (m_result == Type::Maybe || rhs.m_result == Type::Maybe) return Type::Maybe;
    return Type::Yes;
  }
  SatisfiedResult operator||(const SatisfiedResult& rhs) const {
    if (m_result == Type::Yes || rhs.m_result == Type::Yes) return Type::Yes;
    if (m_result == Type::Maybe || rhs.m_result == Type::Maybe) return Type::Maybe;
    return Type::No;
  }
  SatisfiedResult operator!() const {
    if (m_result == Type::Yes) return Type::No;
    if (m_result == Type::No) return Type::Yes;
    return Type::Maybe;
  }
  bool operator==(const SatisfiedResult& rhs) const { return m_result == rhs.m_result; }
  bool operator!=(const SatisfiedResult& rhs) const { return m_result != rhs.m_result; }
private:
  const Type m_result;
};
static constexpr SatisfiedResult Yes(SatisfiedResult::Type::Yes);
static constexpr SatisfiedResult Maybe(SatisfiedResult::Type::Maybe);
static constexpr SatisfiedResult No(SatisfiedResult::Type::No);
class Config;
class Parameter {
public:
  constexpr Parameter(const std::string_view& name) : m_name(name) {}
  const std::string_view& name() const { return m_name; }
  virtual SatisfiedResult defined(const Config& cfg) const = 0;
  virtual bool has_value() const = 0;
protected:
  const std::string_view m_name;
};
class Config {
public:
  struct ExtensionVersion {
    std::string name; Version version;
    ExtensionVersion(const std::string& name_, const std::string& version_) : name(name_), version(version_) {}
    ExtensionVersion(const ExtensionVersion&) = default;
    ExtensionVersion(ExtensionVersion&&) = default;
  };
  Config(const nlohmann::json& implemented_exts, const nlohmann::json& param_values);
  Config(const Config&) = default;
  Config(Config&&) = default;
  SatisfiedResult ext_req_is_met(const ExtensionName& ext_name, const VersionRequirement& req) const;
  const std::vector<ExtensionVersion>& implemented_exts() const { return m_implemented_exts; }
  const std::map<ExtensionName, ExtensionVersion>& implemented_exts_hash() const { return m_implemented_exts_hash; }
  const ExtensionVersion& implemented_ext(const ExtensionName& name) const { return m_implemented_exts_hash.at(name); }
  bool has_param_value(const std::string& name) const { return m_param_values.contains(name); }
  const std::any& param_value(const std::string& name) const { return m_param_values.at(name); }
private:
  std::vector<ExtensionVersion> m_implemented_exts;
  std::map<ExtensionName, ExtensionVersion> m_implemented_exts_hash;
  std::map<std::string, std::any> m_param_values;
};
class DbData {
  DbData() = delete;
public:
  static std::map<std::string, std::string> SCHEMAS;
};
"""


def database_data(context, schemas):
    header = [DB_HEADER]
    source = ['#include "udb/db_data.hxx"\n#include "udb/util.hpp"\nusing namespace udb;']
    entries = []
    for name, text in sorted(schemas.items()):
        delimiter = "UDB_SCHEMA"
        while f'){delimiter}"' in text:
            delimiter += "_"
        entries.append(f'{{"{name}", R"{delimiter}({text}){delimiter}"}}')
    source.append(
        "std::map<std::string, std::string> udb::DbData::SCHEMAS = {" + ",\n".join(entries) + "};"
    )
    tests = "\n".join(
        f'if (name == "{ext.name}") return ExtensionName::{ext.name};'
        for ext in context.database.extensions
    )
    source.append(f"""static ExtensionName str_to_ext_name(const std::string& name) {{
{tests}
udb_assert(false, fmt::format("'{{}}' is not a known extension", name));
__builtin_unreachable();
}}
Config::Config(const nlohmann::json& implemented_exts, const nlohmann::json& param_values) {{
  for (auto e : implemented_exts) {{
    ExtensionVersion ext_ver(
      (e.is_array() ? e[0] : e["name"]).get<std::string>(),
      (e.is_array() ? e[1] : e["version"]).get<std::string>());
    m_implemented_exts.push_back(ext_ver);
    m_implemented_exts_hash.insert(std::pair{{str_to_ext_name(ext_ver.name), ext_ver}});
  }}
""")
    for parameter in context.parameters:
        name = parameter.name
        dtype = context.table.get(name).type
        typ = cpp_type(dtype)
        cls = context.symbol("param", name)
        header.append(f"""
class {cls} : public Parameter {{
public:
  constexpr {cls}() : Parameter("{name}"sv) {{}}
  explicit {cls}(const nlohmann::json& value) : Parameter("{name}"sv), m_value(std::in_place, value.get<{typ}>()) {{}}
  SatisfiedResult defined(const Config& cfg) const override;
  bool has_value() const override {{ return m_value.has_value(); }}
  void set_value({typ} val) {{ m_value = val; }}
  const {typ} value() const {{ return m_value.value(); }}
private:
  std::optional<{typ}> m_value;
}};
""")
        source.append(
            f'if (param_values.contains("{name}")) m_param_values.emplace("{name}", param_values["{name}"].get<{typ}>());'
        )
    source.append(
        "}\nSatisfiedResult Config::ext_req_is_met(const ExtensionName& ext, const VersionRequirement& req) const { auto it = m_implemented_exts_hash.find(ext); return it != m_implemented_exts_hash.end() && req.satisfied_by(it->second.version) ? Yes : No; }"
    )
    for parameter in context.parameters:
        source.append(
            f"SatisfiedResult {context.symbol('param', parameter.name)}::defined(const Config& cfg) const {{ return {condition_cpp(context.condition(parameter), context, parameter_result=True)}; }}"
        )
    return "\n".join(header + ["}"]) + "\n", "\n".join(source) + "\n"


def parameters(context):
    cls = context.symbol("params")
    values = context.arch.configuration.params
    out = [
        '#pragma once\n#include "udb/bits-yaml.hpp"\n#include "udb/db_data.hxx"\nnamespace udb {',
        f"struct {cls} {{",
        "class Error : public std::runtime_error { public: using std::runtime_error::runtime_error; };",
    ]
    checks = []
    for param in context.parameters:
        name = param.name
        if name in values:
            dtype = context.table.get(name).type
            typ = cpp_type(dtype, constexpr_value=values[name])
            out.append(
                f"struct {name}_Constant {{ static constexpr {typ} value() {{ return {literal(values[name])}; }} constexpr bool has_value() const {{ return true; }} }};\nstatic constexpr {name}_Constant {name}{{}};"
            )
            checks.append(
                f'udb_assert(cfg.has_param_value("{name}"), "Required built-in parameter {name} is missing");\nudb_assert(udb_param_val_eq(std::any_cast<const {cpp_type(dtype)}&>(cfg.param_value("{name}")), {name}.value()), "Runtime parameter {name} differs from built-in value");'
            )
        else:
            out.append(f"{context.symbol('param', name)} {name};")
            checks.append(
                f'if ({name}.defined(cfg) == Yes) {{ udb_assert(cfg.has_param_value("{name}"), "Required parameter {name} is missing"); {name}.set_value(std::any_cast<{cpp_type(context.table.get(name).type)}>(cfg.param_value("{name}"))); }} else {{ udb_assert(!cfg.has_param_value("{name}"), "Parameter {name} should not be defined"); }}'
            )
    out += [f"{cls}(const Config& cfg) {{", *checks, "}", "};\n}"]
    return "\n".join(out) + "\n"


def structs(context):
    out = [
        f'#pragma once\n#include "udb/bits.hpp"\n#include "udb/bitfield.hxx"\n#include "udb/enum.hxx"\n#include "udb/cfgs/{context.name}/params.hxx"\nnamespace udb {{'
    ]
    out += [
        f"#define __UDB_STRUCT(name) {context.symbol('cfg')}_ ## name ## _Struct",
        f"#define __UDB_STATIC_PARAM(name) {context.symbol('params')}::name.value()",
        "#define __UDB_RUNTIME_PARAM(name) hart->params().name.value()",
        "#define __UDB_HART hart",
    ]
    emitter = Emitter(context.table)
    for struct in context.global_ast.structs:
        name = context.symbol("struct", struct.name)
        members = []
        runtime = []
        has_runtime = False
        for member, typ in zip(struct.member_names, struct.member_types, strict=True):
            dtype = typ.type(context.table)
            members.append(f"{emitter.type_name(typ)} {member};")
            if dtype.is_runtime:
                has_runtime = True
                initializer = emitter.runtime_initializer(typ, dtype)
                if initializer is not None:
                    runtime.append(f"{member}({initializer})")
        # Runtime structs are always constructed from the hart, even when every
        # runtime member is emitted with a fixed (maximum) width.
        if runtime:
            ctor = f"template <class HartType> {name}(const HartType* hart) : {', '.join(runtime)} {{}}\n{name}() = delete;"
        elif has_runtime:
            ctor = f"template <class HartType> {name}(const HartType*) {{}}\n{name}() = delete;"
        else:
            ctor = f"{name}() = default;"
        assignments = "\n".join(f"{member} = other.{member};" for member in struct.member_names)
        out.append(
            f"struct {name} {{\n"
            + "\n".join(members)
            + f"\n{ctor}\n~{name}() = default;\n{name}& operator=(const {name}& other) {{ if (this == &other) return *this; {assignments} return *this; }}\n}};"
        )
    out += [
        "#undef __UDB_STRUCT\n#undef __UDB_STATIC_PARAM\n#undef __UDB_RUNTIME_PARAM\n#undef __UDB_HART",
        "}",
    ]
    return "\n".join(out) + "\n"


def factory(contexts):
    includes = "\n".join(f'#include "udb/cfgs/{context.name}/hart.hxx"' for context in contexts)
    config_names = ", ".join(f'"{context.name}"' for context in contexts)
    cases = "\n".join(
        f'if (config_name == "{context.name}") return new {context.symbol("hart")}<SocType>(hart_id, soc, cfg);'
        for context in contexts
    )
    return f"""#pragma once
#include "udb/defines.hpp"
#include "udb/config_validator.hpp"
{includes}
namespace udb {{
class HartFactory {{
  HartFactory() = delete;
public:
  static constexpr std::array<std::string_view, {len(contexts)}> configs() {{ return {{{config_names}}}; }}
  template <SocModel SocType>
  static HartBase<SocType>* create(const std::string& config_name, uint64_t hart_id, const std::filesystem::path& path, SocType& soc) {{
    return create(config_name, hart_id, ConfigValidator::validate(YAML::LoadFile(path.string())), soc);
  }}
  template <SocModel SocType>
  static HartBase<SocType>* create(const std::string& config_name, uint64_t hart_id, const std::string& yaml, SocType& soc) {{
    return create(config_name, hart_id, ConfigValidator::validate(YAML::Load(yaml)), soc);
  }}
  template <SocModel SocType>
  static HartBase<SocType>* create(const std::string& config_name, uint64_t hart_id, const nlohmann::json& json, SocType& soc) {{
    Config cfg(json["implemented_extensions"], json["params"]);
    {cases}
    fmt::print("'{{}}' is not a valid config name\\n", config_name);
    exit(1);
  }}
}};
}}
"""

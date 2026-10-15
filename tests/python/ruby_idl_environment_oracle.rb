# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Oracle for slice 16 (the IDL architecture-environment adapter): builds a real
# `Udb::ConfiguredArchitecture` for one config name (default resolver, real
# `cfgs/`/`spec/`) and dumps JSON describing everything
# `src/udb/idl_environment.py` is supposed to reproduce.
#
# Usage: bundle exec ruby tests/python/ruby_idl_environment_oracle.rb <config-name>
#
# Building a real ConfiguredArchitecture is slow and memory-hungry (it runs
# the full YAML resolution pipeline plus the underlying architecture/IDL
# machinery for `create_symtab`) -- callers MUST run one config at a time and
# never run two of these processes concurrently.

require "json"
require "udb"
require "udb/resolver"

config_name = ARGV.fetch(0)

resolver = Udb::Resolver.new(quiet: true)
cfg_arch = resolver.cfg_arch_for(config_name)
symtab = cfg_arch.symtab

def dump_value(value)
  case value
  when Integer, String, TrueClass, FalseClass, Array
    value
  when NilClass
    nil
  else
    value.to_s
  end
end

# Reproduces `symtab_callbacks`'s `implemented`/`implemented_version` closures
# (cfg_arch.rb ~502-543) in their *steady-state* (post-symtab-construction)
# branch -- i.e. with `constructing_symtab?` always false, since this oracle
# never runs `add_global_symbols` (that's slice 15, not yet ported to Python).
def implemented_tri_state(cfg_arch, ext_name, version_reqs = [])
  if cfg_arch.fully_configured?
    cfg_arch.ext?(ext_name, version_reqs)
  elsif cfg_arch.ext?(ext_name, version_reqs)
    true
  elsif cfg_arch.prohibited_ext?(ext_name)
    false
  end
end

global_scope = symtab.keys_pretty[0]
builtin_vars = global_scope.filter_map do |key|
  var = symtab.get(key)
  next unless var.is_a?(Idl::Var) && var.param?

  {
    name: var.name,
    type: var.type.to_s,
    const: var.const?,
    value: var.value.nil? ? "unknown" : dump_value(var.value)
  }
end.sort_by { |h| h[:name] }

enums = %w[ExtensionName ExceptionCode InterruptCode].to_h do |enum_name|
  enum_type = symtab.get(enum_name)
  [enum_name, enum_type.element_names.zip(enum_type.element_values).to_h]
end

csr_names = cfg_arch.csrs.map(&:name).sort

# Reproduces `create_symtab`'s (cfg_arch.rb ~615-638) bootstrap-symtab procedure for
# `register_file_max_widths` exactly, by capturing the `register_file_max_widths:`
# keyword argument `create_symtab` passes to the real `Idl::SymbolTable.new` call --
# that value isn't otherwise exposed via any public reader. `create_symtab` is
# `private`, so it's invoked via `send`; it recomputes params/register-length
# compilation but not the whole YAML resolution pipeline, so a second call here is not
# prohibitively expensive.
captured_rf_max_widths = nil
Idl::SymbolTable.prepend(
  Module.new do
    define_method(:initialize) do |**kwargs|
      captured_rf_max_widths = kwargs[:register_file_max_widths] if kwargs[:register_file_max_widths]&.any?
      super(**kwargs)
    end
  end
)
cfg_arch.send(:create_symtab)
raise "Could not capture register_file_max_widths from create_symtab" if captured_rf_max_widths.nil?

register_files = cfg_arch.register_files.map do |rf|
  max_length =
    begin
      captured_rf_max_widths.fetch(rf.name)
    rescue StandardError => e
      "error: #{e.class}: #{e.message}"
    end
  { name: rf.name, register_length_expr: rf.register_length, max_register_length: max_length }
end.sort_by { |h| h[:name] }

sample_versions = ["= 1.0.0", ">= 2.0.0", "= 0.1.0", "> 1.9.1", "<= 1.9.1"]
extension_results = cfg_arch.extensions.to_h do |ext|
  per_version = sample_versions.to_h { |v| [v, implemented_tri_state(cfg_arch, ext.name, [v])] }
  [ext.name, { implemented: implemented_tri_state(cfg_arch, ext.name), implemented_version: per_version }]
end

# Keep structural CSR parity separate from the still-unported dynamic behavior bodies.
# Query real CSR/field methods, not a second implementation of their YAML interpretation.
csr_samples = {
  "mstatush" => [],
  "scontext" => [],
  "tselect" => [],
  "mstatus" => ["SXL", "MIE"],
  "satp" => ["PPN"]
}
csr_semantics = csr_samples.to_h do |csr_name, field_names|
  csr = cfg_arch.csr(csr_name)
  fields = field_names.to_h do |field_name|
    field = csr.field(field_name)
    location_requires_base =
      begin
        field.location
        false
      rescue ArgumentError
        true
      end
    bases = [32, 64].select { |base| field.defined_in_base?(base) }
    [field_name, {
      exists: field.exists?,
      base32: field.defined_in_base32?,
      base64: field.defined_in_base64?,
      all_bases: field.defined_in_all_bases?,
      widths: bases.to_h { |base| [base.to_s, field.width(base)] },
      locations: bases.to_h { |base| [base.to_s, field.location(base).to_a] },
      location_requires_base: location_requires_base
    }]
  end
  [csr_name, {
    base: csr.base,
    length: csr.length,
    length32: csr.length(32),
    length64: csr.length(64),
    max_length: csr.max_length,
    dynamic: csr.dynamic_length?,
    fields: fields
  }]
end

result = {
  config: config_name,
  mxlen: cfg_arch.mxlen,
  possible_xlens: cfg_arch.possible_xlens,
  builtin_vars: builtin_vars,
  enums: enums,
  csr_names: csr_names,
  register_files: register_files,
  extensions: extension_results,
  csr_semantics: csr_semantics
}

puts JSON.generate(result)

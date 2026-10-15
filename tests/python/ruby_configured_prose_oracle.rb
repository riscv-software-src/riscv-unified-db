# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Development-only oracle. TMPDIR and resolver outputs must be worktree-local.
require "json"
require "pathname"
require "udb"
require "udb/resolver"

root = Pathname.new(ARGV.fetch(0))
payload = JSON.parse($stdin.read)
if payload["whitespace_probe"]
  require "tilt"
  class WhitespaceProbe
    MXLEN = 64
    def ext?(name, requirements = nil) = %i[H A].include?(name)
    def implemented_exception_codes
      [Struct.new(:num, :name).new(1, "One"), Struct.new(:num, :name).new(2, "Two")]
    end
  end
  puts JSON.generate(payload.fetch("templates").map do |template|
    { "template" => template,
      "raw" => { "value" => Tilt["erb"].new(nil, trim: "-") { template }.render(WhitespaceProbe.new) } }
  end)
  exit
end
resolver = Udb::Resolver.new(
  root,
  schemas_path_override: root / "spec/schemas",
  cfgs_path_override: root / "cfgs",
  gen_path_override: root / "gen/handoff/prose-ruby-resolved",
  std_path_override: root / "spec/std/isa",
  custom_path_override: root / "spec/custom/isa",
  quiet: true
)

def attempt
  { "value" => yield }
rescue StandardError => error
  { "error" => { "class" => error.class.name, "message" => error.message } }
end

def code_data(codes)
  codes.sort_by(&:num).map do |code|
    { "num" => code.num, "name" => code.name, "display_name" => code.display_name }
  end
end

results = payload.fetch("configurations").to_h do |name, declaration|
  selected = declaration.fetch("path", name)
  selected = Pathname.new(selected) if selected.end_with?(".yaml")
  architecture = resolver.cfg_arch_for(selected)
  env = architecture.send(:erb_env)
  parameters = architecture.params.to_h do |parameter|
    value = if env.const_defined?(parameter.name, false)
              constant = env.const_get(parameter.name, false)
              constant == :unknown ? { "state" => "unknown" } : { "value" => constant }
            else
              { "state" => "unavailable" }
            end
    [parameter.name, value]
  end
  facts = {
    "parameters" => parameters,
    "extensions" => payload.fetch("extension_queries").to_h do |query|
      [query.fetch("key"), architecture.ext?(query.fetch("name"), query.fetch("requirements"))]
    end,
    "possible_xlens" => attempt { architecture.possible_xlens },
    "exception_codes_raw" => attempt { code_data(architecture.implemented_exception_codes) },
    "interrupt_codes_raw" => attempt { code_data(architecture.implemented_interrupt_codes) },
    "exception_codes" => attempt do
      code_data(architecture.exception_codes.select do |code|
        code.defined_by_condition.could_be_satisfied_by_cfg_arch?(architecture)
      end)
    end,
    "interrupt_codes" => attempt do
      code_data(architecture.interrupt_codes.select do |code|
        code.defined_by_condition.could_be_satisfied_by_cfg_arch?(architecture)
      end)
    end,
    "code_selection_reproduction" => {
      "h_implemented" => architecture.ext?("H"),
      "vscall_condition" => architecture.exception_codes.find { |code| code.name == "VScall" }
        .defined_by_condition.could_be_satisfied_by_cfg_arch?(architecture)
    },
    "structured_exception_records" => attempt do
      architecture.extensions.flat_map do |ext|
        ext.exception_codes.map do |code|
          {
            "num" => code.num,
            "name" => architecture.render_erb(code.name, "exception code name: #{code.name}"),
            "var" => code.var,
            "ext" => ext.name
          }
        end
      end
    end
  }
  if payload["capture_validity"]
    facts["configuration_validity"] = attempt do
      validation = architecture.valid?
      { "valid" => validation.valid, "reasons" => validation.reasons }
    end
  end
  if payload["code_name_templates"]
    payload["code_name_templates"].each do |identifier, template|
      code = architecture.exception_codes.find { |item| item.name == identifier }
      raise "missing exception #{identifier}" unless code
      code.define_singleton_method(:name) { template }
    end
    # Reindex after the controlled identity mutation, as a database loaded from
    # templated-name filenames would. Keep the actual wrapper selection method.
    renamed_codes = architecture.exception_codes.sort_by(&:name)
    architecture.define_singleton_method(:exception_codes) { renamed_codes }
    architecture.extensions.each do |extension|
      extension.remove_instance_variable(:@exception_codes) if extension.instance_variable_defined?(:@exception_codes)
    end
    facts["templated_structured_exception_records"] = attempt do
      architecture.extensions.flat_map do |ext|
        ext.exception_codes.map do |code|
          { "num" => code.num,
            "name" => architecture.render_erb(code.name, "exception code name: #{code.name}"),
            "var" => code.var, "ext" => ext.name }
        end
      end
    end
  end
  raw = payload.fetch("templates").map do |item|
    attempt { architecture.render_erb(item.fetch("template"), item.fetch("source")) }
  end

  # Expected-side semantic projection, not raw Ruby parity. Besides the verified
  # interrupt-accessor defect, synthetic declarations can be unsatisfiable or
  # raise Z3 type errors. Preserve those raw outcomes before substituting the
  # existing code predicate; this projection does not certify config validity.
  architecture.define_singleton_method(:implemented_exception_codes) do
    exception_codes.select { |code| code.defined_by_condition.could_be_satisfied_by_cfg_arch?(self) }
  end
  architecture.define_singleton_method(:implemented_interrupt_codes) do
    interrupt_codes.select { |code| code.defined_by_condition.could_be_satisfied_by_cfg_arch?(self) }
  end
  corrected = payload.fetch("templates").each_with_index.map do |item, index|
    if item.fetch("template").match?(/implemented_(interrupt|exception)_codes/)
      attempt { architecture.render_erb(item.fetch("template"), item.fetch("source")) }
    else
      raw.fetch(index)
    end
  end
  [name, { "inputs" => facts, "raw" => raw, "expected" => corrected }]
end
puts JSON.generate(results)

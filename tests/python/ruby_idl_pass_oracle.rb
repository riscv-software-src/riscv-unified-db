# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Transitional black-box oracle for Ruby IDL analysis passes.
#
# Reads a JSON document from stdin and writes one deterministic JSON document.
# Synthetic cases use mock symbol-table inputs. Real cases build each requested
# UDB configuration exactly once in this process and reuse it for every sample.

require "json"
require "pathname"

repo_root = Pathname.new(File.expand_path("../..", __dir__))
$LOAD_PATH.unshift((repo_root / "tools/ruby-gems/idlc/lib").to_s)
$LOAD_PATH.unshift((repo_root / "tools/ruby-gems/udb/lib").to_s)
$LOAD_PATH.unshift((repo_root / "backends/cpp_hart_gen/lib").to_s)

require "idlc"
require "idlc/passes/find_referenced_csrs"
require "idlc/passes/find_return_values"
require "idlc/passes/find_src_registers"
require "idlc/passes/gen_adoc"
require "idlc/passes/gen_option_adoc"
require "idlc/passes/prune"
require "idlc/passes/reachable_exceptions"
require "idlc/passes/reachable_functions"
require "udb"
require "gen_cpp"

MockRegister = Struct.new(:name)

class OracleRegisterFile
  attr_reader :name, :register_length, :registers

  def initialize(spec)
    @name = spec.fetch("name")
    @register_length = "return #{spec.fetch('width')};"
    @registers = Array.new(spec.fetch("count", 32)) { |i| MockRegister.new("#{@name.downcase}#{i}") }
  end
end

class OracleCsrField
  include Idl::CsrField

  attr_reader :name

  def initialize(spec)
    @name = spec.fetch("name")
    @width = spec.fetch("width")
    @value = spec["value"]
    @type = spec.fetch("type", @value.nil? ? "RW" : "RO")
    @bases = spec.fetch("bases", [32, 64])
    first_bit = spec.fetch("lsb", 0)
    @location = first_bit..(first_bit + @width - 1)
    @exists = spec.fetch("exists", true)
  end

  def defined_in_all_bases? = @bases.sort == [32, 64]
  def defined_in_base32? = @bases.include?(32)
  def defined_in_base64? = @bases.include?(64)
  def base64_only? = @bases == [64]
  def base32_only? = @bases == [32]
  def location(_xlen) = @location
  def width(_xlen = nil) = @width
  def type(_xlen = nil) = @type
  def exists? = @exists
  def reset_value = @value.nil? ? "UNDEFINED_LEGAL" : @value
end

class OracleCsr
  include Idl::Csr

  attr_reader :name, :address, :fields, :value, :max_length

  def initialize(spec)
    @name = spec.fetch("name")
    @address = spec.fetch("address")
    @max_length = spec.fetch("length", 32)
    @value = spec["value"]
    @fields = spec.fetch("fields", []).map { |field| OracleCsrField.new(field) }
  end

  def length(_base = nil) = @max_length
  def dynamic_length? = false
end

def type_from_spec(spec, mxlen)
  return nil if spec.nil?

  text = spec.to_s.strip
  qualifiers = []
  loop do
    qualifier = %w[const signed global known].find { |q| text.start_with?("#{q} ") }
    break if qualifier.nil?

    qualifiers << qualifier.to_sym
    text = text.delete_prefix("#{qualifier} ")
  end

  case text
  when /\ABits<(\d+)>\z/
    Idl::Type.new(:bits, width: Regexp.last_match(1).to_i, qualifiers:)
  when "Bits<unknown>"
    Idl::Type.new(:bits, width: :unknown, max_width: mxlen || 64, qualifiers:)
  when "XReg"
    Idl::XregType.new(mxlen || :unknown).tap { |type| qualifiers.each { |q| type.qualify(q) } }
  when "Boolean"
    Idl::Type.new(:boolean, qualifiers:)
  when "String"
    Idl::Type.new(:string, qualifiers:)
  when "void", "Void"
    Idl::VoidType
  else
    raise ArgumentError, "unsupported type spec #{spec.inspect}"
  end
end

def build_symtab(setup)
  mxlen = setup["mxlen"]
  register_files = setup.fetch("register_files", []).map { |rf| OracleRegisterFile.new(rf) }
  csrs = setup.fetch("csrs", []).map { |csr| OracleCsr.new(csr) }
  symtab = Idl::SymbolTable.new(
    mxlen:,
    possible_xlens_cb: proc { setup.fetch("possible_xlens", [32, 64]) },
    register_files:,
    csrs:
  )
  setup.fetch("vars", []).each do |var|
    type = type_from_spec(var.fetch("type"), mxlen)
    symtab.add!(var.fetch("name"), Idl::Var.new(var.fetch("name"), type, var["value"]))
  end
  symtab
end

def normalize_message(message, repo_root)
  message.to_s
    .gsub(repo_root.to_s, "<repo>")
    .gsub(%r{/[^:\s]+/s17-tests}, "<repo>")
    .strip
end

def captured(repo_root)
  { "ok" => true, "value" => yield }
rescue Exception => e # rubocop:disable Lint/RescueException -- crashes are oracle data
  raise if ENV["UDB_PASS_ORACLE_DEBUG"] == "1"

  {
    "ok" => false,
    "error_class" => e.class.to_s,
    "error" => normalize_message(e.message, repo_root)
  }
end

def canonical_registers(values)
  values.map { |file, index| { "file" => file, "index" => index } }
    .uniq
    .sort_by { |entry| [entry.fetch("file"), entry.fetch("index").to_s] }
end

def canonical_return_values(values)
  values.map do |expression, conditions|
    {
      "expression" => expression.to_idl,
      "conditions" => conditions.map(&:to_idl)
    }
  end
end

def observe_passes(node, symtab, passes, repo_root, forced_type: nil)
  passes.to_h do |pass|
    value =
      case pass
      when "prune"
        captured(repo_root) do
          pruned = node.prune(symtab.deep_clone, forced_type:)
          { "ast_class" => pruned.class.to_s.sub(/\AIdl::/, ""), "to_idl" => pruned.to_idl }
        end
      when "reachable_functions"
        captured(repo_root) { node.reachable_functions(symtab.deep_clone).map(&:name).uniq.sort }
      when "reachable_exceptions"
        captured(repo_root) do
          mask = node.reachable_exceptions(symtab.deep_clone)
          codes = (0...mask.bit_length).select { |code| (mask & (1 << code)) != 0 }
          { "mask" => mask, "codes" => codes }
        end
      when "referenced_csrs"
        captured(repo_root) { node.find_referenced_csrs.sort }
      when "source_registers"
        captured(repo_root) { canonical_registers(node.find_src_registers(symtab.deep_clone)) }
      when "destination_registers"
        captured(repo_root) { canonical_registers(node.find_dst_registers(symtab.deep_clone)) }
      when "return_values"
        captured(repo_root) { canonical_return_values(node.pass_find_return_values(symtab.deep_clone)) }
      when "adoc"
        captured(repo_root) { node.gen_adoc(0) }
      when "option_adoc"
        captured(repo_root) { node.gen_option_adoc }
      else
        raise ArgumentError, "unknown pass #{pass.inspect}"
      end
    [pass, value]
  end
end

def compile_synthetic(compiler, spec, symtab)
  root = spec.fetch("root")
  node =
    case root
    when "expression"
      match = compiler.parser.parse(spec.fetch("text"), root: :expression)
      raise SyntaxError, compiler.parser.failure_reason if match.nil?
      match.to_ast
    when "function_body"
      compiler.compile_func_body(
        spec.fetch("text"),
        symtab:,
        return_type: type_from_spec(spec["return_type"], spec.dig("setup", "mxlen")),
        no_rescue: true,
        input_file: spec.fetch("id")
      )
    when "function_body_syntax"
      match = compiler.parser.parse(spec.fetch("text"), root: :function_body)
      raise SyntaxError, compiler.parser.failure_reason if match.nil?
      match.to_ast
    when "isa"
      compiler.parser.set_input_file(spec.fetch("id"), 0, 0, nil)
      match = compiler.parser.parse(spec.fetch("text"), root: :isa)
      raise SyntaxError, compiler.parser.failure_reason if match.nil?
      isa = match.to_ast
      isa.set_input_file(spec.fetch("id"), 0, 0, nil)
      isa.add_global_symbols(symtab)
      symtab.deep_freeze
      isa.freeze_tree(symtab)
      target = spec["target"]
      target.nil? ? isa : isa.functions.find { |function| function.name == target }.body
    else
      raise ArgumentError, "unsupported synthetic root #{root.inspect}"
    end
  node
end

def analyze_synthetic(spec, repo_root)
  symtab = build_symtab(spec.fetch("setup", {}))
  compiler = Idl::Compiler.new
  node = compile_synthetic(compiler, spec, symtab)
  forced_type = type_from_spec(spec["forced_type"], spec.dig("setup", "mxlen"))
  if spec.key?("shared_targets")
    cache = {}
    values = spec.fetch("shared_targets").to_h do |target|
      function = node.functions.find { |candidate| candidate.name == target }
      [
        target,
        function.body.reachable_functions(symtab.deep_clone, cache).map(&:name).uniq.sort
      ]
    end
    return {
      "id" => spec.fetch("id"),
      "passes" => {
        "reachable_functions_shared" => { "ok" => true, "value" => values }
      }
    }
  end
  {
    "id" => spec.fetch("id"),
    "passes" => observe_passes(
      node,
      symtab,
      spec.fetch("passes"),
      repo_root,
      forced_type:
    )
  }
rescue Exception => e # rubocop:disable Lint/RescueException -- crashes are oracle data
  raise if ENV["UDB_PASS_ORACLE_DEBUG"] == "1"

  {
    "id" => spec.fetch("id"),
    "error_class" => e.class.to_s,
    "error" => normalize_message(e.message, repo_root)
  }
end

def real_node_observation(node, symtab, repo_root, include_option: false)
  passes = %w[
    prune reachable_functions reachable_exceptions referenced_csrs
    source_registers destination_registers return_values adoc
  ]
  passes << "option_adoc" if include_option
  observe_passes(node, symtab, passes, repo_root)
end

def analyze_instruction(architecture, spec, repo_root)
  instruction = architecture.instruction(spec.fetch("name"))
  raise "No instruction #{spec.fetch('name')}" if instruction.nil?

  architecture.possible_xlens.filter_map do |xlen|
    next unless instruction.defined_in_base?(xlen)

    captured(repo_root) do
      node = instruction.type_checked_operation_ast(xlen)
      raise "Instruction has no operation()" if node.nil?
      symtab = instruction.send(:fill_symtab, xlen, node)
      {
        "xlen" => xlen,
        "passes" => real_node_observation(node, symtab, repo_root)
      }
    end
  end
end

def analyze_function(architecture, spec, repo_root)
  function = architecture.function(spec.fetch("name"))
  raise "No function #{spec.fetch('name')}" if function.nil?

  symtab = architecture.symtab.global_clone
  symtab.push(function)
  function.arguments(symtab).each do |type, name|
    symtab.add(name, Idl::Var.new(name, type))
  end
  symtab.add("__expected_return_type", function.return_type(symtab))
  real_node_observation(function.body, symtab, repo_root)
ensure
  symtab&.pop
  symtab&.release
end

def csr_body(architecture, spec)
  csr = architecture.csr(spec.fetch("csr"))
  raise "No CSR #{spec.fetch('csr')}" if csr.nil?

  kind = spec.fetch("body")
  xlen = spec["xlen"] || architecture.possible_xlens.first
  unless architecture.possible_xlens.include?(xlen)
    raise "XLEN #{xlen} is not possible for configuration #{architecture.name}"
  end
  case kind
  when "sw_read"
    node = csr.type_checked_sw_read_ast(xlen)
    [node, csr.send(:fill_symtab, node, xlen)]
  when "field_type", "field_reset", "field_sw_write"
    field = csr.field(spec.fetch("field"))
    raise "No field #{spec.fetch('csr')}.#{spec.fetch('field')}" if field.nil?
    case kind
    when "field_type"
      node = field.type_checked_type_ast(xlen)
      [node, field.send(:fill_symtab_for_type, xlen, node)]
    when "field_reset"
      node = field.type_checked_reset_value_ast
      [node, field.send(:fill_symtab_for_reset, node)]
    when "field_sw_write"
      node = field.type_checked_sw_write_ast(architecture.symtab, xlen)
      [node, field.send(:fill_symtab_for_sw_write, xlen, node)]
    end
  else
    raise ArgumentError, "unknown CSR body #{kind.inspect}"
  end
end

def analyze_csr(architecture, spec, repo_root)
  node, symtab = csr_body(architecture, spec)
  raise "Selected CSR body is absent" if node.nil?
  include_option = %w[field_type field_reset].include?(spec.fetch("body"))
  real_node_observation(node, symtab, repo_root, include_option:)
ensure
  symtab&.release
end

def analyze_real_sample(architecture, spec, repo_root)
  value =
    case spec.fetch("kind")
    when "instruction" then analyze_instruction(architecture, spec, repo_root)
    when "function" then analyze_function(architecture, spec, repo_root)
    when "csr" then analyze_csr(architecture, spec, repo_root)
    else raise ArgumentError, "unknown real sample kind #{spec.fetch('kind').inspect}"
    end
  { "id" => spec.fetch("id"), "ok" => true, "value" => value }
rescue Exception => e # rubocop:disable Lint/RescueException -- crashes are oracle data
  {
    "id" => spec.fetch("id"),
    "ok" => false,
    "error_class" => e.class.to_s,
    "error" => normalize_message(e.message, repo_root)
  }
end

input = JSON.parse($stdin.read)
synthetic = input.fetch("cases", []).map { |spec| analyze_synthetic(spec, repo_root) }

real = {}
unless input.fetch("configs", []).empty?
  scratch = Pathname.new(input.fetch("scratch"))
  scratch.mkpath
  resolver = Udb::Resolver.new(
    repo_root,
    schemas_path_override: repo_root / "spec/schemas",
    cfgs_path_override: repo_root / "cfgs",
    gen_path_override: scratch,
    std_path_override: repo_root / "spec/std/isa",
    custom_path_override: repo_root / "spec/custom/isa",
    quiet: true,
    compile_idl: true
  )
  input.fetch("configs").each do |config|
    architecture = resolver.cfg_arch_for(config)
    real[config] = input.fetch("real_samples", []).map do |spec|
      analyze_real_sample(architecture, spec, repo_root)
    end
  end
end

puts JSON.generate({ "synthetic" => synthetic, "real" => real })

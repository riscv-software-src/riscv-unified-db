# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Transitional oracle for Ruby IDL statement semantics.
#
# Reads {"cases": [...]} from stdin and emits one JSON result per case.
#
# Case schema:
#   id: stable diagnostic label
#   root: function_body | expression | isa | for_loop | constraint_body
#   text: IDL source
#   setup:
#     mxlen: 32 | 64 | null
#     possible_xlens: [32, 64]
#     vars: [{name, type, value?, scope?}]
#     register_files: [{name, width, count}]
#     csrs: [{name, address, length, value?, fields: [...]}]
#   return_type: a type spec used for function_body
#   strict: whether to repeat type_check in strict mode after compilation
#   observe:
#     type, value, values, const_eval, return, execute,
#     symbols: [name, ...], functions: true, constraint_satisfied: true
#
# Type specs are strings ("Bits<8>", "const Bits<8>", "Boolean", "String",
# "XReg") or {"array": <type spec>, "width": N}. Integer results are encoded
# as decimal strings so wide values round-trip through JSON.

require "json"
require "pathname"
require "stringio"

repo_root = Pathname.new(File.expand_path("../..", __dir__))
$LOAD_PATH.unshift((repo_root / "tools/ruby-gems/idlc/lib").to_s)
require "idlc"

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
    @exists = spec.fetch("exists", true)
  end

  def defined_in_all_bases? = @bases.sort == [32, 64]
  def defined_in_base32? = @bases.include?(32)
  def defined_in_base64? = @bases.include?(64)
  def base64_only? = @bases == [64]
  def base32_only? = @bases == [32]
  def location(_xlen) = 0..(@width - 1)
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

def encode(value)
  case value
  when Integer then value.to_s
  when Array then value.map { |v| encode(v) }
  when Hash then value.transform_values { |v| encode(v) }
  when Idl::UnknownLiteral then value.to_s
  when Symbol then value.to_s
  else value
  end
end

def type_from_spec(spec, mxlen)
  if spec.is_a?(Hash)
    return Idl::Type.new(
      :array,
      width: spec.fetch("width"),
      sub_type: type_from_spec(spec.fetch("array"), mxlen)
    )
  end

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
  when "U32"
    Idl::Type.new(:bits, width: 32, qualifiers:)
  when "U64"
    Idl::Type.new(:bits, width: 64, qualifiers:)
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

def type_facts(type)
  {
    "text" => type.to_s,
    "kind" => type.kind.to_s,
    "width" => type.respond_to?(:width) && [:bits, :array, :bitfield, :csr, :enum].include?(type.kind) ?
      encode(type.width) : nil,
    "qualifiers" => type.qualifiers.map(&:to_s).sort
  }
end

def unknown_observation
  { "known" => false, "reason" => Idl::AstNode.value_error_reason.to_s }
end

def observe_method(node, method, symtab)
  value = nil
  result = node.value_try do
    value = node.public_send(method, symtab)
  end
  return unknown_observation if result == :unknown_value

  { "known" => true, "value" => encode(value) }
end

def normalize_message(message, repo_root)
  message.to_s
    .gsub(repo_root.to_s, "<repo>")
    .gsub(%r{/[^:\s]+/s15-tests}, "<repo>")
    .strip
end

input = JSON.parse($stdin.read)
compiler = Idl::Compiler.new

results = input.fetch("cases").map do |c|
  saved_stderr = $stderr
  $stderr = StringIO.new
  begin
    setup = c.fetch("setup", {})
    register_files = setup.fetch("register_files", []).map { |rf| OracleRegisterFile.new(rf) }
    csrs = setup.fetch("csrs", []).map { |csr| OracleCsr.new(csr) }
    possible_xlens = setup.fetch("possible_xlens", [32, 64])
    mxlen = setup["mxlen"]
    symtab = Idl::SymbolTable.new(
      mxlen:,
      possible_xlens_cb: proc { possible_xlens },
      register_files:,
      csrs:
    )
    setup.fetch("vars", []).each do |var|
      symtab.push(nil) if var.fetch("scope", "global") == "local" && symtab.levels == 1
      type = type_from_spec(var.fetch("type"), mxlen)
      symtab.add!(var.fetch("name"), Idl::Var.new(var.fetch("name"), type, var["value"]))
    end

    return_type = c["return_type"].nil? ? nil : type_from_spec(c["return_type"], mxlen)
    ast =
      case c.fetch("root")
      when "function_body"
        compiler.compile_func_body(
          c.fetch("text"),
          symtab:,
          return_type:,
          no_rescue: true,
          input_file: c.fetch("id")
        )
      when "expression"
        compiler.compile_expression(c.fetch("text"), symtab, pass_error: true)
      when "for_loop"
        compiler.compile_for_loop(c.fetch("text"), symtab, pass_error: true)
      when "constraint_body"
        node = compiler.compile_constraint(c.fetch("text"), symtab, pass_error: true)
        node.type_check(symtab, strict: c.fetch("strict", false))
        node
      when "isa"
        compiler.parser.set_input_file(c.fetch("id"), 0, 0, nil)
        match = compiler.parser.parse(c.fetch("text"), root: :isa)
        raise SyntaxError, compiler.parser.failure_reason if match.nil?

        node = match.to_ast
        node.set_input_file(c.fetch("id"), 0, 0, nil)
        node.freeze_tree(symtab)
        # IsaAst#add_global_symbols followed by IsaAst#type_check double-adds
        # enums/bitfields/structs because their type_check methods add their
        # own symbols. Register in dependency order instead: user types,
        # function signatures, globals, then function bodies.
        user_types = node.enums + node.bitfields + node.structs
        user_types.each { |definition| definition.type_check(symtab, strict: c.fetch("strict", false)) }
        node.functions.each { |function| function.add_symbol(symtab) }
        node.globals.each { |global| global.type_check(symtab, strict: c.fetch("strict", false)) }
        node.functions.each { |function| function.type_check(symtab, strict: c.fetch("strict", false)) }
        (node.definitions - user_types - node.functions - node.globals).each do |definition|
          definition.type_check(symtab, strict: c.fetch("strict", false))
        end
        node
      else
        raise ArgumentError, "unsupported root #{c.fetch('root')}"
      end

    if c.fetch("strict", false) && c.fetch("root") != "isa"
      strict_symtab = symtab.deep_clone
      strict_symtab.push(ast) if c.fetch("root") == "function_body"
      strict_symtab.add("__expected_return_type", return_type) unless return_type.nil?
      ast.type_check(strict_symtab, strict: true)
    end

    observe = c.fetch("observe", {})
    result = {
      "ok" => true,
      "ast_class" => ast.class.to_s.sub(/\AIdl::/, ""),
      "to_idl" => c.fetch("root") == "isa" ?
        ast.definitions.map(&:to_idl).join("\n") :
        ast.to_idl,
      "warnings" => $stderr.string
    }
    result["const_eval"] = ast.const_eval?(symtab) if observe["const_eval"]
    result["type"] = type_facts(ast.type(symtab)) if observe["type"]
    result["value"] = observe_method(ast, :value, symtab) if observe["value"]
    result["values"] = observe_method(ast, :values, symtab) if observe["values"]

    if observe["constraint_satisfied"]
      result["satisfied"] = ast.satisfied?(symtab)
    end

    if observe["functions"]
      result["functions"] = ast.functions.map do |func|
        fsym = symtab.deep_clone
        fsym.push(func)
        {
          "name" => func.name,
          "arguments" => func.arguments(fsym).map { |type, name| [type_facts(type), name] },
          "return_type" => type_facts(func.return_type(fsym)),
          "const_eval" => func.const_eval?(symtab),
          "builtin" => func.builtin?,
          "generated" => func.generated?,
          "external" => func.external?
        }
      end
    end

    eval_symtab = symtab.deep_clone
    if c.fetch("root") == "function_body"
      eval_symtab.push(ast)
      eval_symtab.add("__expected_return_type", return_type) unless return_type.nil?
    end
    if observe["return"]
      result["return_type"] = type_facts(ast.return_type(eval_symtab))
      result["return_value"] = observe_method(ast, :return_value, eval_symtab)
      result["return_values"] = observe_method(ast, :return_values, eval_symtab)
    elsif observe["execute"]
      result["execute"] = observe_method(ast, :execute, eval_symtab)
    end

    unless observe.fetch("symbols", []).empty?
      result["symbols"] = {}
      observe.fetch("symbols").each do |name|
        symbol = eval_symtab.get(name) || symtab.get(name)
        result["symbols"][name] =
          if symbol.nil?
            nil
          elsif symbol.is_a?(Idl::Var)
            {
              "type" => type_facts(symbol.type),
              "value" => symbol.value.nil? ? unknown_observation : { "known" => true, "value" => encode(symbol.value) },
              "const_eval" => symbol.const_eval?,
              "for_loop_iter" => symbol.for_loop_iter?
            }
          elsif symbol.is_a?(Idl::Type)
            { "type" => type_facts(symbol) }
          else
            { "class" => symbol.class.to_s }
          end
      end
    end

    result
  rescue Idl::AstNode::TypeError => e
    { "ok" => false, "error" => "type", "class" => e.class.to_s, "message" => normalize_message(e.what, repo_root) }
  rescue Idl::AstNode::InternalError => e
    { "ok" => false, "error" => "internal", "class" => e.class.to_s, "message" => normalize_message(e.what, repo_root) }
  rescue SyntaxError => e
    { "ok" => false, "error" => "syntax", "class" => e.class.to_s, "message" => normalize_message(e.message, repo_root) }
  rescue UncaughtThrowError => e
    { "ok" => false, "error" => "value_unknown", "class" => e.class.to_s, "message" => normalize_message(e.message, repo_root) }
  rescue StandardError => e
    {
      "ok" => false,
      "error" => "other",
      "class" => e.class.to_s,
      "message" => normalize_message("#{e.class}: #{e.message}", repo_root),
      "backtrace" => e.backtrace&.first&.sub(repo_root.to_s, "<repo>")
    }
  ensure
    $stderr = saved_stderr
  end
end

puts JSON.generate(results)

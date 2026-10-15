# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Transitional oracle for Ruby IDL expression typing and constant evaluation.
#
# Reads {"cases": [{"id": str, "text": str, "params": {name: value}}, ...]}
# from stdin. Parameters are bound in a pushed scope as in
# tools/ruby-gems/idlc/test/test_expressions.rb: integers as Bits<bit_length>
# (width 1 for zero), strings as String, and booleans as Boolean.
#
# Writes one result per case:
#   {"ok": true, "type": to_s, "kind": str, "width": int|str|null,
#    "qualifiers": [str], "value": <value> | null, "value_known": bool,
#    "to_idl": str}
# or {"ok": false, "error": "type"|"internal"|"syntax"|"other", "message": str}.
# Integers are emitted as decimal strings so that wide values survive JSON.

require "json"
require "pathname"
require "stringio"

repo_root = Pathname.new(File.expand_path("../..", __dir__))
$LOAD_PATH.unshift((repo_root / "tools/ruby-gems/idlc/lib").to_s)
require "idlc"

def encode(value)
  case value
  when Integer then value.to_s
  when Array then value.map { |v| encode(v) }
  when Hash then value.transform_values { |v| encode(v) }
  else value
  end
end

def bind(symtab, name, value)
  type =
    case value
    when Integer then Idl::Type.new(:bits, width: value.zero? ? 1 : value.bit_length)
    when String then Idl::Type.new(:string)
    when true, false then Idl::Type.new(:boolean)
    when Hash
      if value.key?("bitfield")
        spec = value.fetch("bitfield")
        Idl::BitfieldType.new(
          spec.fetch("name"),
          spec.fetch("width"),
          spec.fetch("fields").keys,
          spec.fetch("fields").values.map { |r| Range.new(r.fetch(0), r.fetch(1)) }
        )
      elsif value.key?("struct")
        spec = value.fetch("struct")
        member_names = spec.fetch("members").keys
        member_types = spec.fetch("members").values.map { |w| Idl::Type.new(:bits, width: w) }
        Idl::StructType.new(spec.fetch("name"), member_types, member_names)
      else
        raise ArgumentError, "unsupported parameter #{name}: #{value.inspect}"
      end
    else raise ArgumentError, "unsupported parameter #{name}: #{value.inspect}"
    end
  bound_value = value.is_a?(Hash) ? value.fetch("value") : value
  symtab.add!(name, Idl::Var.new(name, type, bound_value))
end

# Builds a builtin enum definition from {"name": str, "elements": {element_name: value}}
# so cases can exercise $enum_size/$enum_element_size/$enum_to_a/$enum without an
# `enum ... ;` declaration (declarations are out of scope for this oracle).
def enum_def(spec)
  Idl::SymbolTable::EnumDef.new(
    name: spec.fetch("name"),
    element_names: spec.fetch("elements").keys,
    element_values: spec.fetch("elements").values
  )
end

input = JSON.parse($stdin.read)
compiler = Idl::Compiler.new

results = input.fetch("cases").map do |c|
  builtin_enums = c.fetch("enums", []).map { |spec| enum_def(spec) }
  symtab = Idl::SymbolTable.new(builtin_enums:)
  params = c.fetch("params", {})
  symtab.push(nil) unless params.empty?
  params.each { |name, value| bind(symtab, name, value) }
  saved_stderr = $stderr
  $stderr = StringIO.new
  begin
    ast = compiler.compile_expression(c.fetch("text"), symtab, pass_error: true)
    type = ast.type(symtab)
    value = nil
    known = false
    result = ast.value_try do
      value = ast.value(symtab)
      known = true
    end
    known = false if result == :unknown_value
    {
      "ok" => true,
      "type" => type.to_s,
      "kind" => type.kind.to_s,
      "width" => type.kind == :bits ? (type.width.is_a?(Integer) ? type.width : type.width.to_s) : nil,
      "qualifiers" => type.qualifiers.map(&:to_s).sort,
      "value" => known ? encode(value) : nil,
      "value_known" => known,
      "to_idl" => ast.to_idl,
      "warnings" => $stderr.string
    }
  rescue Idl::AstNode::TypeError => e
    { "ok" => false, "error" => "type", "message" => e.what }
  rescue Idl::AstNode::InternalError => e
    { "ok" => false, "error" => "internal", "message" => e.what }
  rescue SyntaxError => e
    { "ok" => false, "error" => "syntax", "message" => e.message }
  rescue StandardError => e
    { "ok" => false, "error" => "other", "message" => "#{e.class}: #{e.message}" }
  ensure
    $stderr = saved_stderr
  end
end

puts JSON.generate(results)

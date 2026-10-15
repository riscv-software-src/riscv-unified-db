# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Differential oracle for the Python port of Idl::Type (src/udb/idl/types.py).
#
# Reads a single JSON object from stdin describing a list of "commands" and
# writes a JSON array of results (one per command) to stdout. Each command
# builds one or more Idl::Type values from a small JSON "type spec" and
# performs one operation (rendering, a compatibility predicate, a JSON
# Schema conversion, or one of the confirmed-bug reproductions), matching
# the operations exercised by tests/python/test_idl_types.py.

require "json"
require "idlc"

# A minimal fake implementing the `Idl::Csr` interface (idlc/lib/idlc/interfaces.rb)
# for building `Idl::Type.new(:csr, ...)`/`CsrType` values in tests.
FakeCsr = Struct.new(:name, :max_length) do
  include Idl::Csr

  def length(_base) = max_length

  def dynamic_length? = false

  def fields = []

  def value = nil
end

# Recursively builds an Idl::Type from a small JSON "type spec" (see the
# Python-side helper `_ruby_type_spec` in test_idl_types.py for the exact
# shapes this understands).
def build_type(spec)
  kind = spec.fetch("kind").to_sym
  qualifiers = (spec["qualifiers"] || []).map(&:to_sym)

  case kind
  when :bits
    Idl::Type.new(:bits, width: spec.fetch("width"), qualifiers:)
  when :boolean
    Idl::Type.new(:boolean, qualifiers:)
  when :string
    Idl::Type.new(:string, width: spec["width"], qualifiers:)
  when :void
    Idl::Type.new(:void, qualifiers:)
  when :array
    Idl::Type.new(:array, width: spec.fetch("width"), sub_type: build_type(spec.fetch("sub_type")), qualifiers:)
  when :tuple
    Idl::Type.new(:tuple, tuple_types: spec.fetch("tuple_types").map { |s| build_type(s) }, qualifiers:)
  when :enum
    Idl::EnumerationType.new(spec.fetch("name"), spec.fetch("element_names"), spec.fetch("element_values"))
  when :enum_ref
    Idl::EnumerationType.new(spec.fetch("name"), spec.fetch("element_names"), spec.fetch("element_values")).ref_type
  when :bitfield
    field_ranges = spec.fetch("field_ranges").map { |(a, b)| a...b }
    Idl::BitfieldType.new(spec.fetch("name"), spec.fetch("width"), spec.fetch("field_names"), field_ranges)
  when :struct
    Idl::StructType.new(
      spec.fetch("name"),
      spec.fetch("member_types").map { |s| build_type(s) },
      spec.fetch("member_names")
    )
  when :csr
    Idl::CsrType.new(FakeCsr.new(spec.fetch("csr_name"), spec.fetch("max_length")), qualifiers:)
  else
    raise "unhandled type spec kind #{kind}"
  end
end

# Renders the "properties" of a built type as a JSON-safe Hash, matching
# what the Python side inspects. Every property is captured with a rescue
# so a raise in one property (e.g. `to_idl` on an unsupported kind) doesn't
# prevent reporting the others.
def type_props(type)
  props = {}
  props["kind"] = type.kind.to_s
  begin
    props["to_s"] = type.to_s
  rescue StandardError => e
    props["to_s_error"] = e.message
  end
  begin
    props["to_idl"] = type.to_idl
  rescue StandardError => e
    props["to_idl_error"] = e.message
  end
  begin
    props["width"] = type.width
  rescue StandardError
    # Only the fact that width raises is meaningful across languages; Ruby's
    # `T.must(@width)` message ("Passed `nil` into T.must") is Sorbet-internal
    # and has no Python equivalent, so record a boolean flag instead of the
    # exact message (see test_idl_types.py's `_python_type_props`).
    props["width_error"] = true
  end
  props["qualifiers"] = type.qualifiers.map(&:to_s).sort
  begin
    props["name"] = type.name
  rescue StandardError => e
    props["name_error"] = e.message
  end
  begin
    props["default"] = type.default
  rescue StandardError => e
    props["default_error"] = e.message
  end
  props
end

def run_command(cmd)
  case cmd.fetch("op")
  when "props"
    type_props(build_type(cmd.fetch("type")))
  when "compare"
    lhs = build_type(cmd.fetch("lhs"))
    rhs = build_type(cmd.fetch("rhs"))
    method = cmd.fetch("method")
    begin
      { "result" => lhs.public_send(:"#{method}?", rhs) }
    rescue StandardError => e
      { "error" => "#{e.class}: #{e.message}" }
    end
  when "json_schema"
    begin
      type = Idl::Type.from_json_schema(cmd.fetch("schema"))
      type.nil? ? { "type" => nil } : { "type" => type_props(type) }
    rescue StandardError => e
      { "error" => "#{e.class}: #{e.message}" }
    end
  when "bug_b1_equal_to_symbol"
    # B1: `equal_to?`/`convertable_to?` crash on a kind Symbol other than
    # :boolean/:void/:dontcare (TYPE_FROM_KIND only covers those three).
    type = build_type(cmd.fetch("type"))
    begin
      { "result" => type.equal_to?(cmd.fetch("other_kind").to_sym) }
    rescue StandardError => e
      { "error" => "#{e.class}: #{e.message}" }
    end
  when "bug_b1_convertable_to_symbol"
    type = build_type(cmd.fetch("type"))
    begin
      { "result" => type.convertable_to?(cmd.fetch("other_kind").to_sym) }
    rescue StandardError => e
      { "error" => "#{e.class}: #{e.message}" }
    end
  when "bug_b2_comparable_to_csr"
    lhs = build_type(cmd.fetch("lhs"))
    rhs = build_type(cmd.fetch("rhs"))
    begin
      { "result" => lhs.comparable_to?(rhs) }
    rescue StandardError => e
      { "error" => "#{e.class}: #{e.message}" }
    end
  when "bug_b3_array_default_aliasing"
    type = build_type(cmd.fetch("type"))
    default = type.default
    # Mutate the first element (a Hash, from a StructType sub_type) and
    # report whether the *second* element observed the mutation too.
    default[0][cmd.fetch("member_name")] = cmd.fetch("new_value")
    { "second_element" => default[1] }
  else
    raise "unhandled op #{cmd.fetch('op')}"
  end
end

input = JSON.parse($stdin.read)
results = input.fetch("commands").map { |cmd| run_command(cmd) }
puts JSON.generate(results)

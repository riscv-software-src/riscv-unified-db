# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "idlc/type"
require "idlc/interfaces"

require_relative "resolver"

# represents a JSON Schema
#
# Used when an object in the database specifies a constraint using JSON schema
# For example, extension parameters
module Udb
  class Resolver; end
  class Schema
    extend T::Sig
    include Idl::Schema

    @@ref_resolvers = T.let({}, T::Hash[Resolver, T.untyped])

    sig { params(schema_hash: T::Hash[String, T.untyped]).void }
    def initialize(schema_hash)
      @schema_hash = schema_hash
    end

    sig { params(rb_value: T.untyped, udb_resolver: Resolver).returns(T::Boolean) }
    def validate(rb_value, udb_resolver:)
      @@ref_resolvers[udb_resolver] ||= TopLevelDatabaseObject.create_json_schemer_resolver(udb_resolver)
      schemer = JSONSchemer.schema(
        @schema_hash,
        regexp_resolver: "ecma",
        ref_resolver: @@ref_resolvers[udb_resolver],
        insert_property_defaults: true
      )
      schemer.valid?(rb_value)
    end

    # @return [Hash] Hash representation of the JSON Schema
    sig { returns(T::Hash[String, T.untyped]) }
    def to_h = @schema_hash

    sig { params(rb_type: Object).returns(String) }
    def rb_obj_to_jsonschema_type(rb_type)
      case rb_type
      when String
        "string"
      when Integer
        "integer"
      when Numeric
        "number"
      when Array
        "array"
      when Hash
        "object"
      else
        raise "TODO: unsupported const type for '#{@schema_hash['const']}'"
      end
    end
    private :rb_obj_to_jsonschema_type

    # @return Human-readable type of the schema (e.g., array, string, integer)
    sig { params(hsh: T::Hash[String, T.untyped]).returns(String) }
    def type_pretty_helper(hsh)
      if hsh.key?("const")
        rb_obj_to_jsonschema_type(hsh["const"])
      elsif hsh.key?("enum") && !hsh["enum"].empty? && hsh["enum"].all? { |elem| elem.class == hsh["enum"][0].class }
        rb_obj_to_jsonschema_type(hsh["enum"][0])
      elsif hsh.key?("$ref")
        if hsh["$ref"].split("/").last == "uint32"
          "integer"
        elsif hsh["$ref"].split("/").last == "uint64"
          "integer"
        else
          raise "unhandled type ref: #{hsh["$ref"]}"
        end
      elsif hsh.key?("allOf")
        type_pretty_helper(hsh["allOf"][0])
      else
        raise "Missing type information for '#{hsh}'" unless hsh.key?("type")
        hsh["type"]
      end
    end
    private :type_pretty_helper

    sig { returns(String) }
    def type_pretty
      type_pretty_helper(@schema_hash)
    end

    # @return A human-readable description of the schema
    sig { params(schema_hash: T::Hash[String, T.untyped]).returns(String) }
    def to_pretty_s(schema_hash = @schema_hash)
      raise ArgumentError, "Expecting non-empty hash" if schema_hash.empty?

      if schema_hash.key?("const")
        large2hex(schema_hash["const"])
      elsif schema_hash.key?("enum")
        "[#{schema_hash["enum"].join(', ')}]"
      elsif schema_hash.key?("$ref")
        if schema_hash["$ref"].split("/").last == "uint32"
          "32-bit integer"
        elsif schema_hash["$ref"].split("/").last == "uint64"
          "64-bit integer"
        else
          raise "unhandled type ref: #{schema_hash["$ref"]}"
        end
      elsif schema_hash.key?("not")
        if schema_hash["not"].key?("const")
          "≠ #{large2hex(schema_hash["not"]["const"])}"
        elsif schema_hash["not"].key?("anyOf")
          if schema_hash["not"]["anyOf"].all? { |h| h.key?("const") }
            "≠ #{schema_hash["not"]["anyOf"].map { |h| large2hex(h["const"]) }.join(" or ")}"
          else
            raise "unhandled exclusion: #{schema_hash}"
          end
        else
          raise "unhandled exclusion: #{schema_hash}"
        end
      elsif schema_hash.key?("allOf")
        schema_hash["allOf"].map { |hsh| to_pretty_s(hsh) }.join(", ")
      elsif schema_hash.key?("type")
        case schema_hash["type"]
        when "integer"
          min = schema_hash["minimum"]
          minstr = large2hex(min)
          max = schema_hash["maximum"]
          maxstr = large2hex(max)
          if min && max
            sz = num_bits(min, max)
            (sz > 0) ? "#{sz}-bit integer" : "#{minstr} to #{maxstr}"
          elsif min
            "&#8805; #{minstr}"
          elsif max
            "&#8804; #{maxstr}"
          else
            "integer"
          end
        when "string"
          format = schema_hash["format"]
          pattern = schema_hash["pattern"]
          if format
            format
          elsif pattern
            "string matching #{pattern}"
          else
            "string"
          end
        when "boolean"
          "boolean"
        when "array"
          items = schema_hash["items"]
          min_items = schema_hash["minItems"]
          max_items = schema_hash["maxItems"]
          size_str = if min_items && max_items
                       if min_items == max_items
                         "#{min_items}-element "
                       else
                         "#{min_items}-element to #{max_items}-element "
                       end
          elsif min_items
            "at least #{min_items}-element "
          elsif max_items
            "at most #{max_items}-element "
          else
            ""
          end

          array_str = if items.nil?
                        size_str + "array"
          else
            if items.is_a?(Hash)
              "#{size_str}array of #{to_pretty_s(items)}"
            elsif items.is_a?(Array)
              str = size_str + "array where: +\n"
              items.each_with_index do |item, index|
                str = str + "&nbsp;&nbsp;[#{index}] is #{to_pretty_s(item)} +\n"
              end
              additional_items = schema_hash["additionalItems"]
              if additional_items
                str = str + "additional items are: +\n&nbsp;&nbsp;" +
                  to_pretty_s(additional_items)
              end
              str
            else
              raise "to_pretty_s unknown array items #{items} in #{schema_hash}"
            end
          end

          if schema_hash.key?("contains")
            array_str = array_str + " Contains : [#{to_pretty_s(schema_hash["contains"])}]"
          end

          array_str
        else
          raise "to_pretty_s unknown type #{schema_hash["type"]} in #{schema_hash}"
        end
      else
        raise "Unsupported schema for #{schema_hash}"
      end
    end

    # Convert large integers to hex str.
    sig { params(value: T.nilable(T.any(Numeric, T::Boolean, String))).returns(String) }
    def large2hex(value)
      if value.nil?
        ""
      elsif value.is_a?(Integer)
        (value > 999) ? "0x" + value.to_s(16) : value.to_s
      else
        value.to_s
      end
    end

    sig { params(other_schema: T.any(Schema, T::Hash[String, T.untyped])).returns(Schema) }
    def merge(other_schema)
      other_hash = other_schema.is_a?(Schema) ? other_schema.instance_variable_get(:@schema_hash) : other_schema

      Schema.new(@schema_hash.merge(other_hash))
    end

    sig { returns(T::Boolean) }
    def empty?
      @schema_hash.empty?
    end

    sig { returns(T::Boolean) }
    def single_value?
      @schema_hash.key?("const")
    end

    sig { returns(Object) }
    def value
      raise "Schema is not a single value" unless single_value?

      @schema_hash["const"]
    end

    # @return [Boolean] if the maximum value of the schema is known, i.e., is a restricted integer
    sig { override.returns(T::Boolean) }
    def max_val_known?
      to_idl_type.kind == :bits && \
        (@schema_hash.key?("const") || \
         @schema_hash.key?("maximum") || \
         @schema_hash.key?("enum"))
    end

    # @return [Boolean] if the minimum value of the schema is known, i.e., is a restricted integer
    sig { override.returns(T::Boolean) }
    def min_val_known?
      to_idl_type.kind == :bits && \
        (@schema_hash.key?("const") || \
         @schema_hash.key?("minimum") || \
         @schema_hash.key?("enum"))
    end

    # @return [Integer] The maximum value the schema allows. Only valid if #max_val_known? is true
    sig { override.returns(Integer) }
    def max_val
      if @schema_hash.key?("const")
        @schema_hash["const"]
      elsif @schema_hash.key?("enum")
        @schema_hash["enum"].max
      elsif @schema_hash.key?("maximum")
        @schema_hash["maximum"]
      else
        raise "unexpected"
      end
    end

    # @return [Integer] The minimum value the schema allows. Only valid if #min_val_known? is true
    sig { override.returns(Integer) }
    def min_val
      if @schema_hash.key?("const")
        @schema_hash["const"]
      elsif @schema_hash.key?("enum")
        @schema_hash["enum"].min
      elsif @schema_hash.key?("minimum")
        @schema_hash["minimum"]
      else
        raise "unexpected"
      end
    end

    def is_power_of_two?(num)
      return false if num < 1
      return (num & (num - 1)) == 0
    end

    # If min to max range represents an unsigned number of bits, return the number of bits.
    # Otherwise return 0
    def num_bits(min, max)
      return 0 unless min == 0
      is_power_of_two?(max + 1) ? max.bit_length : 0
    end

    # @return [Idl::Type] THe IDL-equivalent type for this schema object
    sig { override.returns(Idl::Type) }
    def to_idl_type
      T.must(Idl::Type.from_json_schema(@schema_hash))
    end
  end
end

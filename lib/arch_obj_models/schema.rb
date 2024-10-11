#frozen_string_literal: true

class Schema 
    def initialize(schema_hash)
        raise ArgumentError, "Expecting hash" unless schema_hash.is_a?(Hash)

        @schema_hash = schema_hash
    end

    def pretty(schema_hash = @schema_hash)
      raise ArgumentError, "Expecting hash" unless schema_hash.is_a?(Hash)
      raise ArgumentError, "Expecting non-empty hash" if schema_hash.empty?

      if schema_hash.key?("const")
        "#{schema_hash["const"]}"
      elsif schema_hash.key?("enum")
        "One of: [#{schema_hash["enum"].join(', ')}]"
      elsif schema_hash.key?("type")
        case schema_hash["type"]
        when "integer"
          min = schema_hash["minimum"]
          max = schema_hash["maximum"]
          if min && max
            "#{min} to #{max}"
          elsif min
            "&#8805; #{min}"
          elsif max
            "&#8804; #{max}"
          else
            "any integer"
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
          "TODO: array"
        else
          raise "TODO: Pretty schema unknown type #{schema_hash["type"]} in #{schema_hash}"
        end
      elsif schema_hash.key?("contains")
        "Contains : [#{pretty(schema_hash["contains"])}]"
      else
        raise "TODO: Pretty schema for #{schema_hash}"
      end
    end

    def merge!(other_schema)
        raise ArgumentError, "Expecting Schema" unless (other_schema.is_a?(Schema) || other_schema.is_a?(Hash))

        hash = other_schema.is_a?(Schema) ? other_schema.instance_variable_get(:@schema_hash) : other_schema

        @schema_hash.merge!(hash)

        self
    end

    def single_value?
        @schema_hash.key?("const")
    end

    def value
      raise "Schema is not a single value" unless single_value?

      @schema_hash["const"]
    end
end


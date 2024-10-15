#frozen_string_literal: true

class Schema 
    def initialize(schema_hash)
        raise ArgumentError, "Expecting hash" unless schema_hash.is_a?(Hash)

        @schema_hash = schema_hash
    end

    def to_pretty_s(schema_hash = @schema_hash)
      raise ArgumentError, "Expecting hash" unless schema_hash.is_a?(Hash)
      raise ArgumentError, "Expecting non-empty hash" if schema_hash.empty?

      if schema_hash.key?("const")
        large2hex(schema_hash["const"])
      elsif schema_hash.key?("enum")
        "[#{schema_hash["enum"].join(', ')}]"
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

          if items.nil? 
            size_str + "array"
          else 
            if items.is_a?(Hash)
              "#{size_str}array of #{to_pretty_s(items)}"
            elsif items.is_a?(Array)
              str = size_str + "array where: +\n"
              items.each_with_index do |item,index|
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
        else
          raise "to_pretty_s unknown type #{schema_hash["type"]} in #{schema_hash}"
        end
      elsif schema_hash.key?("contains")
        "Contains : [#{to_pretty_s(schema_hash["contains"])}]"
      else
        raise "TODO: to_pretty_s schema for #{schema_hash}"
      end
    end

    # Convert large integers to hex str.
    def large2hex(value)
      if value.nil?
        ""
      elsif value.is_a?(Integer)
        (value > 999) ? "0x" + value.to_s(16) : value.to_s
      else
        value.to_s
      end
    end

    def merge!(other_schema)
      raise ArgumentError, "Expecting Schema" unless (other_schema.is_a?(Schema) || other_schema.is_a?(Hash))

      hash = other_schema.is_a?(Schema) ? other_schema.instance_variable_get(:@schema_hash) : other_schema

      @schema_hash.merge!(hash)

      self
    end

    def empty?
      @schema_hash.empty?
    end

    def single_value?
        @schema_hash.key?("const")
    end

    def value
      raise "Schema is not a single value" unless single_value?

      @schema_hash["const"]
    end

    def is_power_of_two?(num)
      return false if num < 1
      return (num & (num-1)) == 0
    end

    # If min to max range represents an unsigned number of bits, return the number of bits.
    # Otherwise return 0
    def num_bits(min, max)
        return 0 unless min == 0
        is_power_of_two?(max+1) ? max.bit_length : 0
    end
end


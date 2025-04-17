# frozen_string_literal: true

# At this point, we insert a placeholder since it will be up
# to the backend to create a specific link.

require "erb"
require "pathname"
require "ostruct"

# collection of functions that can be used inside ERB templates
module TemplateHelpers

  def fix_entities(text)
    text.to_s.gsub("&ne;", "≠")
             .gsub("&pm;", "±")
             .gsub("-&infin;", "−∞")
             .gsub("+&infin;", "+∞")
  end

  # Custom JSON converter for wavedrom that handles hexadecimal literals
  def json_dump_with_hex_literals(data)
    # First convert to standard JSON
    json_string = JSON.dump(data)

    # Replace string hex values with actual hex literals
    json_string.gsub(/"0x([0-9a-fA-F]+)"/) do |match|
      # Remove the quotes, leaving just the hex literal
      "0x#{$1}"
    end.gsub(/"name":/, '"name": ') # Add space after colon for name field
  end

  # Helper to process wavedrom data
  def process_wavedrom(json_data)
    result = json_data.dup

    # Process reg array if it exists
    if result["reg"].is_a?(Array)
      result["reg"].each do |item|
        # For fields that are likely opcodes or immediates (type 2)
        if item["type"] == 2
          # Convert to number first (if it's a string)
          if item["name"].is_a?(String)
            if item["name"].start_with?("0x")
              # Already hexadecimal
              numeric_value = item["name"].to_i(16)
            elsif item["name"] =~ /^[01]+$/
              # Binary string without prefix
              numeric_value = item["name"].to_i(2)
            elsif item["name"] =~ /^\d+$/
              # Decimal
              numeric_value = item["name"].to_i
            else
              # Not a number, leave it alone
              next
            end
          else
            # Already a number
            numeric_value = item["name"]
          end

          # Convert to hexadecimal string
          hex_str = numeric_value.to_s(16).downcase

          # Set the name to a specially formatted string that will be converted
          # to a hex literal in our custom JSON converter
          item["name"] = "0x" + hex_str
        end

        # Ensure bits is a number
        if item["bits"].is_a?(String) && item["bits"] =~ /^\d+$/
          item["bits"] = item["bits"].to_i
        end
      end
    end

    result
  end

  # Insert a hyperlink to an extension.
  # @param name [#to_s] Name of the extension
  def link_to_ext(name)
    "%%LINK%ext;#{name};#{name}%%"
  end

  # Insert a hyperlink to an extension parameter.
  # @param ext_name [#to_s] Name of the extension
  # @param param_name [#to_s] Name of the parameter
  def link_to_ext_param(ext_name, param_name)
    "<<ext-#{ext_name.gsub(".", "_")}-param-#{param_name}-def, #{ext_name}>>"
  end

  # Insert a hyperlink to an instruction.
  # @param name [#to_s] Name of the instruction
  def link_to_inst(name)
    "%%LINK%inst;#{name};#{name}%%"
  end

  # Insert a hyperlink to a CSR.
  # @param name [#to_s] Name of the CSR
  def link_to_csr(name)
    "%%LINK%csr;#{name};#{name}%%"
  end

  # Insert a hyperlink to a CSR field.
  # @param csr_name [#to_s] Name of the CSR
  # @param field_name [#to_s] Name of the CSR field
  def link_to_csr_field(csr_name, field_name)
    "%%LINK%csr_field;#{csr_name}.#{field_name};#{csr_name}.#{field_name}%%"
  end

  # Insert anchor to an extension.
  # @param name [#to_s] Name of the extension
  def anchor_for_ext(name)
    "[[ext-#{name.gsub(".", "_")}-def]]"
  end

  # Insert anchor to an extension parameter.
  # @param ext_name [#to_s] Name of the extension
  # @param param_name [#to_s] Name of the parameter
  def anchor_for_ext_param(ext_name, param_name)
    "[[ext-#{ext_name.gsub(".", "_")}-param-#{param_name}-def]]"
  end

  # Insert anchor to an instruction.
  # @param name [#to_s] Name of the instruction
  def anchor_for_inst(name)
    "[[inst-#{name.gsub(".", "_")}-def]]"
  end

  # Insert anchor to a CSR.
  # @param name [#to_s] Name of the CSR
  def anchor_for_csr(name)
    "[[csr-#{name.gsub(".", "_")}-def]]"
  end

  # Insert anchor to a CSR field.
  # @param csr_name [#to_s] Name of the CSR
  # @param field_name [#to_s] Name of the CSR field
  def anchor_for_csr_field(csr_name, field_name)
    "[[csr_field-#{csr_name.gsub(".", "_")}-#{field_name.gsub(".", "_")}-def]]"
  end

  def partial(template_path, locals = {})
    template_path = Pathname.new($root / "backends" / "common_templates" / template_path)
    raise ArgumentError, "Template '#{template_path} not found" unless template_path.exist?

    erb = ERB.new(template_path.read, trim_mode: "-")
    erb.filename = template_path.realpath.to_s

    erb.result(OpenStruct.new(locals).instance_eval { binding })
  end
end

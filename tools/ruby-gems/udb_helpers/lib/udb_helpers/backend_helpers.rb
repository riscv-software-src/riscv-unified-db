# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true
# typed: true

# Collection of "helper" functions that can be called from backends and/or ERB templates.

require "sorbet-runtime"
require "erb"
require "pathname"
require "ostruct"

# Add to standard String class.
class String
  extend T::Sig

  # Should be called on all RISC-V extension, instruction, CSR, and CSR field names.
  # Parameters never have periods in their names so they don't need to be sanitized.
  # Returns new String with periods replaced with hyphens and ampersands replaced with "-and-"
  # Don't use underscore as a replacement character since it is used by doc_links to separate list items.
  sig { returns(String) }
  def sanitize = String.new(self).gsub(".", "-").gsub("&", "-and-")
end

module Udb::Helpers::WavedromUtil
  extend T::Sig

  sig { params(text: String).returns(String) }
  def fix_entities(text)
    text.to_s.gsub("&ne;", "≠")
             .gsub("&pm;", "±")
             .gsub("-&infin;", "−∞")
             .gsub("+&infin;", "+∞")
  end

  # Custom JSON converter for wavedrom that handles hexadecimal literals
  sig { params(data: T.untyped).returns(String) }
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
  sig { params(json_data: T::Hash[String, T.untyped]).returns(T::Hash[String, T.untyped]) }
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
end

# This module is included in the CfgArch and Design classes so its methods are available to be called directly
# from them without having to prefix a method with the module name.
module Udb::Helpers::TemplateHelpers
  # Include a partial ERB template into a full ERB template.
  # Returns result of ERB evaluation of the template file
  #
  # template_pname - Path to template file relative to "backends" directory.
  # inputs - Input objects to pass into template
  extend T::Sig

  sig { params(template_pname: String, inputs: T::Hash[String, T.untyped]).returns(String) }
  def partial(template_pname, inputs = {})
    template_path = Pathname.new($root / "backends" / template_pname)
    raise ArgumentError, "Template '#{template_path} not found" unless template_path.exist?

    erb = ERB.new(template_path.read, trim_mode: "-")
    erb.filename = template_path.realpath.to_s

    erb.result(OpenStruct.new(inputs).instance_eval { binding })
  end

  #########
  # LINKS #
  #########

  # Links are created with this proprietary format so that they can be converted
  # later into either AsciiDoc or Antora links (see the two implementations of "resolve_links").
  #   %%UDB_DOC_LINK%<type>;<name>;<link_text>%%
  #
  # Documentation:
  #   - How to make cross-references: https://docs.asciidoctor.org/asciidoc/latest/macros/xref/
  #   - How to create anchors: https://docs.asciidoctor.org/asciidoc/latest/attributes/id/

  # Returns a hyperlink to UDB extension documentation
  # ext_name - Name of the extension
  sig { params(ext_name: String).returns(String) }
  def link_to_udb_doc_ext(ext_name)
    "%%UDB_DOC_LINK%ext;#{ext_name.sanitize};#{ext_name}%%"
  end

  # Returns a hyperlink to UDB parameter documentation
  # ext_name - Name of the extension
  # param_name - Name of the parameter
  # link_text - What to put in the link text (don't assume param_name)
  sig { params(ext_name: String, param_name: String, link_text: String).returns(String) }
  def link_to_udb_doc_ext_param(ext_name, param_name, link_text)
    check_no_periods(param_name)
    "%%UDB_DOC_LINK%ext_param;#{ext_name.sanitize}.#{param_name};#{link_text}%%"
  end

  # Returns a hyperlink to UDB instruction documentation
  # inst_name - Name of the instruction
  sig { params(inst_name: String).returns(String) }
  def link_to_udb_doc_inst(inst_name)
    "%%UDB_DOC_LINK%inst;#{inst_name.sanitize};#{inst_name}%%"
  end

  # Returns a hyperlink to UDB CSR documentation
  # csr_name - Name of the CSR
  sig { params(csr_name: String).returns(String) }
  def link_to_udb_doc_csr(csr_name)
    "%%UDB_DOC_LINK%csr;#{csr_name.sanitize};#{csr_name}%%"
  end

  # Returns a hyperlink to UDB CSR field documentation
  # csr_name - Name of the CSR
  # field_name - Name of the CSR field
  sig { params(csr_name: String, field_name: String).returns(String) }
  def link_to_udb_doc_csr_field(csr_name, field_name)
    "%%UDB_DOC_LINK%csr_field;#{csr_name.sanitize}.#{field_name.sanitize};#{csr_name}.#{field_name}%%"
  end

  # Returns a hyperlink to UDB IDL function documentation
  # func_name - Name of the IDL function
  sig { params(func_name: String).returns(String) }
  def link_to_udb_doc_idl_func(func_name)
    "%%UDB_DOC_LINK%func;#{func_name.sanitize};#{func_name}%%"
  end

  # Returns a hyperlink to a UDB normative rule
  # fmt -  Is link to normative rule defined in its own separate chapter (fmt = "sep")
  #        or in a chapter that combines (fmt = "combo") normative rules, coverage points, and test procedures
  # name - Unique name of the normative rule
  sig { params(fmt: String, name: String).returns(String) }
  def link_to_udb_doc_norm_rule(fmt, name)
    raise ArgumentError, "Unknown fmt value of '#{fmt}' for '#{name}'" unless fmt == "sep" || fmt == "combo" || fmt == "appendix"
    "%%UDB_DOC_NORM_RULE_LINK%#{fmt};#{name.sanitize};#{name}%%"
  end

  # Returns a hyperlink to a UDB coverage point
  # fmt - Is link to coverage point defined in its own separate chapter (fmt = "sep")
  #       or in a chapter that combines (fmt = "combo") normative rules, coverage points, and test procedures
  # name - Unique name of the coverage point
  sig { params(fmt: String, name: String).returns(String) }
  def link_to_udb_doc_cover_pt(fmt, name)
    raise ArgumentError, "Unknown fmt value of '#{fmt}' for '#{name}'" unless fmt == "sep" || fmt == "combo" || fmt == "appendix"
    "%%UDB_DOC_COVER_PT_LINK%#{fmt};#{name.sanitize};#{name}%%"
  end

  # Returns a hyperlink into IDL instruction code
  # func_name - Name of the instruction
  # name - name within the instruction code
  sig { params(inst_name: String, name: String).returns(String) }
  def link_into_idl_inst_code(inst_name, name)
    "%%IDL_CODE_LINK%inst;#{inst_name.sanitize}.#{name.sanitize};#{inst_name}.#{name}%%"
  end
  # TODO: Add csr and csr_field support

  ###########
  # ANCHORS #
  ###########

  # Returns an anchor for UDB extension documentation
  # ext_name - Name of the extension
  sig { params(ext_name: String).returns(String) }
  def anchor_for_udb_doc_ext(ext_name)
    "[#udb:doc:ext:#{ext_name.sanitize}]"
  end

  # Returns an anchor for UDB parameter documentation
  # ext_name - Name of the extension
  # param_name - Name of the parameter
  sig { params(ext_name: String, param_name: String).returns(String) }
  def anchor_for_udb_doc_ext_param(ext_name, param_name)
    check_no_periods(param_name)
    "[#udb:doc:param:#{ext_name.sanitize}:#{param_name}]"
  end

  # Returns an anchor for UDB instruction documentation
  # name - Name of the instruction
  sig { params(name: String).returns(String) }
  def anchor_for_udb_doc_inst(name)
    "[#udb:doc:inst:#{name.sanitize}]"
  end

  # Returns an anchor for UDB CSR documentation
  # name - Name of the CSR
  sig { params(name: String).returns(String) }
  def anchor_for_udb_doc_csr(name)
    "[#udb:doc:csr:#{name.sanitize}]"
  end

  # Returns an anchor for UDB CSR field documentation
  # csr_name - Name of the CSR
  # field_name - Name of the CSR field
  sig { params(csr_name: String, field_name: String).returns(String) }
  def anchor_for_udb_doc_csr_field(csr_name, field_name)
    "[#udb:doc:csr_field:#{csr_name.sanitize}:#{field_name.sanitize}]"
  end

  # Returns an anchor for an IDL function documentation
  # name - Name of the function
  sig { params(name: String).returns(String) }
  def anchor_for_udb_doc_idl_func(name)
    "[#udb:doc:func:#{name.sanitize}]"
  end

  # Returns an anchor for a UDB normative rule documentation
  # fmt Is anchor in normative rule defined in its own separate chapter (fmt = "sep")
  #     or in a chapter that combines (fmt = "combo") normative rules, coverage points, and test procedures
  # name - name of the normative rule
  # Have to use [[anchor]] instead of [#anchor] since only the former works when in a table cell.
  sig { params(fmt: String, name: String).returns(String) }
  def anchor_for_udb_doc_norm_rule(fmt, name)
    raise ArgumentError, "Unknown fmt value of '#{fmt}' for name '#{name}'" unless fmt == "sep" || fmt == "combo" || fmt == "appendix"
    "[[udb:doc:norm_rule:#{fmt}:#{name.sanitize}]]"
  end

  # Returns an anchor for a UDB coverage point documentation
  # fmt - Is anchor in coverage point defined in its own separate chapter (fmt = "sep")
  #       or in a chapter that combines (fmt = "combo") normative rules, coverage points, and test procedures
  # name - name of the coverage point
  # Have to use [[anchor]] instead of [#anchor] since only the former works when in a table cell.
  sig { params(fmt: String, name: String).returns(String) }
  def anchor_for_udb_doc_cover_pt(fmt, name)
    raise ArgumentError, "Unknown fmt value of '#{fmt}' for name '#{name}'" unless fmt == "sep" || fmt == "combo" || fmt == "appendix"
    "[[udb:doc:cover_pt:#{fmt}:#{name.sanitize}]]"
  end

  # Returns an anchor inside IDL instruction code
  # func_name - Name of the instruction
  # name - name within the instruction code
  sig { params(inst_name: String, name: String).returns(String) }
  def anchor_inside_idl_inst_code(inst_name, name)
    "[#idl:code:inst:#{inst_name.sanitize}:#{name.sanitize}]"
  end
  # TODO: Add csr and csr_field support

  sig { params(s: String).void }
  def check_no_periods(s)
    raise ArgumentError, "Periods are not allowed in '#{s}'" if s.include?(".")
  end
  private :check_no_periods

  include Udb::Helpers::WavedromUtil
end

# Utilities for a backend to generate AsciiDoc.
module Udb::Helpers::AsciidocUtils
  # The syntax "class << self" causes all methods to be treated as class methods.
  class << self
    # Convert proprietary link format to legal AsciiDoc links.
    # They are converted to AsciiDoc internal cross references (i.e., <<anchor_name,link_text>>).
    # For example,
    #   %%UDB_DOC_LINK%inst;add;add instruction%%
    # is converted to:
    #   <<udb:inst:add,add instruction>>
    #
  extend T::Sig

  sig { params(path_or_str: T.any(Pathname, String)).returns(String) }
  def resolve_links(path_or_str)
      str =
        if path_or_str.is_a?(Pathname)
          path_or_str.read
        else
          path_or_str
        end
      str.gsub(/%%UDB_DOC_LINK%([^;%]+)\s*;\s*([^;%]+)\s*;\s*([^%]+)%%/) do
        type = Regexp.last_match[1]
        name = Regexp.last_match[2]
        link_text = Regexp.last_match[3]

        case type
        when "ext"
          "<<udb:doc:ext:#{name},#{link_text}>>"
        when "ext_param"
          ext_name, param_name = name.split('.')
          "<<udb:doc:param:#{ext_name}:#{param_name},#{link_text}>>"
        when "inst"
          "<<udb:doc:inst:#{name},#{link_text}>>"
        when "csr"
          "<<udb:doc:csr:#{name},#{link_text}>>"
        when "csr_field"
          csr_name, field_name = name.split('.')
          "<<udb:doc:csr_field:#{csr_name}:#{field_name},#{link_text}>>"
        when "func"
          "<<udb:doc:func:#{name},#{link_text}>>"
        else
          raise "Unhandled link type of '#{type}' for '#{name}' with link_text '#{link_text}'"
        end
      end.gsub(/%%UDB_DOC_NORM_RULE_LINK%([^;%]+)\s*;\s*([^;%]+)\s*;\s*([^%]+)%%/) do
        fmt = Regexp.last_match[1] # "sep", "combo", or "appendix"
        name = Regexp.last_match[2]
        link_text = Regexp.last_match[3]

        raise "Unhandled link fmt of '#{fmt}' for name '#{name}' with link_text '#{link_text}'" unless fmt == "sep" || fmt == "combo" || fmt == "appendix"

        "<<udb:doc:norm_rule:#{fmt}:#{name},#{link_text}>>"
      end.gsub(/%%UDB_DOC_COVER_PT_LINK%([^;%]+)\s*;\s*([^;%]+)\s*;\s*([^%]+)%%/) do
        fmt = Regexp.last_match[1] # "sep", "combo", or "appendix"
        name = Regexp.last_match[2]
        link_text = Regexp.last_match[3]

        raise "Unhandled link fmt of '#{fmt}' for name '#{name}' with link_text '#{link_text}'" unless fmt == "sep" || fmt == "combo" || fmt == "appendix"

        "<<udb:doc:cover_pt:#{fmt}:#{name},#{link_text}>>"
      end.gsub(/%%IDL_CODE_LINK%([^;%]+)\s*;\s*([^;%]+)\s*;\s*([^%]+)%%/) do
        type = Regexp.last_match[1]
        name = Regexp.last_match[2]
        link_text = Regexp.last_match[3]

        case type
        when "inst"
          inst_name, name = name.split('.')
          "<<idl:code:inst:#{inst_name}:#{name},#{link_text}>>"
        # TODO: Add csr and csr_field support
        else
          raise "Unhandled link type of '#{type}' for '#{name}' with link_text '#{link_text}'"
        end
      end
    end
  end
end

# Utilities for a backend to generate an Antora web-site.
module Udb::Helpers::AntoraUtils
  # The syntax "class << self" causes all methods to be treated as class methods.
  class << self
    # Convert proprietary link format to legal AsciiDoc links.
    #
    # They are converted to AsciiDoc external cross references in the form:
    #   xref:<module>:<file>.adoc:#<anchor_name>[<link_text>])
    # where <> don't appear in the actual cross reference (just there to indicate variable content).
    #
    # For example,
    #   %%UDB_DOC_LINK%inst;add;add instruction%%
    # is converted to:
    #   xref:insts:add.adoc#udb:doc:add[add instruction]
    #
    # Antora supports the module name after the "xref:". In the example above, it the module name is "insts"
    # and corresponds to the directory name the add.adoc file is located in. For more details, see:
    #    https://docs.antora.org/antora/latest/page/xref/
    # and then
    #    https://docs.antora.org/antora/latest/page/resource-id-coordinates/
    #
  extend T::Sig

  sig { params(path_or_str: T.any(Pathname, String)).returns(String) }
  def resolve_links(path_or_str)
      str =
        if path_or_str.is_a?(Pathname)
          path_or_str.read
        else
          path_or_str
        end
      str.gsub(/%%UDB_DOC_LINK%([^;%]+)\s*;\s*([^;%]+)\s*;\s*([^%]+)%%/) do
        type = Regexp.last_match[1]
        name = Regexp.last_match[2]
        link_text = Regexp.last_match[3]

        case type
        when "ext"
          "xref:exts:#{name}.adoc#udb:doc:ext:#{name}[#{link_text}]"
        when "ext_param"
          ext_name, param_name = name.split('.')
          "xref:exts:#{ext_name}.adoc#udb:doc:param:#{ext_name}:#{param_name}[#{link_text}]"
        when "inst"
          "xref:insts:#{name}.adoc#udb:doc:inst:#{name}[#{link_text}]"
        when "csr"
          "xref:csrs:#{name}.adoc#udb:doc:csr:#{name}[#{link_text}]"
        when "csr_field"
          csr_name, field_name = name.split('.')
          "xref:csrs:#{csr_name}.adoc#udb:doc:csr_field:#{csr_name}:#{field_name}[#{link_text}]"
        when "func"
          # All functions are in the same file called "funcs.adoc".
          "xref:funcs:funcs.adoc#udb:doc:func:#{name}[#{link_text.gsub(']', '\]')}]"
        else
          raise "Unhandled link type of '#{type}' for '#{name}' with link_text '#{link_text}'"
        end
      end.gsub(/%%IDL_CODE_LINK%([^;%]+)\s*;\s*([^;%]+)\s*;\s*([^%]+)%%/) do
        type = Regexp.last_match[1]
        name = Regexp.last_match[2]
        link_text = Regexp.last_match[3]

        case type
        when "inst"
          inst_name, name = name.split('.')
          "xref:insts:#{inst_name}.adoc#idl:code:inst:#{inst_name}:#{name}[#{link_text}]"
        # TODO: Add csr and csr_field support
        else
          raise "Unhandled link type of '#{type}' for '#{name}' with link_text '#{link_text}'"
        end
      end
    end
  end
end

# frozen_string_literal: true
#
# Collection of "helper" functions that can be called from backends and/or ERB templates.

require "erb"
require "pathname"

# Add to standard String class.
class String
  # Should be called on all RISC-V extension, instruction, CSR, and CSR field names.
  # Parameters never have periods in their names so they don't need to be sanitized.
  #
  # @param name [#to_s] Some RISC-V name which might have periods in it
  # @return [String] Periods replaced with underscores
  def sanitize = self.gsub(".", "_")
end

# This module is included in the Design class so its methods are available to be called directly
# without having to prefix a method with the module name.
module TemplateHelpers
  # Include a partial ERB template into a full ERB template.
  #
  # @param template_pname [String] Path to template file relative to backends directory
  # @param inputs [Hash<String, Object>] Input objects to pass into template
  # @return [String] Result of ERB evaluation of the template file
  def partial(template_pname, inputs = {})
    template_path = Pathname.new($root / "backends" / template_pname)
    raise ArgumentError, "Template '#{template_path} not found" unless template_path.exist?

    erb = ERB.new(template_path.read, trim_mode: "-")
    erb.filename = template_path.realpath.to_s

    erb.result(OpenStruct.new(inputs).instance_eval { binding })
  end

  # Links are created with this proprietary format so that they can be converted
  # later into either Asciidoc or Antora links (see the two implementations of "resolve_links").
  #   %%LINK%<type>;<name>;<link_text>%%
  #
  # Documentation:
  #   - How to make cross-references: https://docs.asciidoctor.org/asciidoc/latest/macros/xref/
  #   - How to create anchors: https://docs.asciidoctor.org/asciidoc/latest/attributes/id/
  #   - See https://github.com/riscv/riscv-isa-manual/issues/1397#issuecomment-2515109936 for
  #     discussion about using [#anchor] instead of [[anchor]] due to Antora's support.

  # @return [String] A hyperlink to an extension
  # @param ext_name [#to_s] Name of the extension
  def link_to_ext(ext_name)
    "%%LINK%ext;#{ext_name.sanitize};#{ext_name.sanitize}%%"
  end

  # @return [String] A hyperlink to a parameter defined by a particular extension.
  # @param ext_name [#to_s] Name of the extension
  # @param param_name [#to_s] Name of the parameter
  def link_to_ext_param(ext_name, param_name)
    check_no_periods(param_name)
    "%%LINK%ext_param;#{ext_name.sanitize}.#{param_name};#{param_name}%%"
  end

  # @return [String] A hyperlink to an instruction
  # @param inst_name [#to_s] Name of the instruction
  def link_to_inst(inst_name)
    "%%LINK%inst;#{inst_name.sanitize};#{inst_name.sanitize}%%"
  end

  # @return [String] A hyperlink to a CSR
  # @param csr_name [#to_s] Name of the CSR
  def link_to_csr(csr_name)
    "%%LINK%csr;#{csr_name.sanitize};#{csr_name.sanitize}%%"
  end

  # @return [String] A hyperlink to an IDL function
  # @param func_name [#to_s] Name of the IDL function
  def link_to_func(func_name)
    "%%LINK%func;#{func_name.sanitize};#{func_name.sanitize}%%"
  end

  # @return [String] A hyperlink to a CSR field
  # @param csr_name [#to_s] Name of the CSR
  # @param field_name [#to_s] Name of the CSR field
  def link_to_csr_field(csr_name, field_name)
    "%%LINK%csr_field;#{csr_name.sanitize}.#{field_name.sanitize};#{csr_name.sanitize}.#{field_name.sanitize}%%"
  end

  # @return [String] An anchor for an extension
  # @param ext_name [#to_s] Name of the extension
  def anchor_for_ext(ext_name)
    "[#ext-#{ext_name.sanitize}-def]"
  end

  # @return [String] An anchor for a parameter defined by a particular extension.
  # @param ext_name [#to_s] Name of the extension
  # @param param_name [#to_s] Name of the parameter
  def anchor_for_ext_param(ext_name, param_name)
    check_no_periods(param_name)
    "[#ext_param-#{ext_name.sanitize}-#{param_name}-def]"
  end

  # Insert anchor to an instruction.
  # @param name [#to_s] Name of the instruction
  def anchor_for_inst(name)
    "[#inst-#{name.sanitize}-def]"
  end

  # Insert anchor to a CSR.
  # @param name [#to_s] Name of the CSR
  def anchor_for_csr(name)
    "[#csr-#{name.sanitize}-def]"
  end

  # Insert anchor to a CSR field.
  # @param csr_name [#to_s] Name of the CSR
  # @param field_name [#to_s] Name of the CSR field
  def anchor_for_csr_field(csr_name, field_name)
    "[#csr_field-#{csr_name.sanitize}-#{field_name.sanitize}-def]"
  end

  # Insert anchor to an IDL function.
  # @param name [#to_s] Name of the function
  def anchor_for_func(name)
    "[#func-#{name.sanitize}-def]"
  end

  private
    #@ param s [String]
    def check_no_periods(s)
      raise ArgumentError, "Periods are not allowed in '#{s}'" if s.include?(".")
    end
end

# Utilities for a backend to generate Asciidoc.
module AsciidocUtils
  # The syntax "class << self" causes all methods to be treated as class methods.
  class << self
    # Convert proprietary link format to legal Asciidoc links.
    # They are converted to standard xref:#anchor_name[link_text] format here.
    # For example,
    #   %%LINK%inst;add;add instruction%%
    # is converted to:
    #   xref:#inst-add-def[add instruction]
    #
    # @param path_or_str [Pathname or String]
    # @return [String]
    def resolve_links(path_or_str)
      str =
        if path_or_str.is_a?(Pathname)
          path_or_str.read
        else
          path_or_str
        end
      str.gsub(/%%LINK%([^;%]+)\s*;\s*([^;%]+)\s*;\s*([^%]+)%%/) do
        type = Regexp.last_match[1]
        name = Regexp.last_match[2]
        link_text = Regexp.last_match[3]

        case type
        when "ext"
          "xref:#ext-#{name}-def[#{link_text}]"
          # link_text
        when "ext_param"
          ext_name, param_name = name.split('.')
          "xref:#ext_param-#{ext_name}-#{param_name}-def[#{link_text}]"
        when "inst"
          #"xref:#inst-#{name}-def[#{link_text.gsub(']', '\]')}]"
          # XXX: Is the gsub above necessary?
          "xref:#inst-#{name}-def[#{link_text}]"
        when "csr"
          "xref:#csr-#{name}-def[#{link_text}]"
        when "csr_field"
          csr_name, field_name = name.split('.')
          "xref:#csr_field-#{csr_name}-#{field_name}-def[#{link_text}]"
          # link_text
        when "func"
          "xref:#func-#{name}-def[#{link_text}]"
        else
          raise "Unhandled link type '#{type}' for '#{name}' in '#{path_or_str}'"
        end
      end
    end
  end
end

# Utilities for a backend to generate an Antora web-site.
module AntoraUtils
  # The syntax "class << self" causes all methods to be treated as class methods.
  class << self
    # Convert proprietary link format to legal Asciidoc links.
    # They are converted to standard xref:#anchor_name[link_text] format here.
    # For example,
    #   %%LINK%inst;add;add instruction%%
    # is converted to:
    #   xref:#inst-add-def[add instruction]
    #
    # @param path_or_str [Pathname or String]
    # @return [String]
    def resolve_links(path_or_str)
      str =
        if path_or_str.is_a?(Pathname)
          path_or_str.read
        else
          path_or_str
        end
      str.gsub(/%%LINK%([^;%]+)\s*;\s*([^;%]+)\s*;\s*([^%]+)%%/) do
        type = Regexp.last_match[-1]
        name = Regexp.last_match[0]
        link_text = Regexp.last_match[1]

        case type
        when "inst"
          "xref:insts:#{name}.adoc##{name}-def[#{link_text.gsub(']', '\]')}]"
        when "csr"
          "xref:csrs:#{name}.adoc##{name}-def[#{link_text.gsub(']', '\]')}]"
        when "csr_field"
          csr_name, field_name = name.split('.')
          "xref:csrs:#{csr_name}.adoc##{csr_name}-#{field_name}-def[#{link_text.gsub(']', '\]')}]"
        when "ext"
          "xref:exts:#{name}.adoc##{name}-def[#{link_text.gsub(']', '\]')}]"
        else
          raise "Unhandled link type of '#{type}' for '#{name}' in '#{path_or_str}'"
        end
      end
    end
  end
end

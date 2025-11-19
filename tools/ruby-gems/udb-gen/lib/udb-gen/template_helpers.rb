# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

module UdbGen
  module TemplateHelpers
    extend T::Sig
    include Kernel

    sig { params(template_pname: String, inputs: T::Hash[Symbol, T.untyped]).returns(String) }
    def partial(template_pname, inputs = {})
      template_path = Pathname.new(__dir__) / ".." / ".." / "templates" / template_pname
      raise ArgumentError, "Template '#{template_path} not found" unless template_path.exist?

      erb = ERB.new(template_path.read, trim_mode: "-")
      erb.filename = template_path.realpath.to_s

      context = OpenStruct.new(inputs)
      context.singleton_class.include(TemplateHelpers)
      erb.result(context.instance_eval { binding })
    end

    LinkableObj = T.type_alias { T.any(Udb::Instruction, Udb::Csr, Udb::CsrField, Idl::FunctionDefAst) }

    # return an asciidoc link to obj, with text "text"
    sig { params(obj: LinkableObj, text: String).returns(String) }
    def link_to(obj, text = obj.name)
      # link on the same page
      "xref:##{link_name(obj)}[#{text}]"
    end

    # return an asciidoc anchor for obj
    sig { params(obj: LinkableObj).returns(String) }
    def anchor_for(obj)
      "[##{link_name(obj)}]"
    end

    # return an asciidoc link to obj, with text "text"
    sig { params(obj: LinkableObj).returns(String) }
    def link_name(obj)
      case obj
      when Udb::Instruction
        "udb-insn-#{obj.name.gsub(".", "_")}"
      when Udb::Csr
        "udb-csr-#{obj.name.gsub(".", "_")}"
      when Udb::CsrField
        "udb-csrfield-#{obj.parent.name.gsub(".", "_")}-#{obj.name.gsub(".", "_")}"
      when Idl::FunctionDefAst
        "udb-function-#{obj.name.gsub(".", "_")}"
      else
        T.absurd(obj)
      end
    end

    sig { params(cfg_arch: Udb::ConfiguredArchitecture, adoc: String).returns(String) }
    def convert_monospace_to_links(cfg_arch, adoc)
      adoc.gsub(/`([\\w.]+)`/) do |match|
        name = Regexp.last_match(1)
        csr_name, field_name = T.must(name).split(".")
        csr = cfg_arch.not_prohibited_csrs.find { |c| c.name == csr_name }
        if !field_name.nil? && !csr.nil? && csr.field?(field_name)
          link_to(csr.field(field_name), match)
        elsif !csr.nil?
          link_to(csr, match)
        elsif cfg_arch.not_prohibited_instructions.any? { |inst| inst.name == name }
          link_to(cfg_arch.instruction(name), match)
        elsif cfg_arch.not_prohibited_extensions.any? { |ext| ext.name == name }
          link_to(cfg_arch.extension(name), match)
        else
          match
        end
      end
    end

    sig { params(cfg_arch: Udb::ConfiguredArchitecture, adoc: String).returns(String) }
    def resolve_intermediate_links(cfg_arch, adoc)
      adoc.gsub(/%%UDB_DOC_LINK%([^;%]+)\s*;\s*([^;%]+)\s*;\s*([^%]+)%%/) do |match|
        type = T.must(Regexp.last_match(1))
        name = T.must(Regexp.last_match(2))
        link_text = T.must(Regexp.last_match(3))

        case type
        when "ext"
          ext = cfg_arch.extension(name)
          if ext
            link_to(cfg_arch.extension(name), link_text)
          else
            warn "Attempted link to undefined extension: #{name}"
            match
          end
        when "ext_param"
          param = cfg_arch.param(name)
          if param
            link_to(param, link_text)
          else
            warn "Attempted link to undefined parameter: #{name}"
            match
          end
        when "inst"
          inst = cfg_arch.instruction(name)
          if inst
            link_to(inst, link_text)
          else
            warn "Attempted link to undefined instruction: #{name}"
            match
          end
        when "csr"
          csr = cfg_arch.csr(name)
          if csr
            link_to(cfg_arch.csr(name), link_text)
          else
            warn "Attempted link to undefined CSR: #{name}"
            match
          end
        when "csr_field"
          csr_name, field_name = name.split("*")
          csr = cfg_arch.csr(csr_name)
          if csr
            csr_field = csr.field(field_name)
            if csr_field
              link_to(csr_field, link_text)
            else
              warn "Attempted link to undefined CSR field: #{name}"
              match
            end
          else
            warn "Attempted link to undefined CSR: #{csr_name}"
            match
          end
        when "func"
          func = cfg_arch.function(name)
          if func
            link_to(func, link_text)
          else
            warn "Attempted link to undefined function: #{name}"
            match
          end
        else
          raise "Unhandled link type of '#{type}' for '#{name}' with link_text '#{link_text}'"
        end
      end
    end
  end
end

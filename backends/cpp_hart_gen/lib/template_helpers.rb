# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"

class Array
  def to_cxx
    "{#{map(&:to_cxx).join(', ')}}"
  end
end

module Udb
  class Instruction
    def assembly_fmt(xlen)
      fmt = assembly.dup
      dvs = encoding(xlen).decode_variables
      dvs.each do |dv|
        fmt.gsub!(dv.name, "{}")
      end
      fmt
    end

    def assembly_fmt_args(xlen)
      args = []
      dvs = encoding(xlen).decode_variables
      dvs.each do |dv|
        if dv.name[0] == "x" || dv.name[0] == "r"
          args << "Reg(#{dv.name}()).to_string()"
        elsif dv.name[0] == "f"
          args << "Reg(#{dv.name}(), true).to_string()"
        else
          args << "#{dv.name}()"
        end
      end
      if args.empty?
        ""
      else
        ", #{args.reverse.join(', ')}"
      end
    end
  end
end

module Udb

  class LogicNode
    sig { params(block: T.proc.params(arg0: T.any(ExtensionTerm, ParameterTerm, XlenTerm)).returns(String)).returns(String) }
    def to_cxx(&block)
      if type == LogicNodeType::Term
        raise "unexpected" if @children[0].is_a?(FreeTerm)

        yield @children[0]
      elsif type == LogicNodeType::Not
        "!(#{@children[0].to_cxx(&block)})"
      elsif type == LogicNodeType::And
        "(#{@children.map { |c| c.to_cxx(&block) }.join(" && ")})"
      elsif type == LogicNodeType::Or
        "(#{@children.map { |c| c.to_cxx(&block) }.join(" || ")})"
      elsif type == LogicNodeType::Xor
        sum = []
        @children.size.times do |i|
          prod = []
          @children.size.times do |j|
            prod << "#{i == j ? "" : "!"}(#{@children.fetch(i).to_cxx(&block)})"
          end
          sum << prod.join(" && ")
        end
        "(#{sum.join(" || ")})"
      else
        raise "unexpected logic node type: #{type}"
      end
    end
  end

  class Condition

    sig { params(block: T.proc.params(arg0: T.any(Udb::ExtensionTerm, Udb::ParameterTerm, Udb::XlenTerm)).returns(String)).returns(String) }
    def to_cxx(&block)
      raise ArgumentError, "Missing block" unless block_given?

      to_logic_tree(expand: false).to_cxx(&block)
    end
  end
end

module CppHartGen
  module TemplateHelpers
    extend T::Sig

    # get the name of a c++ class
    #
    # e.g.:
    #
    # name_of(:hart, cfg_arch)
    # name_of(:params, "rv64")
    sig { params(kind: Symbol, cfg_arch_or_config_name: T.any(Udb::ConfiguredArchitecture, String), extras: T.anything).returns(String) }
    def name_of(kind, cfg_arch_or_config_name, *extras)
      config_name = cfg_arch_or_config_name.is_a?(Udb::ConfiguredArchitecture) ? cfg_arch.name : cfg_arch_or_config_name
      config_name = config_name.gsub("-", "_")
      case kind
      when :cfg
        config_name.camelize
      when :hart
        "#{config_name.camelize}_Hart"
      when :param
        "#{extras[0].name}_Parameter"
      when :params
        "#{config_name.camelize}_Params"
      when :csr
        raise "Missing csr name" unless extras.size == 1

        "#{config_name.camelize}_#{extras[0].gsub(".", "_").capitalize}_Csr"
      when :csr_field
        raise "Missing csr name" unless extras.size == 2

        "#{config_name.camelize}_#{extras[0].gsub(".", "_").capitalize}_#{extras[1].capitalize}_Field"
      when :csr_container
        "#{config_name.camelize}_CsrContainer"
      when :csr_view
        raise "Missing csr name" unless extras.size == 1

        "#{config_name.camelize}_#{extras[0].gsub(".", "_").capitalize}_CsrView"
      when :inst
        raise "Missing Instruction name" unless extras.size == 1

        "#{config_name.camelize}_#{extras[0].gsub(".", "_").capitalize}_Inst"
      when :struct
        raise "Missing struct name" unless extras.size == 1

        "#{config_name.camelize}_#{extras[0]}_Struct"
      else
        raise "TODO: #{kind}"
      end
    end

    # if val is a String, quotes it. Otherwise, returns val
    sig { type_parameters(:V).params(val: T.type_parameter(:V)).returns(T.type_parameter(:V)) }
    def quot_str(val)
      if val.is_a?(String)
        "\"#{val}\""
      elsif val.is_a?(Integer)
        "#{val}_b"
      else
        val
      end
    end
  end

  class TemplateEnv
    attr_reader :cfg_arch
    def initialize(cfg_arch)
      @cfg_arch = cfg_arch
    end

    include TemplateHelpers

    def get_binding
      binding
    end
  end
end

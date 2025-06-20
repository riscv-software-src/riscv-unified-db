# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

module Idl
  class Type
    def to_cxx_no_qualifiers
      case @kind
      when :bits
        raise "@width is a #{@width.class}" unless @width.is_a?(Integer) || @width == :unknown

        width_cxx =
          case @width
          when Integer
            @width
          when Symbol
            raise "bad width" unless @width == :unknown

            "BitsInfinitePrecision"
          else
            T.absurd(@width)
          end

        if signed?
          "Bits<#{width_cxx}, true>"
        else
          "Bits<#{width_cxx}>"
        end
      when :enum
        @name
      when :boolean
        "bool"
      when :enum_ref
        @enum_class.name
      when :tuple
        "std::tuple<#{@tuple_types.map(&:to_cxx).join(',')}>"
      when :bitfield
        @name
      when :array
        if @width == :unknown
          "std::vector<#{@sub_type.to_cxx_no_qualifiers}>"
        else
          "std::array<#{@sub_type.to_cxx_no_qualifiers}, #{@width}>"
        end
      when :csr
        "#{T.unsafe(CppHartGen::TemplateEnv).new(@csr.cfg_arch).name_of(:csr, @csr.cfg_arch, @csr.name)}<SocType>"
      when :string
        "std::string"
      when :void
        "void"
      else
        raise @kind.to_s
      end
    end

    def to_cxx
      ((@qualifiers.nil? || @qualifiers.empty?) ? '' : "#{@qualifiers.include?(:const) ? 'const' : ''} ") + \
      to_cxx_no_qualifiers
    end
  end
end

# SPDX-License-Identifier: BSD-3-Clause-Clear
# SPDX-FileCopyrightText: Copyright (c) Charlie Jenkins

# typed: false
# frozen_string_literal: true

require "pathname"
require "fileutils"
require "optparse"
require "udb/resolver"

module UdbGen
  module InstTable
    class TableBuilder
      extend T::Sig

      sig { params(arch: Udb::ConfiguredArchitecture, file_name: T.nilable(String)).void }
      def initialize(arch, file_name)
        @arch = arch
        @file_name = file_name
      end

      def get_encoding(inst, base)
        return [] unless inst.defined_in_base?(base)

        fields = []

        enc_obj = inst.encoding(base)
        fixed = enc_obj.opcode_fields.map do |fo|
          "#{fo.name}<#{fo.range.first}"
        end

        fields.append(fixed.join("|"))

        dvs = inst.decode_variables(base)

        dvs.each do |d|
          field = "#{d.name}"

          if d.sext?
            field += "~"
          end

          unless d.excludes.empty?
            field += "!#{d.excludes.join('!')}"
          end

          if d.left_shift > 0
            field += "<#{d.left_shift}"
          end

          field += "=#{d.location}"

          fields.append(field)
        end

        return fields
      end

      sig { returns(String) }
      def generate
        lines = []
        @arch.instructions.each do |inst|
          enc_32 = get_encoding(inst, 32)
          enc_64 = get_encoding(inst, 64)

          if enc_32.empty? && enc_64.empty?
            puts "instruction #{inst.name} not supported by 32-bit or 64-bit"
            next
          end

          # Same encoding for 32/64-bit
          if (enc_32 == enc_64)
            lines << ([inst.name, "common"] + enc_64).join(" ")
            next
          end

          # There are some instructions that have different encodings on 32/64-bit
          unless enc_32.empty? || enc_64.empty?
            lines << ([inst.name, "common,32"] + enc_32).join(" ")
            lines << ([inst.name, "common,64"] + enc_64).join(" ")
            next
          end

          if enc_32.any?
            lines << ([inst.name, "32"] + enc_32).join(" ")
            next
          end

          if enc_64.any?
            lines << ([inst.name, "64"] + enc_64).join(" ")
            next
          end
        end

        command = "./bin/generate inst-table"
        command += " -o #{@file_name}" unless @file_name.nil?

        header = <<EOM
# SPDX-License-Identifier: BSD-3-Clause-Clear
#
# GENERATED WITH https://github.com/riscv-software-src/riscv-unified-db
# "#{command}"
#
# Each line of the instruction table should have the following format:
# NAME BASE FIXED_BITS [VARIABLE_LIST]
# NAME                        instruction name
# BASE                        instruction base size (common[,(32|64)])
#                             "common" means the instruction is valid on both architecture sizes
#                             "32" or "64" means the instruction is valid on that size
#                             if the instruction is valid on both architectures but has unique
#                             encodings, use a 32-bit entry "common,32" and 64-bit entry
# FIXED_BITS                  bitfields of the fixed bits of an instruction concatenated with '|'
#                             continuous grouping of fixed bits are in the form of 'bits<offset'
# VARIABLE_LIST               a variable sized list of all variables in the instruction definition
#                             in the form of name[~][<num][!num...]=(high[-low])|...
#                             symbols after the name represent different modifiers:
#                                 ~ sign extension, can only appear once
#                                 < left shift by 'num' amount on extraction, can only appear once
#                                 ! mark 'num' as an invalid input for this variable
EOM

        # Sort alphabetically by instruction mnemonic so the output is
        # deterministic regardless of where the instruction files live (moving a
        # file between extension directories must not change this table). Each
        # line begins with the instruction name, so sorting the full lines orders
        # by mnemonic and keeps an instruction's multi-row entries (e.g.
        # "common,32"/"common,64") grouped and stably ordered.
        lines.sort!

        header + lines.join("\n") + "\n"
      end
    end
  end
end

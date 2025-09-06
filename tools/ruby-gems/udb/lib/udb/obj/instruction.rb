# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true
# typed: true

# require 'ruby-prof-flamegraph'

require_relative "database_obj"
require_relative "certifiable_obj"
require_relative "../presence"
require "udb_helpers/backend_helpers"
require "awesome_print"

module Udb
class InstructionType < DatabaseObject
  sig {
    params(
      data: T::Hash[String, T.untyped],
      data_path: T.any(String, Pathname),
      arch: ConfiguredArchitecture,
      name: T.nilable(String)
    ).void
  }
  def initialize(data, data_path, arch, name: nil)
    super(data, data_path, arch, DatabaseObject::Kind::InstructionType, name:)
  end

  def length = @data["length"]
  def size = length
end

class InstructionSubtype < DatabaseObject
  class Opcode
    extend T::Sig

    sig { returns(String) }
    attr_reader :name

    sig { returns(Range) }
    attr_reader :range

    sig { params(name: String, range: Range).void }
    def initialize(name, range)
      @name = name
      @range = range
    end

    sig { params(other: T.any(Opcode, Instruction::DecodeVariable)).returns(T::Boolean) }
    def overlaps?(other)
      if other.is_a?(Opcode)
        range.eql?(other.range) || range.cover?(other.range.first) || other.range.cover?(range.first)
      else
        other.location_bits.any? { |i| range.cover?(i)}
      end
    end
  end

  sig {
    params(
      data: T::Hash[String, T.untyped],
      data_path: T.any(String, Pathname),
      arch: ConfiguredArchitecture,
      name: T.nilable(String)
    ).void
  }
  def initialize(data, data_path, arch, name: nil)
    super(data, data_path, arch, DatabaseObject::Kind::InstructionSubtype, name:)
  end

  sig { returns(InstructionType) }
  def type
    @type ||= @arch.ref(@data["data"]["type"]["$ref"])
  end

  sig { returns(T::Array[Instruction::DecodeVariable]) }
  def variables
    @variables ||=
      if @data["data"].key?("variables")
        @data["data"]["variables"].map { |var_name, var_data| Instruction::DecodeVariable.new(var_name, var_data) }
      else
        []
      end
  end

  sig { returns(T::Array[Instruction::Encoding::Field]) }
  def opcodes
    @opcodes ||=
      @data["data"]["opcodes"].map do |opcode_name, opcode_data|
        next if opcode_name[0] == "$"

        raise "unexpected: opcode field is not contiguous" if opcode_data["location"].include?("|")

        loc = opcode_data["location"]
        range =
          if loc =~ /^([0-9]+)$/
            bit = ::Regexp.last_match(1)
            bit.to_i..bit.to_i
          elsif loc =~ /^([0-9]+)-([0-9]+)$/
            msb = ::Regexp.last_match(1)
            lsb = ::Regexp.last_match(2)
            raise "range must be specified 'msb-lsb'" unless msb.to_i >= lsb.to_i

            lsb.to_i..msb.to_i
          else
            raise "location format error"
          end
        Instruction::Encoding::Field.new(opcode_name, range)
      end.reject(&:nil?)
  end
end

# model of a specific instruction in a specific base (RV32/RV64)
class Instruction < TopLevelDatabaseObject
  # Add all methods in this module to this type of database object.
  include CertifiableObject
  include Helpers::WavedromUtil

  sig { returns(T::Boolean) }
  def has_type? = @data.key?("format")

  sig { params(base: Integer).returns(InstructionType) }
  def type(base)
    @type ||= {
      32 =>
        if @data["format"].key?("RV32")
          @arch.ref(@data["format"]["RV32"]["type"]["$ref"])
        else
          @arch.ref(@data["format"]["type"]["$ref"])
        end,
      64 =>
        if @data["format"].key?("RV64")
          @arch.ref(@data["format"]["RV64"]["type"]["$ref"])
        else
          @arch.ref(@data["format"]["type"]["$ref"])
        end
    }
    @type[base]
  end

  sig { params(base: Integer).returns(InstructionSubtype) }
  def subtype(base)
    @subtype ||= {
      32 =>
        if @data["format"].key?("RV32")
          @arch.ref(@data["format"]["RV32"]["subtype"]["$ref"])
        else
          @arch.ref(@data["format"]["subtype"]["$ref"])
        end,
      64 =>
        if @data["format"].key?("RV64")
          @arch.ref(@data["format"]["RV64"]["subtype"]["$ref"])
        else
          @arch.ref(@data["format"]["subtype"]["$ref"])
        end
    }
    @subtype[base]
  end

  class Opcode < InstructionSubtype::Opcode
    extend T::Sig

    sig { returns(Integer) }
    attr_reader :value

    sig { params(name: String, range: Range, value: Integer).void }
    def initialize(name, range, value)
      super(name, range)
      @value = value
    end

    sig { returns(T::Boolean) }
    def opcode? = true

    sig { returns(String) }
    def to_s = "#{name}[#{range}]"
  end

  sig { params(base: Integer).returns(T::Array[Opcode]) }
  def opcodes(base)
    raise "Instruction #{name} is not defined in base RV#{base}" unless defined_in_base?(base)

    @opcodes ||= {}

    return @opcodes[base] unless @opcodes[base].nil?

    @opcodes[base] = @data["format"]["opcodes"].map do |opcode_name, opcode_data|
        next if opcode_name[0] == "$"

        raise "unexpected: opcode field is not contiguous" if opcode_data["location"].include?("|")

        loc = opcode_data["location"]
        range =
          if loc =~ /^([0-9]+)$/
            bit = ::Regexp.last_match(1)
            bit.to_i..bit.to_i
          elsif loc =~ /^([0-9]+)-([0-9]+)$/
            msb = ::Regexp.last_match(1)
            lsb = ::Regexp.last_match(2)
            raise "range must be specified 'msb-lsb'" unless msb.to_i >= lsb.to_i

            lsb.to_i..msb.to_i
          else
            raise "location format error"
          end
        Opcode.new(opcode_name, range, opcode_data["value"])
      end.reject(&:nil?)
  end

  # @return [String] format, as a string of 0,1 and -,
  # @example Format of `sd`
  #      sd.format #=> '-----------------011-----0100011'
  sig { params(base: Integer).returns(String) }
  def encoding_format(base)
    raise ArgumentError, "base must be 32 or 64" unless [32, 64].include?(base)

    if has_type?
      mask = "-" * type(base).length

      opcodes(base).each do |opcode|
        mask[type(base).length - opcode.range.end - 1, opcode.range.size] = opcode.value.to_s(2).rjust(T.must(opcode.range.size), "0")
      end

      mask
    else
      @encoding_format ||=
        if @data["encoding"].key?("RV32")
          {
            32 => @data["encoding"]["RV32"]["match"],
            64 => @data["encoding"]["RV64"]["match"]
          }
        else
          {
            32 => @data["encoding"]["match"],
            64 => @data["encoding"]["match"]
          }
        end
      @encoding_format[base]
    end
  end

  def processed_wavedrom_desc(base)
    data = wavedrom_desc(base)
    processed_data = process_wavedrom(data)
    fix_entities(json_dump_with_hex_literals(processed_data))
  end

  def self.ary_from_location(location_str_or_int)
    return [location_str_or_int] if location_str_or_int.is_a?(Integer)

    bits = []
    parts = location_str_or_int.split("|")
    parts.each do |part|
      if part.include?("-")
        msb, lsb = part.split("-").map(&:to_i)
        (lsb..msb).each { |i| bits << i }
      else
        bits << part.to_i
      end
    end
    bits
  end

  sig { params(inst: Instruction, base: Integer).void }
  def self.validate_encoding(inst, base)
    # make sure there is no overlap between variables/opcodes
    (inst.opcodes(base) + inst.decode_variables(base)).combination(2) do |field1, field2|
      raise "In instruction #{inst.name}, #{field1.name} and #{field2.name} overlap" if field1.overlaps?(field2)
    end

    # makes sure every bit is accounted for
    inst.type(base).length.times do |i|
      covered =
        inst.opcodes(base).any? { |opcode| opcode.range.cover?(i) } || \
        inst.decode_variables(base).any? { |var| var.location_bits.include?(i) }
      raise "In instruction #{inst.name}, there is no opcode or variable at bit #{i}" unless covered
    end

    # make sure opcode values fit
    inst.opcodes(base).each do |opcode|
      raise "In instruction #{inst.name}, opcode #{opcode.name}, value #{opcode.value} does not fit in #{opcode.range}" unless T.must(opcode.range.size) >= opcode.value.bit_length
    end
  end

  def self.deprecated_validate_encoding(encoding, inst_name)
    match = encoding["match"]
    raise "No match for instruction #{inst_name}?" if match.nil?

    variables = encoding.key?("variables") ? encoding["variables"] : []
    match.size.times do |i|
      if match[match.size - 1 - i] == "-"
        # make sure exactly one variable covers this bit
        vars_match = variables.count { |variable| ary_from_location(variable["location"]).include?(i) }
        if vars_match.zero?
          raise ValidationError, "In instruction #{inst_name}, no variable or encoding bit covers bit #{i}"
        elsif vars_match != 1
          raise ValidationError, "In instruction, #{inst_name}, bit #{i} is covered by more than one variable"
        end
      else
        # make sure no variable covers this bit
        unless variables.nil?
          unless variables.none? { |variable| ary_from_location(variable["location"]).include?(i) }
            raise ValidationError, "In instruction, #{inst_name}, bit #{i} is covered by both a variable and the match string"
          end
        end
      end
    end
  end

  sig { override.params(resolver: Resolver).void }
  def validate(resolver)
    super(resolver)

    if has_type?
      if @data["format"]["RV32"].nil?
        b = @data["base"].nil? ? 64 : T.cast(@data["base"], Integer)
        Instruction.validate_encoding(self, b)
      else
        Instruction.validate_encoding(self, 32)
        Instruction.validate_encoding(self, 64)
      end
    else
      if @data["encoding"]["RV32"].nil?
        Instruction.deprecated_validate_encoding(@data["encoding"], name)
      else
        Instruction.deprecated_validate_encoding(@data["encoding"]["RV32"], name)
        Instruction.deprecated_validate_encoding(@data["encoding"]["RV64"], name)
      end
    end

    # Validate hint references
    if @data.key?("hints")
      @data["hints"].each_with_index do |hint, index|
        if hint.key?("$ref")
          begin
            # Try to dereference the hint to validate it exists
            hint_inst = @cfg_arch.ref(hint["$ref"])
            if hint_inst.nil?
              raise "Invalid hint reference in instruction '#{name}' at hints[#{index}]: '#{hint["$ref"]}' - reference not found"
            end
          rescue => e
            raise "Invalid hint reference in instruction '#{name}' at hints[#{index}]: '#{hint["$ref"]}' - #{e.message}"
          end
        end
      end
    end
  end

  def ==(other)
    if other.is_a?(Instruction)
      name == other.name
    else
      raise ArgumentError, "Instruction is not comparable to a #{other.class.name}"
    end
  end

  alias eql? ==

  def <=>(other)
    if other.is_a?(Instruction)
      name <=> other.name
    else
      raise ArgumentError, "Instruction is not comparable to a #{other.class.name}"
    end
  end

  # @return [Hash<String, String>] Hash of access permissions for each mode. The key is the lowercase name of a privilege mode, and the value is one of ['never', 'sometimes', 'always']
  def access
    @data["access"]
  end

  # @return [String] Details of the access restrictions
  # @return [nil] if no details are available
  def access_detail
    @data["access_detail"]
  end

  # @return [Integer] XLEN that must be effective for instruction to exist
  # @return [nil] if instruction exists in all XLENs
  def base
    @data["base"]
  end

  # @return [Boolean] Whether or not the instruction must have data-independent timing when Zkt is enabled.
  def data_independent_timing? = @data["data_independent_timing"]

  # @param xlen [Integer] 32 or 64, the target xlen
  # @return [Boolean] whethen or not instruction is defined in base +xlen+
  def defined_in_base?(xlen)
    base.nil? || (base == xlen)
  end

  # @return [String] Assembly format
  def assembly
    @data["assembly"]
  end

  def fill_symtab(effective_xlen, ast)
    symtab = cfg_arch.symtab.global_clone
    symtab.push(ast)
    symtab.add(
      "__instruction_encoding_size",
      Idl::Var.new("__instruction_encoding_size", Idl::Type.new(:bits, width: encoding_width.bit_length), encoding_width)
    )
    symtab.add(
      "__effective_xlen",
      Idl::Var.new("__effective_xlen", Idl::Type.new(:bits, width: 7), effective_xlen)
    )
    encoding(effective_xlen).decode_variables.each do |d|
      qualifiers = [:const]
      qualifiers << :signed if d.sext?
      width = d.size

      var = Idl::Var.new(d.name, Idl::Type.new(:bits, qualifiers:, width:), decode_var: true)
      symtab.add(d.name, var)
    end

    symtab
  end

  # @param global_symtab [Idl::SymbolTable] Symbol table with global scope populated and a configuration loaded
  # @return [Idl::FunctionBodyAst] A pruned abstract syntax tree
  def pruned_operation_ast(effective_xlen)
    defer :pruned_operation_ast do
      return nil unless @data.key?("operation()")

      type_checked_ast = type_checked_operation_ast(effective_xlen)
      symtab = fill_symtab(effective_xlen, type_checked_ast)
      pruned_ast = type_checked_ast.prune(symtab)
      pruned_ast.freeze_tree(symtab)

      symtab.release
      pruned_ast
    end
  end

  # @param symtab [Idl::SymbolTable] Symbol table with global scope populated
  # @param effective_xlen [Integer] The effective XLEN to evaluate against
  # @return [Array<Idl::FunctionBodyAst>] List of all functions that can be reached from operation()
  def reachable_functions(effective_xlen)
    if @data["operation()"].nil?
      []
    else
      # RubyProf.start
      ast = type_checked_operation_ast(effective_xlen)
      symtab = fill_symtab(effective_xlen, ast)
      fns = ast.reachable_functions(symtab)
      # result = RubyProf.stop
      # RubyProf::FlatPrinter.new(result).print($stdout)
      # exit
      symtab.release
      fns
    end
  end

  # @param symtab [Idl::SymbolTable] Symbol table with global scope populated
  # @param effective_xlen [Integer] Effective XLEN to evaluate against
  # @return [Integer] Mask of all exceptions that can be reached from operation()
  def reachable_exceptions(effective_xlen)
    if @data["operation()"].nil?
      []
    else
      # pruned_ast =  pruned_operation_ast(symtab)
      # type_checked_operation_ast()
      type_checked_ast = type_checked_operation_ast( effective_xlen)
      symtab = fill_symtab(effective_xlen, type_checked_ast)
      type_checked_ast.reachable_exceptions(symtab)
      symtab.release
    end
  end

  def mask_to_array(int)
    elems = []
    idx = 0
    while int != 0
      if (int & (1 << idx)) != 0
        elems << idx
      end
      int &= ~(1 << idx)
      idx += 1
    end
    elems
  end

  # @param effective_xlen [Integer] Effective XLEN to evaluate against. If nil, evaluate against all valid XLENs
  # @return [Array<Integer>] List of all exceptions that can be reached from operation()
  def reachable_exceptions_str(effective_xlen=nil)
    raise ArgumentError, "effective_xlen is a #{effective_xlen.class} but must be an Integer or nil" unless effective_xlen.nil? || effective_xlen.is_a?(Integer)

    if @data["operation()"].nil?
      []
    else
      symtab = cfg_arch.symtab
      etype = symtab.get("ExceptionCode")
      if effective_xlen.nil?
        if cfg_arch.multi_xlen?
          if base.nil?
            (
              pruned_ast = pruned_operation_ast(32)
              symtab = fill_symtab(32, pruned_ast)
              e32 = mask_to_array(pruned_ast.reachable_exceptions(symtab)).map { |code|
                etype.element_name(code)
              }
              symtab.release
              pruned_ast = pruned_operation_ast(64)
              symtab = fill_symtab(64, pruned_ast)
              e64 = mask_to_array(pruned_ast.reachable_exceptions(symtab)).map { |code|
                etype.element_name(code)
              }
              symtab.release
              e32 + e64
            ).uniq
          else
            pruned_ast = pruned_operation_ast(base)
            symtab = fill_symtab(base, pruned_ast)
            e = mask_to_array(pruned_ast.reachable_exceptions(symtab)).map { |code|
              etype.element_name(code)
            }
            symtab.release
            e
          end
        else
          effective_xlen = cfg_arch.mxlen
          pruned_ast = pruned_operation_ast(effective_xlen)
          puts " #{name}..."
          symtab = fill_symtab(effective_xlen, pruned_ast)
          e = mask_to_array(pruned_ast.reachable_exceptions(symtab)).map { |code|
            etype.element_name(code)
          }
          symtab.release
          e
        end
      else
        pruned_ast = pruned_operation_ast(effective_xlen)

        symtab = fill_symtab(effective_xlen, pruned_ast)
        e = mask_to_array(pruned_ast.reachable_exceptions(symtab)).map { |code|
          etype.element_name(code)
        }
        symtab.release
        e
      end
    end
  end

  # represents a single contiguous instruction encoding field
  # Multiple EncodingFields may make up a single DecodeField, e.g., when an immediate
  # is split across multiple locations
  class EncodingField
    # name, which corresponds to a name used in riscv_opcodes
    attr_reader :name

    # range in the encoding
    attr_reader :range

    def initialize(name, range, pretty = nil)
      @name = name
      @range = range
      @pretty = pretty
    end

    # is this encoding field a fixed opcode?
    def opcode?
      name.match?(/^[01]+$/)
    end


    def eql?(other)
      @name == other.name && @range == other.range
    end

    def hash
      [@name, @range].hash
    end

    def pretty_to_s
      return @pretty unless @pretty.nil?

      @name
    end

    def size
      @range.size
    end
  end

  # decode field constructions from YAML file, rather than riscv-opcodes
  # eventually, we will move so that all instructions use the YAML file,
  class DecodeVariable
    extend T::Sig

    # the name of the field
    attr_reader :name

    # alias of this field, or nil if none
    #
    # used, e.g., when a field represents more than one variable (like rs1/rd for destructive instructions)
    attr_reader :alias

    # amount the field is left shifted before use, or nil is there is no left shift
    #
    # For example, if the field is offset[5:3], left_shift is 3
    attr_reader :left_shift

    # @return [Array<Integer>] Specific values that are prohibited for this variable
    attr_reader :excludes

    attr_reader :encoding_fields

    sig { returns(String) }
    attr_reader :location

    # @return [Array<Integer>] Any array containing every encoding index covered by this variable
    sig { returns(T::Array[Integer]) }
    def location_bits
      Instruction.ary_from_location(@location)
    end

    # @return [String] Name, along with any != constraints,
    # @example
    #   pretty_name #=> "rd != 0"
    #   pretty_name #=> "rd != {0,2}"
    def pretty_name
      if excludes.empty?
        name
      elsif excludes.size == 1
        "#{name} != #{excludes[0]}"
      else
        "#{name} != {#{excludes.join(',')}}"
      end
    end

    def extract_location(location)
      @encoding_fields = []

      if location.is_a?(Integer)
        @encoding_fields << EncodingField.new("", location..location)
        return
      end

      location_string = location
      parts = location_string.split("|")
      parts.each do |part|
        if part =~ /^([0-9]+)$/
          bit = ::Regexp.last_match(1)
          @encoding_fields << EncodingField.new("", bit.to_i..bit.to_i)
        elsif part =~ /^([0-9]+)-([0-9]+)$/
          msb = ::Regexp.last_match(1)
          lsb = ::Regexp.last_match(2)
          raise "range must be specified 'msb-lsb'" unless msb.to_i >= lsb.to_i

          @encoding_fields << EncodingField.new("", lsb.to_i..msb.to_i)
        else
          raise "location format error"
        end
      end
    end

    def inst_pos_to_var_pos
      s = size
      map = Array.new(32, nil)
      @encoding_fields.each do |ef|
        ef.range.to_a.reverse.each do |ef_i|
          raise "unexpected" if s <= 0

          map[ef_i] = s - 1
          s -= 1
        end
      end
      map
    end

    # @param encoding [String] Encoding, as a string of 1, 0, and - with MSB at index 0
    # @param value [Integer] Value of the decode variable
    # @return [String] encoding, with the decode variable replaced with value
    def encoding_repl(encoding, value)
      raise ArgumentError, "Expecting string" unless encoding.is_a?(String)
      raise ArgumentError, "Expecting Integer" unless value.is_a?(Integer)

      new_encoding = encoding.dup
      inst_pos_to_var_pos.each_with_index do |pos, idx|
        next if pos.nil?
        raise "Bad encoding" if idx >= encoding.size

        new_encoding[encoding.size - idx - 1] = ((value >> pos) & 1).to_s
      end
      new_encoding
    end

    # given a range of the instruction, return a string representing the bits of the field the range
    # represents
    def inst_range_to_var_range(r)
      var_bits = inst_pos_to_var_pos

      raise "?" if var_bits[r.last].nil?
      parts = [var_bits[r.last]..var_bits[r.last]]
      r.to_a.reverse[1..].each do |i|
        if var_bits[i] == (parts.last.min - 1)
          raise "??" if parts.last.max.nil?
          parts[-1] = var_bits[i]..parts.last.max
        else
          parts << Range.new(var_bits[i], var_bits[i])
        end
      end

      parts.map { |p| p.size == 1 ? p.first.to_s : "#{p.last}:#{p.first}"}.join("|")
    end
    private :inst_range_to_var_range

    # array of constituent encoding fields
    def grouped_encoding_fields
      sorted_encoding_fields = @encoding_fields.sort { |a, b| b.range.last <=> a.range.last }
      # need to group encoding_fields if they are consecutive
      grouped_fields = [sorted_encoding_fields[0].range]
      sorted_encoding_fields[1..].each do |ef|
        if (ef.range.last + 1) == grouped_fields.last.first
          grouped_fields[-1] = (ef.range.first..grouped_fields.last.last)
        else
          grouped_fields << ef.range
        end
      end
      if grouped_fields.size == 1
        if grouped_fields.last.size == size
          [EncodingField.new(pretty_name, grouped_fields[0])]
        else
          [EncodingField.new("#{pretty_name}[#{inst_range_to_var_range(grouped_fields[0])}]", grouped_fields[0])]
        end
      else
        grouped_fields.map do |f|
          EncodingField.new("#{pretty_name}[#{inst_range_to_var_range(f)}]", f)
        end
      end
    end

    def initialize(name, field_data)
      @name = name
      @left_shift = field_data["left_shift"].nil? ? 0 : field_data["left_shift"]
      @sext = field_data["sign_extend"].nil? ? false : field_data["sign_extend"]
      @alias = field_data["alias"].nil? ? nil : field_data["alias"]
      @location = field_data["location"]
      extract_location(field_data["location"])
      @excludes =
        if field_data.key?("not")
          if field_data["not"].is_a?(Array)
            field_data["not"]
          else
            [field_data["not"]]
          end
        else
          []
        end
      @decode_variable =
        if @alias.nil?
          name
        else
          @decode_variable = [name, @alias]
        end
    end

    def eql?(other)
      @name.eql?(other.name)
    end

    def hash
      @name.hash
    end

    # returns true if the field is encoded across more than one groups of bits
    def split?
      @encoding_fields.size > 1
    end

    # returns bits of the encoding that make up the field, as an array
    #   Each item of the array is either:
    #     - A number, to represent a single bit
    #     - A range, to represent a continugous range of bits
    #
    #  The array is ordered from encoding MSB (at index 0) to LSB (at index n-1)
    def bits
      @encoding_fields.map do |ef|
        ef.range.size == 1 ? ef.range.first : ef.range
      end
    end

    # @return [Integer] the number of bits in the field, _including any implicit bits_
    def size
      size_in_encoding + @left_shift
    end

    # the number of bits in the field, _not including any implicit zeros_
    def size_in_encoding
      bits.reduce(0) { |sum, f| sum + (f.is_a?(Integer) ? 1 : f.size) }
    end

    # true if the field should be sign extended
    def sext?
      @sext
    end

    sig { params(other: T.any(Instruction::Opcode, DecodeVariable)).returns(T::Boolean) }
    def overlaps?(other)
      if other.is_a?(Instruction::Opcode)
        location_bits.any? { |i| other.range.cover?(i) }
      else
        location_bits.intersect?(other.location_bits)
      end
    end

    # return code to extract the field
    def extract
      ops = []
      so_far = 0
      bits.each do |b|
        if b.is_a?(Integer)
          op = "$encoding[#{b}]"
          ops << op
          so_far += 1
        elsif b.is_a?(Range)
          op = "$encoding[#{b.end}:#{b.begin}]"
          ops << op
          so_far += T.must(b.size)
        end
      end
      ops << "#{@left_shift}'d0" unless @left_shift.zero?
      ops =
        if ops.size > 1
          "{#{ops.join(', ')}}"
        else
          ops[0]
        end
      ops = "sext(#{ops})" if sext?
      ops
    end
  end

  # represents an instruction encoding
  class Encoding
    # @return [String] format, as a string of 0,1 and -,
    # @example Format of `sd`
    #      sd.format #=> '-----------------011-----0100011'
    attr_reader :format

    # @return [Array<Field>] List of fields containing opcodes
    # @example opcode_fields of `sd`
    #      sd.opcode_fields #=> [Field('011', ...), Field('0100011', ...)]
    attr_reader :opcode_fields

    # @return [Array<DecodeVariable>] List of decode variables
    attr_reader :decode_variables

    # represents an encoding field (contiguous set of bits that form an opcode or decode variable slot)
    class Field
      # @return [String] Either string of 0's and 1's or a bunch of dashes
      # @example Field of a decode variable
      #   encoding.opcode_fields[0] #=> '-----' (for imm5)
      # @example Field of an opcode
      #   encoding.opcode_fields[1] #=> '0010011' (for funct7)
      attr_reader :name

      # @return [Range] Range of bits in the parent corresponding to this field
      attr_reader :range

      # @param name [#to_s] Either string of 0's and 1's or a bunch of dashes
      # @param range [Range] Range of the field in the encoding
      def initialize(name, range)
        @name = name.to_s
        @range = range
      end

      # @return [Boolean] whether or not the field represents part of the opcode (i.e., not a decode variable)
      def opcode?
        name.match?(/^[01]+$/)
      end

      def to_s
        "#{name}[#{range}]"
      end
    end

    def self.overlapping_format?(format1, format2)
      format1.size.times.all? do |i|
        rev_idx = (format1.size - 1) - i
        other_rev_idx = (format2.size - 1) - i
        format1[rev_idx] == "-" \
          || (i >= format2.size) \
          || (format1[rev_idx] == format2[other_rev_idx])
      end
    end

    # @return [Boolean] true if self and other_encoding cannot be distinguished, i.e., they share the same encoding
    def indistinguishable?(other_encoding, check_other: true)
      other_format = other_encoding.format
      same = Encoding.overlapping_format?(format, other_format)

      if same
        # the mask can't be distinguished; is there one or more exclusions that distinguishes them?

        # we have to check all combinations of dvs with exclusions, and their values
        exclusion_dvs = @decode_variables.reject { |dv| dv.excludes.empty? }
        exclusion_dv_values = []
        def expand(exclusion_dvs, exclusion_dv_values, base, idx)
          other_dv = exclusion_dvs[idx]
          other_dv.excludes.each do |other_exclusion_value|
            exclusion_dv_values << base + [[other_dv, other_exclusion_value]]
            if (idx + 1) < exclusion_dvs.size
              expand(exclusion_dvs, exclusion_dv_values, exclusion_dv_values.last, idx + 1)
            end
          end
        end
        exclusion_dvs.each_index do |idx|
          expand(exclusion_dvs, exclusion_dv_values, [], idx)
        end

        exclusion_dv_values.each do |dv_values|
          repl_format = format.dup
          dv_values.each { |dv_and_value| repl_format = dv_and_value[0].encoding_repl(repl_format, dv_and_value[1]) }

          if Encoding.overlapping_format?(repl_format, other_format)
            same = false
            break
          end
        end
      end

      check_other ? same || other_encoding.indistinguishable?(self, check_other: false) : same
    end

    # @param format [String] Format of the encoding, as 0's, 1's and -'s (for decode variables)
    # @param decode_vars [Array<Hash<String,Object>>] List of decode variable definitions from the arch spec
    def initialize(format, decode_vars, opcode_fields = nil)
      @format = format

      @opcode_fields = opcode_fields.nil? ? [] : opcode_fields
      field_chars = []
      @format.chars.each_with_index do |c, idx|
        if c == "-"
          next if field_chars.empty?

          field_text = field_chars.join("")
          field_lsb = @format.size - idx
          field_msb = @format.size - idx - 1 + field_text.size
          @opcode_fields << Field.new(field_text, field_lsb..field_msb) if opcode_fields.nil?

          field_chars.clear
          next
        else
          field_chars << c
        end
      end

      # add the least significant field
      unless field_chars.empty?
        field_text = field_chars.join("")
        @opcode_fields << Field.new(field_text, 0...field_text.size) if opcode_fields.nil?
      end

      if decode_vars&.last.is_a?(DecodeVariable)
        @decode_variables = decode_vars
      else
        @decode_variables = []
        decode_vars&.each do |var|
          @decode_variables << DecodeVariable.new(var["name"], var)
        end
      end
    end

    # @return [Integer] Size, in bits, of the encoding
    def size
      @format.size
    end
  end

  def load_encoding
    @encodings = {}
    if has_type?
      if @data.key?("base")
        @encodings[@data["base"]] = Encoding.new(encoding_format(@data["base"]), subtype(@data["base"]).variables)
      else
        @encodings[32] = Encoding.new(encoding_format(32), subtype(32).variables)
        @encodings[64] = Encoding.new(encoding_format(64), subtype(64).variables)
      end
    else
      if @data["encoding"].key?("RV32")
        # there are different encodings for RV32/RV64
        @encodings[32] = Encoding.new(@data["encoding"]["RV32"]["match"], @data["encoding"]["RV32"]["variables"])
        @encodings[64] = Encoding.new(@data["encoding"]["RV64"]["match"], @data["encoding"]["RV64"]["variables"])
      elsif @data.key("base")
        @encodings[@data["base"]] = Encoding.new(@data["encoding"]["match"], @data["encoding"]["variables"])
      else
        @encodings[32] = Encoding.new(@data["encoding"]["match"], @data["encoding"]["variables"])
        @encodings[64] = Encoding.new(@data["encoding"]["match"], @data["encoding"]["variables"])
      end
    end
  end
  private :load_encoding

  # @return [Boolean] whether or not this instruction has different encodings depending on XLEN
  def multi_encoding?
    if has_type?
      @data["format"].key?("RV32")
    else
      @data.key?("encoding") && @data["encoding"].key?("RV32")
    end
  end

  # @return [Boolean] true if self and other_inst have indistinguishable encodings and can be simultaneously implemented in some design
  def bad_encoding_conflict?(xlen, other_inst)
    return false if !defined_in_base?(xlen) || !other_inst.defined_in_base?(xlen)
    return false unless encoding(xlen).indistinguishable?(other_inst.encoding(xlen))

    # ok, so they have the same encoding. can they be present at the same time?
    return false if !defined_by_condition.compatible?(other_inst.defined_by_condition)

    # is this a hint?
    !(hints.include?(other_inst) || other_inst.hints.include?(self))
  end

  # @return [Array<Instruction>] List of instructions that reuse this instruction's encoding,
  #                              but can't be present in the same system because their defining
  #                              extensions conflict
  def conflicting_instructions(xlen)
    raise "Bad xlen (#{xlen}) for instruction #{name}" unless defined_in_base?(xlen)

    @conflicting_instructions ||= {}
    return @conflicting_instructions[xlen] unless @conflicting_instructions[xlen].nil?

    @conflicting_instructions[xlen] = []

    @arch.instructions.each do |other_inst|
      next unless other_inst.defined_in_base?(xlen)
      next if other_inst == self

      next unless encoding(xlen).indistinguishable?(other_inst.encoding(xlen))

      # is this a hint?
      next if hints.include?(other_inst) || other_inst.hints.include?(self)

      if defined_by_condition.compatible?(other_inst.defined_by_condition)
        raise "bad encoding conflict found between #{name} and #{other_inst.name}"
      end

      @conflicting_instructions[xlen] << other_inst
    end
    @conflicting_instructions[xlen]
  end

  # @return [FunctionBodyAst] A type-checked abstract syntax tree of the operation
  # @param effective_xlen [Integer] 32 or 64, the effective xlen to type check against
  def type_checked_operation_ast(effective_xlen)
    defer :type_checked_operation_ast do
      return nil unless @data.key?("operation()")

      ast = operation_ast

      symtab = fill_symtab(effective_xlen, ast)
      ast.freeze_tree(symtab)
      cfg_arch.idl_compiler.type_check(ast, symtab, "#{name}.operation()")
      symtab.release

      ast
    end
  end

  # @return [FunctionBodyAst] The abstract syntax tree of the instruction operation
  def operation_ast
    defer :operation_ast do
      return nil if @data["operation()"].nil?

      # now, parse the operation
      ast = cfg_arch.idl_compiler.compile_inst_operation(
        self,
        symtab: cfg_arch.symtab,
        input_file: @data["$source"],
        input_line: source_line(["operation()"])
      )

      raise "unexpected #{ast.class}" unless ast.is_a?(Idl::FunctionBodyAst)

      ast
    end
  end

  # @param base [Integer] 32 or 64
  # @return [Encoding] the encoding
  sig { params(base: Integer).returns(Encoding) }
  def encoding(base)
    raise "#{name} is not defined in #{base}" unless defined_in_base?(base)

    load_encoding if @encodings.nil?

    @encodings[base]
  end

  # @return [Integer] the width of the encoding
  sig { returns(Integer) }
  def encoding_width
    if defined_in_base?(32) && defined_in_base?(64)
      raise "unexpected: encodings are different sizes" unless encoding(32).size == encoding(64).size

      encoding(64).size
    elsif defined_in_base?(32)
      encoding(32).size
    else
      raise "unexpected" unless defined_in_base?(64)

      encoding(64).size
    end

  end

  # @return [Integer] the largest encoding width of the instruction, in any XLEN for which this instruction is valid
  sig { returns(Integer) }
  def max_encoding_width
    [(rv32? ? encoding(32).size : 0), (rv64? ? encoding(64).size : 0)].max
  end

  # @return [Array<DecodeVariable>] The decode variables
  def decode_variables(base)
    encoding(base).decode_variables
  end

  # @return [Boolean] true if the instruction has an 'access_detail' field
  def access_detail?
    @data.key?("access_detail")
  end

  # Generates a wavedrom description of the instruction encoding
  #
  # @param base [Integer] The XLEN (32 or 64), needed if the instruction is {#multi_encoding?}
  # @return [String] The wavedrom JSON description
  def wavedrom_desc(base)
    desc = {
      "reg" => []
    }
    display_fields = encoding(base).opcode_fields
    display_fields += encoding(base).decode_variables.map(&:grouped_encoding_fields).flatten

    display_fields.sort { |a, b| b.range.last <=> a.range.last }.reverse.each do |e|
      desc["reg"] << { "bits" => e.range.size, "name" => e.name, "type" => (e.opcode? ? 2 : 4) }
    end

    desc
  end

  # @return [Boolean] whether or not this instruction is defined for RV32
  def rv32?
    !@data.key?("base") || base == 32
  end

  # @return [Boolean] whether or not this instruction is defined for RV64
  def rv64?
    !@data.key?("base") || base == 64
  end

  # @return [Array<Instruction>] List of HINTs based on this instruction encoding
  def hints
    @hints ||= @data.key?("hints") ? @data["hints"].map { |ref| @cfg_arch.ref(ref["$ref"]) } : []
  end

  # @param cfg_arch [ConfiguredArchitecture] The architecture definition
  # @return [Boolean] whether or not the instruction is implemented given the supplied config options
  def exists_in_cfg?(cfg_arch)
    if cfg_arch.fully_configured?
      (@data["base"].nil? || (cfg_arch.possible_xlens.include? @data["base"])) &&
        cfg_arch.implemented_extension_versions.any? { |ext_ver| defined_by_condition.possibly_satisfied_by?(ext_ver) }
    else
      raise "unexpected cfg_arch type" unless cfg_arch.partially_configured?

      (@data["base"].nil? || (cfg_arch.possible_xlens.include? @data["base"])) &&
        cfg_arch.prohibited_extension_versions.none? { |ext_ver| defined_by_condition.possibly_satisfied_by?(ext_ver) }
    end
  end
end

end

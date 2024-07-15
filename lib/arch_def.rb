# frozen_string_literal: true

require "forwardable"
# require "treetop"
require_relative "opcodes"
require_relative "validate"
require_relative "idl"
require_relative "idl/passes/find_return_values"
require_relative "idl/passes/gen_adoc"
# require_relative "ast/ast"
# require_relative "ast/gen_adoc"

# Treetop.load("arch/isa/isa")

# base for any object representation of the Architecture Definition
# does two things:
#
#  1. Makes the raw data for the object accessible via []
#     For example, given:
#        data = {
#          'name' => 'mstatus',
#          'address' => 0x320,
#          ...
#        }
#
#     obj = ArchDefObject.new(data)
#     obj['name']    # 'mstatus'
#     obj['address'] # 0x320
#
#  2. Provides accessor methods for the data properties
#     Given the same example above, the following works:
#
#     obj.name       # 'mstatus'
#     obj.address    # 0x320
#
# Subclasses may override the accessors when a more complex data structure
# is warranted, e.g., the CSR Field 'alias' returns a CsrFieldAlias object
# instead of a simple string
class ArchDefObject
  # @param data [Hash<String,Object>] Hash with fields to be added
  def initialize(data)
    raise "Bad data" unless data.is_a?(Hash)

    @data = data
  end

  def inspect
    self.class.name
  end

  # make the underlying YAML description available with []
  extend Forwardable
  def_delegator :@data, :[]

  # @return [Array<String>] List of keys added by this ArchDefObject
  def keys = @data.keys

  # adds accessor functions for any properties in the data
  def method_missing(method_name, *args, &block)
    if @data.key?(method_name.to_s)
      raise "Unexpected argument to '#{method_name}" unless args.empty?

      raise "Unexpected block given to '#{method_name}" if block_given?

      @data[method_name.to_s]
    else
      super
    end
  end

  def respond_to_missing?(method_name, include_private = false)
    @data.key?(method_name.to_s) || super
  end
end

# A CSR field object
class CsrField < ArchDefObject
  # @return [Csr] The Csr that defines this field
  attr_reader :parent

  # @!attribute field
  #  @return [CsrField] The field being aliased
  # @!attribute range
  #  @return [Range] Range of the aliased field that is being pointed to
  Alias = Struct.new(:field, :range)

  # @param parent_csr [Csr] The Csr that defined this field
  # @param field_data [Hash<String,Object>] Field data from the arch spec
  def initialize(parent_csr, field_data)
    super(field_data)
    @parent = parent_csr
  end

  # @return [ArchDef] The owning ArchDef
  def arch_def
    @parent.arch_def
  end

  # @return [String]
  #    The type of the field. One of:
  #      'RO'    => Read-only
  #      'RO-H'  => Read-only, with hardware update
  #      'RW'    => Read-write
  #      'RW-R'  => Read-write, with a restricted set of legal values
  #      'RW-H'  => Read-write, with a hardware update
  #      'RW-RH' => Read-write, with a hardware update and a restricted set of legal values
  def type
    return @type unless @type.nil?

    @type =
      if @data.key?("type")
        @data["type"]
      else
        # the type is config-specific...
        idl = @data["type()"]
        raise "type() is nil for #{csr.name}.#{name} #{@data}?" if idl.nil?

        expected_return_type =
          Idl::Type.new(:enum_ref, enum_class: csr.sym_table.get("CsrFieldType"))
        sym_table = csr.sym_table

        ast = arch_def.idl_compiler.compile_func_body(
          idl,
          symtab: sym_table,
          return_type: expected_return_type,
          name: "type",
          parent: "#{csr.name}.#{name}"
        )

        sym_table.push # for consistency with template functions

        begin
          case ast.return_value(sym_table)
          when 0
            "RO"
          when 1
            "RO-H"
          when 2
            "RW"
          when 3
            "RW-R"
          when 4
            "RW-H"
          when 5
            "RW-RH"
          else
            raise "Unhandled CsrFieldType value"
          end
        rescue Idl::AstNode::ValueError => e
          warn "In parsing #{csr.name}.#{name}::type()"
          warn "  Return of type() function cannot be evaluated at compile time"
          raise e
        ensure
          sym_table.pop
        end
      end
  end

  # @return [Alias,nil] The aliased field, or nil if there is no alias
  def alias
    return @alias unless @alias.nil?

    if @data.key?("alias")
      raise "Can't parse alias" unless data["alias"] =~ /^[a-z][a-z0-9]+\.[A-Z0-9]+(\[([0-9]+)(:[0-9]+)?\])?$/

      csr_name = Regexp.last_match(1)
      csr_field = Regexp.last_match(2)
      range = Regexp.last_match(3)
      range_start = Regexp.last_match(4)
      range_end = Regexp.last_match(5)

      csr_field = arch_def.csr(csr_name).field(csr_field)
      range =
        if range.nil?
          field.location
        elsif range_end.nil?
          (range_start.to_i..range_start.to_i)
        else
          (range_start.to_i..range_end[1..].to_i)
        end
      @alias = Alias.new(csr_field, range)
    end
    @alias
  end

  # @return [Boolean] True if the field has a custom write function (i.e., `write(csr_value)` exists in the spec)
  def has_custom_write?
    @data.key?("write(csr_value)") && !@data["write(csr_value)"].empty?
  end

  # @return [Csr] Parent CSR for this field
  alias csr parent

  # @return [Boolean] Whether or not the location of the field changes dynamically
  #                   (e.g., based on mstatus.SXL)
  def dynamic_location?
    return false if @data.key?("location")

    csr.dynamic_length?
  end

  # @return [Idl::AstNode] Abstract syntax tree of the reset_value function
  # @raise StandardError if there is no reset_value function (i.e., the reset value is static)
  def reset_value_func
    raise "Not an IDL value" unless @data.key?("reset_value()")

    return @reset_value_func unless @reset_value_func.nil?

    @reset_value_func = arch_def.idl_compiler.compile_func_body(
      @data["reset_value()"],
      return_type: Idl::Type.new(:bits, width: 64),
      symtab: csr.sym_table,
      name: "reset_value",
      parent: "CSR[#{parent.name}].#{name}",
      input_file: "CSR[#{parent.name}].#{name}",
      no_rescue: true
    )
  end

  # @return [Integer] The reset value of this field
  # @return [String]  The string 'UNDEFINED_LEGAL' if, for this config, there is no defined reset value
  def reset_value
    return @reset_value unless @reset_value.nil?

    symtab = arch_def.sym_table

    symtab.push # for consistency with template functions

    begin
      @reset_value =
        if @data.key?("reset_value")
          @data["reset_value"]
        else
          reset_value_func.return_value(arch_def.sym_table)
        end
    ensure
      symtab.pop
    end
  end

  # @param effective_xlen [Integer] The effective xlen, needed since some fields change location with XLEN. If the field location is not determined by XLEN, then this parameter can be nil
  # @return [Range] the location within the CSR as a range (single bit fields will be a range of size 1)
  def location(effective_xlen = nil)
    key =
      if @data.key?("location")
        "location"
      else
        raise ArgumentError, "Expecting 32 or 64" unless [32, 64].include?(effective_xlen)

        "location_rv#{effective_xlen}"
      end

    raise "Missing location for #{csr.name}.#{name} (#{key})?" unless @data.key?(key)

    if @data[key].is_a?(Integer)
      if @data[key] > csr.length(effective_xlen || @data["base"])
        raise "Location (#{@data[key]}) is past the csr length (#{csr.length(effective_xlen)}) in #{csr.name}.#{name}"
      end

      @data[key]..@data[key]
    elsif @data[key].is_a?(String)
      e, s = @data[key].split("-").map(&:to_i)
      raise "Invalid location" if s > e

      if e > csr.length(effective_xlen)
        raise "Location (#{@data[key]}) is past the csr length (#{csr.length(effective_xlen)}) in #{csr.name}.#{name}"
      end

      s..e
    end
  end

  # @return [Boolean] Whether or not this field only exists when XLEN == 64
  def base64_only? = @data.key?("base") && @data["base"] == 64

  # @return [Boolean] Whether or not this field only exists when XLEN == 32
  def base32_only? = @data.key?("base") && @data["base"] == 32

  # @return [Boolean] Whether or not this field exists for any XLEN
  def defined_in_all_bases? = @data["base"].nil?

  # @param effective_xlen [Integer] The effective xlen, needed since some fields change location with XLEN. If the field location is not determined by XLEN, then this parameter can be nil
  # @return [Integer] Number of bits in the field
  def width(effective_xlen)
    location(effective_xlen).size
  end

  # @return [String] Pretty-printed location string
  def location_pretty
    derangeify = proc { |loc|
      return loc.min.to_s if loc.size == 1

      "#{loc.max}:#{loc.min}"
    }
    if dynamic_location?
      condition =
        case csr.priv_mode
        when "S"
          "CSR[mstatus].SXL == %%"
        when "VS"
          "CSR[hstatus].VSXL == %%"
        else
          raise "Unexpected priv mode"
        end

      <<~LOC
        #{derangeify.call(location(32))} when #{condition.sub('%%', '0')}
        #{derangeify.call(location(64))} when #{condition.sub('%%', '1')}
      LOC
    else
      derangeify.call(location(csr.arch_def.config_params["XLEN"]))
    end
  end

  TYPE_DESC_MAP = {
    "RO" =>
      %(*Read-Only* Field has a hardwired value that does not change.
        Writes to an RO field are ignored.),
    "RO-H" =>
      %(*Read-Only with Hardware update*
        Writes are ignored.
        Reads reflect a value dynamically generated by hardware.),
    "RW" =>
      %(*Read-Write*
        Field is writable by software.
        Any value that fits in the field is acceptable and shall be retained for subsequent reads.),
    "RW-R" =>
      %(*Read-Write Restricted*
        Field is writable by software.
        Only certain values are legal.
        Writing an illegal value into the field is ignored, and the field retains its prior state.),
    "RW-H" =>
      %(*Read-Write with Hardware update*
        Field is writable by software.
        Any value that fits in the field is acceptable.
        Hardware also updates the field without an explicit software write.),
    "RW-RH" =>
      %(*Read-Write Restricted with Hardware update*
        Field is writeable by software.
        Only certain values are legal.
        Writing an illegal value into the field is ignored, such that the field retains its prior state.
        Hardware also updates the field without an explicit software write.)
  }.freeze

  # @return [String] Long description of the field type
  def type_desc
    TYPE_DESC_MAP[type]
  end
end

# CSR definition
class Csr < ArchDefObject
  # @return [ArchDef] The owning ArchDef
  attr_reader :arch_def
  
  # @return [Idl::SymbolTable] The symbol table holding global names
  attr_reader :sym_table

  # @param csr_data [Hash<String,Object>] Hash of data from the specification
  # @param sym_table [Idl::SymbolTable] The symbol table holding global names
  # @param arch_def [ArchDef] The architecture definition
  def initialize(csr_data, sym_table, arch_def)
    super(csr_data)

    @arch_def = arch_def
    @sym_table = sym_table
  end

  # @return [Boolean] Whether or not the length of the CSR depends on a runtime value
  #                   (e.g., mstatus.SXL)
  def dynamic_length?
    return false if @data["length"].is_a?(Integer)

    case @data["length"]
    when "MXLEN"
      false # mxlen can never change
    when "SXLEN"
      arch_def.config_params["SXLEN"] == 3264
    when "VSXLEN"
      arch_def.config_params["VSXLEN"] == 3264
    else
      raise "Unexpected length"
    end
    !@data["length"].is_a?(Integer) && (@data["length"] != "MXLEN")
  end

  # @param effective_xlen [Integer] The effective xlen, needed since some fields change location with XLEN. If the field location is not determined by XLEN, then this parameter can be nil
  # @return [Integer] Length, in bits, of the CSR
  def length(effective_xlen = nil)
    case @data["length"]
    when "MXLEN"
      arch_def.config_params["XLEN"]
    when "SXLEN"
      if arch_def.config_params["SXLEN"] == 3264
        raise ArgumentError, "effective_xlen is required when length is dynamic (#{name})" if effective_xlen.nil?

        effective_xlen
      else
        raise "CSR #{name} is not implemented" if arch_def.implemented_csrs.none? { |c| c.name == name }
        raise "CSR #{name} is not implemented" if arch_def.config_params["SXLEN"].nil?

        arch_def.config_params["SXLEN"]
      end
    when "VSXLEN"
      if arch_def.config_params["VSXLEN"] == 3264
        raise ArgumentError, "effective_xlen is required when length is dynamic (#{name})" if effective_xlen.nil?

        effective_xlen
      else
        raise "CSR #{name} is not implemented" if arch_def.config_params["VSXLEN"].nil?

        arch_def.config_params["VSXLEN"]
      end
    when Integer
      @data["length"]
    else
      raise "Unexpected length field for #{csr.name}"
    end
  end

  # @return [String] IDL condition of when the effective xlen is 32
  def length_cond32
    case @data["length"]
    when "SXLEN"
      "CSR[mstatus].SXL == 0"
    when "VSXLEN"
      "CSR[hstatus].VSXL == 0"
    else
      raise "Unexpected length #{@data['length']} for #{name}"
    end
  end

  # @return [String] IDL condition of when the effective xlen is 64
  def length_cond64
    case @data["length"]
    when "SXLEN"
      "CSR[mstatus].SXL == 1"
    when "VSXLEN"
      "CSR[hstatus].VSXL == 1"
    else
      raise "Unexpected length"
    end
  end

  # @return [String] Pretty-printed length string
  def length_pretty
    if dynamic_length?
      cond = 
        case @data["length"]
        when "SXLEN"
          "CSR[mstatus].SXL == %%"
        when "VSXLEN"
          "CSR[hstatus].VSXL == %%"
        else
          raise "Unexpected length"
        end

      <<~LENGTH
        #{length(32)} when #{cond.sub('%%', '0')}
        #{length(64)} when #{cond.sub('%%', '1')}
      LENGTH
    else
      "#{length}-bit"
    end
  end

  # parse description field with asciidoctor, and return the HTML result
  #
  # @return [String] Parsed description in HTML
  def description_html
    Asciidoctor.convert description
  end

  # @return [Array<CsrField>] All fields for this CSR, regardless of whether or not they are implemented
  def fields
    return @fields unless @fields.nil?

    @fields = []
    @data["fields"].each_value do |field_data|
      @fields << CsrField.new(self, field_data)
    end
    @fields
  end

  # @return [Array<CsrField>] All implemented fields for this CSR at the given effective XLEN, sorted by location (smallest location first)
  #                           Excluded any fields that are defined by unimplemented extensions or a base that is not effective_xlen
  def implemented_fields_for(effective_xlen)
    @implemented_fields_for ||= {}
    return @implemented_fields_for[effective_xlen] unless @implemented_fields_for[effective_xlen].nil?

    @implemented_fields_for[effective_xlen] = []
    @data["fields"].each_value do |field_data|
      next if field_data.key?("base") && (field_data["base"] != effective_xlen)

      defined_by = []
      defined_by << field_data["definedBy"] if field_data.key?("definedBy") && field_data["definedBy"].is_a?(String)
      defined_by += field_data["definedBy"] if field_data.key?("definedBy") && field_data["definedBy"].is_a?(Array)
      if !field_data.key?("definedBy") || (defined_by.any? { |ext_name| arch_def.ext?(ext_name) })
        @implemented_fields_for[effective_xlen] << CsrField.new(self, field_data)
      end
    end
    @implemented_fields_for[effective_xlen].sort! do |a, b|
      a.location(effective_xlen).max <=> b.location(effective_xlen).max
    end

    @implemented_fields_for[effective_xlen]
  end

  # @return [Array<CsrField>] All implemented fields for this CSR
  #                           Excluded any fields that are defined by unimplemented extensions
  def implemented_fields
    return @implemented_fields unless @implemented_fields.nil?

    implemented_bases =
      if arch_def.config_params["SXLEN"] == 3264 ||
         arch_def.config_params["UXLEN"] == 3264 ||
         arch_def.config_params["VSXLEN"] == 3264 ||
         arch_def.config_params["VUXLEN"] == 3264
        [32,64]
      else
        [arch_def.config_params["XLEN"]]
      end

    @implemented_fields = []
    @data["fields"].each_value do |field_data|
      next if field_data.key?("base") && implemented_bases.none?(field_data["base"])

      defined_by = []
      defined_by << field_data["definedBy"] if field_data.key?("definedBy") && field_data["definedBy"].is_a?(String)
      defined_by += field_data["definedBy"] if field_data.key?("definedBy") && field_data["definedBy"].is_a?(Array)
      if !field_data.key?("definedBy") || (defined_by.any? { |ext_name| arch_def.ext?(ext_name) })
        @implemented_fields << CsrField.new(self, field_data)
      end
    end

    @implemented_fields
  end

  # @return [Hash<String,CsrField>] Hash of fields, indexed by field name
  def field_hash
    @field_hash unless @field_hash.nil?

    @field_hash = {}
    fields.each do |field|
      @field_hash[field.name] = field
    end

    @field_hash
  end

  # @return [Boolean] true if a field named 'field_name' is defined in the csr, and false otherwise
  def field?(field_name)
    field_hash.key?(field_name.to_s)
  end

  # returns [CsrField,nil] field named 'field_name' if it exists, and nil otherwise
  def field(field_name)
    field_hash[field_name.to_s]
  end

  # @return [Boolean] true if the CSR has a custom sw_read function
  def has_custom_sw_read?
    @data.key?("sw_read") && !sw_read.empty?
  end

  # def sw_read_source
  #   return "" unless has_custom_sw_read?

  #   sw_read_ast.gen_adoc.gsub("((", '\((')
  # end

  # @example Result for an I-type instruction
  #   {reg: [
  #     {bits: 7,  name: 'OP-IMM',    attr: ['{op_major_name}'], type: 8},
  #     {bits: 5,  name: 'rd',        attr: [''], type: 2},
  #     {bits: 3,  name: {funct3},    attr: ['{mnemonic}'], type: 8},
  #     {bits: 5,  name: 'rs1',       attr: [''], type: 4},
  #     {bits: 12, name: 'imm12',     attr: [''], type: 6}
  #   ]}
  #
  # @param effective_xlen [Integer,nil] Effective XLEN to use when CSR length is dynamic
  # @return [String] A JSON representation of the WaveDrom drawing for the CSR
  def wavedrom_desc(effective_xlen)
    desc = {
      "reg" => []
    }
    last_idx = -1
    implemented_fields_for(effective_xlen).each do |field|

      if field.location(effective_xlen).min != last_idx + 1
        # have some reserved space
        desc["reg"] << { "bits" => (field.location(effective_xlen).min - last_idx - 1), type: 1 }
      end
      desc["reg"] << { "bits" => field.location(effective_xlen).size, "name" => field.name, type: 2 }
      last_idx = field.location(effective_xlen).max
    end
    if !implemented_fields_for(effective_xlen).empty? && (fields.last.location(effective_xlen).max != (length(effective_xlen) - 1))
      # reserved space at the end
      desc["reg"] << { "bits" => (length(effective_xlen) - 1 - last_idx), type: 1 }
      # desc['reg'] << { 'bits' => 1, type: 1 }
    end
    desc["config"] = { "bits" => length(effective_xlen) }
    desc["config"]["lanes"] = length(effective_xlen) / 16
    desc
  end
end

# really ugly way to generate fields out of riscv-opcodes
# hopefully this goes away soon
module RiscvOpcodes
  VARIABLE_FIELDS = {
    "rd" => {
      bits: (7..11)
    },
    "rd_p" => {
      bits: (2..4),
      lshift: 2,
      display: "rd'",
      decode_variable: "rd"
    },
    "rd_n0" => {
      bits: (7..11),
      display: "rd != 0",
      decode_variable: "rd"
    },
    "rd_n2" => {
      bits: (7..11),
      display: "rd != {0,2}",
      decode_variable: "rd"
    },
    "rs1" => {
      bits: (15..19)
    },
    "rs1_p" => {
      bits: (7..9),
      lshift: 2,
      display: "rs1'",
      decode_variable: "rs1"
    },
    "c_rs1_n0" => {
      bits: (7..11),
      display: "rs1 != 0",
      decode_variable: "rs1"
    },

    "rs2" => {
      bits: (20..24)
    },
    "c_rs2" => {
      bits: (2..6),
      display: "rs2"
    },
    "rs2_p" => {
      bits: (2..4),
      lshift: 2,
      display: "rs2'",
      decode_variable: "rs2"
    },
    "c_rs2_n0" => {
      bits: (2..6),
      display: "rs2 != 0",
      decode_variable: "rs2"
    },
    "rd_rs1" => {
      bits: (7..11),
      display: "rs1/rd != 0",
      decode_variable: ["rd", "rs1"]
    },
    "rd_rs1_p" => {
      bits: (7..9),
      lshift: 2,
      display: "rd'/rs1'",
      decode_variable: ["rd", "rs1"]
    },
    "rd_rs1_n0" => {
      bits: (7..11),
      display: "rd/rs1 != 0",
      decode_variable: ["rd", "rs1"]
    },
    "rs1_n0" => {
      bits: (7..11),
      display: "rs1 != 0",
      decode_variable: "rs1"
    },
    "shamtd" => {
      bits: 20..25,
      display: "shamt",
      decode_variable: "shamt"
    },
    "shamtw" => {
      bits: 20..24,
      display: "shamt",
      decode_variable: "shamt"
    },
    "csr" => {
      bits: 20..31
    },
    "zimm" => {
      bits: 15..19
    },
    "imm12" => {
      bits: (20..31),
      sext: true,
      display: "imm[11:0]",
      decode_variable: "imm"
    },
    "imm20" => {
      bits: (12..31),
      lshift: 12,
      sext: true,
      display: "imm[31:20]",
      decode_variable: "imm"
    },
    "jimm20" => {
      bits: [31, (12..19), 20, (21..30)],
      group_by: 12..31,
      lshift: 1,
      sext: true,
      display: "imm[20|10:1|11|19:12]",
      decode_variable: "imm"
    },
    ["bimm12hi", "bimm12lo"] => {
      bits: [31, 7, (25..30), (8..11)],
      group_by: [(25..31), (7..11)],
      sext: true,
      lshift: 1,
      display: ["imm[12|10:5]", "imm[4:1|11]"],
      decode_variable: "imm"
    },
    ["imm12hi", "imm12lo"] => {
      bits: [(25..31), (7..11)],
      group_by: [(25..31), (7..11)],
      sext: true,
      display: ["imm[11:5]", "imm[4:0]"],
      decode_variable: "imm"
    },
    "pred" => {
      bits: (24..27)
    },
    "succ" => {
      bits: (20..23)
    },
    "fm" => {
      bits: (28..31)
    },

    "c_nzuimm10" => {
      bits: [(7..10), (11..12), 5, 6],
      group_by: 5..12,
      lshift: 2,
      display: "nzuimm[5:4|9:6|2|3]",
      decode_variable: "imm"
    },
    ["c_uimm8lo", "c_uimm8hi"] => {
      bits: [(5..6), (10..12)],
      group_by: [(5..6), (10..12)],
      lshift: 3,
      display: ["uimm[7:6]", "uimm[5:3]"],
      decode_variable: "imm"
    },
    ["c_uimm7lo", "c_uimm7hi"] => {
      bits: [5, (10..12), 6],
      group_by: [(10..12), (5..6)],
      lshift: 2,
      display: ["uimm[5:3]", "uimm[2|6]"],
      decode_variable: "imm"
    },
    ["c_nzimm6hi", "c_nzimm6lo"] => {
      bits: [12, (2..6)],
      group_by: [12, (2..6)],
      sext: true,
      display: ["nzimm[5]", "nzimm[4:0]"],
      decode_variable: "imm"
    },
    ["c_nzuimm6hi", "c_nzuimm6lo"] => {
      bits: [12, (2..6)],
      group_by: [12, (2..6)],
      display: ["nzuimm[5]", "nzuimm[4:0]"],
      decode_variable: "imm"
    },
    ["c_imm6hi", "c_imm6lo"] => {
      bits: [12, (2..6)],
      group_by: [12, (2..6)],
      sext: true,
      display: ["nzimm[5]", "nzimm[4:0]"],
      decode_variable: "imm"
    },
    ["c_nzimm10hi", "c_nzimm10lo"] => {
      bits: [12, (3..4), 5, 2, 6],
      group_by: [12, (2..6)],
      lshift: 4,
      sext: true,
      display: ["nzimm[9]", "nzimm[4|6|8:7|5]"],
      decode_variable: "imm"
    },
    ["c_nzimm18hi", "c_nzimm18lo"] => {
      bits: [12, (2..6)],
      group_by: [12, (2..6)],
      lshift: 12,
      sext: true,
      display: ["nzimm[17]", "nzimm[16:12]"],
      decode_variable: "imm"
    },
    "c_imm12" => {
      bits: [12, 8, (9..10), 6, 7, 2, 11, (3..5)],
      group_by: 2..12,
      lshift: 1,
      sext: true,
      display: "imm[11|4|9:8|10|6|7|3:1|5]",
      decode_variable: "imm"
    },
    ["c_bimm9hi", "c_bimm9lo"] => {
      bits: [12, (5..6), 2, (10..11), (3..4)],
      group_by: [(10..12), (2..6)],
      lshift: 1,
      sext: true,
      display: ["imm[8|4:3]", "imm[7:6|2:1|5]"],
      decode_variable: "imm"
    },
    ["c_uimm8sphi", "c_uimm8splo"] => {
      bits: [(2..3), 12, (4..6)],
      group_by: [12, (2..6)],
      lshift: 2,
      display: ["uimm5", "uimm[4:2|7:6]"],
      decode_variable: "imm"
    },
    "cuimm8sp_s" => {
      bits: [(7..8), (9..12)],
      group_by: (7..12),
      lshift: 2,
      display: "uimm[5:2|7:6]",
      decode_variable: "imm"
    },
    ["c_uimm9sphi", "c_uimm9splo"] => {
      bits: [(2..3), 12, (4..6)],
      group_by: [12, (2..6)],
      lshift: 3,
      display: ["uimm[5]", "uimm[4:3|8:6]"],
      decode_variable: "imm"
    },
    "c_uimm8sp_s" => {
      bits: [(7..8), (9..12)],
      group_by: 7..12,
      lshift: 2,
      display: "uimm[5:2|7:6]",
      decode_variable: "imm"
    },
    "c_uimm9sp_s" => {
      bits: [(7..9), (10..12)],
      group_by: 7..12,
      lshift: 3,
      display: "uimm[5:3|8:6]",
      decode_variable: "imm"
    },
    "rm" => {
      bits: (12..14)
    }

  }.freeze
end

# model of a specific instruction in a specific base (RV32/RV64)
class Instruction < ArchDefObject

  # @return [Idl::AstNode] Abstract syntax tree of the instruction operation()
  def operation_ast
    parse_operation(@sym_table) if @operation_ast.nil?

    @operation_ast
  end

  # @return [ArchDef] The architecture definition
  attr_reader :arch_def

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
      # @return [String] Either string of 0's ans 1's or a bunch of dashses
      # @example Field of a decode variable
      #   encoding.opcode_fields[0] #=> '-----' (for imm5)
      # @example Field of an opcode
      #   encoding.opcode_fields[1] #=> '0010011' (for funct7)
      attr_reader :name

      # @return [Range] Range of bits in the parent corresponding to this field
      attr_reader :range

      # @param name [#to_s] Either string of 0's ans 1's or a bunch of dashses
      # @param range [Range] Range of the field in the parent CSR
      def initialize(name, range)
        @name = name.to_s
        @range = range
      end

      # @return [Boolean] whether or not the field represents part of the opcode (i.e., not a decode variable)
      def opcode?
        name.match?(/^[01]+$/)
      end
    end

    # @param format [String] Format of the encoding, as 0's, 1's and -'s (for decode variables)
    # @param decode_vars [Array<Hash<String,Object>>] List of decode variable defintions from the arch spec
    def initialize(format, decode_vars)
      @format = format

      @opcode_fields = []
      msb = @format.size
      @format.split("-").each do |e|
        if e.empty?
          msb -= 1
        else
          @opcode_fields << Field.new(e, (msb - e.size + 1)..msb)
          msb -= e.size
        end
      end

      @decode_variables = []
      decode_vars.each do |var|
        @decode_variables << DecodeVariable.new(self, var)
      end
    end

    # @return [Integer] Size, in bits, of the encoding
    def size
      @format.size
    end
  end

  def load_encoding
    @encodings = {}
    if @data["encoding"].key?("RV32")
      # there are different encodings for RV32/RV64
      @encodings[32] = Encoding.new(@data["encoding"]["RV32"]["mask"], @data["encoding"]["RV32"]["fields"])
      @encodings[64] = Encoding.new(@data["encoding"]["RV64"]["mask"], @data["encoding"]["RV64"]["fields"])
    elsif @data.key("base")
      @encodings[@data["base"]] = Encoding.new(@data["encoding"]["mask"], @data["encoding"]["fields"])
    else
      @encodings[32] = Encoding.new(@data["encoding"]["mask"], @data["encoding"]["fields"])
      @encodings[64] = Encoding.new(@data["encoding"]["mask"], @data["encoding"]["fields"])
    end
  end
  private :load_encoding

  # @params inst_data [Hash<String, Object>] Instruction data from the architecture spec
  # @params full_opcode_data [Hash] Opcode data to interpret riscv-opcodes -- this will be deprecated
  # @params sym_table [Idl::SymbolTable] Symbol table with global names
  # @params arch_def [ArchDef] The architecture definition
  def initialize(inst_data, full_opcode_data, sym_table, arch_def)
    @arch_def = arch_def
    @sym_table = sym_table.deep_clone

    super(inst_data)

    if inst_data.key?("encoding")
      load_encoding
    else
      opcode_data_key = name.downcase.gsub(".", "_")
      raise "opcode data not found for #{name}" unless full_opcode_data.key?(opcode_data_key)

      opcode_data = full_opcode_data[opcode_data_key]
      encoding_mask = opcode_data["encoding"]

      opcode_fields = []
      msb = encoding_mask.size
      encoding_mask.split("-").each do |e|
        if e.empty?
          msb -= 1
        else
          opcode_fields << Encoding::Field.new(e, (msb - e.size + 1)..msb)
          msb -= e.size
        end
      end


      decode_variables = []
      opcode_data["variable_fields"].to_a.each do |f|
        decode_field_data = RiscvOpcodes::VARIABLE_FIELDS.to_a.select do |d|
          d[0] == f || (d[0].is_a?(Array) && d[0].any?(f))
        end
        raise "didn't find '#{f}' in DECODER_RING" if decode_field_data.empty?

        raise "Found multiple matches for '#{f}' in DECODER_RING" if decode_field_data.size > 1

        data = decode_field_data[0][1]
        names = []
        if data.key?(:decode_variable)
          if data[:decode_variable].is_a?(String)
            names << data[:decode_variable]
          else
            raise "unexpected" unless data[:decode_variable].is_a?(Array)

            names = data[:decode_variable]
          end
        else
          raise "?" unless decode_field_data[0][0].is_a?(String)

          names = [decode_field_data[0][0]]
        end

        names.each do |name|
          decode_variables << DecodeField.new(self, name, decode_field_data[0][0], decode_field_data[0][1])
        end
      end
      decode_variables.uniq!

      @encodings ||= {}
      klass = Struct.new(:opcode_fields, :decode_variables)
      @encodings[32] = klass.new(opcode_fields, decode_variables)
      @encodings[64] = klass.new(opcode_fields, decode_variables)
    end
  end

  # @return [Boolean] whether or not this instruction has different encodings depending on XLEN
  def multi_encoding?
    @data.key?("encoding") && @data["encoding"].key?("RV32")
  end

  # @return [String] The operation() IDL code
  def operation_source
    return "" if @data["operation()"].nil?

    operation_ast.gen_adoc.gsub("{{", '\((')
    # @data['operation']
  end

  def parse_operation(sym_table)
    # now, parse the operation
    return if @data["operation()"].nil? || !@operation_ast.nil?

    cloned_symtab = sym_table.deep_clone

    cloned_symtab.push
    @encodings[@arch_def.config_params["XLEN"]].decode_variables.each do |d|
      qualifiers = []
      qualifiers << :signed if d.sext?
      width = d.size

      var = Idl::Var.new(d.name, Idl::Type.new(:bits, qualifiers:, width:), decode_var: true)
      cloned_symtab.add(d.name, var)
    end

    m = arch_def.idl_compiler.compile_inst_operation(
      @data["operation()"],
      symtab: cloned_symtab,
      name:,
      parent: nil,
      input_file: "Instruction #{name}"
    )

    cloned_symtab.pop

    raise "unexpected #{m.class}" unless m.is_a?(Idl::InstructionOperationAst)

    m.make_left # fix up right recursion

    @operation_ast = m
  end
  private :parse_operation

  # @return [String] the encoding as, e.g.,:
  #   0000101----------001-----0110011
  def encoding(base)
    @encodings[base].format
  end

  # @return [Array<DecodeVariable>] The decode variables
  def decode_variables(base)
    @encodings[base].decode_variables
  end

  # def encoding_variable_fields
  #   @decode_variables.map(&:decode_variable).flatten
  # end

  # @return [String] the extension that defines this instruction
  # @return [Array<String>] the extensions that define this instruction
  def extension
    @data["definedBy"]
    # parts = @data["extension"][0].split("_")
    # if @data["definedBy"].is_a?(String)
    #   parts[1].capitalize
    # else
    #   parts[1..].map(&:capitalize)
    # end
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

    display_fields = @encodings[base].opcode_fields
    display_fields += @encodings[base].decode_variables.map(&:grouped_encoding_fields).flatten

    display_fields.sort { |a, b| b.range.last <=> a.range.last }.reverse.each do |e|
      desc["reg"] << { "bits" => e.range.size, "name" => e.name, "type" => (e.opcode? ? 2 : 4) }
    end

    desc
  end
end

# Extension definition
class Extension < ArchDefObject
  # @return [ArchDef] The architecture defintion
  attr_reader :arch_def

  # @param ext_data [Hash<String, Object>] The extension data from the architecture spec
  # @param arch_def [ArchDef] The architecture defintion
  def initialize(ext_data, arch_def)
    super(ext_data)
    @arch_def = arch_def
  end

  # @return [Array<String>] Array of extensions implied by this one
  def implies
    case @data["implies"]
    when nil
      []
    when Array
      @data["implies"]
    else
      [@data["implies"]]
    end
  end
end

# A specific version of an extension
class ExtensionVersion
  # @return [String] Name of the extension
  attr_reader :name

  # @return [Gem::Version] Version of the extension
  attr_reader :version

  # @return [ArchDef] Owning ArchDef
  attr_reader :arch_def

  # @return [Extension] The full definition of the extension (all versions)
  attr_reader :extension

  # @param name [#to_s] The extension name
  # @param version [Integer,String] The version specifier
  # @param arch_def [ArchDef] The architecture definition
  def initialize(name, version, arch_def)
    @name = name.to_s
    @version = Gem::Version.new(version)
    @arch_def = arch_def
    @extension = @arch_def.extension(@name)
  end

  # @override ==(other)
  #   @param other [String] An extension name
  #   @return [Boolean] whether or not this ExtensionVersion is named 'other'
  # @override ==(other)
  #   @param other [ExtensionVersion] An extension name and version
  #   @return [Boolean] whether or not this ExtensionVersion has the exact same name and version as other
  def ==(other)
    case other
    when String
      @name == other
    when ExtensionVersion
      @name == other.name && @version == other.version
    else
      raise "Unexpected comparison"
    end
  end

  # @param ext_name [String] Extension name
  # @param ext_version_requirements [Number,String,Array] Extension version requirements, taking the same inputs as Gem::Requirement
  # @see https://docs.ruby-lang.org/en/3.0/Gem/Requirement.html#method-c-new Gem::Requirement#new
  # @return [Boolean] whether or not this ExtensionVersion is named `ext_name` and satifies the version requirements
  def satisfies?(ext_name, *ext_version_requirements)
    @name == ext_name && Gem::Requirement.new(ext_version_requirements).satisfied_by?(@version)
  end

  # sorts extension by name, then by version
  def <=>(other)
    raise ArgumentError, "ExtensionVersions are only comparable to other extension versions" unless other.is_a?(ExtensionVersion)

    if other.name != @name
      @name <=> other.name
    else
      @version <=> other.version
    end
  end
end

# Object model for a configured architecture definition
class ArchDef
  # @return [String] Name of the architecture configuration
  attr_reader :name

  # @return [SymbolTable] The symbol table containing global definitions
  attr_reader :sym_table
  
  # @return [Hash] The configuration parameters
  attr_reader :config_params

  # @return [Idl::Compiler] The IDL compiler
  attr_reader :idl_compiler

  # @return [Idl::AstNode] Abstract syntax tree of global scope
  attr_reader :global_ast

  # Initialize a new configured architecture defintiion
  #
  # @params config_name [#to_s] The name of a configuration, which must correspond
  #                             to a folder under $root/cfgs
  def initialize(config_name)
    @name = config_name.to_s
    arch_def_file = $root / "gen" / @name / "arch" / "arch_def.yaml"

    validator = Validator.instance
    begin
      validator.validate_str(arch_def_file.read, type: :arch)
    rescue Validator::ValidationError => e
      warn "While parsing unified architecture definition at #{arch_def_file}"
      raise e
    end

    @arch_def = YAML.load_file(arch_def_file)

    @config_params = @arch_def["params"]

    @sym_table = Idl::SymbolTable.new(self)
    @idl_compiler = Idl::Compiler.new(self)

    # load the globals into the symbol table
    @global_ast = @idl_compiler.compile_file(
      $root / "arch" / "isa" / "globals.isa",
      @sym_table
    )
  end

  # @return [Boolean] true if this configuration can execute in multiple xlen environments
  # (i.e., that in some mode the effective xlen can be either 32 or 64, depending on CSR values)
  def multi_xlen?
    ["SXLEN", "UXLEN", "VSXLEN", "VUXLEN"].any? { |key| @config_params[key] == 3264 }
  end

  # @return [Array<ExtensionVersion>] List of all extensions, with specific versions, that are implemented
  def implemented_extensions
    return @implemented_extensions unless @implemented_extensions.nil?

    @implemented_extensions = []
    @arch_def["implemented_extensions"].each do |e|
      @implemented_extensions << ExtensionVersion.new(e["name"], e["version"], self)
    end

    @implemented_extensions
  end

  # @return [Array<Extesion>] List of all extensions, even those that are't implemented
  def extensions
    return @extensions unless @extensions.nil?

    @extensions = []
    @arch_def["extensions"].each_value do |ext_data|
      @extensions << Extension.new(ext_data, self)
    end
    @extensions
  end

  # @retuns [Hash<String, Extension>] Hash of all extensions, even those that aren't implemented, indexed by extension name
  def extension_hash
    return @extension_hash unless @extension_hash.nil?

    @extension_hash = {}
    extensions.each do |ext|
      @extension_hash[ext.name] = ext
    end
    @extension_hash
  end

  # @param name [#to_s] Extension name
  # @return [Extension] Extension named `name`
  # @return [nil] if no extension `name` exists
  def extension(name)
    extension_hash[name.to_s]
  end

  # @overload ext?(ext_name)
  #   @param ext_name [#to_s] Extension name (case sensitive)
  #   @return [Boolean] True if the extension `name` is implemented
  # @overload ext?(ext_name, ext_version_requirements)
  #   @param ext_name [#to_s] Extension name (case sensitive)
  #   @param ext_version_requirements [Number,String,Array] Extension version requirements, taking the same inputs as Gem::Requirement
  #   @see https://docs.ruby-lang.org/en/3.0/Gem/Requirement.html#method-c-new Gem::Requirement#new
  #   @return [Boolean] True if the extension `name` meeting `ext_version_requirements` is implemented
  #   @example Checking extension presence with a version requirement
  #     arch_def.ext?(:S, ">= 1.12")
  #   @example Checking extension presence with multiple version requirements
  #     arch_def.ext?(:S, ">= 1.12", "< 1.15")
  #   @example Checking extension precsence with a precise version requirement
  #     arch_def.ext?(:S, 1.12)
  def ext?(ext_name, *ext_version_requirements)
    implemented_extensions.any? do |e|
      if ext_version_requirements.empty?
        e.name == ext_name.to_s
      else
        requirement = Gem::Requirement.new(ext_version_requirements)
        (e.name == ext_name.to_s) && requirement.satisfied_by?(e.version)
      end
    end
  end

  # @return [Hash] The raw architecture defintion data structure
  def data
    @arch_def
  end

  # @return [Array<Csr>] List of all implemented CSRs
  def implemented_csrs
    return @implemented_csrs unless @implemented_csrs.nil?

    @implemented_csrs = @arch_def["csrs"].select{ |csr_name, _csr_data| @arch_def["implemented_csrs"].include?(csr_name)}.map do |_csr_name, csr_data|
      Csr.new(csr_data, @sym_table, self)
    end
  end

  # @return [Array<Csr>] List of all CSRs defined by RISC-V, whether or not they are implemented
  def csrs
    return @csrs unless @csrs.nil?

    @csrs = @arch_def["csrs"].map do |_csr_name, csr_data|
      Csr.new(csr_data, @sym_table, self)
    end
  end

  # @return [Array<String>] List of all known CSRs, even those not implemented by
  #                         this config
  def all_known_csr_names
    @arch_def["csrs"].map { |csr| csr[0] }
  end

  # @return [Hash<String, Csr>] Implemented csrs, indexed by CSR name
  def implemented_csr_hash
    return @implemented_csr_hash unless @implemented_csr_hash.nil?

    @implemented_csr_hash = {}
    implemented_csrs.each do |csr|
      @implemented_csr_hash[csr.name] = csr
    end
    @implemented_csr_hash
  end

  # @return [Hash<String, Csr>] All csrs, even unimplemented ones, indexed by CSR name
  def csr_hash
    return @csr_hash unless @csr_hash.nil?

    @csr_hash = {}
    csrs.each do |csr|
      @csr_hash[csr.name] = csr
    end
    @csr_hash
  end

  # @param csr_name [#to_s] CSR name
  # @return [Csr,nil] a specific csr, or nil if it doesn't exist or isn't implemented
  def implemented_csr(csr_name)
    implemented_csr_hash[csr_name]
  end

  # @param csr_name [#to_s] CSR name
  # @return [Csr,nil] a specific csr, or nil if it doesn't exist
  def csr(csr_name)
    csr_hash[csr_name]
  end

  # @return [Array<Instruction>] List of all instructions, whether or not they are implemented
  def instructions
    return @instructions unless @instructions.nil?

    opcode_data = YAML.load_file("#{$root}/ext/riscv-opcodes/instr_dict.yaml")

    @instructions = @arch_def["instructions"].map do |_inst_name, inst_data|
      Instruction.new(inst_data, opcode_data, @sym_table, self)
    end

    @instructions
  end

  # @return [Hash<String, Instruction>] All instructions, indexed by name
  def instruction_hash
    return @instruction_hash unless @instruction_hash.nil?

    @instruction_hash = {}
    instructions.each do |inst|
      @instruction_hash[inst.name] = inst
    end
    @instruction_hash
  end

  # @return [Array<Instruction>] List of all implemented instructions
  def implemented_instructions
    return @implemented_instructions unless @implemented_instructions.nil?

    opcode_data = YAML.load_file("#{$root}/ext/riscv-opcodes/instr_dict.yaml")

    @implemented_instructions = @arch_def["implemented_instructions"].map do |inst_name|
      instruction_hash[inst_name]
    end

    @implemented_instructions
  end

  # @param inst_name [#to_s] Instruction name
  # @return [Instruction,nil] An instruction named 'inst_name', or nil if it doesn't exist
  def inst(inst_name)
    instruction_hash[inst_name.to_s]
  end

  # given an adoc string, find names of CSR/Instruction/Extension enclosed in `monospace`
  # and replace them with links to the relevant object page
  #
  # @param adoc [String] Asciidoc source
  # @return [String] Asciidoc source, with link placeholders
  def find_replace_links(adoc)
    adoc.gsub(/`([\w.]+)`/) do |match|
      name = Regexp.last_match(1)
      csr_name, field_name = name.split(".")
      csr = csr(csr_name)
      if !field_name.nil? && !csr.nil? && csr.field?(field_name)
        "%%LINK[csr_field;#{csr_name}.#{field_name};#{csr_name}.#{field_name}]%%"
      elsif !csr.nil?
        "%%LINK[csr;#{csr_name};#{csr_name}]%%"
      elsif inst(name.downcase)
        "%%LINK[inst;#{name};#{name}]%%"
      elsif extension(name)
        "%%LINK[ext;#{name};#{name}]%%"
      else
        match
      end
    end
  end
end

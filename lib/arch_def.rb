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
  attr_reader :parent

  # @!attribute field
  #  @return [CsrField] The field being aliased
  # @!attribute range
  #  @return [Range] Range of the aliased field that is being pointed to
  Alias = Struct.new(:field, :range)

  def initialize(parent_csr, field_data)
    super(field_data)
    @parent = parent_csr
  end

  # @return [ArchDef] The owning ArchDef
  def arch_def
    @parent.arch_def
  end

  def type
    return @type unless @type.nil?

    @type =
      if @data.key?("type")
        @data["type"]
      else
        # the type is config-specific...
        idl = @data["type()"]
        expected_return_type =
          Idl::Type.new(:enum_ref, enum_class: csr.sym_table.get("CsrFieldType"))
        ast = arch_def.idl_compiler.compile_func_body(
          idl,
          symtab: csr.sym_table,
          return_type: expected_return_type,
          name: "type",
          parent: "#{csr.name}.#{name}"
        )
        case ast.value(csr.sym_table, arch_def)
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
        if  range.nil?
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

  def has_custom_write?
    @data.key?("write(value)") && !@data["write(value)"].empty?
  end

  # @return [Csr] Parent CSR for this field
  def csr
    @parent
  end

  # @return [Boolean] Whether or not the location of the field changes dynamically
  #                   (e.g., based on mstatus.SXL)
  def dynamic_location?
    return false unless @data.key?("location()")

    puts "#{csr.name}.#{name} is dynamic?    #{!location_func.constexpr_returns?(csr.sym_table, csr.arch_def)}"

    !location_func.constexpr_returns?(csr.sym_table, csr.arch_def)
  end

  def location_func
    raise "Not an IDL location" unless @data.key?("location()")

    return @length_func unless @length_func.nil?

    begin
      @length_func = arch_def.idl_compiler.compile_func_body(
        @data["location()"],
        return_type: Idl::Type.new(:bits, width: 6),
        symtab: csr.sym_table,
        name: "location 1",
        parent: "CSR[#{parent.name}].#{name}",
        input_file: "CSR[#{parent.name}].#{name}",
        no_rescue: true
      )
    rescue Idl::AstNode::TypeError => e
      # maybe the failure was because we got an array back. try again
      begin
        @length_func = arch_def.idl_compiler.compile_func_body(
          @data["location()"],
          return_type: Idl::Type.new(:array, width: 2, sub_type: Idl::Type.new(:bits, width: 6)),
          symtab: csr.sym_table,
          name: "location 2",
          parent: "CSR[#{parent.name}].#{name}",
          input_file: "CSR[#{parent.name}].#{name}",
          no_rescue: true
        )
      rescue Idl::AstNode::TypeError => e2
        puts "While compiling #{csr.name}.#{name}.location(), got type error for both an expected int and array return"
        puts e
        puts e2
        exit 1
      end
    end

    @length_func
  end

  def reset_value_func
    raise "Not an IDL value" unless @data.key?("reset_value()")

    return @reset_value_func unless @reset_value_func.nil?

    @reset_value_func = arch_def.idl_compiler.compile_func_body(
      @data["reset_value()"],
      return_type: Idl::Type.new(:bits, width: 64),
      symtab: csr.sym_table,
      name: "location",
      parent: "CSR[#{parent.name}].#{name}",
      input_file: "CSR[#{parent.name}].#{name}",
      no_rescue: true
    )
  end

  def reset_value
    return @reset_value unless @reset_value.nil?

    @reset_value =
      if @data.key?("reset_value")
        @data["reset_value"]
      else
        reset_value_func.return_value(arch_def.sym_table, arch_def)
      end
  end

  def locations
    return TypeError, "location for #{name} is static; use location()" unless dynamic_location?

    ast = arch_def.idl_compiler.compile_func_body(
      @data["location()"],
      return_type: Idl::Type.new(:bits, width: 6),
      symtab: arch_def.sym_table,
      name: "location",
      parent: "#{parent.name}:#{name}"
    )

    possible_values = ast.pass_find_return_values(arch_def.sym_table, arch_def)

    locs = []
    possible_values.each do |v|
      value = v[0]
      raise "Expecting constexpr location" unless value.constexpr_returns?(arch_def.sym_table, arch_def)

      conditions = v[1]

      locs << {
        value: value.return_value(arch_def.sym_table, arch_def),
        when: conditions.map(&:to_idl).join(' && ')
      }
    end

    locs
  end

  # @return [Range] the location within the CSR as a range (single bit fields will be a range of size 1)
  # @raise [TypeError] if the location is dynamic
  def location
    raise TypeError, "location for #{name} is dynamic; use locations() get options" if dynamic_location?

    if @data["location"].is_a?(Integer)
      raise "Location is past XLEN" if @data["location"] > arch_def.config_params["XLEN"]

      @data["location"]..@data["location"]
    elsif @data["location"].is_a?(String)
      e, s = @data["location"].split("-").map(&:to_i)
      raise "Invalid location" if s > e

      s..e
    elsif @data.key? "location()"
      loc = location_func.return_value(csr.sym_table, csr.arch_def)
      if loc.is_a?(Integer)
        loc..loc
      else
        raise "location() returned a range in the wrong order (should be [MSB, LSB])" if loc[0] < loc[1]

        loc[1]..loc[0]
      end
    else
      raise "Bad location"
    end
  end

  # @return [Integer] Number of bits in the field
  def width
    location.size
  end

  # @return [String] Pretty-printed location string
  def location_pretty
    if dynamic_location?
      possible_values = location_func.pass_find_return_values(csr.sym_table, arch_def)

      result = ""
      possible_values.each do |h|
        result += "#{h[0].return_value(csr.sym_table, arch_def)} when #{h[1].map(&:to_idl).join(' && ')}\n\n"
      end
      result
    else
      return location.min.to_s if location.size == 1

      "#{location.max}:#{location.min}"
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

  # @return [Integer,String] Reset value
  def reset_value
    type == "RO" ? @data["value"] : @data["reset_value"]
  end
end

# CSR definition
class Csr < ArchDefObject
  # @@parser = IsaDefParser.new

  # @return [ArchDef] The owning ArchDef
  attr_reader :arch_def, :sym_table

  def initialize(csr_data, sym_table, arch_def)
    super(csr_data)

    @arch_def = arch_def
    @sym_table = sym_table
  end

  # @return [Boolean] Whether or not the length of the CSR depends on a runtime value
  #                   (e.g., mstatus.SXL)
  def dynamic_length?
    return false unless @data.key?("length()")

    puts "#{name} is dynamic?    #{!length_ast.constexpr_returns?(@sym_table, @arch_def)}"

    !length_ast.constexpr_returns?(@sym_table, @arch_def)
  end

  def length
    raise "length is dynamic" if dynamic_length?

    return @data["length"] if @data.key?("length")

    length_ast.return_value(@sym_table, @arch_def)
  end

  def length_ast
    raise "Not an IDL length" unless @data.key?("length()")

    return @length_ast unless @length_ast.nil?

    @length_ast = arch_def.idl_compiler.compile_func_body(
      @data["length()"],
      return_type: Idl::Type.new(:bits, width: 7),
      symtab: @sym_table,
      name: "length",
      parent: name
    )
  end

  # when the length is determined dynamically, there are multiple valid lengths
  # this function returns the set of valid lengths, along with the condition
  # under which that length is used
  #
  # @return [Array<Hash>] Length, as a hash of {when => value}
  def lengths
    return @lengths unless @lengths.nil?

    return TypeError, "length for #{name} is static; use length" unless dynamic_length?

    ast = arch_def.idl_compiler.compile_func_body(
      @data["length()"],
      return_type: Idl::Type.new(:bits, width: 6),
      symtab: arch_def.sym_table,
      name: "length",
      parent: name
    )

    possible_values = ast.pass_find_return_values(arch_def.sym_table, arch_def)

    @lengths = []
    possible_values.each do |v|
      value = v[0]
      raise "Expecting constexpr length" unless value.constexpr?(arch_def.sym_table, arch_def)

      conditions = v[1]

      @lengths << {
        value: value.value(arch_def.sym_table, arch_def),
        when: conditions.map(&:to_idl).join(' && ')
      }
    end

    @lengths
  end

  # return the length of the field as an Integer
  # In some cases, the length is dynamic (e.g., depending on SXLEN).
  # When the length is dynamic, a specific value for the mode must be given
  #
  # @example Compute length when length is 32
  #   computed_length() => 32
  #
  # @example Compute length when length is 'SXLEN' and 'SXLEN' parameter is 32
  #   computed_length() => 32
  #
  # @example Compute length when length is 'SXLEN'. and 'SXLEN' parameter is 3264
  #   computed_length(64) => 64
  #
  # @example Compute length when length is 'SXLEN', and 'SXLEN' parameter is [32, 64]
  #   computed_length() => ArgumentError
  #
  # @param effective_xlen [Integer,nil] Value to use when length is dynamic (e.g., 'SXLEN')
  # @return [Integer] Length of the CSR, in bits
  def computed_length(effective_xlen = nil)
    if dynamic_length?
      if effective_xlen.nil?
        raise ArgumentError, <<~MSG
          Length of #{name} depends on #{@data['length']};
            it must be supplied to length() to get a value
        MSG
      end

      unless arch_def.config_params[length].include?(effective_xlen)
        raise ArgumentError, "#{effective_xlen} is not a valid value of #{length} (#{arch_def.config_params[length]})"
      end

      effective_xlen
    else
      raise ArgumentError, "Length is not dynamic; effective_xlen should not be provided" unless effective_xlen.nil?

      # length isn't dynamic, but it still might be parameterized
      if length.is_a?(String)
        arch_def.config_params[length]
      else
        length
      end
    end
  end

  def sw_read_ast
    "TODO: add sw_read_ast back"
    # return @sw_read_ast unless @sw_read_ast.nil?

    # return if @data["sw_read"].nil?

    # @@parser.set_input_file("CSR #{name}")
    # m = @@parser.parse(@data["sw_read"], root: :function_statements)
    # if m.nil?
    #   warn "While parsing sw_read for CSR '#{name}'"
    #   warn "Parsing error at #{@@parser.failure_line}:#{@@parser.failure_column}"
    #   warn @@parser.failure_reason
    #   raise "Parse failed"
    # end

    # m.make_left

    # @sym_table.push
    # @sym_table.add!("__expected_return_type", Type.new(:bits, width: length))
    # begin
    #   m.func_stmt_list.elements.each do |e|
    #     e.choice.type_check(@sym_table, @arch_def)
    #   end
    # rescue Ast::TypeError => e
    #   warn "In the sw_read of CSR #{name}:"
    #   warn e.what
    #   exit 1
    # rescue Ast::InternalError => e
    #   warn "In the sw_read of CSR #{name}:"
    #   warn e.what
    #   warn e.backtrace
    #   exit 1
    # end
    # @sym_table.pop

    # @sw_read_ast = m
  end

  # parse description field with asciidoctor, and retur the HTML result
  #
  # @return [String] Parsed description in HTML
  def description_html
    Asciidoctor.convert description
  end

  # @return [Array<CsrField>] All fields for this CSR, sorted by location (smallest location first)
  def fields
    return @fields unless @fields.nil?

    @fields = []
    @data["fields"].each_value do |field_data|
      @fields << CsrField.new(self, field_data)
    end
    @fields.sort! do |a, b|
      if a.dynamic_location?
        1
      elsif b.dynamic_location?
        -1
      else
        a.location.max <=> b.location.max
      end
    end
    @fields
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

  def sw_read_source
    return "" unless has_custom_sw_read?

    sw_read_ast.gen_adoc.gsub("((", '\((')
  end

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
  def wavedrom_desc(effective_length = nil)
    effective_length = length if effective_length.nil?
    raise "bad length" unless effective_length.is_a?(Integer)
    desc = {
      "reg" => []
    }
    last_idx = -1
    if fields.any?(&:dynamic_location?)
      fields.each(&:locations)
    end
    fields.each do |field|
      next if field.dynamic_location?

      if field.location.min != last_idx + 1
        # have some reserved space
        desc["reg"] << { "bits" => (field.location.min - last_idx - 1), type: 1 }
      end
      desc["reg"] << { "bits" => field.location.size, "name" => field.name, type: 2 }
      last_idx = field.location.max
    end
    if !fields.empty? && (fields.last.dynamic_location? || (fields.last.location.max != (effective_length - 1)))
      # reserved space at the end
      desc["reg"] << { "bits" => (effective_length - 1 - last_idx), type: 1 }
      # desc['reg'] << { 'bits' => 1, type: 1 }
    end
    desc["config"] = { "bits" => effective_length }
    desc["config"]["lanes"] = effective_length / 16
    desc
  end

  def gen_html(scope)
    scope = scope.clone
    scope.csr = self
    scope.current_url = Class.new { extend AssetMap }.csr_url("#{name}.html")

    Slim::Template.new(
      "#{ROOT}/lib/views/csr.slim",
      pretty: true
    ).render(scope)
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

# represents a single contiguous instruction encoding field
# Multiple EncodingFields may make up a single DecodeField, e.g., when an immediate
# is split across multiple locations
# class EncodingField
#   # name, which corresponds either:
#   #   * to a name used in riscv_opcodes
#   #   * to a binary value, as a String, for a fixed opcode
#   attr_reader :name

#   # range in the encoding
#   attr_reader :range

#   def initialize(name, range, pretty = nil)
#     @name = name
#     @range = range
#     @pretty = pretty
#   end

#   # is this encoding field part of a variable?
#   def variable?
#     !opcode?
#   end

#   # is this encoding field a fixed opcode?
#   def opcode?
#     name.match?(/^[01]+$/)
#   end

#   def eql?(other)
#     @name == other.name && @range == other.range
#   end

#   def hash
#     [@name, @range].hash
#   end

#   def pretty_to_s
#     return @pretty unless @pretty.nil?

#     @name
#   end

#   def size
#     @range.size
#   end
# end

# class DecodeField
#   # the name of the field
#   attr_reader :name

#   # array of constituent encoding fields
#   attr_reader :encoding_fields

#   # aliases of this field.
#   #  if there is one alias, a String
#   #  if there is more than one alias, an Array
#   #  if there are no aliases, nil
#   attr_reader :decode_variable

#   def initialize(inst, name, decode_ring_key, field_data)
#     raise "No field '#{name}', needed by #{inst.name}, in Opcodes module" unless RiscvOpcodes::VARIABLE_FIELDS.key?(decode_ring_key)

#     @encoding_fields = []
#     if decode_ring_key.is_a?(Array)
#       raise "Split fields '#{decode_ring_key}' must have an alias" unless field_data.key?(:decode_variable)

#       raise "Split fields '#{decode_ring_key}' must have a group_by field" unless field_data.key?(:group_by)

#       decode_ring_key.each_index do |i|
#         range = field_data[:group_by][i].is_a?(Integer) ? (field_data[:group_by][i]..field_data[:group_by][i]) : field_data[:group_by][i]
#         raise "expecting a range" unless range.is_a?(Range)

#         display =
#           if field_data[:display].nil?
#             nil
#           elsif field_data[:display].is_a?(Array)
#             field_data[:display][i]
#           else
#             field_data[:display]
#           end
#         @encoding_fields << EncodingField.new(decode_ring_key[i], range, display)
#       end
#     else
#       raise 'decode_ring_key must be an Array or a String' unless decode_ring_key.is_a?(String)

#       range = field_data[:bits].is_a?(Range) ? field_data[:bits] : field_data[:group_by]
#       raise 'expecting a range' unless range.is_a?(Range)

#       @encoding_fields << EncodingField.new(decode_ring_key, range, field_data[:display])
#     end

#     @name = name
#     if field_data.key?(:decode_variable) && field_data[:decode_variable] != name
#       if field_data[:decode_variable].is_a?(String)
#         @alias = field_data[:decode_variable]
#       else
#         raise "unexpected" unless field_data[:decode_variable].is_a?(Array)

#         other_aliases = field_data[:decode_variable].reject { |a| a == @name }
#         if other_aliases.size == 1
#           @alias = other_aliases[0]
#         else
#           @laias = other_aliases
#         end
#       end
#     end
#     raise "unexpected: #{name}" unless @name.is_a?(String)

#     @data = field_data
#   end

#   def eql?(other)
#     @name.eql?(other.name)
#   end

#   def hash
#     @name.hash
#   end

#   def sext?
#     @data[:sext] == true
#   end

#   def lshift?
#     @data[:lshift].is_a?(Integer)
#   end

#   def lshift
#     @data[:lshift]
#   end

#   # returns true if the field is encoded across more than one groups of bits
#   def split?
#     encoding_fields.size > 1
#   end

#   # returns bits of the encoding that make up the field, as an array
#   #   Each item of the array is either:
#   #     - A number, to represent a single bit
#   #     - A range, to represent a continugous range of bits
#   #
#   #  The array is ordered from encoding MSB (at index 0) to LSB (at index n-1)
#   def bits
#     @data[:bits].is_a?(Range) ? [@data[:bits]] : @data[:bits]
#   end
# end

class Instruction < ArchDefObject

  attr_reader :encoding_fields, :decode_variables, :operation_ast

  attr_reader :arch_def

  def initialize(inst_data, full_opcode_data, sym_table, arch_def)
    @arch_def = arch_def
    super(inst_data)

    opcode_data_key = name.downcase.gsub(".", "_")
    raise "opcode data not found for #{name}" unless full_opcode_data.key?(opcode_data_key)

    @opcode_data = full_opcode_data[opcode_data_key]

    @encoding_fields = []
    msb = encoding.size
    encoding.split("-").each do |e|
      if e.empty?
        msb -= 1
      else
        @encoding_fields << EncodingField.new(e, (msb - e.size + 1)..msb)
        msb -= e.size
      end
    end

    @decode_variables = []
    @opcode_data["variable_fields"].to_a.each do |f|
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
        @decode_variables << DecodeField.new(self, name, decode_field_data[0][0], decode_field_data[0][1])
      end
    end
    @decode_variables.uniq!

    @decode_variables.each do |v|
      v.encoding_fields.each do |e|
        @encoding_fields << e unless @encoding_fields.any?(e)
      end
    end

    @encoding_fields.uniq!
    @encoding_fields.sort! { |a, b| b.range.end <=> a.range.end }

    parse_operation(sym_table)
  end

  def operation_source
    return "" if @operation_ast.nil?

    @operation_ast.gen_adoc.gsub("{{", '\((')
    # @data['operation']
  end

  def parse_operation(sym_table)
    # now, parse the operation
    return if @data["operation()"].nil?

    sym_table.push
    @decode_variables.each do |d|
      qualifiers = []
      qualifiers << :signed if d.sext?
      width = d.size

      var = Idl::Var.new(d.name, Idl::Type.new(:bits, qualifiers:, width:), decode_var: true)
      sym_table.add(d.name, var)
    end

    m = arch_def.idl_compiler.compile_inst_operation(
      @data["operation()"],
      symtab: sym_table,
      name: name,
      parent: nil,
      input_file: "Instruction #{name}"
    )

    sym_table.pop

    raise "unexpected #{m.class}" unless m.is_a?(Idl::InstructionOperationAst)

    m.make_left # fix up right recursion

    @operation_ast = m
  end

  # returns the encoding as, e.g.,:
  #   0000101----------001-----0110011
  def encoding
    @opcode_data["encoding"]
  end

  def encoding_variable_fields
    @opcode_data["variable_fields"]
  end

  # returns the extension(s) that define this instruction
  def extension
    parts = @opcode_data["extension"][0].split("_")
    if parts.size == 2
      parts[1].capitalize
    else
      parts[1..].map(&:capitalize)
    end
  end

  # @return [Boolean] true if the instruction has an 'access_detail' field
  def access_detail?
    @data.key?("access_detail")
  end

  def wavedrom_desc
    fields = []

    starting_index = encoding.size - 1
    encoding.split("-").each do |field|
      if field.empty?
        starting_index -= 1
      else
        fields << [field, ((starting_index - (field.size - 1))..starting_index)]
        starting_index -= field.size
      end
    end

    encoding_variable_fields.each do |field|
      fields <<
        case field
        when "rd" then ["rd", (7..11)]
        when "rs1" then ["rs1", (15..19)]
        when "rs2" then ["rs2", (20..24)]
        when "imm12" then ["imm[11:0]", (20..31)]
        when "imm20" then ["imm[31:12]", (12..31)]
        when "bimm12hi" then ["imm[12|10:5]", (25..31)]
        when "bimm12lo" then ["imm[4:1|11]", (7..11)]
        when "imm12hi" then ["imm[11:5]", (25..31)]
        when "imm12lo" then ["imm[4:0]", (7..11)]
        when "fm" then ["fm", (28..31)]
        when "pred" then ["pred", (24..27)]
        when "succ" then ["succ", (20..23)]
        when "jimm20" then ["imm[20|10:1|11|19:12]", (12..31)]
        when "shamtd" then ["shamt", (20..25)]
        when "shamtw" then ["shamt", (20..24)]
        when "csr" then ["csr", (20..31)]
        when "zimm" then ["zimm", (15..19)]
        else raise "Unknown variable field '#{field}' for #{name}"
        end
    end

    raise "Fields don't add up to 32" unless fields.reduce(0) { |sum, field| sum + field[1].size } == 32

    desc = {
      "reg" => []
    }

    fields.sort! { |a, b| a[1].begin <=> b[1].begin }

    # fields.each do |field|
    #   desc['reg'] << { 'bits' => field[1].size, 'name' => field[0], type: 2 }
    # end

    @encoding_fields.reverse.each do |e|
      desc["reg"] << { "bits" => e.range.size, "name" => e.pretty_to_s, "type" => (e.opcode? ? 2 : 4) }
    end

    desc
  end
end

# Extension definition
class Extension < ArchDefObject
  def initialize(ext_data, arch_def)
    super(ext_data)
    @arch_def = arch_def
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

  def initialize(name, version, arch_def)
    @name = name
    @version = Gem::Version.new(version)
    @arch_def = arch_def
    @extension = @arch_def.extension(name)
  end
end

# interface to the unified architecture defintion
class ArchDef
  # @return [String] Name of the architecture configuration
  attr_reader :name

  attr_reader :isa_def, :sym_table, :config_params

  attr_reader :idl_compiler

  def initialize(config_name)
    @name = config_name
    arch_def_file = $root / "gen" / config_name / "arch" / "arch_def.yaml"

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

    # load the globals
    @isa_def = @idl_compiler.compile_file(
      $root / "arch" / "isa" / "globals.isa",
      @sym_table
    )
  end

  # @return [Array<ExtensionVersion>] List of all extensions that are implemented
  def implemented_extensions
    return @implemented_extensions unless @implemented_extensions.nil?

    @implemented_extensions = []
    @arch_def["implemented_extensions"].each do |e|
      @implemented_extensions << ExtensionVersion.new(e["name"], e["version"], self)
    end
    @implemented_extensions
  end

  # @return [Array<Extesions>] List of all extensions, even those that are't implemented
  def extensions
    return @extensions unless @extensions.nil?

    @extensions = []
    @arch_def["extensions"].each_value do |ext_data|
      @extensions << Extension.new(ext_data, self)
    end
    @extensions
  end

  def extension_hash
    return @extension_hash unless @extension_hash.nil?

    @extension_hash = {}
    extensions.each do |ext|
      @extension_hash[ext.name] = ext
    end
    @extension_hash
  end

  # @param name [#to_s] Extension name
  # @return [Extension,nil] Extension named 'name', or nil if none exists
  def extension(name)
    extension_hash[name.to_s]
  end

  def ext?(ext_name, ext_version = nil)
    implemented_extensions.any? do |e|
      if ext_version.nil?
        e.name == ext_name.to_s
      else
        requirement = Gem::Requirement.new(ext_version)
        (e.name == ext_name.to_s) && requirement.satisfied_by?(e.version)
      end
    end
  end

  # return the raw data
  def data
    @arch_def
  end

  # @return [Array<Csr>] List of all implemented CSRs
  def csrs
    return @csrs unless @csrs.nil?

    @csrs = @arch_def["csrs"].map do |_csr_name, csr_data|
      Csr.new(csr_data, @sym_table, self)
    end
  end

  # @return [Hash<String, Csr>] All csrs, indexed by CSR name
  def csr_hash
    return @csr_hash unless @csr_hash.nil?

    @csr_hash = {}
    csrs.each do |csr|
      @csr_hash[csr.name] = csr
    end
    @csr_hash
  end

  # @param csr_name [#to_s] CSR name
  # @return [Csr,nil] a specific csr, or nil if it doesn't exist
  def csr(csr_name)
    csr_hash[csr_name]
  end

  # @return [Array<Instruction>] List of all implemented instructions
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

  # @param inst_name [#to_s] Instruction name
  # @return [Instruction,nil] An instruction named 'inst_name', or nil if it doesn't exist
  def inst(inst_name)
    instruction_hash[inst_name]
  end

  # given an adoc string, find instances of `CSR/Instruction/Extension`
  # and replace them with links to the relevant object
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
        # "xref:csrs:#{name}.adoc##{name}-#{field_name}-def[#{match}]"
      elsif !csr.nil?
        "%%LINK[csr;#{csr_name};#{csr_name}]%%"
        # "xref:csrs:#{name}.adoc##{name}-def[#{match}]"
      elsif inst(name.downcase)
        "%%LINK[inst;#{name};#{name}]%%"
        # "xref:insts:#{name}.adoc##{name.gsub('.', '_')}-def[#{match}]"
      elsif extension(name)
        "%%LINK[ext;#{name};#{name}]%%"
      else
        match
      end
    end
  end
end

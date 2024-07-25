# frozen_string_literal: true

require "forwardable"
require "ruby-prof"

require_relative "validate"
require_relative "idl"
require_relative "idl/passes/find_return_values"
require_relative "idl/passes/gen_adoc"
require_relative "idl/passes/prune"
require_relative "idl/passes/reachable_functions"
require_relative "idl/passes/reachable_exceptions"

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
  attr_reader :data

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
  
  # @param k (see Hash#key?)
  # @return (see Hash#key?)
  def key?(k) = @data.key?(k)

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

  # @overload defined_by?(ext_name, ext_version)
  #   @param ext_name [#to_s] An extension name
  #   @param ext_version [#to_s] A specific extension version
  #   @return [Boolean] Whether or not the instruction is defined by extesion `ext`, version `version`
  # @overload defined_by?(ext_version)
  #   @param ext_version [ExtensionVersion] An extension version
  #   @return [Boolean] Whether or not the instruction is defined by ext_version
  def defined_by?(*args)
    if args.size == 1
      raise ArgumentError, "Parameter must be an ExtensionVersion" unless args[0].is_a?(ExtensionVersion)

      extension_requirements.any? do |r|
        r.satisfied_by?(args[0])
      end
    elsif args.size == 2
      raise ArgumentError, "First parameter must be an extension name" unless args[0].respond_to?(:to_s)
      raise ArgumentError, "Second parameter must be an extension version" unless args[0].respond_to?(:to_s)

      extension_requirements.any? do |r|
        r.satisfied_by?(args[0].to_s, args[1].to_s)
      end
    end
  end

  def to_extension_requirement(obj)
    if obj.is_a?(String)
      ExtensionRequirement.new(obj, ">= 0")
    else
      ExtensionRequirement.new(*obj)
    end
  end
  private :to_extension_requirement

  def extension_requirement?(obj)
    obj.is_a?(String) && obj =~ /^([A-WY])|([SXZ][a-z]+)$/ ||
      obj.is_a?(Array) && obj[0] =~ /^([A-WY])|([SXZ][a-z]+)$/
  end
  private :extension_requirement?

  # @return [Array<ExtensionRequirement>] Extension requirements for the instruction. If *any* requirement is met, the instruction is defined
  def extension_requirements
    return @extension_requirements unless @extension_requirements.nil?

    @extension_requirements = []
    if @data["definedBy"].is_a?(Array)
      # could be either a single extension with requirement, or a list of requirements
      if extension_requirement?(@data["definedBy"][0])
        @extension_requirements << to_extension_requirement(@data["definedBy"][0])
      else
        # this is a list
        @data["definedBy"].each do |r|
          @extension_requirements << to_extension_requirement(r)
        end
      end
    else
      @extension_requirements << to_extension_requirement(@data["definedBy"])
    end

    raise "empty requirements" if @extension_requirements.empty?

    @extension_requirements
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

  # @param possible_xlens [Array<Integer>] List of xlens that be used in any implemented mode
  # @param extensions [Array<ExtensionVersion>] List of extensions implemented
  # @return [Boolean] whether or not the instruction is implemented given the supplies config options
  def exists_in_cfg?(possible_xlens, extensions)
    parent.exists_in_cfg?(possible_xlens, extensions) &&
      (@data["definedBy"].nil? || extensions.any? { |e| defined_by?(e) } )
  end

  # @param arch_def [ArchDef] A config
  # @return [String]
  #    The type of the field. One of:
  #      'RO'    => Read-only
  #      'RO-H'  => Read-only, with hardware update
  #      'RW'    => Read-write
  #      'RW-R'  => Read-write, with a restricted set of legal values
  #      'RW-H'  => Read-write, with a hardware update
  #      'RW-RH' => Read-write, with a hardware update and a restricted set of legal values
  def type(arch_def)
    if !@type_cache.nil? && @type_cache.key?(arch_def)
      return @type_cache[arch_def]
    end

    @type_cache ||= {}

    type =
      if @data.key?("type")
        @data["type"]
      else
        # the type is config-specific...
        idl = @data["type()"]
        raise "type() is nil for #{csr.name}.#{name} #{@data}?" if idl.nil?

        expected_return_type =
          Idl::Type.new(:enum_ref, enum_class: arch_def.sym_table.get("CsrFieldType"))
        sym_table = arch_def.sym_table

        puts "Compiling CSR[#{csr.name}].#{name} type()"
        ast = arch_def.idl_compiler.compile_func_body(
          idl,
          symtab: sym_table,
          return_type: expected_return_type,
          name: "type",
          parent: "#{csr.name}.#{name}"
        )

        sym_table = sym_table.deep_clone(clone_values: true)
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
    @type_cache[arch_def] = type
    type
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

  # @return [Boolean] True if the field has a custom write function (i.e., `sw_write(csr_value)` exists in the spec)
  def has_custom_write?
    @data.key?("sw_write(csr_value)") && !@data["sw_write(csr_value)"].empty?
  end

  def sw_write_ast(arch_def, effective_xlen = nil)
    return @sw_write_ast unless @sw_write_ast.nil?
    return nil if @data["sw_write(csr_value)"].nil?

    # now, parse the function

    symtab = arch_def.sym_table.deep_clone

    # push the csr_value
    symtab.push
    symtab.add("csr_value", Idl::Var.new("csr_value", csr.bitfield_type(arch_def, effective_xlen)))

    puts "Compiling CSR[#{csr.name}].#{name} sw_write"
    @sw_write_ast = arch_def.idl_compiler.compile_func_body(
      @data["sw_write(csr_value)"],
      return_type: Idl::Type.new(:bits, width: 128), # big int to hold special return values
      symtab:,
      name: "CSR[#{csr.name}].#{name}.sw_write(csr_value)",
      input_file: "CSR #{name}, field #{name}"
    )

    raise "unexpected #{@sw_write_ast.class}" unless @sw_write_ast.is_a?(Idl::FunctionBodyAst)

    @sw_write_ast
  end

  def reachable_functions(symtab, effective_xlen = nil)
    ast = sw_write_ast(symtab.archdef, effective_xlen)
    return [] if ast.nil?

    symtab = symtab.deep_clone
    symtab.push
    symtab.add("csr_value", Idl::Var.new("csr_value", csr.bitfield_type(symtab.archdef, effective_xlen)))

    ast.reachable_functions(symtab)
  end

  # @return [Csr] Parent CSR for this field
  alias csr parent

  # @param arch_def [ArchDef] A configuration
  # @return [Boolean] Whether or not the location of the field changes dynamically
  #                   (e.g., based on mstatus.SXL) in the configuration
  def dynamic_location?(arch_def)
    if @data.key?("location_rv32")
      csr.modes_with_access.each do |mode|
        return true if arch_def.multi_xlen_in_mode?(mode)
      end
    end
    false
  end

  # @param arch_def [ArchDef] A config
  # @return [Idl::AstNode] Abstract syntax tree of the reset_value function
  # @raise StandardError if there is no reset_value function (i.e., the reset value is static)
  def reset_value_func(arch_def)
    raise "Not an IDL value" unless @data.key?("reset_value()")

    return @reset_value_func unless @reset_value_func.nil?

    puts "Compiling CSR[#{csr.name}].#{name} reset_value()"
    @reset_value_func = arch_def.idl_compiler.compile_func_body(
      @data["reset_value()"],
      return_type: Idl::Type.new(:bits, width: 64),
      symtab: arch_def.sym_table,
      name: "reset_value",
      parent: "CSR[#{parent.name}].#{name}",
      input_file: "CSR[#{parent.name}].#{name}",
      no_rescue: true
    )
  end

  # @param arch_def [ArchDef] A config
  # @return [Integer] The reset value of this field
  # @return [String]  The string 'UNDEFINED_LEGAL' if, for this config, there is no defined reset value
  def reset_value(arch_def)
    if !@reset_value_cache.nil? && @reset_value_cache.key?(arch_def)
      return @reset_value_cache[arch_def]
    end

    @reset_value_cache ||= {}

    symtab = arch_def.sym_table.deep_clone(clone_values: true)
    raise "not at global scope" unless symtab.levels == 1

    symtab.push # for consistency with template functions

    begin
      reset_value =
        if @data.key?("reset_value")
          @data["reset_value"]
        else
          reset_value_func(arch_def).return_value(symtab)
        end
      @reset_value_cache[arch_def] = reset_value
      reset_value
    ensure
      symtab.pop
    end
  end

  # @param arch_def [ArchDef] A config. May be nil if the locaiton is not configturation-dependent
  # @param effective_xlen [Integer] The effective xlen, needed since some fields change location with XLEN. If the field location is not determined by XLEN, then this parameter can be nil
  # @return [Range] the location within the CSR as a range (single bit fields will be a range of size 1)
  def location(arch_def, effective_xlen = nil)
    key =
      if @data.key?("location")
        "location"
      else
        raise ArgumentError, "Expecting 32 or 64" unless [32, 64].include?(effective_xlen)

        "location_rv#{effective_xlen}"
      end

    raise "Missing location for #{csr.name}.#{name} (#{key})?" unless @data.key?(key)

    if @data[key].is_a?(Integer)
      if @data[key] > csr.length(arch_def, effective_xlen || @data["base"])
        raise "Location (#{@data[key]}) is past the csr length (#{csr.length(arch_def, effective_xlen)}) in #{csr.name}.#{name}"
      end

      @data[key]..@data[key]
    elsif @data[key].is_a?(String)
      e, s = @data[key].split("-").map(&:to_i)
      raise "Invalid location" if s > e

      if e > csr.length(arch_def, effective_xlen)
        raise "Location (#{@data[key]}) is past the csr length (#{csr.length(arch_def, effective_xlen)}) in #{csr.name}.#{name}"
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

  # @param arch_def [ArchDef] A config. May be nil if the width of the field is not configuration-dependent
  # @param effective_xlen [Integer] The effective xlen, needed since some fields change location with XLEN. If the field location is not determined by XLEN, then this parameter can be nil
  # @return [Integer] Number of bits in the field
  def width(arch_def, effective_xlen)
    location(arch_def, effective_xlen).size
  end

  # @return [String] Pretty-printed location string
  def location_pretty(arch_def)
    derangeify = proc { |loc|
      return loc.min.to_s if loc.size == 1

      "#{loc.max}:#{loc.min}"
    }
    if dynamic_location?(arch_def)
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
        #{derangeify.call(location(arch_def, 32))} when #{condition.sub('%%', '0')}
        #{derangeify.call(location(arch_def, 64))} when #{condition.sub('%%', '1')}
      LOC
    else
      derangeify.call(location(arch_def, arch_def.config_params["XLEN"]))
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

  # @param arch_def [ArchDef] A configuration
  # @return [Boolean] Whether or not the format of this CSR changes when the effective XLEN changes in some mode
  def format_changes_with_xlen?(arch_def)
    dynamic_length?(arch_def) ||
      implemented_fields(arch_def).any? do |f|
        f.dynamic_location?(arch_def)
      end
  end

  # @param arch_def [ArchDef] A configuration
  # @return [Array<Idl::FunctionDefAst>] List of functions reachable from this CSR's sw_read or a field's sw_wirte function
  def reachable_functions(arch_def)
    fns = []

    if has_custom_sw_read?
      ast = sw_read_ast(arch_def)
      symtab = arch_def.sym_table.deep_clone
      symtab.push
      fns.concat(ast.reachable_functions(symtab))
    end

    implemented_fields(arch_def).each do |field|
      if arch_def.multi_xlen? && format_changes_with_xlen?
        fns.concat(field.reachable_functions(arch_def.sym_table, 32))
        fns.concat(field.reachable_functions(arch_def.sym_table, 64))
      else
        fns.concat(field.reachable_functions(arch_def.sym_table, arch_def.config_params["XLEN"]))
      end
    end

    fns.uniq
  end

  # @param arch_def [ArchDef] A configuration
  # @return [Boolean] Whether or not the length of the CSR depends on a runtime value
  #                   (e.g., mstatus.SXL)
  def dynamic_length?(arch_def)
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

  # @param arch_def [ArchDef] A configuration (can be nil if the lenth is not dependent on a config parameter)
  # @param effective_xlen [Integer] The effective xlen, needed since some fields change location with XLEN. If the field location is not determined by XLEN, then this parameter can be nil
  # @return [Integer] Length, in bits, of the CSR
  def length(arch_def, effective_xlen = nil)
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

  # @return [Integer] The largest length of this CSR in any valid mode/xlen for the config
  def max_length(arch_def)
    case @data["length"]
    when "MXLEN"
      arch_def.config_params["XLEN"]
    when "SXLEN"
      if arch_def.config_params["SXLEN"] == 3264
        raise ArgumentError, "effective_xlen is required when length is dynamic (#{name})" if effective_xlen.nil?

        64
      else
        raise "CSR #{name} is not implemented" if arch_def.implemented_csrs.none? { |c| c.name == name }
        raise "CSR #{name} is not implemented" if arch_def.config_params["SXLEN"].nil?

        arch_def.config_params["SXLEN"]
      end
    when "VSXLEN"
      if arch_def.config_params["VSXLEN"] == 3264
        raise ArgumentError, "effective_xlen is required when length is dynamic (#{name})" if effective_xlen.nil?

        64
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

  # @param arch_def [ArchDef] A configuration
  # @return [String] Pretty-printed length string
  def length_pretty(arch_def)
    if dynamic_length?(arch_def)
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
        #{length(arch_def, 32)} when #{cond.sub('%%', '0')}
        #{length(arch_def, 64)} when #{cond.sub('%%', '1')}
      LENGTH
    else
      "#{length(arch_def)}-bit"
    end
  end

  # list of modes that can potentially access the field
  def modes_with_access
    case @data["priv_mode"]
    when "M"
      ["M"]
    when "S"
      ["M", "S", "VS"]
    when "U"
      ["M", "S", "U", "VS", "VU"]
    when "VS"
      ["M", "S", "VS"]
    else
      raise "unexpected priv mode"
    end
  end

  # parse description field with asciidoctor, and return the HTML result
  #
  # @return [String] Parsed description in HTML
  def description_html
    Asciidoctor.convert description
  end

  # @param arch_Def [ArchDef] A configuration
  # @return [Array<CsrField>] All implemented fields for this CSR at the given effective XLEN, sorted by location (smallest location first)
  #                           Excluded any fields that are defined by unimplemented extensions or a base that is not effective_xlen
  def implemented_fields_for(arch_def, effective_xlen)
    @implemented_fields_for ||= {}
    key = [arch_def.name, effective_xlen].hash

    return @implemented_fields_for[key] unless @implemented_fields_for[key].nil?

    @implemented_fields_for[key] =
      implemented_fields(arch_def).select do |f|
        !f.key?("base") || f.base == effective_xlen
      end
  end

  # @param arch_def [ArchDef] A configuration
  # @return [Array<CsrField>] All implemented fields for this CSR
  #                           Excluded any fields that are defined by unimplemented extensions
  def implemented_fields(arch_def)
    return @implemented_fields unless @implemented_fields.nil?

    implemented_bases =
      if arch_def.config_params["SXLEN"] == 3264 ||
         arch_def.config_params["UXLEN"] == 3264 ||
         arch_def.config_params["VSXLEN"] == 3264 ||
         arch_def.config_params["VUXLEN"] == 3264
        [32, 64]
      else
        [arch_def.config_params["XLEN"]]
      end

    @implemented_fields = fields.select do |f|
      f.exists_in_cfg?(implemented_bases, arch_def.implemented_extensions)
    end
  end

  # @return [Array<CsrField>] All known fields of this CSR
  def fields
    return @fields unless @fields.nil?

    @fields = @data["fields"].map { |_field_name, field_data| CsrField.new(self, field_data) }
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

  # @param arch_def [ArchDef] A configuration
  # @param effective_xlen [Integer] The effective XLEN to apply, needed when field locations change with XLEN in some mode
  # @return [Idl::BitfieldType] A bitfield type that can represent all fields of the CSR
  def bitfield_type(arch_def, effective_xlen = nil)
    Idl::BitfieldType.new(
      "Csr#{name.capitalize}Bitfield",
      length(arch_def, effective_xlen),
      fields.map(&:name),
      fields.map { |f| f.location(arch_def, effective_xlen) }
    )
  end

  # @return [Boolean] true if the CSR has a custom sw_read function
  def has_custom_sw_read?
    @data.key?("sw_read()") && !@data["sw_read()"].empty?
  end

  def sw_read_ast(arch_def)
    return @sw_read_ast unless @sw_read_ast.nil?
    return nil if @data["sw_read()"].nil?

    # now, parse the function
    extra_syms = {
      # all CSR instructions are 32-bit
      "__instruction_encoding_size" =>
        Idl::Var.new("__instruction_encoding_size", Idl::Type.new(:bits, width: 6), 32)
    }

    puts "Compiling CSR[#{name}] sw_read"
    @sw_read_ast = arch_def.idl_compiler.compile_func_body(
      @data["sw_read()"],
      return_type: Idl::Type.new(:bits, width: 128), # big int to hold special return values
      symtab: arch_def.sym_table,
      name: "CSR[#{name}].sw_read()",
      input_file: "CSR #{name}",
      extra_syms:
    )

    puts "done compiling"

    raise "unexpected #{@sw_read_ast.class}" unless @sw_read_ast.is_a?(Idl::FunctionBodyAst)

    @sw_read_ast
  end

  def pruned_sw_read_ast(symtab)
    puts "PRUNING #{name}.sw_read()"
    ast = sw_read_ast(symtab.archdef).prune(symtab)
    puts "done"
    ast
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
  # @param arch_def [ArchDef] A configuration
  # @param effective_xlen [Integer,nil] Effective XLEN to use when CSR length is dynamic
  # @return [Hash] A representation of the WaveDrom drawing for the CSR (should be turned into JSON for wavedrom)
  def wavedrom_desc(arch_def, effective_xlen)
    desc = {
      "reg" => []
    }
    last_idx = -1
    implemented_fields_for(arch_def, effective_xlen).each do |field|

      if field.location(arch_def, effective_xlen).min != last_idx + 1
        # have some reserved space
        desc["reg"] << { "bits" => (field.location(arch_def, effective_xlen).min - last_idx - 1), type: 1 }
      end
      desc["reg"] << { "bits" => field.location(arch_def, effective_xlen).size, "name" => field.name, type: 2 }
      last_idx = field.location(arch_def, effective_xlen).max
    end
    if !implemented_fields_for(arch_def, effective_xlen).empty? && (fields.last.location(arch_def, effective_xlen).max != (length(arch_def, effective_xlen) - 1))
      # reserved space at the end
      desc["reg"] << { "bits" => (length(arch_def, effective_xlen) - 1 - last_idx), type: 1 }
      # desc['reg'] << { 'bits' => 1, type: 1 }
    end
    desc["config"] = { "bits" => length(arch_def, effective_xlen) }
    desc["config"]["lanes"] = length(arch_def, effective_xlen) / 16
    desc
  end

  # @param possible_xlens [Array<Integer>] List of xlens that be used in any implemented mode
  # @param extensions [Array<ExtensionVersion>] List of extensions implemented
  # @return [Boolean] whether or not the instruction is implemented given the supplies config options
  def exists_in_cfg?(possible_xlens, extensions)
    (@data["base"].nil? || (possible_xlens.include? @data["base"])) &&
      extensions.any? { |e| defined_by?(e) }
  end
end

# model of a specific instruction in a specific base (RV32/RV64)
class Instruction < ArchDefObject

  def fill_symtab(global_symtab)
    symtab = global_symtab.deep_clone(clone_values: true)
    symtab.push
    symtab.add(
      "__instruction_encoding_size",
      Idl::Var.new("__instruction_encoding_size", Idl::Type.new(:bits, width:encoding_width.bit_length), encoding_width)
    )
    @encodings[symtab.archdef.config_params["XLEN"]].decode_variables.each do |d|
      qualifiers = []
      qualifiers << :signed if d.sext?
      width = d.size

      var = Idl::Var.new(d.name, Idl::Type.new(:bits, qualifiers:, width:), decode_var: true)
      symtab.add(d.name, var)
    end

    symtab
  end
  private :fill_symtab

  # type check the instruction operation in the context of symtab
  #
  # @param global_symtab [Idl::SymbolTable] A symbol table with global scope populated
  # @raise Idl::AstNode::TypeError if there is a type problem
  def type_check_operation(global_symtab)
    global_symtab.archdef.idl_compiler.type_check(
      operation_ast(global_symtab.archdef.idl_compiler),
      fill_symtab(global_symtab),
      "#{name}.operation()"
    )
  end

  # @param global_symtab [Idl::SymbolTable] Symbol table with global scope populated and a configuration loaded
  # @return [Idl::FunctionBodyAst] A pruned abstract syntax tree
  def pruned_operation_ast(global_symtab)

    type_check_operation(global_symtab)
    puts "PRUNING        #{name}"
    operation_ast(global_symtab.archdef.idl_compiler).prune(fill_symtab(global_symtab))
  end

  # @param symtab [Idl::SymbolTable] Symbol table with global scope populated
  # @return [Array<Idl::FunctionBodyAst>] List of all functions that can be reached from operation()
  def reachable_functions(symtab)
    if @data["operation()"].nil?
      []
    else
      pruned_operation_ast(symtab).reachable_functions(fill_symtab(symtab))
    end
  end

  # @param symtab [Idl::SymbolTable] Symbol table with global scope populated
  # @return [Array<Integer>] List of all exceptions that can be reached from operation()
  def reachable_exceptions(symtab)
    if @data["operation()"].nil?
      []
    else
      puts "Calculating reachable exceptions"
      pruned_operation_ast(symtab).reachable_exceptions(fill_symtab(symtab)).uniq
    end
  end

  # @param symtab [Idl::SymbolTable] Symbol table with global scope populated
  # @return [Array<Integer>] List of all exceptions that can be reached from operation()
  def reachable_exceptions_str(symtab)
    if @data["operation()"].nil?
      []
    else
      puts "Calculating reachable exceptions"

      # RubyProf.start
      etype = symtab.get("ExceptionCode")
      pruned_operation_ast(symtab).reachable_exceptions(fill_symtab(symtab)).uniq.map { |code|
        etype.element_name(code)
      }
      # result = RubyProf.stop
      # RubyProf::FlatPrinter.new(result).print(STDOUT)
    end
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
      decode_vars&.each do |var|
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
      @encodings[32] = Encoding.new(@data["encoding"]["RV32"]["match"], @data["encoding"]["RV32"]["variables"])
      @encodings[64] = Encoding.new(@data["encoding"]["RV64"]["match"], @data["encoding"]["RV64"]["variables"])
    elsif @data.key("base")
      @encodings[@data["base"]] = Encoding.new(@data["encoding"]["match"], @data["encoding"]["variables"])
    else
      @encodings[32] = Encoding.new(@data["encoding"]["match"], @data["encoding"]["variables"])
      @encodings[64] = Encoding.new(@data["encoding"]["match"], @data["encoding"]["variables"])
    end
  end
  private :load_encoding

  # @return [Boolean] whether or not this instruction has different encodings depending on XLEN
  def multi_encoding?
    @data.key?("encoding") && @data["encoding"].key?("RV32")
  end

  # @return [FunctionBodyAst] The abstract syntax tree of the instruction operation
  def operation_ast(idl_compiler)
    return @operation_ast unless @operation_ast.nil?
    return nil if @data["operation()"].nil?

    # now, parse the operation

    puts "compiling #{name} operation"
    @operation_ast = idl_compiler.compile_inst_operation(
      self,
      input_file: "Instruction #{name}"
    )

    raise "unexpected #{@operation_ast.class}" unless @operation_ast.is_a?(Idl::FunctionBodyAst)

    @operation_ast
  end

  # @param base [Integer] 32 or 64
  # @return [Encoding] the encoding
  def encoding(base)
    load_encoding if @encodings.nil?

    @encodings[base]
  end

  # @return [Integer] the width of the encoding
  def encoding_width
    raise "unexpected: encodings are different sizes" unless encoding(32).size == encoding(64).size

    encoding(64).size
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

  # @return [Array<ExtensionRequirement>] Extension requirements for the instruction. If *any* requirement is met, the instruction is defined
  def extension_requirements
    return @extension_requirements unless @extension_requirements.nil?

    @extension_requirements = []
    if @data["definedBy"].is_a?(Array)
      # could be either a single extension with requirement, or a list of requirements
      if extension_requirement?(@data["definedBy"][0])
        @extension_requirements << to_extension_requirement(@data["definedBy"][0])
      else
        # this is a list
        @data["definedBy"].each do |r|
          @extension_requirements << to_extension_requirement(r)
        end
      end
    else
      @extension_requirements << to_extension_requirement(@data["definedBy"])
    end

    raise "empty requirements" if @extension_requirements.empty?

    @extension_requirements
  end

  # @return [Array<ExtensionRequirement>] Extension exclusions for the instruction. If *any* exclusion is met, the instruction is not defined
  def extension_exclusions
    return @extension_exclusions unless @extension_excludions.nil?

    @extension_exclusions = []
    if @data.key?("excludedBy")
      if @data["exludedBy"].is_a?(Array)
        # could be either a single extension with exclusion, or a list of exclusions
        if extension_exclusion?(@data["definedBy"][0])
          @extension_exclusions << to_extension_requirement(@data["excludedBy"][0])
        else
          # this is a list
          @data["excludeddBy"].each do |r|
            @extension_exclusions << to_extension_exclusion(r)
          end
        end
      else
        @extension_exclusions << to_extension_requirement(@data["excludedBy"])
      end
    end

    @extension_exclusions
  end

  # @overload excluded_by?(ext_name, ext_version)
  #   @param ext_name [#to_s] An extension name
  #   @param ext_version [#to_s] A specific extension version
  #   @return [Boolean] Whether or not the instruction is excluded by extesion `ext`, version `version`
  # @overload excluded_by?(ext_version)
  #   @param ext_version [ExtensionVersion] An extension version
  #   @return [Boolean] Whether or not the instruction is excluded by ext_version
  def excluded_by?(*args)
    if args.size == 1
      raise ArgumentError, "Parameter must be an ExtensionVersion" unless args[0].is_a?(ExtensionVersion)

      extension_exclusions.any? do |r|
        r.satisfied_by?(args[0])
      end
    elsif args.size == 2
      raise ArgumentError, "First parameter must be an extension name" unless args[0].respond_to?(:to_s)
      raise ArgumentError, "Second parameter must be an extension version" unless args[0].respond_to?(:to_s)

      extension_exclusions.any? do |r|
        r.satisfied_by?(args[0].to_s, args[1].to_s)
      end
    end
  end

  # @param possible_xlens [Array<Integer>] List of xlens that be used in any implemented mode
  # @param extensions [Array<ExtensionVersion>] List of extensions implemented
  # @return [Boolean] whether or not the instruction is implemented given the supplies config options
  def exists_in_cfg?(possible_xlens, extensions)
    (@data["base"].nil? || (possible_xlens.include? @data["base"])) &&
      extensions.any? { |e| defined_by?(e) } &&
      extensions.none? { |e| excluded_by?(e) }
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

  # @param version_requirement [String] Version requirement
  # @return [Array<ExtensionVersion>] Array of extensions implied by any version of this extension meeting version_requirement
  def implies(version_requirement = ">= 0")
    implications = []
    @data["versions"].each do |v|
      next unless Gem::Requirement.new(version_requirement).satisfied_by?(Gem::Version.new(v["version"]))

      case v["implies"]
      when nil
        next
      when Array
        if v["implies"][0].is_a?(Array)
          implications += v["implies"].map { |e| ExtensionVersion.new(e[0], e[1])}
        else
          implications << ExtensionVersion.new(v["implies"][0], v["implies"][1])
        end
      end
    end
    implications
  end

  # returns the list of instructions implemented by this extension
  def instructions
    arch_def.instructions.select { |i| i.definedBy == name || (i.definedBy.is_a?(Array) && i.definedBy.include?(name)) }
  end
end

# A specific version of an extension
class ExtensionVersion
  # @return [String] Name of the extension
  attr_reader :name

  # @return [Gem::Version] Version of the extension
  attr_reader :version


  # @param name [#to_s] The extension name
  # @param version [Integer,String] The version specifier
  # @param arch_def [ArchDef] The architecture definition
  def initialize(name, version)
    @name = name.to_s
    @version = Gem::Version.new(version)
  end

  # @return Extension the extension object
  def ext(arch_def)
    arch_def.extension(name)
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

# represents an extension requirement, that is an extension name paired with version requirement(s)
class ExtensionRequirement
  # @return [String] Extension name
  attr_reader :name

  # @return [Gem::Requirement] Version requirement
  def version_requirement
    @requirement
  end

  def initialize(name, *requirements)
    @name = name
    requirements =
      if requirements.empty?
        [">= 0"]
      else
        requirements
      end
    @requirement = Gem::Requirement.new(requirements)
  end

  # @overload
  #   @param extension_version [ExtensionVersion] A specific extension version
  #   @return [Boolean] whether or not the extension_version meets this requirement
  # @overload
  #   @param extension_name [#to_s] An extension name
  #   @param extension_name [#to_s] An extension version
  #   @return [Boolean] whether or not the extension_version meets this requirement
  def satisfied_by?(*args)
    if args.size == 1
      raise ArgumentError, "Single argument must be an ExtensionVersion" unless args[0].is_a?(ExtensionVersion)

      args[0].name == @name &&
        @requirement.satisfied_by?(Gem::Version.new(args[0].version))
    elsif args.size == 2
      raise ArgumentError, "First parameter must be an extension name" unless args[0].respond_to?(:to_s)
      raise ArgumentError, "First parameter must be an extension version" unless args[1].respond_to?(:to_s)

      args[0] == @name &&
        @requirement.satisfied_by?(Gem::Version.new(args[1]))
    else
      raise ArgumentError, "Wrong number of args (expecting 1 or 2)"
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

  # @return [Integer] 32 or 64, the XLEN in m-mode
  attr_reader :mxlen

  # hash for Hash lookup
  def hash = @name.hash

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
    @mxlen = @arch_def["params"]["XLEN"]

    @sym_table = Idl::SymbolTable.new(self)
    @idl_compiler = Idl::Compiler.new(self)

    # load the globals into the symbol table
    puts "Compiling globals"
    @global_ast = @idl_compiler.compile_file(
      $root / "arch" / "isa" / "globals.isa",
      @sym_table
    )

    @sym_table.deep_freeze
  end

  def inspect = "ArchDef##{name}"

  # @return [Boolean] true if this configuration can execute in multiple xlen environments
  # (i.e., that in some mode the effective xlen can be either 32 or 64, depending on CSR values)
  def multi_xlen?
    ["SXLEN", "UXLEN", "VSXLEN", "VUXLEN"].any? { |key| @config_params[key] == 3264 }
  end

  # @param mode [String] One of ['M', 'S', 'U', 'VS', 'VU']
  # @return [Boolean] whether or not XLEN can change in the mode
  def multi_xlen_in_mode?(mode)
    case mode
    when "M"
      false
    when "S"
      @config_params["SXLEN"] == 3264
    when "U"
      @config_params["UXLEN"] == 3264
    when "VS"
      @config_params["VSXLEN"] == 3264
    when "VU"
      @config_params["VUXLEN"] == 3264
    else
      raise ArgumentError, "Bad mode"
    end
  end

  # @return [Array<ExtensionVersion>] List of all extensions, with specific versions, that are implemented
  def implemented_extensions
    return @implemented_extensions unless @implemented_extensions.nil?

    @implemented_extensions = []
    @arch_def["implemented_extensions"].each do |e|
      @implemented_extensions << ExtensionVersion.new(e["name"], e["version"])
2    end

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

    @implemented_csrs = csrs.select { |c| @arch_def["implemented_csrs"].include?(c.name) }
  end

  # @return [Array<Csr>] List of all CSRs defined by RISC-V, whether or not they are implemented
  def csrs
    return @csrs unless @csrs.nil?

    @csrs = @arch_def["csrs"].map do |_csr_name, csr_data|
      Csr.new(csr_data)
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

    @instructions = @arch_def["instructions"].map do |_inst_name, inst_data|
      Instruction.new(inst_data)
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

  # @return [Array<FuncDefAst>] List of all reachable IDL functions for the config
  def implemented_functions
    return @implemented_functions unless @implemented_functions.nil?

    @implemented_functions = []

    implemented_instructions.each do |inst|
      inst_funcs = inst.reachable_functions(sym_table)
      inst_funcs.each do |f|
        @implemented_functions << f unless @implemented_functions.any? { |i| i.name == f.name }
      end
    end

    implemented_csrs.each do |csr|
      csr_funcs = csr.reachable_functions(self)
      csr_funcs.each do |f|
        @implemented_functions << f unless @implemented_functions.any? { |i| i.name == f.name }
      end
    end

    @implemented_functions
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
        "%%LINK%csr_field;#{csr_name}.#{field_name};#{csr_name}.#{field_name}%%"
      elsif !csr.nil?
        "%%LINK%csr;#{csr_name};#{csr_name}%%"
      elsif inst(name.downcase)
        "%%LINK%inst;#{name};#{name}%%"
      elsif extension(name)
        "%%LINK%ext;#{name};#{name}%%"
      else
        match
      end
    end
  end
end

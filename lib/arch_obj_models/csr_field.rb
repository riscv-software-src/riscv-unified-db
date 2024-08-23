# frozen_string_literal: true

require_relative "obj"

# A CSR field object
class CsrField < ArchDefObject
  # @return [Csr] The Csr that defines this field
  attr_reader :parent

  # @!attribute field
  #  @return [CsrField] The field being aliased
  # @!attribute range
  #  @return [Range] Range of the aliased field that is being pointed to
  Alias = Struct.new(:field, :range)

  # @return [Integer] The base XLEN required for this CsrField to exist. One of [32, 64]
  # @return [nil] if the CsrField exists in any XLEN
  def base
    @data["base"]
  end

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
      (@data["base"].nil? || possible_xlens.include?(@data["base"])) &&
      (@data["definedBy"].nil? || extensions.any? { |e| defined_by?(e) } )
  end

  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the type() function
  # @return [nil] if the type property is not a function
  # @param idl_compiler [Idl::Compiler] A compiler
  def type_ast(idl_compiler)
    return @type_ast unless @type_ast.nil?
    return nil if @data["type()"].nil?

    @type_ast = idl_compiler.compile_func_body(
      @data["type()"],
      name: "CSR[#{name}].type()",
      input_file: csr.__source,
      input_line: csr.source_line("fields", name, "type()"),
      type_check: false
    )

    raise "unexpected #{@type_ast.class}" unless @type_ast.is_a?(Idl::FunctionBodyAst)

    @type_ast
  end

  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the type() function, after it has been type checked
  # @return [nil] if the type property is not a function
  # @param idl_compiler [Idl::Compiler] A compiler
  def type_checked_type_ast(arch_def)
    @type_checked_type_asts ||= {}
    ast = @type_checked_type_asts[arch_def.name]
    return ast unless ast.nil?

    symtab = arch_def.sym_table.deep_clone
    symtab.push
    # all CSR instructions are 32-bit
    symtab.add(
      "__expected_return_type",
      Idl::Type.new(:enum_ref, enum_class: arch_def.sym_table.get("CsrFieldType"))
    )

    ast = type_ast(arch_def.idl_compiler)
    arch_def.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].type()"
    )
    @type_checked_type_asts[arch_def.name] = ast
  end

  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the type() function, after it has been type checked and pruned
  # @return [nil] if the type property is not a function
  # @param idl_compiler [Idl::Compiler] A compiler
  def pruned_type_ast(arch_def)
    @pruned_type_asts ||= {}
    ast = @pruned_type_asts[arch_def.name]
    return ast unless ast.nil?

    ast = type_checked_type_ast(arch_def).prune(arch_def.sym_table.deep_clone)

    symtab = arch_def.sym_table.deep_clone
    symtab.push
    # all CSR instructions are 32-bit
    symtab.add(
      "__expected_return_type",
      Idl::Type.new(:enum_ref, enum_class: arch_def.sym_table.get("CsrFieldType"))
    )

    arch_def.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].type()"
    )
    @pruned_type_asts[arch_def.name] = ast
  end

  # returns the definitive type for a configuration
  #
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
      elsif arch_def.is_a?(ImplArchDef)
        # the type is config-specific...
        idl = @data["type()"]
        raise "type() is nil for #{csr.name}.#{name} #{@data}?" if idl.nil?

        sym_table = arch_def.sym_table.deep_clone(clone_values: true)
        sym_table.push # for consistency with template functions

        begin
          case pruned_type_ast(arch_def).return_value(sym_table)
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
      else
        raise "arch def is generic, can't know type exactly"
      end
    @type_cache[arch_def] = type
  end

  # @return [String] A pretty-printed type string
  def type_pretty(arch_def)
    if arch_def.is_a?(ImplArchDef)
      type(arch_def)
    else
      if @data.key?("type")
        @data["type"]
      else
        @data["type()"]
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

  # @return [Array<Idl::FunctionDefAst>] List of functions called thorugh this field
  # @param archdef [ImplArchDef] a configuration
  # @Param effective_xlen [Integer] 32 or 64; needed because fields can change in different XLENs
  def reachable_functions(archdef, effective_xlen)
    return @reachable_functions unless @reachable_functions.nil?

    fns = []
    if has_custom_sw_write?
      ast = pruned_sw_write_ast(archdef, effective_xlen)
      unless ast.nil?
        symtab = archdef.sym_table.deep_clone
        symtab.push
        symtab.add("csr_value", Idl::Var.new("csr_value", csr.bitfield_type(symtab.archdef, effective_xlen)))

        fns.concat ast.reachable_functions(symtab)
      end
    end
    if @data.key?("type()")
      ast = pruned_type_ast(archdef)
      unless ast.nil?
        fns.concat ast.reachable_functions(archdef.sym_table.deep_clone.push)
      end
    end
    if @data.key?("reset_value()")
      ast = pruned_reset_value_ast(archdef)
      unless ast.nil?
        fns.concat ast.reachable_functions(archdef.sym_table.deep_clone.push)
      end
    end

    @reachable_functions = fns.uniq
  end

  # @return [Array<Idl::FunctionDefAst>] List of functions called thorugh this field, irrespective of context
  # @param archdef [ArchDef] Architecture definition
  def reachable_functions_unevaluated(archdef)
    return @reachable_functions_unevaluated unless @reachable_functions_unevaluated.nil?

    fns = []
    if has_custom_sw_write?
      ast = sw_write_ast(archdef.idl_compiler)
      unless ast.nil?
        fns.concat ast.reachable_functions_unevaluated(archdef)
      end
    end
    if @data.key?("type()")
      ast = type_ast(archdef.idl_compiler)
      unless ast.nil?
        fns.concat ast.reachable_functions_unevaluated(archdef)
      end
    end
    if @data.key?("reset_value()")
      ast = reset_value_ast(archdef.idl_compiler)
      unless ast.nil?
        fns.concat ast.reachable_functions_unevalutated(archdef)
      end
    end

    @reachable_functions_unevaluated = fns.uniq
  end

  # @return [Csr] Parent CSR for this field
  alias csr parent

  # @param arch_def [ArchDef] A configuration
  # @return [Boolean] Whether or not the location of the field changes dynamically
  #                   (e.g., based on mstatus.SXL) in the configuration
  def dynamic_location?(arch_def)
    if arch_def.is_a?(ImplArchDef)
      unless @data["location_rv32"].nil?
        csr.modes_with_access.each do |mode|
          return true if arch_def.multi_xlen_in_mode?(mode)
        end
      end
      false
    else
      !@data["location_rv32"].nil?
    end
  end

  # @param arch_def [IdL::Compiler] A compiler
  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the reset_value function
  # @return [nil] If the reset_value is not a function
  def reset_value_ast(idl_compiler)
    return @reset_value_ast unless @reset_value_ast.nil?
    return nil unless @data.key?("reset_value()")

    @reset_value_ast = idl_compiler.compile_func_body(
      @data["reset_value()"],
      return_type: Idl::Type.new(:bits, width: 64),
      name: "CSR[#{parent.name}].#{name}.reset_value()",
      input_file: csr.__source,
      input_line: csr.source_line("fields", name, "reset_value()"),
      type_check: false
    )
  end

  # @param arch_def [ImplArchDef] A config
  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the reset_value function, after being type checked
  # @return [nil] If the reset_value is not a function
  def type_checked_reset_value_ast(arch_def)
    @type_checked_reset_value_asts ||= {}
    ast = @type_checked_reset_value_asts[arch_def.name]
    return ast unless ast.nil?

    return nil unless @data.key?("reset_value()")

    ast = reset_value_ast(arch_def.idl_compiler)

    symtab = arch_def.sym_table.deep_clone
    symtab.push
    symtab.add("__expected_return_type", Idl::Type.new(:bits, width: 64))
    arch_def.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{csr.name}].reset_value()"
    )
    @type_checked_reset_value_asts[arch_def.name] = ast
  end

  # @param arch_def [ImplArchDef] A config
  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the reset_value function, type checked and pruned
  # @return [nil] If the reset_value is not a function
  def pruned_reset_value_ast(arch_def)
    @pruned_reset_value_asts ||= {}
    ast = @pruned_reset_value_asts[arch_def.name]
    return ast unless ast.nil?

    return nil unless @data.key?("reset_value()")

    ast = type_checked_reset_value_ast(arch_def)

    symtab = arch_def.sym_table.deep_clone
    symtab.push
    symtab.add("__expected_return_type", Idl::Type.new(:bits, width: 64))

    ast = ast.prune(symtab)

    symtab = arch_def.sym_table.deep_clone
    symtab.push
    symtab.add("__expected_return_type", Idl::Type.new(:bits, width: 64))
    arch_def.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{csr.name}].reset_value()"
    )

    @type_checked_reset_value_asts[arch_def.name] = ast
  end

  # @param arch_def [ArchDef] A config
  # @return [Integer] The reset value of this field
  # @return [String]  The string 'UNDEFINED_LEGAL' if, for this config, there is no defined reset value
  def reset_value(arch_def)
    if !@reset_value_cache.nil? && @reset_value_cache.key?(arch_def)
      return @reset_value_cache[arch_def]
    end

    @reset_value_cache ||= {}

    @reset_value_cache[arch_def] =
      if @data.key?("reset_value")
        @data["reset_value"]
      else
        symtab = arch_def.sym_table.deep_clone
        symtab.push
        val = pruned_reset_value_ast(arch_def).return_value(symtab)
        val = "UNDEFINED_LEGAL" if val == 0x1_0000_0000_0000_0000
        val
      end
  end

  def reset_value_pretty(arch_def)
    if arch_def.is_a?(ImplArchDef)
      reset_value(arch_def)
    else
      if @data.key?("reset_value")
        @data["reset_value"]
      else
        @data["reset_value()"]
      end
    end
  end

  # @return [Boolean] true if the CSR field has a custom sw_write function
  def has_custom_sw_write?
    @data.key?("sw_write(csr_value)") && !@data["sw_write(csr_value)"].empty?
  end

  # @return [FunctionBodyAst] The abstract syntax tree of the sw_write() function, after being type checked
  # @param effective_xlen [Integer] 32 or 64; the effective XLEN to evaluate this field in (relevant when fields move in different XLENs)
  # @param arch_def [ImplArchDef] A configuration
  def type_checked_sw_write_ast(arch_def, effective_xlen)
    @type_checked_sw_write_asts ||= {}
    ast = @type_checked_sw_write_asts[arch_def.name]
    return ast unless ast.nil?

    return nil unless @data.key?("sw_write(csr_value)")

    symtab = arch_def.sym_table.deep_clone
    symtab.push
    # all CSR instructions are 32-bit
    symtab.add(
      "__instruction_encoding_size",
      Idl::Var.new("__instruction_encoding_size", Idl::Type.new(:bits, width: 6), 32)
    )
    symtab.add(
      "__expected_return_type",
      Idl::Type.new(:bits, width: 128) # to accomodate special return values (e.g., UNDEFIEND_LEGAL_DETERMINISITIC)
    )
    symtab.add(
      "csr_value",
      Idl::Var.new("csr_value", csr.bitfield_type(arch_def, effective_xlen))
    )

    ast = sw_write_ast(arch_def.idl_compiler)
    arch_def.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].sw_write()"
    )
    @type_checked_sw_write_asts[arch_def.name] = ast
  end

  # @return [Idl::FunctionBodyAst] The abstract syntax tree of the sw_write() function
  # @return [nil] If there is no sw_write() function
  # @param idl_compiler [Idl::Compiler] A compiler
  def sw_write_ast(idl_compiler)
    return @sw_write_ast unless @sw_write_ast.nil?
    return nil if @data["sw_write(csr_value)"].nil?

    # now, parse the function
    @sw_write_ast = idl_compiler.compile_func_body(
      @data["sw_write(csr_value)"],
      return_type: Idl::Type.new(:bits, width: 128), # big int to hold special return values
      name: "CSR[#{csr.name}].#{name}.sw_write(csr_value)",
      input_file: csr.source_line("fields", name, "sw_write(csr_value)"),
      type_check: false
    )

    raise "unexpected #{@sw_write_ast.class}" unless @sw_write_ast.is_a?(Idl::FunctionBodyAst)

    @sw_write_ast
  end

  # @return [Idl::FunctionBodyAst] The abstract syntax tree of the sw_write() function, type checked
  # @return [nil] if there is no sw_write() function
  # @param effective_xlen [Integer] effective xlen, needed because fields can change in different bases
  # @param arch_def [ImplArchDef] A configuration
  def pruned_sw_write_ast(arch_def, effective_xlen)
    @pruned_sw_write_asts ||= {}
    ast = @pruned_sw_write_asts[arch_def.name]
    return ast unless ast.nil?

    return nil unless @data.key?("sw_write(csr_value)")

    symtab = arch_def.sym_table.deep_clone
    symtab.push
    # all CSR instructions are 32-bit
    symtab.add(
      "__instruction_encoding_size",
      Idl::Var.new("__instruction_encoding_size", Idl::Type.new(:bits, width: 6), 32)
    )
    symtab.add(
      "__expected_return_type",
      Idl::Type.new(:bits, width: 128)
    )
    symtab.add(
      "csr_value",
      Idl::Var.new("csr_value", csr.bitfield_type(arch_def, effective_xlen))
    )

    ast = type_checked_sw_write_ast(arch_def, effective_xlen).prune(symtab)

    arch_def.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].sw_write(csr_value)"
    )
    @pruned_sw_write_asts[arch_def.name] = ast
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
        raise "Location (#{key} = #{@data[key]}) is past the csr length (#{csr.length(arch_def, effective_xlen)}) in #{csr.name}.#{name}"
      end

      @data[key]..@data[key]
    elsif @data[key].is_a?(String)
      e, s = @data[key].split("-").map(&:to_i)
      raise "Invalid location" if s > e

      if e > csr.length(arch_def, effective_xlen)
        raise "Location (#{key} = #{@data[key]}) is past the csr length (#{csr.length(arch_def, effective_xlen)}) in #{csr.name}.#{name}"
      end

      s..e
    end
  end

  # @return [Boolean] Whether or not this field only exists when XLEN == 64
  def base64_only? = @data.key?("base") && @data["base"] == 64

  # @return [Boolean] Whether or not this field only exists when XLEN == 32
  def base32_only? = @data.key?("base") && @data["base"] == 32

  def defined_in_base32? = @data["base"].nil? || @data["base"] == 32
  def defined_in_base64? = @data["base"].nil? || @data["base"] == 64

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
      if arch_def.is_a?(ImplArchDef)
        derangeify.call(location(arch_def, arch_def.param_values["XLEN"]))
      else
        derangeify.call(location(arch_def, nil))
      end
    end
  end

  TYPE_DESC_MAP = {
    "RO" =>
      <<~DESC,
        *Read-Only*

        Field has a hardwired value that does not change.
        Writes to an RO field are ignored.
      DESC
    "RO-H" =>
      <<~DESC,
        *Read-Only with Hardware update*

        Writes are ignored.
        Reads reflect a value dynamically generated by hardware.
      DESC
    "RW" =>
      <<~DESC,
        *Read-Write*

        Field is writable by software.
        Any value that fits in the field is acceptable and shall be retained for subsequent reads.
      DESC
    "RW-R" =>
      <<~DESC,
        *Read-Write Restricted*

        Field is writable by software.
        Only certain values are legal.
        Writing an illegal value into the field is ignored, and the field retains its prior state.
      DESC
    "RW-H" =>
      <<~DESC,
        *Read-Write with Hardware update*

        Field is writable by software.
        Any value that fits in the field is acceptable.
        Hardware also updates the field without an explicit software write.
      DESC
    "RW-RH" =>
      <<~DESC
        *Read-Write Restricted with Hardware update*

        Field is writeable by software.
        Only certain values are legal.
        Writing an illegal value into the field is ignored, such that the field retains its prior state.
        Hardware also updates the field without an explicit software write.)
      DESC
  }.freeze

  # @return [String] Long description of the field type
  def type_desc(arch_def)
    TYPE_DESC_MAP[type(arch_def)]
  end
end
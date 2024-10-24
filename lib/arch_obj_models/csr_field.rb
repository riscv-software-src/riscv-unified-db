# frozen_string_literal: true

require_relative "obj"

require_relative "../idl/passes/gen_option_adoc"

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
  def exists_in_cfg?(arch_def)
    if arch_def.fully_configured?
      parent.exists_in_cfg?(arch_def) &&
        (@data["base"].nil? || arch_def.possible_xlens.include?(@data["base"])) &&
        (@data["definedBy"].nil? || arch_def.implemented_extensions.any? { |ext_ver| defined_by?(ext_ver) })
    else
      raise "unexpected type" unless arch_def.partially_configured?

      parent.exists_in_cfg?(arch_def) &&
        (@data["base"].nil? || arch_def.possible_xlens.include?(@data["base"])) &&
        (@data["definedBy"].nil? || arch_def.prohibited_extensions.none? { |ext_ver| defined_by?(ext_ver) })
    end
  end

  # @return [Boolean] For a partially configured arch_def, whether or not the field is optional (not mandatory or prohibited)
  def optional_in_cfg?(arch_def)
    raise "optional_in_cfg? should only be called on a partially configured arch_def" unless arch_def.partially_configured?

    exists_in_cfg?(arch_def) &&
      (
        parent.optional_in_cfg?(arch_def) ||
        (data["definedBy"].nil? || arch_def.mandatory_extensions.all? do |ext_req|
          ext_req.satisfying_versions(arch_def).none? { |ext_ver| defined_by?(ext_ver) }
        end)
      )
  end

  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the type() function
  # @return [nil] if the type property is not a function
  # @param symtab [SymbolTable] Symbol table with execution context
  def type_ast(symtab)
    return @type_ast unless @type_ast.nil?
    return nil if @data["type()"].nil?

    @type_ast = symtab.archdef.idl_compiler.compile_func_body(
      @data["type()"],
      name: "CSR[#{csr.name}].#{name}.type()",
      input_file: csr.__source,
      input_line: csr.source_line("fields", name, "type()"),
      symtab:,
      type_check: false
    )

    raise "unexpected #{@type_ast.class}" unless @type_ast.is_a?(Idl::FunctionBodyAst)

    @type_ast
  end

  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the type() function, after it has been type checked
  # @return [nil] if the type property is not a function
  # @param symtab [Idl::SymbolTable] Symbol table
  def type_checked_type_ast(symtab)
    @type_checked_type_asts ||= {}
    ast = @type_checked_type_asts[symtab.hash]
    return ast unless ast.nil?

    symtab_hash = symtab.hash

    symtab = symtab.global_clone

    symtab.push(ast)
    # all CSR instructions are 32-bit
    symtab.add(
      "__expected_return_type",
      Idl::Type.new(:enum_ref, enum_class: symtab.get("CsrFieldType"))
    )

    ast = type_ast(symtab)
    symtab.archdef.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].type()"
    )
    symtab.pop
    symtab.release

    @type_checked_type_asts[symtab_hash] = ast
  end

  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the type() function, after it has been type checked and pruned
  # @return [nil] if the type property is not a function
  # @param symtab [Idl::SymbolTable] Global symbols
  def pruned_type_ast(symtab)
    @pruned_type_asts ||= {}
    ast = @pruned_type_asts[symtab.hash]
    return ast unless ast.nil?

    ast = type_checked_type_ast(symtab).prune(symtab.deep_clone)

    symtab_hash = symtab.hash
    symtab = symtab.global_clone
    symtab.push(ast)
    # all CSR instructions are 32-bit
    symtab.add(
      "__expected_return_type",
      Idl::Type.new(:enum_ref, enum_class: symtab.get("CsrFieldType"))
    )

    ast.freeze_tree(symtab)

    symtab.archdef.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].type()"
    )
    symtab.pop
    symtab.release
    @pruned_type_asts[symtab_hash] = ast
  end

  # returns the definitive type for a configuration
  #
  # @param symtab [SymbolTable] Symbol table
  # @return [String]
  #    The type of the field. One of:
  #      'RO'    => Read-only
  #      'RO-H'  => Read-only, with hardware update
  #      'RW'    => Read-write
  #      'RW-R'  => Read-write, with a restricted set of legal values
  #      'RW-H'  => Read-write, with a hardware update
  #      'RW-RH' => Read-write, with a hardware update and a restricted set of legal values
  def type(symtab)
    raise ArgumentError, "Argument 1 should be a symtab" unless symtab.is_a?(Idl::SymbolTable)

    unless @type_cache.nil?
      raise "Different archdef for type #{@type_cache.keys},  #{symtab.archdef}" unless @type_cache.key?(symtab.archdef)

      return @type_cache[symtab.archdef]
    end

    type =
      if @data.key?("type")
        @data["type"]
      else
        # the type is config-specific...
        idl = @data["type()"]
        raise "type() is nil for #{csr.name}.#{name} #{@data}?" if idl.nil?

        

        # value_result = Idl::AstNode.value_try do
        ast = type_checked_type_ast(symtab)
        begin
          symtab = symtab.global_clone

          symtab.push(ast)
          type =  case ast.return_value(symtab)
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
        ensure
          symtab.pop
          symtab.release
        end
        type
        # end
        # Idl::AstNode.value_else(value_result) do
        #   warn "In parsing #{csr.name}.#{name}::type()"
        #   raise "  Return of type() function cannot be evaluated at compile time"
        #   Idl::AstNode.value_error ""
        # end
      end

    @type_cache ||= {}
    @type_cache[symtab.archdef] = type
  end

  # @return [String] A pretty-printed type string
  def type_pretty(symtab)
    raise ArgumentError, "Expecting SymbolTable" unless symtab.is_a?(Idl::SymbolTable)

    str = nil
    value_result = Idl::AstNode.value_try do
      str = type(symtab)
    end
    Idl::AstNode.value_else(value_result) do
      ast = type_ast(symtab)
      str = ast.gen_option_adoc
    end
    str
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
  # @param archdef [ArchDef] a configuration
  # @Param effective_xlen [Integer] 32 or 64; needed because fields can change in different XLENs
  def reachable_functions(archdef, effective_xlen)
    return @reachable_functions unless @reachable_functions.nil?

    symtab =
      if (archdef.configured?)
        archdef.symtab
      else
        raise ArgumentError, "Must supply effective_xlen for generic ArchDef" if effective_xlen.nil?

        if effective_xlen == 32
          archdef.symtab_32
        else
          archdef.symtab_64
        end
      end

    fns = []
    if has_custom_sw_write?
      ast = pruned_sw_write_ast(archdef, effective_xlen)
      unless ast.nil?
        sw_write_symtab = symtab.deep_clone
        sw_write_symtab.push(ast)
        sw_write_symtab.add("csr_value", Idl::Var.new("csr_value", csr.bitfield_type(symtab.archdef, effective_xlen)))
        fns.concat ast.reachable_functions(sw_write_symtab)
      end
    end
    if @data.key?("type()")
      ast = pruned_type_ast(symtab.deep_clone)
      unless ast.nil?
        fns.concat ast.reachable_functions(symtab.deep_clone.push(ast))
      end
    end
    if @data.key?("reset_value()")
      ast = pruned_reset_value_ast(symtab.deep_clone)
      unless ast.nil?
        fns.concat ast.reachable_functions(symtab.deep_clone.push(ast))
      end
    end

    @reachable_functions = fns.uniq
  end

  # @return [Array<Idl::FunctionDefAst>] List of functions called thorugh this field, irrespective of context
  # @param symtab [SymbolTable]
  def reachable_functions_unevaluated(symtab)
    raise ArgumentError, "Argument should be a symtab" unless symtab.is_a?(Idl::SymbolTable)

    return @reachable_functions_unevaluated unless @reachable_functions_unevaluated.nil?

    fns = []
    if has_custom_sw_write?
      ast = sw_write_ast(symtab)
      unless ast.nil?
        fns.concat ast.reachable_functions_unevaluated(symtab)
      end
    end
    if @data.key?("type()")
      ast = type_ast(symtab)
      unless ast.nil?
        fns.concat ast.reachable_functions_unevaluated(symtab)
      end
    end
    if @data.key?("reset_value()")
      ast = reset_value_ast(symtab)
      unless ast.nil?
        fns.concat ast.reachable_functions_unevalutated(symtab)
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
    # if there is no location_rv32, the the field never changes
    return false unless @data["location"].nil?

    # the field changes *if* some mode with access can change XLEN
    csr.modes_with_access.any? { |mode| arch_def.multi_xlen_in_mode?(mode) }
  end

  # @param arch_def [IdL::Compiler] A compiler
  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the reset_value function
  # @return [nil] If the reset_value is not a function
  def reset_value_ast(symtab)
    raise ArgumentError, "Argument should be a symtab (is a #{symtab.class.name})" unless symtab.is_a?(Idl::SymbolTable)

    return @reset_value_ast unless @reset_value_ast.nil?
    return nil unless @data.key?("reset_value()")

    @reset_value_ast = symtab.archdef.idl_compiler.compile_func_body(
      @data["reset_value()"],
      return_type: Idl::Type.new(:bits, width: 64),
      name: "CSR[#{parent.name}].#{name}.reset_value()",
      input_file: csr.__source,
      input_line: csr.source_line("fields", name, "reset_value()"),
      symtab:,
      type_check: false
    )
  end

  # @param symtab [Idl::SymbolTable] A symbol table with globals
  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the reset_value function, after being type checked
  # @return [nil] If the reset_value is not a function
  def type_checked_reset_value_ast(symtab)
    raise ArgumentError, "Expecting Idl::SymbolTable" unless symtab.is_a?(Idl::SymbolTable)

    @type_checked_reset_value_asts ||= {}
    ast = @type_checked_reset_value_asts[symtab.hash]
    return ast unless ast.nil?

    return nil unless @data.key?("reset_value()")

    ast = reset_value_ast(symtab)

    symtab_hash = symtab.hash
    symtab = symtab.deep_clone
    symtab.push(ast)
    symtab.add("__expected_return_type", Idl::Type.new(:bits, width: 64))
    symtab.archdef.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{csr.name}].reset_value()"
    )
    @type_checked_reset_value_asts[symtab_hash] = ast
  end

  # @param symtab [Idl::SymbolTable] Global symbol table
  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the reset_value function, type checked and pruned
  # @return [nil] If the reset_value is not a function
  def pruned_reset_value_ast(symtab)
    @pruned_reset_value_asts ||= {}
    ast = @pruned_reset_value_asts[symtab.hash]
    return ast unless ast.nil?

    return nil unless @data.key?("reset_value()")

    ast = type_checked_reset_value_ast(symtab)

    symtab_hash = symtab.hash
    symtab = symtab.deep_clone
    symtab.push(ast)
    symtab.add("__expected_return_type", Idl::Type.new(:bits, width: 64))

    ast = ast.prune(symtab)

    symtab.pop

    ast.freeze_tree(symtab)

    symtab.push(ast)
    symtab.add("__expected_return_type", Idl::Type.new(:bits, width: 64))
    symtab.archdef.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{csr.name}].#{name}.reset_value()"
    )

    @type_checked_reset_value_asts[symtab_hash] = ast
  end

  # @param arch_def [ArchDef] A config
  # @return [Integer] The reset value of this field
  # @return [String]  The string 'UNDEFINED_LEGAL' if, for this config, there is no defined reset value
  def reset_value(arch_def, effective_xlen = nil)
    cached_value = @reset_value_cache.nil? ? nil : @reset_value_cache[arch_def]
    return cached_value if cached_value

    @reset_value_cache ||= {}

    @reset_value_cache[arch_def] =
      if @data.key?("reset_value")
        @data["reset_value"]
      else
        symtab =
          if !arch_def.mxlen.nil?
            arch_def.symtab
          else
            raise ArgumentError, "effective_xlen is required when using generic arch_def" if effective_xlen.nil?

            effective_xlen == 32 ? arch_def.symtab_32 : arch_def.symtab_64
          end
        ast = pruned_reset_value_ast(symtab.deep_clone)
        val = ast.return_value(symtab.deep_clone.push(ast))
        val = "UNDEFINED_LEGAL" if val == 0x1_0000_0000_0000_0000
        val
      end
  end

  def dynamic_reset_value?(arch_def)
    return false unless @data["reset_value"].nil?

    value_result = value_try do
      if arch_def.mxlen.nil?
        # need to try with generic symtab_32/symtab_64
        reset_value_32 = reset_value(arch_def, 32)
        reset_value_64 = reset_value(arch_def, 64)
        reset_value_32 != reset_value_64
      else
        # just call the function, see if we get a value error
        reset_value(arch_def)
        false
      end
    end || true
  end

  def reset_value_pretty(arch_def)
    str = nil
    value_result = Idl::AstNode.value_try do
      str =
        if arch_def.mxlen.nil?
          if dynamic_reset_value?(arch_def)
            Idl::AstNode.value_error ""
          else
            reset_value(arch_def, 32) # 32 or 64, doesn't matter
          end
        else
          reset_value(arch_def)
        end
    end
    Idl::AstNode.value_else(value_result) do
      ast = reset_value_ast(arch_def.symtab)
      str = ast.gen_option_adoc
    end
    str
  end

  # @return [Boolean] true if the CSR field has a custom sw_write function
  def has_custom_sw_write?
    @data.key?("sw_write(csr_value)") && !@data["sw_write(csr_value)"].empty?
  end

  # @return [FunctionBodyAst] The abstract syntax tree of the sw_write() function, after being type checked
  # @param effective_xlen [Integer] 32 or 64; the effective XLEN to evaluate this field in (relevant when fields move in different XLENs)
  # @param symtab [Idl::SymbolTable] Symbol table with globals
  def type_checked_sw_write_ast(symtab, effective_xlen)
    @type_checked_sw_write_asts ||= {}
    ast = @type_checked_sw_write_asts[symtab.hash]
    return ast unless ast.nil?

    return nil unless @data.key?("sw_write(csr_value)")

    symtab_hash = symtab.hash
    symtab = symtab.global_clone
    symtab.push(ast)
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
      Idl::Var.new("csr_value", csr.bitfield_type(symtab.archdef, effective_xlen))
    )

    ast = sw_write_ast(symtab)
    symtab.archdef.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{csr.name}].#{name}.sw_write()"
    )
    symtab.pop
    symtab.release
    @type_checked_sw_write_asts[symtab_hash] = ast
  end

  # @return [Idl::FunctionBodyAst] The abstract syntax tree of the sw_write() function
  # @return [nil] If there is no sw_write() function
  # @param archdef [ArchDef] An architecture definition
  def sw_write_ast(symtab)
    raise ArgumentError, "Argument should be a symtab" unless symtab.is_a?(Idl::SymbolTable)

    return @sw_write_ast unless @sw_write_ast.nil?
    return nil if @data["sw_write(csr_value)"].nil?

    # now, parse the function
    @sw_write_ast = symtab.archdef.idl_compiler.compile_func_body(
      @data["sw_write(csr_value)"],
      return_type: Idl::Type.new(:bits, width: 128), # big int to hold special return values
      name: "CSR[#{csr.name}].#{name}.sw_write(csr_value)",
      input_file: csr.__source,
      input_line: csr.source_line("fields", name, "sw_write(csr_value)"),
      symtab:,
      type_check: false
    )

    raise "unexpected #{@sw_write_ast.class}" unless @sw_write_ast.is_a?(Idl::FunctionBodyAst)

    @sw_write_ast
  end

  # @return [Idl::FunctionBodyAst] The abstract syntax tree of the sw_write() function, type checked and pruned
  # @return [nil] if there is no sw_write() function
  # @param effective_xlen [Integer] effective xlen, needed because fields can change in different bases
  # @param arch_def [ArchDef] A configuration
  def pruned_sw_write_ast(arch_def, effective_xlen)
    @pruned_sw_write_asts ||= {}
    ast = @pruned_sw_write_asts[arch_def.name]
    return ast unless ast.nil?

    return nil unless @data.key?("sw_write(csr_value)")

    raise ArgumentError, "arch_def must be configured to prune" if arch_def.unconfigured?

    symtab = arch_def.symtab.global_clone
    symtab.push(ast)
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

    ast = type_checked_sw_write_ast(arch_def.symtab, effective_xlen)
    ast = ast.prune(symtab)
    raise "Symbol table didn't come back at global + 1" unless symtab.levels == 2

    ast.freeze_tree(arch_def.symtab)


    arch_def.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].sw_write(csr_value)"
    )

    symtab.pop
    symtab.release

    @pruned_sw_write_asts[arch_def.name] = ast
  end

  # @param arch_def [ArchDef] A config. May be nil if the location is not configturation-dependent
  # @param effective_xlen [Integer] The effective xlen, needed since some fields change location with XLEN. If the field location is not determined by XLEN, then this parameter can be nil
  # @return [Range] the location within the CSR as a range (single bit fields will be a range of size 1)
  def location(arch_def, effective_xlen = nil)
    key =
      if @data.key?("location")
        "location"
      else
        raise ArgumentError, "The location of #{csr.name}.#{name} changes with XLEN, so effective_xlen must be provided" unless [32, 64].include?(effective_xlen)

        "location_rv#{effective_xlen}"
      end

    raise "Missing location for #{csr.name}.#{name} (#{key})?" unless @data.key?(key)

    if @data[key].is_a?(Integer)
      csr_length = csr.length(arch_def, effective_xlen || @data["base"])
      if csr_length.nil?
        # we don't know the csr length for sure, so we can only check again max_length
        if @data[key] > csr.max_length(arch_def)
          raise "Location (#{key} = #{@data[key]}) is past the max csr length (#{csr.max_length(arch_def)}) in #{csr.name}.#{name}"
        end
      elsif @data[key] > csr_length
        raise "Location (#{key} = #{@data[key]}) is past the csr length (#{csr.length(arch_def, effective_xlen)}) in #{csr.name}.#{name}"
      end

      @data[key]..@data[key]
    elsif @data[key].is_a?(String)
      e, s = @data[key].split("-").map(&:to_i)
      raise "Invalid location" if s > e

      csr_length = csr.length(arch_def, effective_xlen || @data["base"])
      if csr_length.nil?
        # we don't know the csr length for sure, so we can only check again max_length
        if e > csr.max_length(arch_def)
          raise "Location (#{key} = #{@data[key]}) is past the max csr length (#{csr.max_length(arch_def)}) in #{csr.name}.#{name}"
        end
      elsif e > csr_length
        raise "Location (#{key} = #{@data[key]}) is past the csr length (#{csr_length}) in #{csr.name}.#{name}"

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

  def location_cond32
    case csr.priv_mode
    when "M"
      "CSR[misa].MXL == 0"
    when "S"
      "CSR[mstatus].SXL == 0"
    when "VS"
      "CSR[hstatus].VSXL == 0"
    else
      raise "Unexpected priv mode #{csr.priv_mode} for #{csr.name}"
    end
  end

  def location_cond64
    case csr.priv_mode
    when "M"
      "CSR[misa].MXL == 1"
    when "S"
      "CSR[mstatus].SXL == 1"
    when "VS"
      "CSR[hstatus].VSXL == 1"
    else
      raise "Unexpected priv mode #{csr.priv_mode} for #{csr.name}"
    end
  end

  # @return [String] Pretty-printed location string
  def location_pretty(arch_def, effective_xlen = nil)
    derangeify = proc { |loc|
      next loc.min.to_s if loc.size == 1

      "#{loc.max}:#{loc.min}"
    }

    if dynamic_location?(arch_def)
      condition =
        case csr.priv_mode
        when "M"
          "CSR[misa].MXL == %%"
        when "S"
          "CSR[mstatus].SXL == %%"
        when "VS"
          "CSR[hstatus].VSXL == %%"
        else
          raise "Unexpected priv mode #{csr.priv_mode} for #{csr.name}"
        end

      if effective_xlen.nil?
        <<~LOC
          * #{derangeify.call(location(arch_def, 32))} when #{condition.sub('%%', '0')}
          * #{derangeify.call(location(arch_def, 64))} when #{condition.sub('%%', '1')}
        LOC
      else
        derangeify.call(location(arch_def, effective_xlen))
      end
    else
      derangeify.call(location(arch_def, arch_def.mxlen))
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
    TYPE_DESC_MAP[type(arch_def.symtab)]
  end
end
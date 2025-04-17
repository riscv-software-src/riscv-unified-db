# frozen_string_literal: true
# typed: true

require "sorbet-runtime"

require_relative "database_obj"
require_relative "../idl/passes/gen_option_adoc"
require_relative "certifiable_obj"

# A CSR field object
class CsrField < DatabaseObject
  extend T::Sig
  # Add all methods in this module to this type of database object.
  include CertifiableObject

  # @return [Csr] The Csr that defines this field
  sig { returns(Csr) }
  attr_reader :parent

  # @!attribute field
  #  @return [CsrField] The field being aliased
  # @!attribute range
  #  @return [Range] Range of the aliased field that is being pointed to
  Alias = Struct.new(:field, :range)

  # @return [Integer] The base XLEN required for this CsrField to exist. One of [32, 64]
  # @return [nil] if the CsrField exists in any XLEN
  sig { returns(T.nilable(Integer)) }
  def base
    @data["base"]
  end

  # @param parent_csr [Csr] The Csr that defined this field
  # @param field_data [Hash<String,Object>] Field data from the arch spec
  sig { params(parent_csr: Csr, field_name: String, field_data: T::Hash[String, T.untyped]).void }
  def initialize(parent_csr, field_name, field_data)
    super(field_data, parent_csr.data_path, parent_csr.arch)
    @name = field_name
    @parent = parent_csr
  end

  # CSR fields are defined in their parent CSR YAML file
  def __source = @parent.__source

  # CSR field data starts at fields: NAME: with the YAML
  def source_line(*path)
    T.unsafe(self).super("fields", name, *path)
  end

  # For a full config, whether or not the field is implemented
  # For a partial config, whether or the it is possible for the field to be implemented
  #
  # @return [Boolean] True if this field might exist in a config
  sig { params(cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
  def exists_in_cfg?(cfg_arch)
    if cfg_arch.fully_configured?
      parent.exists_in_cfg?(cfg_arch) &&
        (@data["base"].nil? || cfg_arch.possible_xlens.include?(@data["base"])) &&
        (@data["definedBy"].nil? || cfg_arch.transitive_implemented_extension_versions.any? { |ext_ver| defined_by_condition.possibly_satisfied_by?(ext_ver) })
    elsif cfg_arch.partially_configured?
      parent.exists_in_cfg?(cfg_arch) &&
        (@data["base"].nil? || cfg_arch.possible_xlens.include?(@data["base"])) &&
        (@data["definedBy"].nil? || cfg_arch.possible_extension_versions.any? { |ext_ver| defined_by_condition.possibly_satisfied_by?(ext_ver) } )
    else
      true
    end
  end

  # @return [Boolean] For a partially configured cfg_arch, whether or not the field is optional (not mandatory or prohibited)
  sig { params(cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
  def optional_in_cfg?(cfg_arch)
    raise "optional_in_cfg? should only be called on a partially configured cfg_arch" unless cfg_arch.partially_configured?

    exists_in_cfg?(cfg_arch) &&
      (
        if data["definedBy"].nil?
          parent.optional_in_cfg?(cfg_arch)
        else
          cfg_arch.prohibited_extension_versions.none? do |ext_ver|
            defined_by_condition.possibly_satisfied_by?(ext_ver)
          end
        end
      )
  end

  # @return [Boolean] Whether or not the presence of ext_ver affects this CSR Field definition
  #                   This does not take the parent CSR into account, i.e., a field can be unaffected
  #                   by ext_ver even if the parent CSR is affected
  sig { params(ext_ver: ExtensionVersion).returns(T::Boolean) }
  def affected_by?(ext_ver)
    @data["definedBy"].nil? ? false : defined_by_condition.possibly_satisfied_by?(ext_ver)
  end

  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the type() function
  # @return [nil] if the type property is not a function
  sig { returns(T.nilable(Idl::FunctionBodyAst)) }
  def type_ast
    return @type_ast unless @type_ast.nil?
    return nil if @data["type()"].nil?

    idl_code = T.must(@data["type()"])

    @type_ast = @cfg_arch.idl_compiler.compile_func_body(
      idl_code,
      name: "CSR[#{csr.name}].#{name}.type()",
      input_file: csr.__source,
      input_line: csr.source_line("fields", name, "type()"),
      symtab: @cfg_arch.symtab,
      type_check: false
    )

    raise "ast is nil?" if @type_ast.nil?

    raise "unexpected #{@type_ast.class}" unless @type_ast.is_a?(Idl::FunctionBodyAst)

    @type_ast
  end

  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the type() function, after it has been type checked
  # @return [nil] if the type property is not a function
  # @param effective_xlen [32, 64] The effective xlen to evaluate for
  sig { params(effective_xlen: T.nilable(Integer)).returns(T.nilable(Idl::FunctionBodyAst)) }
  def type_checked_type_ast(effective_xlen)
    @type_checked_type_ast ||= { 32 => nil, 64 => nil }
    return @type_checked_type_ast[effective_xlen] unless @type_checked_type_ast[effective_xlen].nil?

    ast = type_ast

    if ast.nil?
      # there is no type() (it must be constant)
      return nil
    end

    symtab = fill_symtab_for_type(effective_xlen, ast)

    symtab.cfg_arch.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].type()"
    )

    symtab.pop
    symtab.release

    @type_checked_type_ast[effective_xlen] = ast
  end

  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the type() function, after it has been type checked and pruned
  # @return [nil] if the type property is not a function
  # @param effective_xlen [32, 64] The effective xlen to evaluate for
  sig { params(effective_xlen: T.nilable(Integer)).returns(T.nilable(Idl::FunctionBodyAst)) }
  def pruned_type_ast(effective_xlen)
    @pruned_type_ast ||= { 32 => nil, 64 => nil }
    return @pruned_type_ast[effective_xlen] unless @pruned_type_ast[effective_xlen].nil?

    ast = type_checked_type_ast(effective_xlen)

    if ast.nil?
      # there is no type() (it must be constant)
      return nil
    end

    symtab = fill_symtab_for_type(effective_xlen, ast)
    ast = ast.prune(symtab)
    symtab.release

    symtab = fill_symtab_for_type(effective_xlen, ast)
    ast.freeze_tree(symtab)

    symtab.cfg_arch.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].type()"
    )

    symtab.pop
    symtab.release

    @pruned_type_ast[effective_xlen] = ast
  end

  # returns the definitive type for a configuration
  #
  # @param effective_xlen [32, 64] The effective xlen to evaluate for
  # @return [String]
  #    The type of the field. One of:
  #      'RO'    => Read-only
  #      'RO-H'  => Read-only, with hardware update
  #      'RW'    => Read-write
  #      'RW-R'  => Read-write, with a restricted set of legal values
  #      'RW-H'  => Read-write, with a hardware update
  #      'RW-RH' => Read-write, with a hardware update and a restricted set of legal values
  # @return [nil] when the type isn't knowable
  sig { params(effective_xlen: T.nilable(Integer)).returns(T.nilable(String)) }
  def type(effective_xlen = nil)
    @type ||= { 32 => nil, 64 => nil }
    return @type[effective_xlen] unless @type[effective_xlen].nil?

    type = T.let(nil, T.untyped)
    type =
      if @data.key?("type")
        @data["type"]
      else
        # the type is config-specific...

        ast = T.must(type_checked_type_ast(effective_xlen))
        begin
          symtab = fill_symtab_for_type(effective_xlen, ast)

          value_result = ast.value_try do
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
          end
          ast.value_else(value_result) do
            type = nil
          end
        ensure
          symtab&.pop
          symtab&.release
        end
        type
        # end
        # Idl::AstNode.value_else(value_result) do
        #   warn "In parsing #{csr.name}.#{name}::type()"
        #   raise "  Return of type() function cannot be evaluated at compile time"
        #   Idl::AstNode.value_error ""
        # end
      end

    @type[effective_xlen] = type
  end

  # @return [String] A pretty-printed type string
  # @param effective_xlen [32, 64] The effective xlen to evaluate for
  sig { params(effective_xlen: T.nilable(Integer)).returns(String) }
  def type_pretty(effective_xlen = nil)
    str = type(effective_xlen)
    if str.nil?
      ast = T.must(type_ast)
      str = ast.gen_option_adoc
    end
    T.must(str)
  end

  # @return [Alias,nil] The aliased field, or nil if there is no alias
  sig { returns(T.nilable(Alias)) }
  def alias
    return @alias unless @alias.nil?

    if @data.key?("alias")
      raise "Can't parse alias" unless data["alias"] =~ /^[a-z][a-z0-9]+\.[A-Z0-9]+(\[([0-9]+)(:[0-9]+)?\])?$/

      csr_name = T.must(Regexp.last_match(1))
      csr_field = Regexp.last_match(2)
      range = Regexp.last_match(3)
      range_start = Regexp.last_match(4)
      range_end = Regexp.last_match(5)

      csr_field = cfg_arch.csr(csr_name).field(csr_field)
      range =
        if range.nil?
          csr_field.location
        elsif range_end.nil?
          (range_start.to_i..range_start.to_i)
        else
          (range_start.to_i..range_end[1..].to_i)
        end
      @alias = Alias.new(csr_field, range)
    end
    @alias
  end

  # @return [Array<Idl::FunctionDefAst>] List of functions called through this field
  # @param cfg_arch [ConfiguredArchitecture] a configuration
  # @Param effective_xlen [Integer] 32 or 64; needed because fields can change in different XLENs
  sig { params(effective_xlen: T.nilable(Integer)).returns(T::Array[Idl::FunctionDefAst]) }
  def reachable_functions(effective_xlen)
    return @reachable_functions unless @reachable_functions.nil?

    fns = []
    if has_custom_sw_write?
      ast = pruned_sw_write_ast(effective_xlen)
      unless ast.nil?
        sw_write_symtab = fill_symtab_for_sw_write(effective_xlen, ast)
        fns.concat ast.reachable_functions(sw_write_symtab)
        sw_write_symtab.release
      end
    end
    if @data.key?("type()")
      ast = pruned_type_ast(effective_xlen)
      unless ast.nil?
        type_symtab = fill_symtab_for_type(effective_xlen, ast)
        fns.concat ast.reachable_functions(type_symtab)
        type_symtab.release
      end
    end
    if @data.key?("reset_value()")
      ast = pruned_reset_value_ast
      unless ast.nil?
        symtab = fill_symtab_for_reset(ast)
        fns.concat ast.reachable_functions(symtab)
        symtab.release
      end
    end

    @reachable_functions = fns.uniq
  end

  # @return [Csr] Parent CSR for this field
  alias csr parent

  # @return [Boolean] Whether or not the location of the field changes dynamically
  #                   (e.g., based on mstatus.SXL) in the configuration
  sig { returns(T::Boolean) }
  def dynamic_location?
    # if there is no location_rv32, the the field never changes
    return false unless @data["location"].nil?

    # the field changes *if* some mode with access can change XLEN
    csr.modes_with_access.any? { |mode| @cfg_arch.multi_xlen_in_mode?(mode) }
  end

  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the reset_value function
  # @return [nil] If the reset_value is not a function
  sig { returns(T.nilable(Idl::FunctionBodyAst)) }
  def reset_value_ast
    return @reset_value_ast unless @reset_value_ast.nil?
    return nil unless @data.key?("reset_value()")

    @reset_value_ast = cfg_arch.idl_compiler.compile_func_body(
      @data["reset_value()"],
      return_type: Idl::Type.new(:bits, width: max_width),
      name: "CSR[#{parent.name}].#{name}.reset_value()",
      input_file: csr.__source,
      input_line: csr.source_line("fields", name, "reset_value()"),
      symtab: cfg_arch.symtab,
      type_check: false
    )
  end

  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the reset_value function, after being type checked
  # @return [nil] If the reset_value is not a function
  sig { returns(T.nilable(Idl::FunctionBodyAst)) }
  def type_checked_reset_value_ast
    return @type_checked_reset_value_ast unless @type_checked_reset_value_ast.nil?

    return nil unless @data.key?("reset_value()")

    ast = reset_value_ast

    symtab = fill_symtab_for_reset(ast)
    cfg_arch.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{csr.name}].reset_value()"
    )
    symtab.release

    @type_checked_reset_value_ast = ast
  end

  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the reset_value function, type checked and pruned
  # @return [nil] If the reset_value is not a function
  sig { returns(T.nilable(Idl::FunctionBodyAst)) }
  def pruned_reset_value_ast
    return @pruned_reset_value_ast unless @pruned_reset_value_ast.nil?

    return nil unless @data.key?("reset_value()")

    ast = T.must(type_checked_reset_value_ast)

    symtab = fill_symtab_for_reset(ast)
    ast = ast.prune(symtab)
    symtab.pop
    ast.freeze_tree(symtab)
    symtab.release

    @pruned_reset_value_ast = ast
  end

  # @return [Integer] The reset value of this field
  # @return [String]  The string 'UNDEFINED_LEGAL' if, for this config, there is no defined reset value
  def reset_value
    defer :reset_value do
      if @data.key?("reset_value")
        @data["reset_value"]
      else
        ast = T.must(pruned_reset_value_ast)
        symtab = fill_symtab_for_reset(ast)
        val = T.let(nil, T.untyped)
        value_result = Idl::AstNode.value_try do
          val = ast.return_value(symtab)
        end
        Idl::AstNode.value_else(value_result) do
          val = "UNDEFINED_LEGAL"
        end
        val = "UNDEFINED_LEGAL" if val == 0x1_0000_0000_0000_0000
        symtab.release
        val
      end
    end
  end

  sig { returns(T::Boolean) }
  def dynamic_reset_value?
    return false unless @data["reset_value"].nil?

    Idl::AstNode.value_try do
      reset_value
      false
    end || true
  end

  sig { returns(String) }
  def reset_value_pretty
    str = T.let(nil, T.nilable(String))
    value_result = Idl::AstNode.value_try do
      str = reset_value
    end
    Idl::AstNode.value_else(value_result) do
      ast = T.must(reset_value_ast)
      str = ast.gen_option_adoc
    end
    T.must(str).to_s
  end

  # @return [Boolean] true if the CSR field has a custom sw_write function
  sig { returns(T::Boolean) }
  def has_custom_sw_write?
    @data.key?("sw_write(csr_value)") && !@data["sw_write(csr_value)"].empty?
  end

  # @param effective_xlen [Integer] 32 or 64; the effective XLEN to evaluate this field in (relevant when fields move in different XLENs)
  # @param symtab [Idl::SymbolTable] Symbol table with globals
  # @return [FunctionBodyAst] The abstract syntax tree of the sw_write() function, after being type checked
  sig { params(symtab: Idl::SymbolTable, effective_xlen: T.nilable(Integer)).returns(T.nilable(Idl::FunctionBodyAst)) }
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
      Idl::Type.new(:bits, width: 128) # to accommodate special return values (e.g., UNDEFIEND_LEGAL_DETERMINISITIC)
    )
    symtab.add(
      "csr_value",
      Idl::Var.new("csr_value", csr.bitfield_type(symtab.cfg_arch, effective_xlen))
    )

    ast = T.must(sw_write_ast(symtab))
    symtab.cfg_arch.idl_compiler.type_check(
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
  # @param symtab [Idl::SymbolTable] Symbols
  sig { params(symtab: Idl::SymbolTable).returns(T.nilable(Idl::FunctionBodyAst)) }
  def sw_write_ast(symtab)
    return @sw_write_ast unless @sw_write_ast.nil?
    return nil if @data["sw_write(csr_value)"].nil?

    # now, parse the function
    @sw_write_ast = symtab.cfg_arch.idl_compiler.compile_func_body(
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

  sig { params(effective_xlen: T.nilable(Integer), ast: Idl::AstNode).returns(Idl::SymbolTable) }
  def fill_symtab_for_sw_write(effective_xlen, ast)
    symtab = cfg_arch.symtab.global_clone
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
      Idl::Var.new("csr_value", csr.bitfield_type(@cfg_arch, effective_xlen))
    )
    if symtab.get("MXLEN").value.nil?
      symtab.add(
        "MXLEN",
        Idl::Var.new(
          "MXLEN",
          Idl::Type.new(:bits, width: 6, qualifiers: [:const]),
          effective_xlen,
          param: true
        )
      )
    end
    symtab
  end

  sig { params(effective_xlen: T.nilable(Integer), ast: Idl::AstNode).returns(Idl::SymbolTable) }
  def fill_symtab_for_type(effective_xlen, ast)
    symtab = cfg_arch.symtab.global_clone
    symtab.push(ast)

    # all CSR instructions are 32-bit
    symtab.add(
      "__instruction_encoding_size",
      Idl::Var.new("__instruction_encoding_size", Idl::Type.new(:bits, width: 6), 32)
    )
    symtab.add(
      "__expected_return_type",
      Idl::Type.new(:enum_ref, enum_class: symtab.get("CsrFieldType"))
    )
    if symtab.get("MXLEN").value.nil?
      symtab.add(
        "MXLEN",
        Idl::Var.new(
          "MXLEN",
          Idl::Type.new(:bits, width: 6, qualifiers: [:const]),
          effective_xlen,
          param: true
        )
      )
    end

    symtab
  end

  def fill_symtab_for_reset(ast)
    symtab = cfg_arch.symtab.global_clone
    symtab.push(ast)

    symtab.add("__expected_return_type", Idl::Type.new(:bits, width: max_width))

    # XLEN at reset is always mxlen
    symtab.add(
      "__effective_xlen",
      Idl::Var.new("__effective_xlen", Idl::Type.new(:bits, width: 6), cfg_arch.mxlen)
    )

    symtab
  end

  # @return [Idl::FunctionBodyAst] The abstract syntax tree of the sw_write() function, type checked and pruned
  # @return [nil] if there is no sw_write() function
  # @param effective_xlen [Integer] effective xlen, needed because fields can change in different bases
  sig { params(effective_xlen: T.nilable(Integer)).returns(T.nilable(Idl::AstNode)) }
  def pruned_sw_write_ast(effective_xlen)
    return @pruned_sw_write_ast unless @pruned_sw_write_ast.nil?

    return nil unless @data.key?("sw_write(csr_value)")

    ast = T.must(type_checked_sw_write_ast(cfg_arch.symtab, effective_xlen))

    return ast if cfg_arch.unconfigured?

    symtab = fill_symtab_for_sw_write(effective_xlen, ast)

    ast = ast.prune(symtab)
    raise "Symbol table didn't come back at global + 1" unless symtab.levels == 2

    ast.freeze_tree(cfg_arch.symtab)

    cfg_arch.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].sw_write(csr_value)"
    )

    symtab.pop
    symtab.release

    @pruned_sw_write_ast = ast
  end

  # @param cfg_arch [ConfiguredArchitecture] A config. May be nil if the location is not configturation-dependent
  # @param effective_xlen [Integer] The effective xlen, needed since some fields change location with XLEN. If the field location is not determined by XLEN, then this parameter can be nil
  # @return [Range] the location within the CSR as a range (single bit fields will be a range of size 1)
  sig { params(effective_xlen: T.nilable(Integer)).returns(T::Range[Integer]) }
  def location(effective_xlen = nil)
    key =
      if @data.key?("location")
        "location"
      else
        raise ArgumentError, "The location of #{csr.name}.#{name} changes with XLEN, so effective_xlen must be provided" unless [32, 64].include?(effective_xlen)

        "location_rv#{effective_xlen}"
      end

    raise "Missing location for #{csr.name}.#{name} (#{key})?" unless @data.key?(key)

    if @data[key].is_a?(Integer)
      csr_length = csr.length(effective_xlen || @data["base"])
      if csr_length.nil?
        # we don't know the csr length for sure, so we can only check again max_length
        if @data[key] > csr.max_length
          raise "Location (#{key} = #{@data[key]}) is past the max csr length (#{csr.max_length}) in #{csr.name}.#{name}"
        end
      elsif @data[key] > csr_length
        raise "Location (#{key} = #{@data[key]}) is past the csr length (#{csr.length(effective_xlen)}) in #{csr.name}.#{name}"
      end

      @data[key]..@data[key]
    else
      raise "Unexpected location field" unless @data[key].is_a?(String)

      e, s = @data[key].split("-").map(&:to_i)
      raise "Invalid location" if s > e

      csr_length = csr.length(effective_xlen || @data["base"])
      if csr_length.nil?
        # we don't know the csr length for sure, so we can only check again max_length
        if e > csr.max_length
          raise "Location (#{key} = #{@data[key]}) is past the max csr length (#{csr.max_length}) in #{csr.name}.#{name}"
        end
      elsif e > csr_length
        raise "Location (#{key} = #{@data[key]}) is past the csr length (#{csr_length}) in #{csr.name}.#{name}"

      end

      s..e
    end
  end

  # @return [Boolean] Whether or not this field only exists when XLEN == 64
  sig { returns(T::Boolean) }
  def base64_only? = @data.key?("base") && @data["base"] == 64

  # @return [Boolean] Whether or not this field only exists when XLEN == 32
  sig { returns(T::Boolean) }
  def base32_only? = @data.key?("base") && @data["base"] == 32

  sig { returns(T::Boolean) }
  def defined_in_base32? = @data["base"].nil? || @data["base"] == 32

  sig { returns(T::Boolean) }
  def defined_in_base64? = @data["base"].nil? || @data["base"] == 64

  sig { params(xlen: Integer).returns(T::Boolean) }
  def defined_in_base?(xlen) = @data["base"].nil? || @data["base"] == xlen

  # @return [Boolean] Whether or not this field exists for any XLEN
  sig { returns(T::Boolean) }
  def defined_in_all_bases? = @data["base"].nil?

  # @param effective_xlen [Integer] The effective xlen, needed since some fields change location with XLEN. If the field location is not determined by XLEN, then this parameter can be nil
  # @return [Integer] Number of bits in the field
  sig { params(effective_xlen: T.nilable(Integer)).returns(Integer) }
  def width(effective_xlen)
    T.must(location(effective_xlen).size)
  end

  sig { returns(Integer) }
  def max_width
    @max_width ||=
      if base64_only?
        cfg_arch.possible_xlens.include?(64) ? width(64) : 0
      elsif base32_only?
        cfg_arch.possible_xlens.include?(32) ? width(32) : 0
      else
        @cfg_arch.possible_xlens.map do |xlen|
          width(xlen)
        end.max
      end
  end

  sig { returns(String) }
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

  sig { returns(String) }
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

  # @param effective_xlen [Integer or nil] 32 or 64 for fixed xlen, nil for dynamic
  # @return [String] Pretty-printed location string
  sig { params(effective_xlen: T.nilable(Integer)).returns(String) }
  def location_pretty(effective_xlen = nil)
    derangeify = proc { |loc|
      next loc.min.to_s if loc.size == 1

      "#{loc.max}:#{loc.min}"
    }

    if dynamic_location?
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
          * #{derangeify.call(location(32))} when #{condition.sub('%%', '0')}
          * #{derangeify.call(location(64))} when #{condition.sub('%%', '1')}
        LOC
      else
        derangeify.call(location(effective_xlen))
      end
    else
      derangeify.call(location(cfg_arch.mxlen))
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
  sig { params(effective_xlen: T.nilable(Integer)).returns(String) }
  def type_desc(effective_xlen=nil)
    TYPE_DESC_MAP[type(effective_xlen)]
  end
end

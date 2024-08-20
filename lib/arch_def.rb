# frozen_string_literal: true

require "forwardable"
require "ruby-prof"

require_relative "validate"
require_relative "idl"
require_relative "idl/passes/find_return_values"
require_relative "idl/passes/gen_adoc"
require_relative "idl/passes/prune"
require_relative "idl/passes/reachable_functions"
require_relative "idl/passes/reachable_functions_unevaluated"
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
  attr_reader :data, :name, :long_name, :description

  # @return [String] Source file that data for this object can be attributed to
  # @return [nil] if the source isn't known
  def __source
    @data["__source"]
  end

  # The raw content of definedBy in the data.
  # @note Generally, you should prefer to use {#defined_by?}, etc. from Ruby
  #
  # @return [String] An extension name
  # @return [Array(String, Number)] An extension name and versions
  # @return [Array<*>] A list of extension names or extension names and versions
  def definedBy
    @data["definedBy"]
  end

  # @param data [Hash<String,Object>] Hash with fields to be added
  def initialize(data)
    raise "Bad data" unless data.is_a?(Hash)

    @data = data
    @name = data["name"]
    @long_name = data["long_name"]
    @description = data["description"]

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
  # def method_missing(method_name, *args, &block)
  #   if @data.key?(method_name.to_s)
  #     raise "Unexpected argument to '#{method_name}" unless args.empty?

  #     raise "Unexpected block given to '#{method_name}" if block_given?

  #     @data[method_name.to_s]
  #   else
  #     super
  #   end
  # end

  # def respond_to_missing?(method_name, include_private = false)
  #   @data.key?(method_name.to_s) || super
  # end

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

      defined_by.any? do |r|
        r.satisfied_by?(args[0])
      end
    elsif args.size == 2
      raise ArgumentError, "First parameter must be an extension name" unless args[0].respond_to?(:to_s)
      raise ArgumentError, "Second parameter must be an extension version" unless args[0].respond_to?(:to_s)

      defined_by.any? do |r|
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

  # @return [Array<ExtensionRequirement>] Extension(s) that define the instruction. If *any* requirement is met, the instruction is defined.
  def defined_by
    return @defined_by unless @defined_by.nil?

    @defined_by = []
    if @data["definedBy"].is_a?(Array)
      # could be either a single extension with requirement, or a list of requirements
      if extension_requirement?(@data["definedBy"][0])
        @defined_by << to_extension_requirement(@data["definedBy"][0])
      else
        # this is a list
        @data["definedBy"].each do |r|
          @defined_by << to_extension_requirement(r)
        end
      end
    else
      @defined_by << to_extension_requirement(@data["definedBy"])
    end

    raise "empty requirements" if @defined_by.empty?

    @defined_by
  end

  # @return [Integer] THe source line number of +path+ in the YAML file
  # @param path [Array<String>] Path to the scalar you want.
  # @example
  #   yaml = <<~YAML
  #     misa:
  #       sw_read(): ...
  #       fields:
  #         A:
  #           type(): ...
  #   YAML
  #   misa_csr.source_line("sw_read()")  #=> 2
  #   mis_csr.source_line("fields", "A", "type()") #=> 5
  def source_line(*path)

    # find the line number of this operation() in the *original* file
    yaml_filename = @data["__source"]
    raise "No __source for #{name}" if yaml_filename.nil?
    line = nil
    path_idx = 0
    Psych.parse_stream(File.read(yaml_filename), filename: yaml_filename) do |doc|
      mapping = doc.children[0]
      data = mapping.children[1]
      while path_idx < path.size
        idx = 0
        while idx < data.children.size
          if data.children[idx].value == path[path_idx]
            if path_idx == path.size - 1
              line = data.children[idx + 1].start_line
              if data.children[idx + 1].style == Psych::Nodes::Scalar::LITERAL
                line += 1 # the string actually begins on the next line
              end
              return line
            else
              data = data.children[idx + 1]
              path_idx += 1
              break
            end
          end
          idx += 2
        end
      end
    end
    raise "Didn't find key '#{path}' in #{@data['__source']}"
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
  # @param idl_compiler [Idl::SymbolTable] Symbol table with globals
  def type_checked_type_ast(symtab)
    @type_checked_type_asts ||= {}
    ast = @type_checked_type_asts[symtab.hash]
    return ast unless ast.nil?

    symtab_hash = symtab.hash
    symtab = symtab.deep_clone
    symtab.push
    # all CSR instructions are 32-bit
    symtab.add(
      "__expected_return_type",
      Idl::Type.new(:enum_ref, enum_class: symtab.get("CsrFieldType"))
    )

    ast = type_ast(symtab.archdef.idl_compiler)
    symtab.archdef.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].type()"
    )
    @type_checked_type_asts[symtab_hash] = ast
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
        raise Idl::AstNode::ValueError.new(
          type_ast(arch_def.idl_compiler).lineno,
          type_ast(arch_def.idl_compiler).input_file,
          "arch def is generic, can't know type exactly"
        )
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

  # @param symtab [Idl::SymbolTable] A symbol table with globals
  # @return [Idl::FunctionBodyAst] Abstract syntax tree of the reset_value function, after being type checked
  # @return [nil] If the reset_value is not a function
  def type_checked_reset_value_ast(symtab)
    raise ArgumentError, "Expecting Idl::SymbolTable" unless symtab.is_a?(Idl::SymbolTable)

    @type_checked_reset_value_asts ||= {}
    ast = @type_checked_reset_value_asts[symtab.hash]
    return ast unless ast.nil?

    return nil unless @data.key?("reset_value()")

    ast = reset_value_ast(symtab.archdef.idl_compiler)

    symtab_hash = symtab.hash
    symtab = symtab.deep_clone
    symtab.push
    symtab.add("__expected_return_type", Idl::Type.new(:bits, width: 64))
    symtab.archdef.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{csr.name}].reset_value()"
    )
    @type_checked_reset_value_asts[symtab_hash] = ast
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
  # @param symtab [Idl::SymbolTable] Symbol table with globals
  def type_checked_sw_write_ast(symtab, effective_xlen)
    @type_checked_sw_write_asts ||= {}
    ast = @type_checked_sw_write_asts[symtab.hash]
    return ast unless ast.nil?

    return nil unless @data.key?("sw_write(csr_value)")

    symtab_hash = symtab.hash
    symtab = symtab.deep_clone
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
      Idl::Var.new("csr_value", csr.bitfield_type(symtab.archdef, effective_xlen))
    )

    ast = sw_write_ast(symtab.archdef.idl_compiler)
    symtab.archdef.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].sw_write()"
    )
    @type_checked_sw_write_asts[symtab_hash] = ast
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
        raise Idl::AstNode::ValueError.new(
          csr.source_line("fields", name, key), csr.__source,
          "Location (#{key} = #{@data[key]}) is past the csr length (#{csr.length(arch_def, effective_xlen)}) in #{csr.name}.#{name}"
        )
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

# CSR definition
class Csr < ArchDefObject

  # @return [Integer] CSR address (the value passed as an immediate to csrrw, etc.)
  # @return [nil] if the CSR is indirect-accesss-only
  def address
    @data["address"]
  end

  # @return [String] Least-privileged mode that can access this CSR. One of ['m', 's', 'u', 'vs', 'vu']
  def priv_mode
    @data["priv_mode"]
  end

  def long_name
    @data["long_name"]
  end

  # @return [Integer] CSR address in VS/VU mode, if different from other modes
  # @return [nil] If the CSR is not accessible in VS/VU mode, or if it's address does not change in those modes
  def virtual_address
    @data["virtual_address"]
  end

  # @return [Integer] 32 or 64, the XLEN this CSR is exclusively defined in
  # @return [nil] if this CSR is defined in all bases
  def base = @data["base"]

  # @return [Boolean] true if this CSR is defined when XLEN is 32
  def defined_in_base32? = @data["base"].nil? || @data["base"] == 32

  # @return [Boolean] true if this CSR is defined when XLEN is 64
  def defined_in_base64? = @data["base"].nil? || @data["base"] == 64

  # @return [Boolean] true if this CSR is defined regardless of the effective XLEN
  def defined_in_all_bases? = @data["base"].nil?

  # @param arch_def [ArchDef] A configuration
  # @return [Boolean] Whether or not the format of this CSR changes when the effective XLEN changes in some mode
  def format_changes_with_xlen?(arch_def)
    dynamic_length?(arch_def) ||
      implemented_fields(arch_def).any? do |f|
        f.dynamic_location?(arch_def)
      end
  end

  # @param arch_def [ImplArchDef] A configuration
  # @return [Array<Idl::FunctionDefAst>] List of functions reachable from this CSR's sw_read or a field's sw_wirte function
  def reachable_functions(arch_def)
    return @reachable_functions unless @reachable_functions.nil?

    fns = []

    if has_custom_sw_read?
      ast = pruned_sw_read_ast(arch_def)
      symtab = arch_def.sym_table.deep_clone
      symtab.push
      fns.concat(ast.reachable_functions(symtab))
    end

    if arch_def.multi_xlen?
      implemented_fields_for(arch_def, 32).each do |field|
        fns.concat(field.reachable_functions(arch_def, 32))
      end
      implemented_fields_for(arch_def, 64).each do |field|
        fns.concat(field.reachable_functions(arch_def, 64))
      end
    else
      implemented_fields_for(arch_def, arch_def.mxlen).each do |field|
        fns.concat(field.reachable_functions(arch_def, arch_def.mxlen))
      end
    end

    @reachable_functions = fns.uniq
  end

  # @param arch_def [ArchDef] Architecture definition
  # @return [Array<Idl::FunctionDefAst>] List of functions reachable from this CSR's sw_read or a field's sw_wirte function, irrespective of context
  def reachable_functions_unevaluated(arch_def)
    return @reachable_functions_unevaluated unless @reachable_functions_unevaluated.nil?

    fns = []

    if has_custom_sw_read?
      ast = sw_read_ast(arch_def.idl_compiler)
      fns.concat(ast.reachable_functions_unevaluated(arch_def))
    end

    fields.each do |field|
      fns.concat(field.reachable_functions_unevaluated(arch_def))
    end

    @reachable_functions_unevaluated = fns.uniq
  end

  # @param arch_def [ArchDef] A configuration
  # @return [Boolean] Whether or not the length of the CSR depends on a runtime value
  #                   (e.g., mstatus.SXL)
  def dynamic_length?(arch_def)
    return false if @data["length"].is_a?(Integer)

    case @data["length"]
    when "MXLEN"
      if arch_def.is_a?(ImplArchDef)
        false # mxlen can never change
      else
        if @data["base"].nil?
          # don't know MXLEN
          true
        else
          # mxlen is always "base"
          false
        end
      end
    when "SXLEN"
      if arch_def.is_a?(ImplArchDef)
        arch_def.param_values["SXLEN"] == 3264
      else
        if @data["base"].nil?
          # don't know SXLEN
          true
        else
          # sxlen is always "base"
          false
        end
      end
    when "VSXLEN"
      if arch_def.is_a?(ImplArchDef)
        arch_def.param_values["VSXLEN"] == 3264
      else
        if @data["base"].nil?
          # don't know VSXLEN
          true
        else
          # vsxlen is always "base"
          false
        end
      end
    else
      raise "Unexpected length"
    end
    # !@data["length"].is_a?(Integer) && (@data["length"] != "MXLEN")
  end

  # @param arch_def [ArchDef] A configuration (can be nil if the lenth is not dependent on a config parameter)
  # @param effective_xlen [Integer] The effective xlen, needed since some fields change location with XLEN. If the field location is not determined by XLEN, then this parameter can be nil
  # @return [Integer] Length, in bits, of the CSR
  def length(arch_def, effective_xlen = nil)
    case @data["length"]
    when "MXLEN"
      if arch_def.is_a?(ImplArchDef)
        arch_def.mxlen
      else
        if !@data["base"].nil?
          @data["base"]
        else
          # don't know MXLEN
          raise ArgumentError, "effective_xlen is required when length is MXLEN and arch_def is generic" if effective_xlen.nil?

          effective_xlen
        end
      end
    when "SXLEN"
      if arch_def.is_a?(ImplArchDef)
        if arch_def.param_values["SXLEN"] == 3264
          raise ArgumentError, "effective_xlen is required when length is dynamic (#{name})" if effective_xlen.nil?

          effective_xlen
        else
          raise "CSR #{name} is not implemented" if arch_def.implemented_csrs.none? { |c| c.name == name }
          raise "CSR #{name} is not implemented" if arch_def.param_values["SXLEN"].nil?

          arch_def.param_values["SXLEN"]
        end
      else
        if !@data["base"].nil?
          @data["base"]
        else
          # don't know SXLEN
          raise ArgumentError, "effective_xlen is required when length is SXLEN and arch_def is generic" if effective_xlen.nil?

          effective_xlen
        end
      end
    when "VSXLEN"
      if arch_def.is_a?(ImplArchDef)
        if arch_def.param_values["VSXLEN"] == 3264
          raise ArgumentError, "effective_xlen is required when length is dynamic (#{name})" if effective_xlen.nil?

          effective_xlen
        else
          raise "CSR #{name} is not implemented" if arch_def.param_values["VSXLEN"].nil?

          arch_def.param_values["VSXLEN"]
        end
      else
        if !@data["base"].nil?
          @data["base"]
        else
          # don't know VSXLEN
          raise ArgumentError, "effective_xlen is required when length is VSXLEN and arch_def is generic" if effective_xlen.nil?

          effective_xlen
        end
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
      arch_def.param_values["XLEN"]
    when "SXLEN"
      if arch_def.param_values["SXLEN"] == 3264
        raise ArgumentError, "effective_xlen is required when length is dynamic (#{name})" if effective_xlen.nil?

        64
      else
        raise "CSR #{name} is not implemented" if arch_def.implemented_csrs.none? { |c| c.name == name }
        raise "CSR #{name} is not implemented" if arch_def.param_values["SXLEN"].nil?

        arch_def.param_values["SXLEN"]
      end
    when "VSXLEN"
      if arch_def.param_values["VSXLEN"] == 3264
        raise ArgumentError, "effective_xlen is required when length is dynamic (#{name})" if effective_xlen.nil?

        64
      else
        raise "CSR #{name} is not implemented" if arch_def.param_values["VSXLEN"].nil?

        arch_def.param_values["VSXLEN"]
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

    return @implemented_fields_for[key] if @implemented_fields_for.key?(key)

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
      if arch_def.param_values["SXLEN"] == 3264 ||
         arch_def.param_values["UXLEN"] == 3264 ||
         arch_def.param_values["VSXLEN"] == 3264 ||
         arch_def.param_values["VUXLEN"] == 3264
        [32, 64]
      else
        [arch_def.param_values["XLEN"]]
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

  # @return [Array<CsrField>] All known fields of this CSR when XLEN == +effective_xlen+
  # equivalent to {#fields} if +effective_xlen+ is nil
  def fields_for(effective_xlen)
    fields.select { |f| effective_xlen.nil? || !f.key?("base") || f.base == effective_xlen }
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
      fields_for(effective_xlen).map(&:name),
      fields_for(effective_xlen).map { |f| f.location(arch_def, effective_xlen) }
    )
  end

  # @return [Boolean] true if the CSR has a custom sw_read function
  def has_custom_sw_read?
    @data.key?("sw_read()") && !@data["sw_read()"].empty?
  end

  # @return [FunctionBodyAst] The abstract syntax tree of the sw_read() function, after being type checked
  # @param symtab [Idl::SymbolTable] Symbol table with globals
  def type_checked_sw_read_ast(symtab)
    @type_checked_sw_read_asts ||= {}
    ast = @type_checked_sw_read_asts[symtab.hash]
    return ast unless ast.nil?

    symtab_hash = symtab.hash
    symtab = symtab.deep_clone
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

    ast = sw_read_ast(symtab.archdef.idl_compiler)
    symtab.archdef.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].sw_read()"
    )
    @type_checked_sw_read_asts[symtab_hash] = ast
  end

  # @return [FunctionBodyAst] The abstract syntax tree of the sw_read() function
  # @param idl_compiler [Idl::Compiler] A compiler
  def sw_read_ast(idl_compiler)
    return @sw_read_ast unless @sw_read_ast.nil?
    return nil if @data["sw_read()"].nil?

    # now, parse the function
    @sw_read_ast = idl_compiler.compile_func_body(
      @data["sw_read()"],
      return_type: Idl::Type.new(:bits, width: 128), # big int to hold special return values
      name: "CSR[#{name}].sw_read()",
      input_file: source_line("sw_read()"),
      type_check: false
    )

    raise "unexpected #{@sw_read_ast.class}" unless @sw_read_ast.is_a?(Idl::FunctionBodyAst)

    @sw_read_ast
  end

  def pruned_sw_read_ast(arch_def)
    @pruned_sw_read_asts ||= {}
    ast = @pruned_sw_read_asts[arch_def.name]
    return ast unless ast.nil?

    ast = type_checked_sw_read_ast(arch_def).prune(arch_def.sym_table.deep_clone)

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

    arch_def.idl_compiler.type_check(
      ast,
      symtab,
      "CSR[#{name}].sw_read()"
    )
    @pruned_sw_read_asts[arch_def.name] = ast
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
    field_list =
      if arch_def.is_a?(ImplArchDef)
        implemented_fields_for(arch_def, effective_xlen)
      else
        fields
      end
    field_list.each do |field|

      if field.location(arch_def, effective_xlen).min != last_idx + 1
        # have some reserved space
        desc["reg"] << { "bits" => (field.location(arch_def, effective_xlen).min - last_idx - 1), type: 1 }
      end
      desc["reg"] << { "bits" => field.location(arch_def, effective_xlen).size, "name" => field.name, type: 2 }
      last_idx = field.location(arch_def, effective_xlen).max
    end
    if !field_list.empty? && (field_list.last.location(arch_def, effective_xlen).max != (length(arch_def, effective_xlen) - 1))
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

  # @param xlen [Integer] 32 or 64, the target xlen
  # @return [Boolean] whethen or not instruction is defined in base +xlen+
  def defined_in_base?(xlen)
    base == xlen
  end

  # @return [String] Assembly format
  def assembly
    @data["assembly"]
  end

  # @return [Array<ExtensionRequirement>] List of extensions requirements (in addition to one returned by {#defined_by}) that must be met for the instruction to exist
  def extension_requirements
    return [] unless @data.key?("requires")

    @extension_requirements = []
    if @data["requires"].is_a?(Array)
      # could be either a single extension with requirement, or a list of requirements
      if extension_requirement?(@data["requires"][0])
        @extension_requirements << to_extension_requirement(@data["requires"][0])
      else
        # this is a list
        @data["requires"].each do |r|
          @extension_requirements << to_extension_requirement(r)
        end
      end
    else
      @extension_requirements << to_extension_requirement(@data["requires"])
    end

    @extension_requirements
  end

  def fill_symtab(global_symtab, effective_xlen)
    symtab = global_symtab.deep_clone
    symtab.push
    symtab.add(
      "__instruction_encoding_size",
      Idl::Var.new("__instruction_encoding_size", Idl::Type.new(:bits, width: encoding_width.bit_length), encoding_width)
    )
    symtab.add(
      "__effective_xlen",
      Idl::Var.new("__effective_xlen", Idl::Type.new(:bits, width: 7), effective_xlen)
    )
    @encodings[effective_xlen].decode_variables.each do |d|
      qualifiers = []
      qualifiers << :signed if d.sext?
      width = d.size

      var = Idl::Var.new(d.name, Idl::Type.new(:bits, qualifiers:, width:), decode_var: true)
      symtab.add(d.name, var)
    end

    symtab
  end
  private :fill_symtab

  # @param global_symtab [Idl::SymbolTable] Symbol table with global scope populated and a configuration loaded
  # @return [Idl::FunctionBodyAst] A pruned abstract syntax tree
  def pruned_operation_ast(global_symtab, effective_xlen)
    @pruned_asts ||= {}

    arch_def = global_symtab.archdef

    pruned_ast = @pruned_asts[arch_def.name]
    return pruned_ast unless pruned_ast.nil?

    return nil unless @data.key?("operation()")

    type_checked_ast = type_checked_operation_ast(arch_def, effective_xlen)
    pruned_ast = type_checked_ast.prune(fill_symtab(global_symtab, effective_xlen))
    arch_def.idl_compiler.type_check(
      pruned_ast,
      fill_symtab(global_symtab, effective_xlen),
      "#{name}.operation() (pruned)"
    )

    @pruned_asts[arch_def.name] = pruned_ast
  end

  # @param symtab [Idl::SymbolTable] Symbol table with global scope populated
  # @param effective_xlen [Integer] The effective XLEN to evaluate against
  # @return [Array<Idl::FunctionBodyAst>] List of all functions that can be reached from operation()
  def reachable_functions(symtab, effective_xlen)
    if @data["operation()"].nil?
      []
    else
      # RubyProf.start
      pruned_operation_ast(symtab, effective_xlen).reachable_functions(fill_symtab(symtab, effective_xlen))
      # result = RubyProf.stop
      # RubyProf::FlatPrinter.new(result).print($stdout)
      # exit
    end
  end

  # @param symtab [Idl::SymbolTable] Symbol table with global scope populated
  # @param effective_xlen [Integer] Effective XLEN to evaluate against
  # @return [Array<Integer>] List of all exceptions that can be reached from operation()
  def reachable_exceptions(symtab, effective_xlen)
    if @data["operation()"].nil?
      []
    else
      pruned_operation_ast(symtab).reachable_exceptions(fill_symtab(symtab, effective_xlen)).uniq
    end
  end

  # @param symtab [Idl::SymbolTable] Symbol table with global scope populated
  # @param effective_xlen [Integer] Effective XLEN to evaluate against. If nil, evaluate against all valid XLENs
  # @return [Array<Integer>] List of all exceptions that can be reached from operation()
  def reachable_exceptions_str(symtab, effective_xlen=nil)
    if @data["operation()"].nil?
      []
    else
      # RubyProf.start
      etype = symtab.get("ExceptionCode")
      if effective_xlen.nil?
        if symtab.archdef.multi_xlen?
          if base.nil?
            (
              pruned_operation_ast(symtab, 32).reachable_exceptions(fill_symtab(symtab, 32)).uniq.map { |code|
                etype.element_name(code)
              } +
              pruned_operation_ast(symtab, 64).reachable_exceptions(fill_symtab(symtab, 64)).uniq.map { |code|
                etype.element_name(code)
              }
            ).uniq
          else
            pruned_operation_ast(symtab, base).reachable_exceptions(fill_symtab(symtab, base)).uniq.map { |code|
              etype.element_name(code)
            }
          end
        else
          effective_xlen = symtab.archdef.mxlen
          pruned_operation_ast(symtab, effective_xlen).reachable_exceptions(fill_symtab(symtab, effective_xlen)).uniq.map { |code|
            etype.element_name(code)
          }
        end
      else
        pruned_operation_ast(symtab, effective_xlen).reachable_exceptions(fill_symtab(symtab, effective_xlen)).uniq.map { |code|
          etype.element_name(code)
        }
      end
      # result = RubyProf.stop
      # RubyProf::FlatPrinter.new(result).print(STDOUT)
    end
  end

  # @return [ArchDef] The architecture definition
  attr_reader :arch_def

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
    # the name of the field
    attr_reader :name

    # alias of this field, or nil if none
    #
    # used, e.g., when a field reprsents more than one variable (like rs1/rd for destructive instructions)
    attr_reader :alias

    # amount the field is left shifted before use, or nil is there is no left shift
    #
    # For example, if the field is offset[5:3], left_shift is 3
    attr_reader :left_shift

    # @return [Array<Integer>] Specific values that are prohibited for this variable
    attr_reader :excludes

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
        "#{name} != {#{excludes[0].join(',')}}"
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

    def initialize(inst, field_data)
      @inst = inst
      @name = field_data["name"]
      @left_shift = field_data["left_shift"].nil? ? 0 : field_data["left_shift"]
      @sext = field_data["sign_extend"].nil? ? false : field_data["sign_extend"]
      @alias = field_data["alias"].nil? ? nil : field_data["alias"]
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

    # the number of bits in the field, _not including any implicit ones_
    def size_in_encoding
      bits.reduce(0) { |sum, f| sum + (f.is_a?(Integer) ? 1 : f.size) }
    end

    # true if the field should be sign extended
    def sext?
      @sext
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
          so_far += b.size
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

      def to_s
        "#{name}[#{range}]"
      end
    end

    # @param format [String] Format of the encoding, as 0's, 1's and -'s (for decode variables)
    # @param decode_vars [Array<Hash<String,Object>>] List of decode variable defintions from the arch spec
    def initialize(format, decode_vars)
      @format = format

      @opcode_fields = []
      field_chars = []
      @format.chars.each_with_index do |c, idx|
        if c == "-"
          next if field_chars.empty?
          
          field_text = field_chars.join("")
          field_lsb = @format.size - idx
          field_msb = @format.size - idx - 1 + field_text.size
          @opcode_fields << Field.new(field_text, field_lsb..field_msb)

          field_chars.clear
          next
        else
          field_chars << c
        end
      end

      # add the least significant field
      unless field_chars.empty?
        field_text = field_chars.join("")
        @opcode_fields << Field.new(field_text, 0...field_text.size)
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

  # @return [FunctionBodyAst] A type-checked abstract syntax tree of the operation
  # @param idl_compiler [Idl::Compiler] Compiler
  # @param symtab [Idl::SymbolTable] Symbol table with globals
  # @param effective_xlen [Integer] 32 or 64, the effective xlen to type check against
  def type_checked_operation_ast(idl_compiler, symtab, effective_xlen)
    @type_checked_operation_ast ||= {}
    ast = @type_checked_operation_ast[symtab.hash]
    return ast unless ast.nil?

    return nil unless @data.key?("operation()")

    ast = operation_ast(idl_compiler)

    idl_compiler.type_check(ast, fill_symtab(symtab, effective_xlen), "#{name}.operation()")

    @type_checked_operation_ast[symtab.hash] = ast
  end

  # @return [FunctionBodyAst] The abstract syntax tree of the instruction operation
  def operation_ast(idl_compiler)
    return @operation_ast unless @operation_ast.nil?
    return nil if @data["operation()"].nil?

    # now, parse the operation
    @operation_ast = idl_compiler.compile_inst_operation(
      self,
      input_file: @data["__source"],
      input_line: source_line("operation()")
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

# an implmentation parameter/option for an extension
class ExtensionParameter
  # @return [String] Parameter name
  attr_reader :name

  # @return [String] Asciidoc description
  attr_reader :desc

  # @return [Hash] JSON Schema for the parameter value
  attr_reader :schema

  # @return [String] Ruby code to perform validation above and beyond JSON schema
  # @return [nil] If there is no extra validatino
  attr_reader :extra_validation

  # @return [Array<Extension>] The extension(s) that define this parameter
  #
  # Some parameters are defined by multiple extensions (e.g., CACHE_BLOCK_SIZE by Zicbom and Zicboz).
  # When defined in multiple places, the parameter *must* mean the extact same thing.
  attr_reader :exts

  # @returns [Idl::Type] Type of the parameter
  attr_reader :type

  def initialize(name, desc, schema, extra_validation, exts)
    @name = name
    @desc = desc
    @schema = schema
    @extra_validation = extra_validation
    @exts = exts
    begin
      @type = Idl::Type.from_json_schema(@schema).make_const.freeze
    rescue
      warn "While parsing scheme for ExtensionParameter #{ext.name}.#{name}"
      raise
    end
  end
end

class ExtensionParameterWithValue
  # @return [Object] The parameter value
  attr_reader :value

  # @return [String] Parameter name
  def name = @param.name

  # @return [String] Asciidoc description
  def desc = @param.desc

  # @return [Hash] JSON Schema for the parameter value
  def schema = @param.schema

  # @return [String] Ruby code to perform validation above and beyond JSON schema
  # @return [nil] If there is no extra validatino
  def extra_validation = @param.extra_validation

  # @return [Extension] The extension that defines this parameter
  def ext = @param.ext

  def initialize(param, value)
    @param = param
    @value = value
  end
end

# Extension definition
class Extension < ArchDefObject
  # @return [ArchDef] The architecture defintion
  attr_reader :arch_def

  # @return [String] Company that developed the extension
  # @return [nil] if the company isn't known
  def company
    @data["company"]
  end

  # @return [{ name: String, url: String}] The name and URL of a document license the doc falls under
  # @return [nil] if the license isn't known
  def doc_license
    @data["doc_license"]
  end

  # @return [Array<Hash>] versions hash from config
  def versions
    @data["versions"]
  end

  # @return [Array<Hash>] Ratified versions hash from config
  def ratified_versions
    @data["versions"].select { |v| v["state"] == "ratified" }
  end

  # @return [String] Mimumum defined version of this extension
  def min_version
    versions.map { |v| Gem::Version.new(v["version"]) }.min
  end

  # @return [String] Maximum defined version of this extension
  def max_version
    versions.map { |v| Gem::Version.new(v["version"]) }.max
  end

  # @return [String] Mimumum defined ratified version of this extension
  # @return [nil] if there is no ratified version
  def min_ratified_version
    return nil if ratified_versions.empty?

    ratified_versions.map { |v| Gem::Version.new(v["version"]) }.min
  end

  # @return [Array<ExtensionParameter>] List of parameters added by this extension
  def params
    return @params unless @params.nil?

    @params = []
    if @data.key?("params")
      @data["params"].each do |param_name, param_data|
        also_defined_in = []
        unless param_data["also_defined_in"].nil?
          if param_data["also_defined_in"].is_a?(String)
            other_ext = arch_def.extension(param_data["also_defined_in"])
            raise "Definition error in #{name}.#{param_name}: #{param_data['also_defined_in']} is not a known extension" if other_ext.nil?
            also_defined_in << other_ext
          else
            unless param_data["also_defined_in"].is_a?(Array) && param_data["also_defined_in"].all? { |e| e.is_a?(String) }
              raise "schema error: also_defined_in should be a string or array of strings"
            end

            param_data["also_defined_in"].each do |other_ext_name|
              other_ext = arch_def.extension(other_ext_name)
              raise "Definition error in #{name}.#{param_name}: #{param_data['also_defined_in']} is not a known extension" if other.nil?
              also_defined_in << other_ext
            end
          end
        end
        @params << ExtensionParameter.new(
          param_name,
          param_data["description"],
          param_data["schema"],
          param_data["extra_validation"],
          [self] + also_defined_in
        )
      end
    end
    @params
  end

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

  # @return [Array<Instruction>] the list of instructions implemented by this extension (may be empty)
  def instructions
    return @instructions unless @instructions.nil?

    @instructions = arch_def.instructions.select { |i| i.definedBy == name || (i.definedBy.is_a?(Array) && i.definedBy.include?(name)) }
  end

  # @return [Array<Csr>] the list of CSRs implemented by this extension (may be empty)
  def csrs
    return @csrs unless @csrs.nil?

    @csrs = arch_def.csrs.select { |csr| csr.defined_by?(ExtensionVersion.new(name, max_version)) }
  end

  # return the set of reachable functions from any of this extensions's CSRs or instructions in the given evaluation context
  #
  # @param symtab [Idl::SymbolTable] The evaluation context
  # @return [Array<Idl::FunctionDefAst>] Array of IDL functions reachable from any instruction or CSR in the extension
  def reachable_functions(symtab)
    @reachable_functions ||= {}

    return @reachable_functions[symtab] unless @reachable_functions[symtab].nil?

    funcs = []

    puts "Finding all reachable functions from extension #{name}"

    instructions.each do |inst|
      funcs += inst.reachable_functions(symtab, 32) if inst.defined_in_base?(32)
      funcs += inst.reachable_functions(symtab, 64) if inst.defined_in_base?(64)
    end

    csrs.each do |csr|
      funcs += csr.reachable_functions(arch_def)
    end

    @reachable_functions[symtab] = funcs.uniq
  end

  # @return [Array<Idl::FunctionDefAst>] Array of IDL functions reachable from any instruction or CSR in the extension, irrespective of a specific evaluation context
  def reachable_functions_unevaluated
    return @reachable_functions_unevaluated unless @reachable_functions_unevaluated.nil?

    funcs = []
    instructions.each do |inst|
      funcs += inst.operation_ast(arch_def.idl_compiler).reachable_functions_unevaluated(arch_def)
    end

    csrs.each do |csr|
      funcs += csr.reachable_functions_unevaluated(arch_def)
    end

    @reachable_functions_unevaluated = funcs.uniq(&:name)
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

  # @overload ==(other)
  #   @param other [String] An extension name
  #   @return [Boolean] whether or not this ExtensionVersion is named 'other'
  # @overload ==(other)
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

  def to_s
    "#{name} #{@requirement}"
  end

  # @param name [#to_s] Extension name
  # @param requirements (see Gem::Requirement#new)
  def initialize(name, *requirements)
    @name = name.to_s
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

class ArchDef
  # @return [Idl::Compiler] The IDL compiler
  attr_reader :idl_compiler

  # @return [Idl::AstNode] Abstract syntax tree of global scope
  attr_reader :global_ast

  def name = "_"

  # Initialize a new configured architecture defintiion
  #
  # @param config_name [#to_s] The name of a configuration, which must correspond
  #                            to a folder under $root/cfgs
  def initialize(from_child: false)
    @idl_compiler = Idl::Compiler.new(self)

    unless from_child
      arch_def_file = $root / "gen" / "_" / "arch" / "arch_def.yaml"

      @arch_def = YAML.load_file(arch_def_file)

      # parse globals
      @global_ast = @idl_compiler.compile_file(
        $root / "arch" / "isa" / "globals.isa",
        symtab: sym_table_32
      )
      sym_table_32.deep_freeze

      # do it again for rv64, but we don't need the ast this time
      @idl_compiler.compile_file(
        $root / "arch" / "isa" / "globals.isa",
        symtab: sym_table_64
      )
      sym_table_64.deep_freeze

    end
  end

  # Get a symbol table with globals defined for a generic (config-independent) RV32 architecture defintion
  # Being config-independent, parameters in this symbol table will not have values assigned
  #
  # @return [Idl::SymbolTable] Symbol table with config-independent global symbols populated for RV32
  def sym_table_32
    return @sym_table_32 unless @sym_table_32.nil?

    @sym_table_32 = Idl::SymbolTable.new(self, 32)
  end

  # Get a symbol table with globals defined for a generic (config-independent) RV64 architecture defintion
  # Being config-independent, parameters in this symbol table will not have values assigned
  #
  # @return [Idl::SymbolTable] Symbol table with config-independent global symbols populated for RV64
  def sym_table_64
    return @sym_table_64 unless @sym_table_64.nil?

    @sym_table_64 = Idl::SymbolTable.new(self, 64)
  end

  def possible_xlens = [32, 64]

  def inspect = "ArchDef"

  # @return [Array<Extesion>] List of all extensions, even those that are't implemented
  def extensions
    return @extensions unless @extensions.nil?

    @extensions = []
    @arch_def["extensions"].each_value do |ext_data|
      @extensions << Extension.new(ext_data, self)
    end
    @extensions
  end

  # @return [Hash<String, Extension>] Hash of all extensions, even those that aren't implemented, indexed by extension name
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

  # @return [Array<ExtensionParameter>] List of all parameters defined in the architecture
  def params
    return @params unless @params.nil?

    @params = []
    extensions.each do |ext|
      @params += ext.params
    end
    @params
  end

  # @return [Hash<String, ExtensionParameter>] Hash of all extension parameters defined in the architecture
  def params_hash
    return @params_hash unless @params_hash.nil?

    @params_hash = {}
    params.each do |param|
      @params_hash[param.name] = param
    end
    @param_hash
  end

  # @return [ExtensionParameter] Parameter named +name+
  # @return [nil] if there is no parameter named +name+
  def param(name)
    params_hash[name]
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

  # @param inst_name [#to_s] Instruction name
  # @return [Instruction,nil] An instruction named 'inst_name', or nil if it doesn't exist
  def inst(inst_name)
    instruction_hash[inst_name.to_s]
  end

  # @return [Array<Idl::FunctionBodyAst>] List of all functions defined by the architecture
  def functions
    return @functions unless @functions.nil?

    @functions = @global_ast.functions
  end

  # @return [Hash<String,FunctionBodyAst>] Function hash of name => FunctionBodyAst
  def function_hash
    return @function_hash unless @function_hash.nil?

    @function_hash = {}
    functions.each do |func|
      @function_hash[func.name] = func
    end

    @function_hash
  end

  # @param name [String] A function name
  # @return [Idl::FunctionBodyAst] A function named +name+
  # @return [nil] if no function named +name+ is found
  def function(name)
    function_hash[name]
  end

  # @return [Array<ExceptionCode>] All exception codes defined by extensions
  def exception_codes
    return @exception_codes unless @exception_codes.nil?

    @exception_codes =
      extensions.reduce([]) do |list, ext_version|
        ecodes = extension(ext_version.name)["exception_codes"]
        next list if ecodes.nil?

        ecodes.each do |ecode|
          # double check that all the codes are unique
          raise "Duplicate exception code" if list.any? { |e| e.num == ecode["num"] || e.name == ecode["name"] || e.var == ecode["var"] }

          list << ExceptionCode.new(ecode["name"], ecode["var"], ecode["num"], self)
        end
        list
      end
  end

  # @return [Array<InteruptCode>] All interrupt codes defined by extensions
  def interrupt_codes
    return @interrupt_codes unless @interrupt_codes.nil?

    @interupt_codes =
      extensions.reduce([]) do |list, ext_version|
        icodes = extension(ext_version.name)["interrupt_codes"]
        next list if icodes.nil?

        icodes.each do |icode|
          # double check that all the codes are unique
          if list.any? { |i| i.num == icode["num"] || i.name == icode["name"] || i.var == icode["var"] }
            raise "Duplicate interrupt code"
          end

          list << InterruptCode.new(icode["name"], icode["var"], icode["num"], self)
        end
        list
      end
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
      elsif inst(name)
        "%%LINK%inst;#{name};#{name}%%"
      elsif extension(name)
        "%%LINK%ext;#{name};#{name}%%"
      else
        match
      end
    end
  end
end

# a synchroncous exception code
class ExceptionCode

  # @return [String] Long-form display name (can include special characters)
  attr_reader :name

  # @return [String] Field name for an IDL enum
  attr_reader :var

  # @return [Integer] Code, written into *mcause
  attr_reader :num

  # @return [Extension] Extension that defines this code
  attr_reader :ext

  def initialize(name, var, number, ext)
    @name = name
    @var = var
    @num = number
    @ext = ext
  end
end

# all the same informatin as ExceptinCode, but for interrupts
InterruptCode = Class.new(ExceptionCode)

# Object model for a configured architecture definition
class ImplArchDef < ArchDef
  # @return [String] Name of the architecture configuration
  attr_reader :name

  # @return [SymbolTable] The symbol table containing global definitions
  attr_reader :sym_table

  # @return [Hash<String, Object>] The configuration parameter name => value
  attr_reader :param_values

  # @return [Integer] 32 or 64, the XLEN in m-mode
  attr_reader :mxlen

  # hash for Hash lookup
  def hash = @name.hash

  # @return [Array<ExtensionParameterWithValue>] List of all available parameters for the config
  def params_with_value
    return @params_with_value unless @params_with_value.nil?

    @params_with_value = []
    implemented_extensions.each do |ext_version|
      ext = extension(ext_version.name)
      ext.params.each do |ext_param|
        if param_values.key?(ext_param.name)
          @params_with_value << ExtensionParameterWithValue.new(
            ext_param,
            param_values[ext_param.name]
          )
        end
      end
    end
    @params_with_value
  end

  def erb_env
    return @env unless @env.nil?

    @env = Class.new
    @env.instance_variable_set(:@cfg, @cfg)
    @env.instance_variable_set(:@params, @params)
    @env.instance_variable_set(:@arch_gen, self)

    # add each parameter, either as a method (lowercase) or constant (uppercase)
    params.each do |param|
      @env.const_set(param.name, param.value)
    end

    @env.instance_exec do
      # method to check if a given extension (with an optional version number) is present
      #
      # @param ext_name [String,#to_s] Name of the extension
      # @param ext_requirement [String, #to_s] Version string, as a Gem Requirement (https://guides.rubygems.org/patterns/#pessimistic-version-constraint)
      # @return [Boolean] whether or not extension +ext_name+ meeting +ext_requirement+ is implemented in the config
      def ext?(ext_name, ext_requirement = ">= 0")
        @arch_gen.ext?(ext_name.to_s, ext_requirement)
      end

      # @return [Array<Integer>] List of possible XLENs for any implemented mode
      def possible_xlens
        @arch_gen.possible_xlens
      end

      # insert a hyperlink to an object
      # At this point, we insert a placeholder since it will be up
      # to the backend to create a specific link
      #
      # @params type [Symbol] Type (:section, :csr, :inst, :ext)
      # @params name [#to_s] Name of the object
      def link_to(type, name)
        "%%LINK%#{type};#{name}%%"
      end

      # info on interrupt and exception codes

      # @returns [Hash<Integer, String>] architecturally-defined exception codes and their names
      def exception_codes
        @arch_gen.exception_codes
      end

      # returns [Hash<Integer, String>] architecturally-defined interrupt codes and their names
      def interrupt_codes
        @arch_gen.interrupt_codes
      end
    end

    @env
  end
  private :erb_env

  # passes _erb_template_ through ERB within the content of this config
  #
  # @param erb_template [String] ERB source
  # @return [String] The rendered text
  def render_erb(erb_template)
    t = Tempfile.new("template")
    t.write erb_template
    t.flush
    Tilt["erb"].new(t.path, trim: "-").render(erb_env)
  end

  # Initialize a new configured architecture defintiion
  #
  # @param config_name [#to_s] The name of a configuration, which must correspond
  #                            to a folder under $root/cfgs
  def initialize(config_name)
    super(from_child: true)

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

    @param_values = @arch_def["params"]
    @mxlen = @arch_def["params"]["XLEN"]

    @sym_table = Idl::SymbolTable.new(self)

    # load the globals into the symbol table
    custom_globals_path = $root / "cfgs" / @name / "arch_overlay" / "isa" / "globals.isa"
    idl_path = File.exist?(custom_globals_path) ? custom_globals_path : $root / "arch" / "isa" / "globals.isa"
    @global_ast = @idl_compiler.compile_file(
      idl_path,
      symtab: @sym_table
    )

    @sym_table.deep_freeze
  end

  def inspect = "ArchDef##{name}"

  # @return [Boolean] true if this configuration can execute in multiple xlen environments
  # (i.e., that in some mode the effective xlen can be either 32 or 64, depending on CSR values)
  def multi_xlen?
    ["SXLEN", "UXLEN", "VSXLEN", "VUXLEN"].any? { |key| @param_values[key] == 3264 }
  end

  # @return [Array<Integer>] List of possible XLENs in any mode for this config
  def possible_xlens
    multi_xlen? ? [32, 64] : [mxlen]
  end

  # @param mode [String] One of ['M', 'S', 'U', 'VS', 'VU']
  # @return [Boolean] whether or not XLEN can change in the mode
  def multi_xlen_in_mode?(mode)
    case mode
    when "M"
      false
    when "S"
      @param_values["SXLEN"] == 3264
    when "U"
      @param_values["UXLEN"] == 3264
    when "VS"
      @param_values["VSXLEN"] == 3264
    when "VU"
      @param_values["VUXLEN"] == 3264
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
    end

    @implemented_extensions
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
    @ext_cache ||= {}
    cached_result = @ext_cache[[ext_name, ext_version_requirements]]
    return cached_result unless cached_result.nil?

    result =
      implemented_extensions.any? do |e|
        if ext_version_requirements.empty?
          e.name == ext_name.to_s
        else
          requirement = Gem::Requirement.new(ext_version_requirements)
          (e.name == ext_name.to_s) && requirement.satisfied_by?(e.version)
        end
      end
    @ext_cache[[ext_name, ext_version_requirements]] = result
  end

  # @return [Array<ExceptionCode>] All exception codes from this implementation
  def exception_codes
    return @exception_codes unless @exception_codes.nil?

    @exception_codes =
      implemented_extensions.reduce([]) do |list, ext_version|
        ecodes = extension(ext_version.name)["exception_codes"]
        next list if ecodes.nil?

        ecodes.each do |ecode|
          # double check that all the codes are unique
          raise "Duplicate exception code" if list.any? { |e| e.num == ecode["num"] || e.name == ecode["name"] || e.var == ecode["var"] }

          list << ExceptionCode.new(ecode["name"], ecode["var"], ecode["num"], self)
        end
        list
      end
  end

  # @return [Array<InteruptCode>] All interrupt codes from this implementation
  def interrupt_codes
    return @interrupt_codes unless @interrupt_codes.nil?

    @interupt_codes =
      implemented_extensions.reduce([]) do |list, ext_version|
        icodes = extension(ext_version.name)["interrupt_codes"]
        next list if icodes.nil?

        icodes.each do |icode|
          # double check that all the codes are unique
          raise "Duplicate interrupt code" if list.any? { |i| i.num == icode["num"] || i.name == icode["name"] || i.var == icode["var"] }

          list << InterruptCode.new(icode["name"], icode["var"], icode["num"], self)
        end
        list
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

  # @return [Hash<String, Csr>] Implemented csrs, indexed by CSR name
  def implemented_csr_hash
    return @implemented_csr_hash unless @implemented_csr_hash.nil?

    @implemented_csr_hash = {}
    implemented_csrs.each do |csr|
      @implemented_csr_hash[csr.name] = csr
    end
    @implemented_csr_hash
  end



  # @param csr_name [#to_s] CSR name
  # @return [Csr,nil] a specific csr, or nil if it doesn't exist or isn't implemented
  def implemented_csr(csr_name)
    implemented_csr_hash[csr_name]
  end

  # @return [Array<Instruction>] List of all implemented instructions
  def implemented_instructions
    return @implemented_instructions unless @implemented_instructions.nil?

    @implemented_instructions = @arch_def["implemented_instructions"].map do |inst_name|
      instruction_hash[inst_name]
    end

    @implemented_instructions
  end

  # @return [Array<FuncDefAst>] List of all reachable IDL functions for the config
  def implemented_functions
    return @implemented_functions unless @implemented_functions.nil?

    @implemented_functions = []

    puts "  Finding all reachable functions from instruction operations"

    implemented_instructions.each do |inst|
      @implemented_functions <<
        if inst.base.nil?
          if multi_xlen?
            (inst.reachable_functions(sym_table, 32) +
             inst.reachable_functions(sym_table, 64))
          else
            inst.reachable_functions(sym_table, mxlen)
          end
        else
          inst.reachable_functions(sym_table, inst.base)
        end
    end
    @implemented_functions.flatten!.uniq!(&:name)


    puts "  Finding all reachable functions from CSR operations"

    implemented_csrs.each do |csr|
      csr_funcs = csr.reachable_functions(self)
      csr_funcs.each do |f|
        @implemented_functions << f unless @implemented_functions.any? { |i| i.name == f.name }
      end
    end

    @implemented_functions
  end
end

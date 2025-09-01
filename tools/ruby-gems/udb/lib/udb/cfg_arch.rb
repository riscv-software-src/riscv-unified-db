# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

# Many classes include DatabaseObject have an "cfg_arch" member which is a ConfiguredArchitecture class.
# It combines knowledge of the RISC-V Architecture with a particular configuration.
# A configuration is an instance of the AbstractConfig object either located in the /cfg directory
# or created at runtime for things like profiles and certificate models.

require "concurrent"
require "ruby-prof"
require "tilt"
require "yaml"
require "pathname"
require_relative 'obj/non_isa_specification'
require_relative "config"
require_relative "architecture"

require "idlc"
require "idlc/symbol_table"
require "idlc/passes/find_return_values"
require "idlc/passes/gen_adoc"
require "idlc/passes/prune"
require "idlc/passes/reachable_exceptions"
require "idlc/passes/reachable_functions"

require "udb_helpers/backend_helpers"

include Udb::Helpers::TemplateHelpers

module Udb

class ConfiguredArchitecture < Architecture
  extend T::Sig

  # @return [Idl::Compiler] The IDL compiler
  sig { returns(Idl::Compiler) }
  attr_reader :idl_compiler

  # @return [Idl::IsaAst] Abstract syntax tree of global scope
  sig { returns(Idl::IsaAst) }
  attr_reader :global_ast

  # @return [String] Name of this definition. Special names are:
  #                  * '_'   - The generic architecture, with no configuration settings.
  #                  * 'rv32' - A generic RV32 architecture, with only one parameter set (XLEN == 32)
  #                  * 'rv64' - A generic RV64 architecture, with only one parameter set (XLEN == 64)
  sig { returns(String) }
  attr_reader :name

  sig { returns(AbstractConfig) }
  attr_reader :config

  sig { returns(T::Boolean) }
  def fully_configured? = @config.fully_configured?

  sig { returns(T::Boolean) }
  def partially_configured? = @config.partially_configured?

  sig { returns(T::Boolean) }
  def unconfigured? = @config.unconfigured?

  sig { returns(T.nilable(Integer)) }
  def mxlen = @config.mxlen

  sig { returns(T::Hash[String, T.untyped]) }
  def param_values = @config.param_values

  # Returns whether or not it may be possible to switch XLEN given this definition.
  #
  # There are three cases when this will return true:
  #   1. A mode (e.g., U) is known to be implemented, and the CSR bit that controls XLEN in that mode is known to be writable.
  #   2. A mode is known to be implemented, but the writability of the CSR bit that controls XLEN in that mode is not known.
  #   3. It is not known if the mode is implemented.
  #
  #
  # @return [Boolean] true if this configuration might execute in multiple xlen environments
  #                   (e.g., that in some mode the effective xlen can be either 32 or 64, depending on CSR values)
  sig { returns(T::Boolean) }
  def multi_xlen?
    return true if @mxlen.nil?

    ["S", "U", "VS", "VU"].any? { |mode| multi_xlen_in_mode?(mode) }
  end

  # Returns whether or not it may be possible to switch XLEN in +mode+ given this definition.
  #
  # There are three cases when this will return true:
  #   1. +mode+ (e.g., U) is known to be implemented, and the CSR bit that controls XLEN in +mode+ is known to be writable.
  #   2. +mode+ is known to be implemented, but the writability of the CSR bit that controls XLEN in +mode+ is not known.
  #   3. It is not known if +mode+ is implemented.
  #
  # Will return false if +mode+ is not possible (e.g., because U is a prohibited extension)
  #
  # @param mode [String] mode to check. One of "M", "S", "U", "VS", "VU"
  # @return [Boolean] true if this configuration might execute in multiple xlen environments in +mode+
  #                   (e.g., that in some mode the effective xlen can be either 32 or 64, depending on CSR values)
  sig { params(mode: String).returns(T::Boolean) }
  def multi_xlen_in_mode?(mode)
    return false if mxlen == 32

    case mode
    when "M"
      mxlen.nil?
    when "S"
      return true if unconfigured?

      if fully_configured?
        ext?(:S) && (param_values["SXLEN"] == 3264)
      elsif partially_configured?
        return false if prohibited_ext?(:S)

        return true unless ext?(:S) # if S is not known to be implemented, we can't say anything about it

        return true unless param_values.key?("SXLEN")

        param_values["SXLEN"] == 3264
      else
        raise "Unexpected configuration state"
      end
    when "U"
      return false if prohibited_ext?(:U)

      return true if unconfigured?

      if fully_configured?
        ext?(:U) && (param_values["UXLEN"] == 3264)
      elsif partially_configured?
        return true unless ext?(:U) # if U is not known to be implemented, we can't say anything about it

        return true unless param_values.key?("UXLEN")

        param_values["UXLEN"] == 3264
      else
        raise "Unexpected configuration state"
      end
    when "VS"
      return false if prohibited_ext?(:H)

      return true if unconfigured?

      if fully_configured?
        ext?(:H) && (param_values["VSXLEN"] == 3264)
      elsif partially_configured?
        return true unless ext?(:H) # if H is not known to be implemented, we can't say anything about it

        return true unless param_values.key?("VSXLEN")

        param_values["VSXLEN"] == 3264
      else
        raise "Unexpected configuration state"
      end
    when "VU"
      return false if prohibited_ext?(:H)

      return true if unconfigured?

      if fully_configured?
        ext?(:H) && (param_values["VUXLEN"] == 3264)
      elsif partially_configured?
        return true unless ext?(:H) # if H is not known to be implemented, we can't say anything about it

        return true unless param_values.key?("VUXLEN")

        param_values["VUXLEN"] == 3264
      else
        raise "Unexpected configuration state"
      end
    when "D"
      mxlen.nil?
    else
      raise ArgumentError, "Bad mode"
    end
  end

  # @return [Array<Integer>] List of possible XLENs in any mode for this config
  sig { returns(T::Array[Integer]) }
  def possible_xlens = multi_xlen? ? [32, 64] : [mxlen]

  # hash for Hash lookup
  sig { override.returns(Integer) }
  def hash = @name_sym.hash

  # @return [Idl::SymbolTable] Symbol table with global scope
  # @return [nil] if the architecture is not configured (use symtab_32 or symtab_64)
  sig { returns(Idl::SymbolTable) }
  def symtab
    raise NotImplementedError, "Un-configured ConfiguredArchitectures have no symbol table" if @symtab.nil?

    @symtab
  end

  sig { returns(ConfigType) }
  def config_type = @config_type

  # return the params as a hash of symbols for the SymbolTable
  sig { returns(T::Hash[String, T.any(Idl::Var, Idl::Type)]) }
  def param_syms
    syms = {}

    params_with_value.each do |param_with_value|
      type = Idl::Type.from_json_schema(param_with_value.schema).make_const
      if type.kind == :array && type.width == :unknown
        type = Idl::Type.new(:array, width: T.cast(param_with_value.value, T.untyped).length, sub_type: type.sub_type, qualifiers: [:const])
      end

      # could already be present...
      existing_sym = syms[param_with_value.name]
      if existing_sym.nil?
        syms[param_with_value.name] = Idl::Var.new(param_with_value.name, type, param_with_value.value, param: true)
      else
        unless existing_sym.type.equal_to?(type) && existing_sym.value == param_with_value.value
          raise Idl::SymbolTable::DuplicateSymError, "Definition error: Param #{param_with_value.name} is defined by multiple extensions and is not the same definition in each"
        end
      end
    end

    # now add all parameters, even those not implemented
    params_without_value.each do |param|
      if param.exts.size == 1
        syms[param.name] = Idl::Var.new(param.name, param.idl_type.make_const, param: true)
      else
        # could already be present...
        existing_sym = syms[param.name]
        if existing_sym.nil?
          syms[param.name] = Idl::Var.new(param.name, param.idl_type.make_const, param: true)
        else
          unless existing_sym.type.equal_to?(param.idl_type)
            raise "Definition error: Param #{param.name} is defined by multiple extensions and is not the same definition in each"
          end
        end
      end
    end

    syms
  end

  # validate a configuration
  sig {
    params(
      config_path: Pathname,
      std_path: Pathname,   # path to standard architecture spec
      custom_path: Pathname, # path to custom overlay, if needed
      gen_path: Pathname    # path to put generated files
    ).returns(T::Boolean)
  }
  def self.validate(
    config_path,
    std_path: Udb.default_std_isa_path,
    custom_path: Udb.default_custom_isa_path,
    gen_path: Udb.default_gen_path
  )

    config_spec = YAML.load_file(config_path)
    case config_spec.fetch("type")
    when "unconfigured"
      true  # nothing else to do!
    when "fully configured"
      validate_full_config(config_path, std_path:, custom_path:, gen_path:)
    when "partially configured"
      validate_partial_config(config_path, std_path:, custom_path:, gen_path:)
    else
      raise "Not a valid configuration type: #{config_spec.fetch('type')}"
    end
  end

  sig {
    params(
      config_path: Pathname,
      gen_path: Pathname,
      std_path: Pathname,
      custom_path: Pathname
    ).returns(T::Boolean)
  }
  def self.validate_full_config(config_path, gen_path:, std_path:, custom_path:)
    config_spec = YAML.load_file(config_path)
    resolver = Resolver.new(
      gen_path_override: gen_path,
      std_path_override: std_path,
      custom_path_override: custom_path
    )
    resolver.resolve_arch(config_spec)
    resolved_path = resolver.gen_path / "resolved_spec" / config_spec["name"]

    # first, check that all the extensions are defined
    config_spec.fetch("implemented_extensions").each do |e|
      ext_name = T.let("", String)
      ext_version = T.let("", String)
      if e.is_a?(Array)
        ext_name = e.fetch(0)
        ext_version = e.fetch(1)
      else
        ext_name = e.fetch("name")
        ext_version = e.fetch("version")
      end

      unless (resolved_path / "ext" / "#{ext_name}.yaml").file?
        raise "Cannot find defintion of extension #{ext_name} #{resolved_path / "ext" / "#{ext_name}.yaml"}"
      end

      ext_spec = YAML.load_file(resolved_path / "ext" / "#{ext_name}.yaml")
      has_ver = ext_spec.fetch("versions").any? do |ext_ver|
        VersionSpec.new(ext_ver.fetch("version")).eql?(ext_version)
      end

      raise "Cannot find version #{ext_version} of #{ext_name}" unless has_ver
    end

    cfg_arch = resolver.cfg_arch_for(config_path)

    param_missing = T.let(false, T::Boolean)
    # check params
    cfg_arch.transitive_implemented_extension_versions.each do |ext_ver|
      ext_ver.params.each do |param|
        unless config_spec.fetch("params").key?(param.name)
          warn "missing required parameter #{param.name}"
          param_missing = true
          next
        end

        unless param.schema.validate(config_spec.fetch("params").fetch(param.name))
          warn "value of parameter #{param.name} is not valid"
          param_missing = true
        end
      end
    end

    warn "Parameter(s) are missing or invalid" if param_missing
    !param_missing
  end
  private_class_method :validate_full_config

  sig {
    params(
      config_path: Pathname,
      gen_path: Pathname,
      std_path: Pathname,
      custom_path: Pathname
    ).returns(T::Boolean)
  }
  def self.validate_partial_config(config_path, gen_path:, std_path:, custom_path:)
    config_spec = YAML.load_file(config_path)
    resolver = Resolver.new(
      gen_path_override: gen_path,
      std_path_override: std_path,
      custom_path_override: custom_path
    )
    resolver.resolve_arch(config_spec)
    resolved_path = resolver.gen_path / "resolved_spec" / config_spec["name"]

    # first, check that all the extensions are defined
    config_spec.fetch("mandatory_extensions").each do |e|
      ext_name = e.fetch("name")
      ext_req = RequirementSpec.new(e.fetch("version"))

      unless (resolved_path / "ext" / "#{ext_name}.yaml").file?
        raise "Cannot find defintion of extension #{ext_name} #{resolved_path / "ext" / "#{ext_name}.yaml"}"
      end

      ext_spec = YAML.load_file(resolved_path / "ext" / "#{ext_name}.yaml")
      has_ver = ext_spec.fetch("versions").any? do |ext_ver|
        ext_req.satisfied_by?(VersionSpec.new(ext_ver.fetch("version")), ext_spec)
      end

      raise "Cannot find any version of #{ext_name} that satisfies #{ext_req}" unless has_ver
    end

    cfg_arch = resolver.cfg_arch_for(config_path)

    invalid_param = T.let(false, T::Boolean)
    # check params
    possible_params = cfg_arch.mandatory_extension_reqs.map(&:params).flatten.uniq
    if config_spec.key?("params")
      config_spec.fetch("params").each do |pname, pvalue|
        unless possible_params.any? { |param| param.name == pname }
          warn "Parameter #{pname} is not from a mandatory extension"
          invalid_param = true
          next
        end

        param = possible_params.find { |param| param.name == pname }
        unless param.schema.validate(pvalue)
          warn "value of parameter #{param.name} is not valid"
          invalid_param = true
        end
      end
    end

    warn "Parameter(s) are invalid" if invalid_param
    !invalid_param
  end
  private_class_method :validate_partial_config

  # Initialize a new configured architecture definition
  #
  # @param name [:to_s]      The name associated with this ConfiguredArchitecture
  # @param config [AbstractConfig]   The configuration object
  # @param arch_path [Pathnam] Path to the resolved architecture directory corresponding to the configuration
  sig { params(name: String, config: AbstractConfig).void }
  def initialize(name, config)

    super(config.info.resolved_spec_path)

    @name = name.to_s.freeze
    @name_sym = @name.to_sym.freeze

    @config = config
    @config_type = T.let(@config.type, ConfigType)
    @mxlen = config.mxlen
    @mxlen.freeze

    @idl_compiler = Idl::Compiler.new

    symtab_callbacks = Idl::SymbolTable::BuiltinFunctionCallbacks.new(
      implemented: (
        Idl::SymbolTable.make_implemented_callback do |ext_name|
          if fully_configured?
            ext?(ext_name)
          else
            # we can know if it is implemented, but not if it's not implemented for a partially configured
            if ext?(ext_name)
              true
            elsif prohibited_ext?(ext_name)
              false
            end
          end
        end
      ),
      implemented_version: (
        Idl::SymbolTable.make_implemented_version_callback do |ext_name, version|
          if fully_configured?
            ext?(ext_name, [version])
          else
            # we can know if it is implemented, but not if it's not implemented for a partially configured
            if ext?(ext_name, [version])
              true
            elsif prohibited_ext?(ext_name)
              false
            end
          end
        end
      ),
      implemented_csr: (
        Idl::SymbolTable.make_implemented_csr_callback do |csr_addr|
          if fully_configured?
            if transitive_implemented_csrs.any? { |c| c.address == csr_addr }
              true
            end
          else
            if not_prohibited_csrs.none? { |c| c.address == csr_addr }
              false
            end
          end
        end
      )
    )

    params = params_with_value.concat(params_without_value).concat(out_of_scope_params)
    params.uniq! { |p| p.name }
    @symtab =
      Idl::SymbolTable.new(
        mxlen:,
        possible_xlens:,
        params:,
        builtin_funcs: symtab_callbacks,
        builtin_enums: [
          Idl::SymbolTable::EnumDef.new(
            name: "ExtensionName",
            element_values: (1..extensions.size).to_a,
            element_names: extensions.map(&:name)
          ),
          Idl::SymbolTable::EnumDef.new(
            name: "ExceptionCode",
            element_values: exception_codes.map(&:num),
            element_names: exception_codes.map(&:var)
          ),
          Idl::SymbolTable::EnumDef.new(
            name: "InterruptCode",
            element_values: interrupt_codes.map(&:num),
            element_names: interrupt_codes.map(&:var)
          )
        ],
        name: @name,
        csrs:
      )
    overlay_path = config.info.overlay_path

    custom_globals_path = overlay_path.nil? ? Pathname.new("/does/not/exist") : overlay_path / "isa" / "globals.isa"
    idl_path = File.exist?(custom_globals_path) ? custom_globals_path : config.info.spec_path /  "isa" / "globals.isa"
    @global_ast = @idl_compiler.compile_file(
      idl_path
    )
    @global_ast.add_global_symbols(@symtab)
    @symtab.deep_freeze
    raise if @symtab.name.nil?
    @global_ast.freeze_tree(@symtab)

    @params_with_value = T.let(nil, T.nilable(T::Array[ParameterWithValue]))
  end

  # Returns a string representation of the object, suitable for debugging.
  # @return [String] A string representation of the object.
  sig { override.returns(String) }
  def inspect = "ConfiguredArchitecture##{name}"

  # type check all IDL, including globals, instruction ops, and CSR functions
  #
  # @param config [AbstractConfig] Configuration
  # @param show_progress [Boolean] whether to show progress bars
  # @param io [IO] where to write progress bars
  # @return [void]
  sig { params(show_progress: T::Boolean, io: IO).void }
  def type_check(show_progress: true, io: $stdout)
    io.puts "Type checking IDL code for #{@config.name}..." if show_progress
    progressbar =
      if show_progress
        ProgressBar.create(title: "Instructions", total: possible_instructions.size)
      end

    possible_instructions.each do |inst|
      progressbar.increment if show_progress
      if @mxlen == 32
        inst.type_checked_operation_ast(32) if inst.rv32?
      elsif @mxlen == 64
        inst.type_checked_operation_ast(64) if inst.rv64?
        inst.type_checked_operation_ast(32) if possible_xlens.include?(32) && inst.rv32?
      end
    end

    progressbar =
      if show_progress
        ProgressBar.create(title: "CSRs", total: possible_csrs.size)
      end

    possible_csrs.each do |csr|
      progressbar.increment if show_progress
      if csr.has_custom_sw_read?
        if (possible_xlens.include?(32) && csr.defined_in_base32?)
          csr.type_checked_sw_read_ast(32)
        end
        if (possible_xlens.include?(64) && csr.defined_in_base64?)
          csr.type_checked_sw_read_ast(64)
        end
      end
      csr.possible_fields.each do |field|
        unless field.type_ast.nil?
          if possible_xlens.include?(32) && csr.defined_in_base32? && field.defined_in_base32?
            field.type_checked_type_ast(32)
          end
          if possible_xlens.include?(64) && csr.defined_in_base64? && field.defined_in_base64?
            field.type_checked_type_ast(64)
          end
        end
        unless field.reset_value_ast.nil?
          if ((possible_xlens.include?(32) && csr.defined_in_base32? && field.defined_in_base32?) ||
              (possible_xlens.include?(64) && csr.defined_in_base64? && field.defined_in_base64?))
            field.type_checked_reset_value_ast if csr.defined_in_base32? && field.defined_in_base32?
          end
        end
        unless field.sw_write_ast(@symtab).nil?
          field.type_checked_sw_write_ast(@symtab, 32) if possible_xlens.include?(32) && csr.defined_in_base32? && field.defined_in_base32?
          field.type_checked_sw_write_ast(@symtab, 64) if possible_xlens.include?(64) && csr.defined_in_base64? && field.defined_in_base64?
        end
      end
    end

    func_list = reachable_functions
    progressbar =
      if show_progress
        ProgressBar.create(title: "Functions", total: func_list.size)
      end
    func_list.each do |func|
      progressbar.increment if show_progress
      func.type_check(@symtab)
    end

    puts "done" if show_progress
  end

  # @return [Array<ParameterWithValue>] List of all parameters with one known value in the config
  sig { returns(T::Array[ParameterWithValue]) }
  def params_with_value
    @params_with_value ||= T.let(
      case @config_type
      when ConfigType::UnConfig
        T.cast([], T::Array[ParameterWithValue])
      when ConfigType::Full
        params = T.let([], T::Array[ParameterWithValue])
        transitive_implemented_extension_versions.each do |ext_version|
          ext = T.must(extension(ext_version.name))
          ext.params.each do |ext_param|
            if !@config.param_values.key?(ext_param.name)
              if ext_param.when.satisfied_by_cfg_arch?(self) != SatisfiedResult::No
                raise "missing parameter value for #{ext_param.name} in config #{config.name}"
              else
                next
              end
            end
            next if params.any? { |p| p.name == ext_param.name }

            params << ParameterWithValue.new(
              ext_param,
              @config.param_values.fetch(ext_param.name)
            )
          end
        end
        params
      when ConfigType::Partial
        params = T.let([], T::Array[ParameterWithValue])

        mandatory_extension_reqs.each do |ext_requirement|
          ext = T.must(extension(ext_requirement.name))
          ext.params.each do |ext_param|
            # Params listed in the config always only have one value.
            next unless @config.param_values.key?(ext_param.name)
            next if params.any? { |p| p.name == ext_param.name }

            params << ParameterWithValue.new(
              ext_param,
              T.must(@config.param_values[ext_param.name])
            )
          end
        end
        params
      else
        T.absurd(@config_type)
      end,
      T.nilable(T::Array[ParameterWithValue]))
  end

  # @return [Array<Parameter>] List of all available parameters without one known value in the config
  sig { returns(T::Array[Parameter]) }
  def params_without_value
    return @params_without_value unless @params_without_value.nil?

    @params_without_value = []
    extensions.each do |ext|
      next if possible_extensions.none? { |poss| poss.name == ext.name }
      ext.params.each do |ext_param|
        # Params listed in the config always only have one value.
        next if @config.param_values.key?(ext_param.name)
        next if @params_without_value.any? { |p| p.name == ext_param.name }
        next if ext_param.when.satisfied_by_cfg_arch?(self) == SatisfiedResult::No

        @params_without_value << ext_param
      end
    end
    @params_without_value
  end

  # Returns list of parameters that out of scope for the config
  sig { returns(T::Array[Parameter]) }
  def out_of_scope_params
    return @out_of_scope_params unless @out_of_scope_params.nil?

    @out_of_scope_params = []
    extensions.each do |ext|
      ext.params.each do |ext_param|
        next if params_with_value.any? { |p| p.name == ext_param.name }
        next if params_without_value.any? { |p| p.name == ext_param.name }

        @out_of_scope_params << ext_param
      end
    end
    @out_of_scope_params
  end

  # @return [Array<ExtensionVersion>] List of extension versions explicitly marked as implemented in the config.
  #                                   Does *not* include extensions implied by explicitly implemented extensions.
  sig { returns(T::Array[ExtensionVersion]) }
  def explicitly_implemented_extension_versions
    return @explicitly_implemented_extension_versions if defined?(@explicitly_implemented_extension_versions)

    unless fully_configured?
      raise ArgumentError, "implemented_extension_versions only valid for fully configured systems"
    end

    @explicitly_implemented_extension_versions ||=
      T.cast(@config, FullConfig).implemented_extensions.map do |e|
        ExtensionVersion.new(e.fetch("name"), e.fetch("version"), self, fail_if_version_does_not_exist: true)
      end
  end

  # @return [Array<ExtensionVersion>] List of all extensions known to be implemented in this config, including transitive implications
  sig { returns(T::Array[ExtensionVersion]) }
  def transitive_implemented_extension_versions
    return @transitive_implemented_extension_versions unless @transitive_implemented_extension_versions.nil?

    raise "transitive_implemented_extension_versions is only valid for a fully configured definition" unless @config.fully_configured?

    @transitive_implemented_extension_versions = explicitly_implemented_extension_versions.dup

    added_ext_vers = []
    loop do
      @transitive_implemented_extension_versions.each do |ext_ver|
        ext_ver.implications.each do |cond_ext_ver|
          applies = cond_ext_ver.cond.satisfied_by? do |ext_req|
            @transitive_implemented_extension_versions.any? do |inner_ext_ver|
              next false if ext_ver == inner_ext_ver

              ext_req.satisfied_by?(inner_ext_ver)
            end
          end
          if applies && !@transitive_implemented_extension_versions.include?(cond_ext_ver.ext_ver)
            added_ext_vers << cond_ext_ver.ext_ver
          end
        end
      end
      break if added_ext_vers.empty?

      added_ext_vers.each { |ext_ver| @transitive_implemented_extension_versions << ext_ver }

      added_ext_vers = []
    end

    @transitive_implemented_extension_versions.sort!
    @transitive_implemented_extension_versions
  end
  alias implemented_extension_versions transitive_implemented_extension_versions

  # @return [Array<ExtensionRequirement>] List of all mandatory extension requirements (not transitive)
  sig { returns(T::Array[ExtensionRequirement]) }
  def mandatory_extension_reqs
    return @mandatory_extension_reqs if defined?(@mandatory_extension_reqs)

    @mandatory_extension_reqs ||=
      T.cast(@config, PartialConfig).mandatory_extensions.map do |e|
        ename = T.cast(e["name"], String)
        ext = extension(ename)
        raise "Cannot find extension #{e['name']} in the architecture definition" if ext.nil?

        if e["version"].is_a?(Array)
          ExtensionRequirement.new(ename, T.cast(e.fetch("version"), T::Array[String]), presence: Presence.new("mandatory"), arch: self)
        else
          ExtensionRequirement.new(ename, T.cast(e.fetch("version"), String), presence: Presence.new("mandatory"), arch: self)
        end
      end
  end

  # @return [Array<Extension>] List of extensions that are possibly supported
  sig { returns(T::Array[Extension]) }
  def not_prohibited_extensions
    return @not_prohibited_extensions if defined?(@not_prohibited_extensions)

    @not_prohibited_extensions ||=
      if @config.fully_configured?
        transitive_implemented_extension_versions.map { |ext_ver| ext_ver.ext }.uniq
      elsif @config.partially_configured?
        # reject any extension in which all of the extension versions are prohibited
        extensions.reject { |ext| (ext.versions - transitive_prohibited_extension_versions).empty? }
      else
        extensions
      end
  end
  alias possible_extensions not_prohibited_extensions

  # @return [Array<ExtensionVersion>] List of all ExtensionVersions that are possible to support
  sig { returns(T::Array[ExtensionVersion]) }
  def not_prohibited_extension_versions
    return @not_prohibited_extension_versions if defined?(@not_prohibited_extension_versions)

    @not_prohibited_extension_versions ||=
      if @config.fully_configured?
        transitive_implemented_extension_versions
      elsif @config.partially_configured?
        extensions.map(&:versions).flatten.reject { |ext_ver| transitive_prohibited_extension_versions.include?(ext_ver) }
      else
        extensions.map(&:versions).flatten
      end
  end
  alias possible_extension_versions not_prohibited_extension_versions

  sig { params(ext_ver: ExtensionVersion).void }
  def add_ext_ver_and_conflicts(ext_ver)
    @transitive_prohibited_extension_versions << ext_ver
    ext_ver.implications.each do |cond_ext_ver|
      next if @transitive_prohibited_extension_versions.include?(cond_ext_ver.ext_ver)

      sat = cond_ext_ver.cond.satisfied_by_cfg_arch?(self)
      if sat == SatisfiedResult::Yes
        @transitive_prohibited_extension_versions << cond_ext_ver.ext_ver
      end
    end
  end
  private :add_ext_ver_and_conflicts

  # @return [Array<ExtensionVersion>] List of all extension versions that are prohibited.
  #                                   This includes extensions explicitly prohibited by the config file
  #                                   and extensions that conflict with a mandatory extension.
  sig { returns(T::Array[ExtensionVersion]) }
  def transitive_prohibited_extension_versions
    return @transitive_prohibited_extension_versions unless @transitive_prohibited_extension_versions.nil?

    @transitive_prohibited_extension_versions = []

    if @config.partially_configured?
      @transitive_prohibited_extension_versions =
        T.cast(@config, PartialConfig).prohibited_extensions.map do |ext_req_data|
          ext_req = ExtensionRequirement.new(T.cast(ext_req_data.fetch("name"), String), ext_req_data.fetch("version"), arch: self)
          ext_req.satisfying_versions.each { |ext_ver| add_ext_ver_and_conflicts(ext_ver) }
        end

      # now add any extensions that are prohibited by a mandatory extension
      mandatory_extension_reqs.each do |ext_req|
        ext_req.satisfying_versions do |ext_ver|
          add_ext_ver_and_conflicts(ext_ver)
        end
      end

      # now add everything that is not mandatory or implied by mandatory, if additional extensions are not allowed
      unless T.cast(@config, PartialConfig).additional_extensions_allowed?
        extensions.each do |ext|
          ext.versions.each do |ext_ver|
            next if mandatory_extension_reqs.any? { |ext_req| ext_req.satisfied_by?(ext_ver) }
            next if mandatory_extension_reqs.any? { |ext_req| ext_req.extension.implies.eval.any? { |impl| impl.ext_ver == ext_ver } }

            @transitive_prohibited_extension_versions << ext_ver
          end
        end
      end

    elsif @config.fully_configured?
      extensions.each do |ext|
        ext.versions.each do |ext_ver|
          @transitive_prohibited_extension_versions << ext_ver unless transitive_implemented_extension_versions.include?(ext_ver)
        end
      end

    # else, unconfigured....nothing to do                # rubocop:disable Layout/CommentIndentation

    end

    @transitive_prohibited_extension_versions
  end
  alias prohibited_extension_versions transitive_prohibited_extension_versions

  # @overload prohibited_ext?(ext)
  #   Returns true if the ExtensionVersion +ext+ is prohibited
  #   @param ext [ExtensionVersion] An extension version
  #   @return [Boolean]
  #
  # @overload prohibited_ext?(ext)
  #   Returns true if any version of the extension named +ext+ is prohibited
  #   @param ext [String] An extension name
  #   @return [Boolean]
  sig { params(ext: T.any(ExtensionVersion, String, Symbol)).returns(T::Boolean) }
  def prohibited_ext?(ext)
    if ext.is_a?(ExtensionVersion)
      transitive_prohibited_extension_versions.include?(ext)
    elsif ext.is_a?(String) || ext.is_a?(Symbol)
      transitive_prohibited_extension_versions.any? { |ext_ver| ext_ver.name == ext.to_s }
    else
      raise ArgumentError, "Argument to prohibited_ext? should be an ExtensionVersion or a String"
    end
  end

  # @overload ext?(ext_name)
  #   @param ext_name [#to_s] Extension name (case sensitive)
  #   @return [Boolean] True if the extension `name` is implemented
  # @overload ext?(ext_name, ext_version_requirements)
  #   @param ext_name [#to_s] Extension name (case sensitive)
  #   @param ext_version_requirements [Number,String,Array] Extension version requirements
  #   @return [Boolean] True if the extension `name` meeting `ext_version_requirements` is implemented
  #   @example Checking extension presence with a version requirement
  #     ConfigurationArchitecture.ext?(:S, ">= 1.12")
  #   @example Checking extension presence with multiple version requirements
  #     ConfigurationArchitecture.ext?(:S, ">= 1.12", "< 1.15")
  #   @example Checking extension precsence with a precise version requirement
  #     ConfigurationArchitecture.ext?(:S, 1.12)
  sig { params(ext_name: T.any(String, Symbol), ext_version_requirements: T::Array[String]).returns(T::Boolean) }
  def ext?(ext_name, ext_version_requirements = [])
    @ext_cache ||= {}
    cached_result = @ext_cache[[ext_name, ext_version_requirements]]
    return cached_result unless cached_result.nil?

    result =
      if @config.fully_configured?
        transitive_implemented_extension_versions.any? do |e|
          if ext_version_requirements.empty?
            e.name == ext_name.to_s
          else
            requirement = ExtensionRequirement.new(ext_name.to_s, ext_version_requirements, arch: self)
            requirement.satisfied_by?(e)
          end
        end
      elsif @config.partially_configured?
        mandatory_extension_reqs.any? do |e|
          if ext_version_requirements.empty?
            e.name == ext_name.to_s
          else
            requirement = ExtensionRequirement.new(ext_name.to_s, ext_version_requirements, arch: self)
            e.satisfying_versions.all? do |ext_ver|
              requirement.satisfied_by?(ext_ver)
            end
          end
        end
      else
        raise "unexpected type" unless unconfigured?

        false
      end
    @ext_cache[[ext_name, ext_version_requirements]] = result
  end

  # @return [Array<ExceptionCode>] All exception codes known to be implemented
  sig { returns(T::Array[ExceptionCode]) }
  def implemented_exception_codes
    @implemented_exception_codes ||=
      implemented_extension_versions.map { |ext_ver| ext_ver.exception_codes }.compact.flatten
  end

  # @return [Array<InteruptCode>] All interrupt codes known to be implemented
  sig { returns(T::Array[InterruptCode]) }
  def implemented_interrupt_codes
    @implemented_interupt_codes ||=
      implemented_extension_versions.map { |ext_ver| ext_ver.interrupt_codes }.compact.flatten
  end

  # @return [Array<Idl::FunctionBodyAst>] List of all functions defined by the architecture
  sig { returns(T::Array[Idl::FunctionBodyAst]) }
  def functions
    @functions ||= @global_ast.functions
  end

  # @return [Idl::FetchAst] Fetch block
  sig { returns(Idl::FetchAst) }
  def fetch
    @fetch ||= @global_ast.fetch
  end

  # @return [Array<Idl::GlobalAst>] List of globals
  sig { returns(T::Array[T.any(Idl::GlobalAst, Idl::GlobalWithInitializationAst)]) }
  def globals
    return @globals unless @globals.nil?

    @globals = @global_ast.globals
  end

  # @return [Array<Csr>] List of all implemented CSRs
  sig { returns(T::Array[Csr]) }
  def transitive_implemented_csrs
    unless fully_configured?
      raise ArgumentError, "transitive_implemented_csrs is only defined for fully configured systems"
    end

    @transitive_implemented_csrs ||=
      csrs.select do |csr|
        csr.defined_by_condition.satisfied_by? do |ext_req|
          transitive_implemented_extension_versions.any? { |ext_ver| ext_req.satisfied_by?(ext_ver) }
        end
      end
  end
  alias implemented_csrs transitive_implemented_csrs

  # @return [Array<Csr>] List of all CSRs that it is possible to implement
  sig { returns(T::Array[Csr]) }
  def not_prohibited_csrs
    @not_prohibited_csrs ||=
      if @config.fully_configured?
        transitive_implemented_csrs
      elsif @config.partially_configured?
        csrs.select do |csr|
          csr.defined_by_condition.satisfied_by? do |ext_req|
            not_prohibited_extension_versions.any? { |ext_ver| ext_req.satisfied_by?(ext_ver) }
          end
        end
      else
        csrs
      end
  end
  alias possible_csrs not_prohibited_csrs

  # @return [Array<Instruction>] List of all implemented instructions, sorted by name
  sig { returns(T::Array[Instruction]) }
  def transitive_implemented_instructions
    unless fully_configured?
      raise ArgumentError, "transitive_implemented_instructions is only defined for fully configured systems"
    end

    @transitive_implemented_instructions ||=
      instructions.select do |inst|
        inst.defined_by_condition.satisfied_by? do |ext_req|
          transitive_implemented_extension_versions.any? { |ext_ver| ext_req.satisfied_by?(ext_ver) }
        end
      end
  end
  alias implemented_instructions transitive_implemented_instructions

  # @return [Array<Instruction>] List of all prohibited instructions, sorted by name
  sig { returns(T::Array[Instruction]) }
  def transitive_prohibited_instructions
    # an instruction is prohibited if it is not defined by any .... TODO LEFT OFF HERE....
    @transitive_prohibited_instructions ||=
      if fully_configured?
        instructions - transitive_implemented_instructions
      elsif partially_configured?
        instructions.select do |inst|
          inst.defined_by_condition.satisfied_by? do |ext_req|
            not_prohibited_extension_versions.none? { |ext_ver| ext_req.satisfied_by?(ext_ver) }
          end
        end
      else
        []
      end
  end
  alias prohibited_instructions transitive_prohibited_instructions

  # @return [Array<Instruction>] List of all instructions that are not prohibited by the config, sorted by name
  sig { returns(T::Array[Instruction]) }
  def not_prohibited_instructions
    return @not_prohibited_instructions if defined?(@not_prohibited_instructions)

    @not_prohibited_instructions_mutex ||= Thread::Mutex.new
    @not_prohibited_instructions_mutex.synchronize do
      @not_prohibited_instructions ||=
        if @config.fully_configured?
          transitive_implemented_instructions
        elsif @config.partially_configured?
          instructions.select do |inst|
            possible_xlens.any? { |xlen| inst.defined_in_base?(xlen) } && \
              inst.defined_by_condition.satisfied_by? do |ext_req|
                not_prohibited_extension_versions.any? { |ext_ver| ext_req.satisfied_by?(ext_ver) }
              end
          end
        else
          instructions
        end
    end

    @not_prohibited_instructions
  end
  alias possible_instructions not_prohibited_instructions

  # @return [Integer] The largest instruction encoding in the config
  sig { returns(Integer) }
  def largest_encoding
    @largest_encoding ||=
      if fully_configured?
        transitive_implemented_instructions.map(&:max_encoding_width).max
      elsif partially_configured?
        not_prohibited_instructions.map(&:max_encoding_width).max
      else
        instructions.map(&:max_encoding_width).max
      end
  end

  # @return [Array<FuncDefAst>] List of all reachable IDL functions for the config
  sig { returns(T::Array[Idl::FunctionDefAst]) }
  def implemented_functions
    return @implemented_functions if @implemented_functions
    return [] unless fully_configured?

    @implemented_functions = []

    puts "  Finding all reachable functions from instruction operations"

    transitive_implemented_instructions.each do |inst|
      @implemented_functions <<
        if inst.base.nil?
          if multi_xlen?
            (inst.reachable_functions(32) +
            inst.reachable_functions(64))
          else
            inst.reachable_functions(mxlen)
          end
        else
          inst.reachable_functions(inst.base)
        end
    end
    @implemented_functions = @implemented_functions.flatten
    @implemented_functions.uniq!(&:name)

    puts "  Finding all reachable functions from CSR operations"

    transitive_implemented_csrs.each do |csr|
      csr_funcs = csr.reachable_functions
      csr_funcs.each do |f|
        @implemented_functions << f unless @implemented_functions.any? { |i| i.name == f.name }
      end
    end

    # now add everything from fetch
    symtab = @symtab.global_clone
    symtab.push(@global_ast.fetch.body)
    fetch_fns = @global_ast.fetch.body.reachable_functions(symtab)
    fetch_fns.each do |f|
      @implemented_functions << f unless @implemented_functions.any? { |i| i.name == f.name }
    end
    symtab.release

    @implemented_functions
  end

  # @return [Array<FunctionDefAst>] List of functions that can be reached by the configuration
  sig { returns(T::Array[Idl::FunctionDefAst]) }
  def reachable_functions
    return @reachable_functions unless @reachable_functions.nil?

    insts = not_prohibited_instructions
    @reachable_functions = []

    insts.each do |inst|
      fns =
        if inst.base.nil?
          if multi_xlen?
            (inst.reachable_functions(32) +
            inst.reachable_functions(64))
          else
            inst.reachable_functions(mxlen)
          end
        else
          inst.reachable_functions(inst.base)
        end

      @reachable_functions.concat(fns)
    end

    @reachable_functions +=
      not_prohibited_csrs.flat_map(&:reachable_functions).uniq

    # now add everything from fetch
    symtab = @symtab.global_clone
    symtab.push(@global_ast.fetch.body)
    @reachable_functions += @global_ast.fetch.body.reachable_functions(symtab)
    symtab.release

    # now add everything from external functions
    symtab = @symtab.global_clone
    @global_ast.functions.select { |fn| fn.external? }.each do |fn|
      symtab.push(fn)
      @reachable_functions << fn
      fn.apply_template_and_arg_syms(symtab)
      @reachable_functions += fn.reachable_functions(symtab)
      symtab.pop
    end
    symtab.release

    @reachable_functions.uniq!
    @reachable_functions
  end

  # @return [Array<NonIsaSpecification>] List of all non-ISA specs that could apply to this configuration
  sig { returns(T::Array[T.untyped]) }
  def possible_non_isa_specs
    return @possible_non_isa_specs if defined?(@possible_non_isa_specs)



    @possible_non_isa_specs = []

    # Discover local non-ISA specifications
    non_isa_path = Pathname.new(__dir__).parent.parent.parent.parent.parent / "spec/custom/non_isa"
    if non_isa_path.exist?
      non_isa_path.glob("*.yaml").each do |spec_file|
        next if spec_file.basename.to_s.start_with?('prm') # Skip PRM files

        begin
          spec_name = spec_file.basename('.yaml').to_s
          spec_data = YAML.load_file(spec_file)
          next unless spec_data['kind'] == 'non-isa specification'

          spec_obj = Udb::NonIsaSpecification.new(spec_name, spec_data)
          @possible_non_isa_specs << spec_obj
        rescue => e
          warn "Failed to load non-ISA spec #{spec_file}: #{e.message}"
        end
      end
    end

    @possible_non_isa_specs.sort_by(&:name)
  end

  # @return [Array<NonIsaSpecification>] List of all implemented non-ISA specs, filtered by configuration
  sig { returns(T::Array[T.untyped]) }
  def implemented_non_isa_specs
    return @implemented_non_isa_specs if defined?(@implemented_non_isa_specs)

    @implemented_non_isa_specs = possible_non_isa_specs.select do |spec|
      spec.exists_in_cfg?(self)
    end

    @implemented_non_isa_specs
  end
  alias transitive_implemented_non_isa_specs implemented_non_isa_specs

  # Given an adoc string, find names of CSR/Instruction/Extension enclosed in `monospace`
  # and replace them with links to the relevant object page.
  # See backend_helpers.rb for a definition of the proprietary link format.
  #
  # @param adoc [String] Asciidoc source
  # @return [String] Asciidoc source, with link placeholders
  sig { params(adoc: String).returns(String) }
  def convert_monospace_to_links(adoc)
    h = Class.new do include Udb::Helpers::TemplateHelpers end.new
    adoc.gsub(/`([\w.]+)`/) do |match|
      name = Regexp.last_match(1)
      csr_name, field_name = T.must(name).split(".")
      csr = not_prohibited_csrs.find { |c| c.name == csr_name }
      if !field_name.nil? && !csr.nil? && csr.field?(field_name)
        h.link_to_udb_doc_csr_field(csr_name, field_name)
      elsif !csr.nil?
        h.link_to_udb_doc_csr(csr_name)
      elsif not_prohibited_instructions.any? { |inst| inst.name == name }
        h.link_to_udb_doc_inst(name)
      elsif not_prohibited_extensions.any? { |ext| ext.name == name }
        h.link_to_udb_doc_ext(name)
      else
        match
      end
    end
  end

  # Returns an environment hash suitable for use with ERb templates.
  #
  # This method returns a hash containing the architecture definition and other
  # relevant data that can be used to generate ERb templates.
  #
  # @return [Hash] An environment hash suitable for use with ERb templates.
  sig { returns(Object) }
  def erb_env
    return @env unless @env.nil?

    @env = Class.new
    @env.extend T::Sig
    @env.instance_variable_set(:@cfg, @cfg)
    @env.instance_variable_set(:@params, @params)
    @env.instance_variable_set(:@cfg_arch, self)
    @env.instance_variable_set(:@arch, self) # For backwards-compatibility

    # add each parameter, either as a method (lowercase) or constant (uppercase)
    params_with_value.each do |param|
      @env.const_set(param.name, param.value) unless @env.const_defined?(param.name)
    end

    params_without_value.each do |param|
      @env.const_set(param.name, :unknown) unless @env.const_defined?(param.name)
    end

    @env.instance_exec do
      # method to check if a given extension (with an optional version number) is present
      #
      # @param ext_name [String,#to_s] Name of the extension
      # @param ext_requirement [String, #to_s] Version string, as a Gem Requirement (https://guides.rubygems.org/patterns/#pessimistic-version-constraint)
      # @return [Boolean] whether or not extension +ext_name+ meeting +ext_requirement+ is implemented in the config
      sig { params(ext_name: T.any(String, Symbol), ext_requirements: T.any(String, T::Array[String])).returns(T::Boolean) }
      def ext?(ext_name, ext_requirements = [])
        ext_reqs =
          case ext_requirements
          when Array
            ext_requirements
          when String
            [ext_requirements]
          else
            T.absurd(ext_requirements)
          end
        @cfg_arch.ext?(ext_name.to_s, ext_reqs)
      end

      # List of possible XLENs for any implemented mode
      sig { returns(T::Array[Integer]) }
      def possible_xlens
        @cfg_arch.possible_xlens
      end

      # info on interrupt and exception codes

      # @returns [Hash<Integer, String>] architecturally-defined exception codes and their names
      def exception_codes
        @cfg_arch.exception_codes
      end

      # returns [Hash<Integer, String>] architecturally-defined interrupt codes and their names
      def interrupt_codes
        @cfg_arch.interrupt_codes
      end

      # @returns [Hash<Integer, String>] architecturally-defined exception codes and their names
      def implemented_exception_codes
        @cfg_arch.implemented_exception_codes
      end

      # returns [Hash<Integer, String>] architecturally-defined interrupt codes and their names
      def implemented_interrupt_codes
        @cfg_arch.implemented_interrupt_codes
      end
    end

    @env
  end
  private :erb_env

  # passes _erb_template_ through ERB within the content of this config
  #
  # @param erb_template [String] ERB source
  # @return [String] The rendered text
  sig { params(erb_template: String, what: String).returns(String) }
  def render_erb(erb_template, what = "")
    t = Tempfile.new("template")
    t.write erb_template
    t.flush
    begin
      Tilt["erb"].new(t.path, trim: "-").render(erb_env)
    rescue
      warn "While rendering ERB template: #{what}"
      raise
    ensure
      t.close
      t.unlink
    end
  end
end

end

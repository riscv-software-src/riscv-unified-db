# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

# Many classes include DatabaseObject have an "cfg_arch" member which is a ConfiguredArchitecture class.
# It combines knowledge of the RISC-V Architecture with a particular configuration.
# A configuration is an instance of the AbstractConfig object either located in the /cfg directory
# or created at runtime for things like profiles and certificate models.

require "concurrent"
require "tilt"
require "tty-progressbar"
require "yaml"
require "pathname"
require_relative "obj/non_isa_specification"
require_relative "config"
require_relative "architecture"
require_relative "log"

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

    # MXLEN parameter value, or nil if it is not known
    sig { returns(T.nilable(Integer)) }
    def mxlen = @config.mxlen

    # known parameter values as a hash of param_name => param_value
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
    # @return true if this configuration might execute in multiple xlen environments
    #           (e.g., that in some mode the effective xlen can be either 32 or 64, depending on CSR values)
    sig { returns(T::Boolean) }
    def multi_xlen?
      @memo.multi_xlen ||=
        begin
          return true if @mxlen.nil?

          ["S", "U", "VS", "VU"].any? { |mode| multi_xlen_in_mode?(mode) }
        end
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
    # @param mode mode to check. One of "M", "S", "U", "VS", "VU"
    # @return true if this configuration might execute in multiple xlen environments in +mode+
    #           (e.g., that in some mode the effective xlen can be either 32 or 64, depending on CSR values)
    sig { params(mode: String).returns(T::Boolean) }
    def multi_xlen_in_mode?(mode)
      @memo.multi_xlen_in_mode[mode] ||=
        begin
          return false if mxlen == 32

          case mode
          when "M"
            mxlen.nil?
          when "S"
            return true if unconfigured?

            if fully_configured?
              ext?(:S) && (param_values["SXLEN"].size > 1)
            elsif partially_configured?
              return false if prohibited_ext?(:S)

              return true unless ext?(:S) # if S is not known to be implemented, we can't say anything about it

              return true unless param_values.key?("SXLEN")

              param_values["SXLEN"].size > 1
            else
              raise "Unexpected configuration state"
            end
          when "U"
            return false if prohibited_ext?(:U)

            return true if unconfigured?

            if fully_configured?
              ext?(:U) && (param_values["UXLEN"].size > 1)
            elsif partially_configured?
              return true unless ext?(:U) # if U is not known to be implemented, we can't say anything about it

              return true unless param_values.key?("UXLEN")

              param_values["UXLEN"].size > 1
            else
              raise "Unexpected configuration state"
            end
          when "VS"
            return false if prohibited_ext?(:H)

            return true if unconfigured?

            if fully_configured?
              ext?(:H) && (param_values["VSXLEN"].size > 1)
            elsif partially_configured?
              return true unless ext?(:H) # if H is not known to be implemented, we can't say anything about it

              return true unless param_values.key?("VSXLEN")

              param_values["VSXLEN"].size > 1
            else
              raise "Unexpected configuration state"
            end
          when "VU"
            return false if prohibited_ext?(:H)

            return true if unconfigured?

            if fully_configured?
              ext?(:H) && (param_values["VUXLEN"].size > 1)
            elsif partially_configured?
              return true unless ext?(:H) # if H is not known to be implemented, we can't say anything about it

              return true unless param_values.key?("VUXLEN")

              param_values["VUXLEN"].size > 1
            else
              raise "Unexpected configuration state"
            end
          else
            raise ArgumentError, "Bad mode"
          end
        end
    end

    # @return [Array<Integer>] List of possible XLENs in any mode for this config
    sig { returns(T::Array[Integer]) }
    def possible_xlens = multi_xlen? ? [32, 64] : [mxlen]

    # @api private
    # hash for Hash lookup
    sig { override.returns(Integer) }
    def hash = @name_sym.hash

    sig { override.params(other: T.anything).returns(T::Boolean) }
    def eql?(other)
      return false unless other.is_a?(ConfiguredArchitecture)

      @name.eql?(other.name)
    end

    # @return Symbol table with global scope included
    sig { returns(Idl::SymbolTable) }
    def symtab
      @symtab ||=
        begin
          @symtab = create_symtab

          global_ast.add_global_symbols(@symtab)

          @symtab.deep_freeze
          raise if @symtab.name.nil?
          global_ast.freeze_tree(@symtab)
          @symtab
        end
    end

    sig { returns(Idl::IsaAst) }
    def global_ast
      @global_ast ||=
        begin
          # now add globals to the phase1 symtab
          overlay_path = @config.info.overlay_path
          custom_globals_path = overlay_path.nil? ? Pathname.new("/does/not/exist") : overlay_path / "isa" / "globals.isa"
          idl_path = File.exist?(custom_globals_path) ? custom_globals_path : @config.info.spec_path / "isa" / "globals.isa"
          @idl_compiler.compile_file(
            idl_path
          )
        end
    end

    sig { returns(ConfigType) }
    def config_type = @config_type

    # return type for #valid?
    class ValidationResult < T::Struct
      const :valid, T::Boolean
      const :reasons, T::Array[String]   # filled with messages if valid is false
    end

    # whether or not the configuration is valid. if it's not, reasons are provided
    sig { returns(ValidationResult) }
    def valid?
      if fully_configured?
        full_config_valid?
      elsif partially_configured?
        partial_config_valid?
      else
        ValidationResult.new(valid: true, reasons: [])
      end
    end

    # @api private
    sig { returns(ValidationResult) }
    def full_config_valid?
      # check extension requirements
      reasons = []

      explicitly_implemented_extension_versions.each do |ext_ver|
        unless ext_ver.valid?
          reasons << "Extension version has no definition: #{ext_ver}"
          next
        end

        unless ext_ver.combined_requirements_condition.satisfied_by_cfg_arch?(self) == SatisfiedResult::Yes
          reasons << "Extension requirement is unmet: #{ext_ver}. Needs: #{ext_ver.combined_requirements_condition}"
        end
      end

      # check parameter requirements
      config.param_values.each do |param_name, param_value|
        p = param(param_name)
        if p.nil?
          reasons << "Parameter has no definition: '#{param_name}'"
          next
        end
        unless p.schema.validate(param_value, udb_resolver: @config.info.resolver)
          reasons << "Parameter value violates the schema: '#{param_name}' = '#{param_value}'"
        end
        unless p.defined_by_condition.satisfied_by_cfg_arch?(self) == SatisfiedResult::Yes
          reasons << "Parameter is not defined by this config: '#{param_name}'. Needs: #{p.defined_by_condition}"
        end
        unless p.requirements_condition.satisfied_by_cfg_arch?(self) == SatisfiedResult::Yes
          reasons << "Parameter requirements not met: '#{param_name}'. Needs: #{p.requirements_condition}        #{p.requirements_condition.to_logic_tree(expand: true)}"
        end
      end

      # to know all of the parameters that must be listed, we have to expand the implemented extension versions
      # and then collect all of the defined parameters
      required_parameters = params.select do |param|
        param.defined_by_condition.satisfied_by_cfg_arch?(self) == SatisfiedResult::Yes
      end

      missing_params = required_parameters.reject do |param|
        config.param_values.key?(param.name)
      end
      unless missing_params.empty?
        reasons += missing_params.map { |p| "Parameter is required but missing: '#{p.name}'" }
      end

      if reasons.empty?
        ValidationResult.new(valid: true, reasons: [])
      else
        ValidationResult.new(valid: false, reasons:)
      end
    end
    private :full_config_valid?

    # @api private
    sig { returns(ValidationResult) }
    def partial_config_valid?
      reasons = []

      mandatory_extension_reqs.each do |ext_req|
        unless ext_req.valid?
          reasons << "Extension requirement can never be met (no match in the database): #{ext_req}"
        end
      end

      # first check extension requirements
      # need to make sure that it is possible to construct a config that
      # meets the requirements without introducing a conflict
      mandatory_cond =
        Condition.conjunction(
          mandatory_extension_reqs.select(&:valid?).map { |ext_req| ext_req.to_condition },
          self
        )
      unless mandatory_cond.satisfiable?
        mandatory_cond.to_logic_tree(expand: true).minimal_unsat_subsets.each do |min|
          reasons << "Mandatory extension requirements conflict: This is not satisfiable: #{min.to_s(format: LogicNode::LogicSymbolFormat::C)}"
        end
      end

      # check that provided param values are defined and match the schema
      config.param_values.each do |param_name, param_value|
        p = param(param_name)
        # pwv.name is not a defined parameter
        if p.nil?
          reasons << "Parameter has no definition: '#{param_name}'"
          next
        end

        unless p.schema.validate(param_value, udb_resolver: @config.info.resolver)
          reasons << "Parameter value violates the schema: '#{param_name}' = '#{param_value}'"
        end

        # check that parameter is defined by the partial config (e.g., is defined by a mandatory
        # extension and/or other param value).
        unless p.defined_by_condition.satisfied_by_cfg_arch?(self) == SatisfiedResult::Yes
          reasons << "Parameter is not defined by this config: '#{param_name}'. Needs #{p.defined_by_condition}"
        end

        if p.requirements_condition.satisfied_by_cfg_arch?(self) == SatisfiedResult::No
          reasons << "Parameter requirements cannot be met: '#{param_name}'. Needs: #{p.requirements_condition}"
        end
      end

      unless reasons.empty?
        return ValidationResult.new(valid: false, reasons:)
      end

      ValidationResult.new(valid: true, reasons: [])
    end
    private :partial_config_valid?

    # @api private
    # Return callbacks needed by a SymbolTable to check properties of the configuration
    sig { returns(Idl::SymbolTable::BuiltinFunctionCallbacks) }
    def symtab_callbacks
      Idl::SymbolTable::BuiltinFunctionCallbacks.new(
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
              if implemented_csrs.any? { |c| c.address == csr_addr }
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
    end
    private :symtab_callbacks

    # @api private
    # generated enum defintions for the symbol table
    sig { returns(T::Array[Idl::SymbolTable::EnumDef]) }
    def symtab_enums
      [
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
      ]
    end
    private :symtab_enums

    # @api private
    sig { returns(Idl::SymbolTable) }
    def create_symtab
      all_params = # including both those will value/without value, and those in scope/out of scope
        @config.param_values.map do |pname, pvalue|
          p = param(pname)
          unless p.nil?
            ParameterWithValue.new(p, pvalue)
          end
        end.compact \
        + params.reject { |p| @config.param_values.key?(p.name) }
      final_param_vars = all_params.map do |param|
        idl_type =
          if param.schema_known?
            param.idl_type
          else
            begin
              idl_types =
                param.possible_schemas.map do |schema|
                  schema.to_idl_type
                end
              if idl_types.fetch(0).kind == :bits
                # use the worst case sizing
                if !(t = idl_types.find { |t| t.width == :unknown }).nil?
                  t
                else
                  idl_types.max { |t1, t2| T.cast(t1.width, Integer) <=> T.cast(t2.width, Integer) }
                end
              else
                idl_types.at(0)
              end
            rescue Parameter::NoMatchingSchemaError
              # nothing matched. That's only OK if this parameter is not defined in this config
              # unfortunately, we can't easily check that there because that requires a constructed
              # symtab ;(
              # we are just going to assume the user has validated the config (or is in the process
              # of validating it)
              # if param.defined_by_condition.satisfied_by_cfg_arch?(self)
              #   Udb.logger.warn "Parameter '#{param.name}' is defined, but has no matching schema"
              # end

              # just pick some possible schema
              param.all_schemas.fetch(0).to_idl_type
            end
          end
        if param.value_known?
          Idl::Var.new(param.name, idl_type.make_const, param.value, param: true)
        else
          Idl::Var.new(param.name, idl_type.make_const, param: true)
        end
      end

      Idl::SymbolTable.new(
        mxlen:,
        possible_xlens_cb: proc { possible_xlens },
        builtin_global_vars: final_param_vars,
        builtin_funcs: symtab_callbacks,
        builtin_enums: symtab_enums,
        name: @name,
        csrs:,
        params: all_params
      )
    end
    private :create_symtab

    class MemoizedState < T::Struct
      prop :multi_xlen_in_mode, T::Hash[String, T::Boolean]
      prop :multi_xlen, T.nilable(T::Boolean)
      prop :params_with_value, T.nilable(T::Array[ParameterWithValue])
      prop :params_without_value, T.nilable(T::Array[Parameter])
      prop :out_of_scope_params, T.nilable(T::Array[Parameter])
      prop :implemented_extension_versions, T.nilable(T::Array[ExtensionVersion])
      prop :implemented_extension_version_hash, T.nilable(T::Hash[String, ExtensionVersion])
    end

    # Initialize a new configured architecture definition
    #
    # @param name [:to_s]      The name associated with this ConfiguredArchitecture
    # @param config [AbstractConfig]   The configuration object
    # @param arch_path [Pathnam] Path to the resolved architecture directory corresponding to the configuration
    sig { params(name: String, config: AbstractConfig).void }
    def initialize(name, config)
      Udb.logger.info "Constructing ConfiguredArchiture for #{name}"
      super(config.info.resolved_spec_path)

      @name = name.to_s.freeze
      @name_sym = @name.to_sym.freeze

      @memo = MemoizedState.new(multi_xlen_in_mode: {})

      @config = config
      @config_type = T.let(@config.type, ConfigType)
      @mxlen = config.mxlen
      @mxlen.freeze

      @idl_compiler = Idl::Compiler.new
    end

    def inspect
      "CfgArch##{name}"
    end

    # @api private
    # metaprogramming function to create accessor methods for top-level database objects
    #
    # This is defined in ConfiguredArchitecture, rather than Architecture because the object
    # models all expect to work with a ConfiguredArchitecture
    #
    # For example, created the following functions:
    #   extensions        # array of all extensions
    #   extension_hash    # hash of all extensions, indexed by name
    #   extension(name)   # getter for extension 'name'
    #   instructions      # array of all extensions
    #   instruction_hash  # hash of all extensions, indexed by name
    #   instruction(name) # getter for extension 'name'
    #   ...
    #
    # @!macro [attach] generate_obj_methods
    #   @method $1s
    #   @return [Array<$3>] List of all $1s defined in the standard
    #
    #   @method $1_hash
    #   @return [Hash<String, $3>] Hash of all $1s
    #
    #   @method $1
    #   @param name [String] The $1 name
    #   @return [$3] The $1
    #   @return [nil] if there is no $1 named +name+
    sig { params(fn_name: String, arch_dir: String, obj_class: T.class_of(TopLevelDatabaseObject)).void }
    def self.generate_obj_methods(fn_name, arch_dir, obj_class)

      plural_fn = ActiveSupport::Inflector.pluralize(fn_name)

      define_method(plural_fn) do
        return @objects[arch_dir] unless @objects[arch_dir].nil?

        @objects[arch_dir] = Concurrent::Array.new
        @object_hashes[arch_dir] = Concurrent::Hash.new
        Dir.glob(@arch_dir / arch_dir / "**" / "*.yaml") do |obj_path|
          f = File.open(obj_path)
          f.flock(File::LOCK_EX)
          obj_yaml = YAML.load(f.read, filename: obj_path, permitted_classes: [Date])
          f.flock(File::LOCK_UN)
          @objects[arch_dir] << obj_class.new(obj_yaml, Pathname.new(obj_path).realpath, T.cast(self, ConfiguredArchitecture))
          @object_hashes[arch_dir][@objects[arch_dir].last.name] = @objects[arch_dir].last
        end
        @objects[arch_dir]
      end

      define_method("#{fn_name}_hash") do
        return @object_hashes[arch_dir] unless @object_hashes[arch_dir].nil?

        send(plural_fn) # create the hash

        @object_hashes[arch_dir]
      end

      define_method(fn_name) do |name|
        return @object_hashes[arch_dir][name] unless @object_hashes[arch_dir].nil?

        send(plural_fn) # create the hash

        @object_hashes[arch_dir][name]
      end
    end

    # call generate_obj_methods for each known top-level database object
    OBJS.each do |obj_info|
      generate_obj_methods(obj_info[:fn_name], obj_info[:arch_dir], obj_info[:klass])
    end

    # type check all IDL, including globals, instruction ops, and CSR functions
    #
    # @param show_progress whether to show progress bars
    # @param io where to write progress bars
    # @return [void]
    sig { params(show_progress: T::Boolean, io: IO).void }
    def type_check(show_progress: true, io: $stdout)
      io.puts "Type checking IDL code for #{@config.name}..." if show_progress
      insts = possible_instructions(show_progress:)

      progressbar =
        if show_progress
          TTY::ProgressBar.new("type checking possible instructions [:bar]", total: insts.size, output: $stdout)
        end

      possible_instructions.each do |inst|
        progressbar.advance if show_progress
        if @mxlen == 32
          inst.type_checked_operation_ast(32) if inst.rv32?
        elsif @mxlen == 64
          inst.type_checked_operation_ast(64) if inst.rv64?
          inst.type_checked_operation_ast(32) if possible_xlens.include?(32) && inst.rv32?
        end
      end

      progressbar =
        if show_progress
          TTY::ProgressBar.new("type checking CSRs [:bar]", total: possible_csrs.size, output: $stdout)
        end

      possible_csrs.each do |csr|
        progressbar.advance if show_progress
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
          unless field.sw_write_ast(symtab).nil?
            field.type_checked_sw_write_ast(symtab, 32) if possible_xlens.include?(32) && csr.defined_in_base32? && field.defined_in_base32?
            field.type_checked_sw_write_ast(symtab, 64) if possible_xlens.include?(64) && csr.defined_in_base64? && field.defined_in_base64?
          end
        end
      end

      func_list = reachable_functions(show_progress:)
      progressbar =
        if show_progress
          TTY::ProgressBar.new("type checking functions [:bar]", total: func_list.size, output: $stdout)
        end
      func_list.each do |func|
        progressbar.advance if show_progress
        func.type_check(symtab)
      end

      puts "done" if show_progress
    end

    # @return List of all parameters with one known value in the config
    sig { returns(T::Array[ParameterWithValue]) }
    def params_with_value
      @memo.params_with_value ||=
        @config.param_values.map do |param_name, param_value|
          p = param(param_name)
          if p.nil?
            Udb.logger.warn "#{param_name} is not a parameter"
          else
            ParameterWithValue.new(p, param_value)
          end
        end.compact
    end

    # List of all available parameters without one known value in the config
    sig { returns(T::Array[Parameter]) }
    def params_without_value
      @memo.params_without_value ||=
        params.select do |p|
          !@config.param_values.key?(p.name) \
            && p.defined_by_condition.could_be_satisfied_by_cfg_arch?(self)
        end
    end

    # Returns list of parameters that out of scope for the config
    sig { returns(T::Array[Parameter]) }
    def out_of_scope_params
      @memo.out_of_scope_params ||=
        begin
          out_of_scope_params = []
          params.each do |param|
            next if params_with_value.any? { |p| p.name == param.name }
            next if params_without_value.any? { |p| p.name == param.name }

            out_of_scope_params << param
          end
          out_of_scope_params
        end
    end

    # @return List of extension versions explicitly marked as implemented in the config.
    sig { returns(T::Array[ExtensionVersion]) }
    def implemented_extension_versions
      @memo.implemented_extension_versions ||=
        begin
          unless fully_configured?
            raise ArgumentError, "implemented_extension_versions only valid for fully configured systems"
          end

          T.cast(@config, FullConfig).implemented_extensions.map do |e|
            ExtensionVersion.new(e.fetch("name"), e.fetch("version"), self, fail_if_version_does_not_exist: false)
          end
        end
    end

    # @deprecated in favor of implemented_extension_versions
    def explicitly_implemented_extension_versions = implemented_extension_versions

    # @deprecated in favor of implemented_extension_versions
    def transitive_implemented_extension_versions = implemented_extension_versions


    # given the current (invalid) config, try to come up with a list of extension versions that,
    # if added, might make the config valid
    #
    # For example, if C, F, and D are implemented but not Zca, Zcf, Zcd, return [Zca, Zcf, Zcd]
    sig { params(ext_vers: T::Array[ExtensionVersion]).returns(T::Array[ExtensionVersion]) }
    def expand_implemented_extension_list(ext_vers)

      # build up a condition requiring all ext_vers, have it expand, and then minimize it
      # what's left is the full list
      condition =
        Condition.conjunction(ext_vers.map(&:to_condition), self)

      res = condition.implied_extension_requirements
      (ext_vers +
      res.map do |cond_ext_req|
        if cond_ext_req.cond.empty?
          cond_ext_req.ext_req.satisfying_versions.fetch(0)
        else
          nil
        end
      end.compact).uniq
    end


    sig { params(ext_name: String).returns(T.nilable(ExtensionVersion)) }
    def implemented_extension_version(ext_name)
      @memo.implemented_extension_version_hash ||=
        implemented_extension_versions.to_h { |ext_ver| [ext_ver.name, ext_ver] }

      @memo.implemented_extension_version_hash[ext_name]
    end

    # @return List of all mandatory extension requirements (not transitive)
    sig { returns(T::Array[ExtensionRequirement]) }
    def mandatory_extension_reqs
      @mandatory_extension_reqs ||=
        begin
          raise "Only partial configs have mandatory extension requirements" unless @config.is_a?(PartialConfig)

          @config.mandatory_extensions.map do |e|
            ename = T.cast(e["name"], String)

            if e["version"].nil?
              ExtensionRequirement.new(ename, ">= 0", presence: Presence.new("mandatory"), arch: self)
            else
              if e["version"].is_a?(Array)
                ExtensionRequirement.new(ename, T.cast(e.fetch("version"), T::Array[String]), presence: Presence.new("mandatory"), arch: self)
              else
                ExtensionRequirement.new(ename, T.cast(e.fetch("version"), String), presence: Presence.new("mandatory"), arch: self)
              end
            end
          end
        end
    end

    # list of all the extension versions that optional, i.e:
    # lis of all the extension versions would not fufill a mandatory requirement and are not prhohibited
    sig { returns(T::Array[ExtensionRequirement]) }
    def optional_extension_versions
      @optional_extension_versions ||=
        begin
          if fully_configured?
            []
          elsif partially_configured?
            # optional is all extensions - mandatory - prohibited
            extension_versions.reject do |ext_ver|
              mandatory_extension_reqs.any? { |ext_req| ext_req.satisfied_by?(ext_ver) } ||
                prohibited_extension_versions.any? { |prohibited_ext_ver| prohibited_ext_ver == ext_ver }
            end
          else
            # unconfig; all extension versions are optional
            extension_versions
          end
        end
    end

    # @return [Array<Extension>] List of extensions that are possibly supported
    sig { returns(T::Array[Extension]) }
    def possible_extensions
      return @not_prohibited_extensions if defined?(@not_prohibited_extensions)

      @not_prohibited_extensions ||=
        if @config.fully_configured?
          implemented_extension_versions.map { |ext_ver| ext_ver.ext }.uniq
        elsif @config.partially_configured?
          # reject any extension in which all of the extension versions are prohibited
          extensions.reject { |ext| (ext.versions - prohibited_extension_versions).empty? }
        else
          extensions
        end
    end
    alias not_prohibited_extensions possible_extensions

    # @return List of all extension versions that are prohibited.
    #           This includes extensions explicitly prohibited by the config file
    #           and extensions that conflict with a mandatory extension.
    sig { returns(T::Array[ExtensionVersion]) }
    def prohibited_extension_versions
      @prohibited_extension_versions ||=
        extension_versions - possible_extension_versions
    end

    # the complete set of extension versions that could be implemented in this config
    def possible_extension_versions
      @possible_extension_versions ||=
        begin
          if @config.partially_configured?
            # collect all the explictly prohibited extensions
            prohibited_ext_reqs =
              T.cast(@config, PartialConfig).prohibited_extensions.map do |ext_req_yaml|
                ExtensionRequirement.create(ext_req_yaml, self)
              end
            prohibition_condition =
              Condition.conjunction(prohibited_ext_reqs.map(&:to_condition), self)

            # collect all mandatory
            mandatory_ext_reqs =
              T.cast(@config, PartialConfig).mandatory_extensions.map do |ext_req_yaml|
                ExtensionRequirement.create(ext_req_yaml, self)
              end
            mandatory_condition =
              Condition.conjunction(mandatory_ext_reqs.map(&:to_condition), self)

            if T.cast(@config, PartialConfig).additional_extensions_allowed?
              # non-mandatory extensions are OK.
              extensions.map(&:versions).flatten.select do |ext_ver|
                # select all versions that can be satisfied simultaneous with
                # the mandatory and !prohibition conditions
                condition =
                  Condition.conjunction(
                    [
                      ext_ver.to_condition,
                      mandatory_condition,
                      Condition.not(prohibition_condition, self)
                    ],
                    self
                  )

                # can't just call condition.could_be_satisfied_by_cfg_arch? here because
                # that implementation calls possible_extension_versions (this function),
                # and we'll get stuck in an infinite loop
                #
                # so, instead, we partially evaluate whatever parameters are known and then
                # see if the formula is satisfiable
                condition.partially_evaluate_for_params(self, expand: true).satisfiable?
              end
            else
              # non-mandatory extensions are NOT allowed
              # we want to return the list of extension versions implied by mandatory,
              # minus any that are explictly prohibited
              mandatory_extension_reqs.map(&:satisfying_versions).flatten.select do |ext_ver|
                condition = Condition.conjunction([Condition.not(prohibition_condition, self), ext_ver.to_condition], self)

                # see comment above for why we don't call could_be_satisfied_by_cfg_arch?
                condition.partially_evaluate_for_params(self, expand: true).satisfiable?
              end
            end
          elsif @config.fully_configured?
            # full config: only the implemented versions are possible
            implemented_extension_versions
          else
            # unconfig; everything is possible
            extensions.map(&:versions).flatten
          end
        end
    end

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
        prohibited_extension_versions.include?(ext)
      elsif ext.is_a?(String) || ext.is_a?(Symbol)
        prohibited_extension_versions.any? { |ext_ver| ext_ver.name == ext.to_s }
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
    # sig { params(ext_name: T.any(String, Symbol), ext_version_requirements: T::Array[String]).returns(T::Boolean) }
    def ext?(ext_name, ext_version_requirements = [])
      @ext_cache ||= {}
      cached_result = @ext_cache[[ext_name, ext_version_requirements]]
      return cached_result unless cached_result.nil?

      result =
        if @config.fully_configured?
          implemented_extension_versions.any? do |e|
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
        exception_codes.select { |code| code.defined_by_condition.satisfied_by_cfg_arch?(self) }
    end

    # @return [Array<InteruptCode>] All interrupt codes known to be implemented
    sig { returns(T::Array[InterruptCode]) }
    def implemented_interrupt_codes
      @implemented_interupt_codes ||=
        implemented_exception_codes.select { |code| code.defined_by_condition.satisfied_by_cfg_arch?(self) }
    end

    # @return [Array<Idl::FunctionBodyAst>] List of all functions defined by the architecture
    sig { returns(T::Array[Idl::FunctionBodyAst]) }
    def functions
      @functions ||= global_ast.functions
    end

    # @return [Idl::FetchAst] Fetch block
    sig { returns(Idl::FetchAst) }
    def fetch
      @fetch ||= global_ast.fetch
    end

    # @return [Array<Idl::GlobalAst>] List of globals
    sig { returns(T::Array[T.any(Idl::GlobalAst, Idl::GlobalWithInitializationAst)]) }
    def globals
      return @globals unless @globals.nil?

      @globals = global_ast.globals
    end

    # @return [Array<Csr>] List of all implemented CSRs
    sig { returns(T::Array[Csr]) }
    def implemented_csrs
      @implemented_csrs ||=
        begin
          unless fully_configured?
            raise ArgumentError, "implemented_csrs is only defined for fully configured systems"
          end

          csrs.select do |csr|
            csr.defined_by_condition.satisfied_by_cfg_arch?(self) == SatisfiedResult::Yes
          end
        end
    end

    # @deprecated in favor of implemented_csrs
    def transitive_implemented_csrs = implemented_csrs

    # @return [Array<Csr>] List of all CSRs that it is possible to implement
    sig { params(show_progress: T::Boolean).returns(T::Array[Csr]) }
    def possible_csrs(show_progress: false)
      @not_prohibited_csrs ||=
        if @config.fully_configured?
          implemented_csrs
        elsif @config.partially_configured?
          bar =
            if show_progress
              TTY::ProgressBar.new("determining possible CSRs [:bar]", total: csrs.size, output: $stdout)
            end
          csrs.select do |csr|
            bar.advance if show_progress
            csr.defined_by_condition.satisfied_by_cfg_arch?(self) != SatisfiedResult::No
          end
        else
          csrs
        end
    end
    alias not_prohibited_csrs possible_csrs

    # @return List of all implemented instructions, sorted by name
    sig { returns(T::Array[Instruction]) }
    def implemented_instructions
      unless fully_configured?
        raise ArgumentError, "implemented_instructions is only defined for fully configured systems"
      end

      @implemented_instructions ||=
        instructions.select do |inst|
          inst.defined_by_condition.satisfied_by_cfg_arch?(self) == SatisfiedResult::Yes
        end
    end

    # @depracted in favor of #implemented_instructions
    def transitive_implemented_instructions = implemented_instructions

    # @return [Array<Instruction>] List of all prohibited instructions, sorted by name
    sig { returns(T::Array[Instruction]) }
    def prohibited_instructions
      # an instruction is prohibited if it is not defined by any .... TODO LEFT OFF HERE....
      @prohibited_instructions ||=
        if fully_configured?
          instructions - implemented_instructions
        elsif partially_configured?
          instructions.select do |inst|
            inst.defined_by_condition.satisfied_by_cfg_arch?(self) == SatisfiedResult::No
          end
        else
          []
        end
    end

    # @depracated in favor of #prohibited_instructions
    def transitive_prohibited_instructions = prohibited_instructions

    # @return List of all instructions that are not prohibited by the config, sorted by name
    sig { params(show_progress: T::Boolean).returns(T::Array[Instruction]) }
    def possible_instructions(show_progress: false)
      return @not_prohibited_instructions if defined?(@not_prohibited_instructions)

      @not_prohibited_instructions ||=
        if @config.fully_configured?
          implemented_instructions
        elsif @config.partially_configured?
          bar =
            if show_progress
              TTY::ProgressBar.new("determining possible instructions [:bar]", total: instructions.size, output: $stdout)
            end
          instructions.select do |inst|
            bar.advance if show_progress

            possible_xlens.any? { |xlen| inst.defined_in_base?(xlen) } && \
              inst.defined_by_condition.satisfied_by_cfg_arch?(self) != SatisfiedResult::No
          end
        else
          instructions
        end

      @not_prohibited_instructions
    end

    alias not_prohibited_instructions possible_instructions

    # @return [Integer] The largest instruction encoding in the config
    sig { returns(Integer) }
    def largest_encoding
      @largest_encoding ||= possible_instructions.map(&:max_encoding_width).max
    end

    # @return [Array<FuncDefAst>] List of all reachable IDL functions for the config
    sig { returns(T::Array[Idl::FunctionDefAst]) }
    def implemented_functions
      return @implemented_functions unless @implemented_functions.nil?

      @implemented_functions = []

      Udb.logger.info "  Finding all reachable functions from instruction operations"

      implemented_instructions.each do |inst|
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

      Udb.logger.info "  Finding all reachable functions from CSR operations"

      implemented_csrs.each do |csr|
        csr_funcs = csr.reachable_functions
        csr_funcs.each do |f|
          @implemented_functions << f unless @implemented_functions.any? { |i| i.name == f.name }
        end
      end

      # now add everything from fetch
      st = symtab.global_clone
      st.push(global_ast.fetch.body)
      fetch_fns = global_ast.fetch.body.reachable_functions(st)
      fetch_fns.each do |f|
        @implemented_functions << f unless @implemented_functions.any? { |i| i.name == f.name }
      end
      st.release

      @implemented_functions
    end

    # @return [Array<FunctionDefAst>] List of functions that can be reached by the configuration
    sig { params(show_progress: T::Boolean).returns(T::Array[Idl::FunctionDefAst]) }
    def reachable_functions(show_progress: false)
      return @reachable_functions unless @reachable_functions.nil?

      @reachable_functions = []

      insts = possible_instructions(show_progress:)
      csrs = possible_csrs(show_progress:)

      bar =
        if show_progress
          TTY::ProgressBar.new("determining reachable IDL functions [:bar]", total: insts.size + csrs.size + 1 + global_ast.functions.size, output: $stdout)
        end

      possible_instructions.each do |inst|
        bar.advance if show_progress

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
        possible_csrs.flat_map do |csr|
          bar.advance if show_progress

          csr.reachable_functions
        end.uniq

      # now add everything from fetch
      st = @symtab.global_clone
      st.push(global_ast.fetch.body)
      @reachable_functions += global_ast.fetch.body.reachable_functions(st)
      bar.advance if show_progress
      st.release

      # now add everything from external functions
      st = @symtab.global_clone
      global_ast.functions.select { |fn| fn.external? }.each do |fn|
        st.push(fn)
        @reachable_functions << fn
        fn.apply_template_and_arg_syms(st)
        @reachable_functions += fn.reachable_functions(st)
        bar.advance if show_progress
        st.pop
      end
      st.release

      @reachable_functions.uniq!
      @reachable_functions
    end

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


    # @return [Array<NonIsaSpecification>] List of all non-ISA specs that could apply to this configuration
    sig { returns(T::Array[T.untyped]) }
    def possible_non_isa_specs
      return @possible_non_isa_specs if defined?(@possible_non_isa_specs)



      @possible_non_isa_specs = []

      # Discover local non-ISA specifications
      non_isa_path = Pathname.new(__dir__).parent.parent.parent.parent.parent / "spec/custom/non_isa"
      if non_isa_path.exist?
        non_isa_path.glob("*.yaml").each do |spec_file|
          next if spec_file.basename.to_s.start_with?("prm") # Skip PRM files

          begin
            spec_name = spec_file.basename(".yaml").to_s
            spec_data = YAML.load_file(spec_file)
            next unless spec_data["kind"] == "non-isa specification"

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

    # @deprecated in favor of #implemented_non_isa_specs
    def transitive_implemented_non_isa_specs = implemented_non_isa_specs

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

  end
end

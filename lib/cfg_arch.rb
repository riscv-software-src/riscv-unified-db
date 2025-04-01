# frozen_string_literal: true

# Many classes include DatabaseObject have an "cfg_arch" member which is a ConfiguredArchitecture class.
# It combines knowledge of the RISC-V Architecture with a particular configuration.
# A configuration is an instance of the Config object either located in the /cfg directory
# or created at runtime for things like profiles and certificate models.

require "concurrent"
require "forwardable"
require "ruby-prof"
require "tilt"

require_relative "config"
require_relative "architecture"

require_relative "idl"
require_relative "idl/passes/find_return_values"
require_relative "idl/passes/gen_adoc"
require_relative "idl/passes/prune"
require_relative "idl/passes/reachable_exceptions"
require_relative "idl/passes/reachable_functions"

require_relative "template_helpers"

include TemplateHelpers

class ConfiguredArchitecture < Architecture
  extend Forwardable

  # @return [Idl::Compiler] The IDL compiler
  attr_reader :idl_compiler

  # @return [Idl::IsaAst] Abstract syntax tree of global scope
  attr_reader :global_ast

  # @return [String] Name of this definition. Special names are:
  #                  * '_'   - The generic architecture, with no configuration settings.
  #                  * 'rv32' - A generic RV32 architecture, with only one parameter set (XLEN == 32)
  #                  * 'rv64' - A generic RV64 architecture, with only one parameter set (XLEN == 64)
  attr_reader :name

  def_delegators \
    :@config, \
    :fully_configured?, :partially_configured?, :unconfigured?, :configured?, \
    :mxlen, :param_values

  # Returns whether or not it may be possible to switch XLEN given this definition.
  #
  # There are three cases when this will return true:
  #   1. A mode (e.g., U) is known to be implemented, and the CSR bit that controls XLEN in that mode is known to be writeable.
  #   2. A mode is known to be implemented, but the writability of the CSR bit that controls XLEN in that mode is not known.
  #   3. It is not known if the mode is implemented.
  #
  #
  # @return [Boolean] true if this configuration might execute in multiple xlen environments
  #                   (e.g., that in some mode the effective xlen can be either 32 or 64, depending on CSR values)
  def multi_xlen?
    return true if @mxlen.nil?

    ["S", "U", "VS", "VU"].any? { |mode| multi_xlen_in_mode?(mode) }
  end

  # Returns whether or not it may be possible to switch XLEN in +mode+ given this definition.
  #
  # There are three cases when this will return true:
  #   1. +mode+ (e.g., U) is known to be implemented, and the CSR bit that controls XLEN in +mode+ is known to be writeable.
  #   2. +mode+ is known to be implemented, but the writability of the CSR bit that controls XLEN in +mode+ is not known.
  #   3. It is not known if +mode+ is implemented.
  #
  # Will return false if +mode+ is not possible (e.g., because U is a prohibited extension)
  #
  # @param mode [String] mode to check. One of "M", "S", "U", "VS", "VU"
  # @return [Boolean] true if this configuration might execute in multiple xlen environments in +mode+
  #                   (e.g., that in some mode the effective xlen can be either 32 or 64, depending on CSR values)
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
    else
      raise ArgumentError, "Bad mode"
    end
  end

  # @return [Array<Integer>] List of possible XLENs in any mode for this config
  def possible_xlens = multi_xlen? ? [32, 64] : [mxlen]

  # hash for Hash lookup
  def hash = @name_sym.hash

  # @return [Idl::SymbolTable] Symbol table with global scope
  # @return [nil] if the architecture is not configured (use symtab_32 or symtab_64)
  def symtab
    raise NotImplementedError, "Un-configured ConfiguredArchitectures have no symbol table" if @symtab.nil?

    @symtab
  end

  def config_type = @config.type

  # Initialize a new configured architecture definition
  #
  # @param name [:to_s]      The name associated with this ConfiguredArchitecture
  # @param config [Config]   The configuration object
  # @param arch_path [:to_s] Path to the resolved architecture directory corresponding to the configuration
  def initialize(name, config, arch_path)
    raise ArgumentError, "name needs to be a String but is a #{name.class}" unless name.to_s.is_a?(String)
    raise ArgumentError, "config needs to be a Config but is a #{config.class}" unless config.is_a?(Config)
    raise ArgumentError, "arch_path needs to be a String but is a #{arch_path.class}" unless arch_path.to_s.is_a?(String)
    super(arch_path)

    @name = name.to_s.freeze
    @name_sym = @name.to_sym.freeze

    @obj_cache = {}

    @config = config
    @mxlen = config.mxlen
    @mxlen.freeze

    @idl_compiler = Idl::Compiler.new

    @symtab = Idl::SymbolTable.new(self)
    overlay_path =
      if config.arch_overlay.nil?
        "/does/not/exist"
      elsif File.exist?(config.arch_overlay)
        File.realpath(config.arch_overlay)
      else
        "#{$root}/arch_overlay/#{config.arch_overlay}"
      end

    custom_globals_path = Pathname.new "#{overlay_path}/isa/globals.isa"
    idl_path = File.exist?(custom_globals_path) ? custom_globals_path : $root / "arch" / "isa" / "globals.isa"
    @global_ast = @idl_compiler.compile_file(
      idl_path
    )
    @global_ast.add_global_symbols(@symtab)
    @symtab.deep_freeze
    @global_ast.freeze_tree(@symtab)
  end

  # Returns a string representation of the object, suitable for debugging.
  # @return [String] A string representation of the object.
  def inspect = "ConfiguredArchitecture##{name}"

  # type check all IDL, including globals, instruction ops, and CSR functions
  #
  # @param config [Config] Configuration
  # @param show_progress [Boolean] whether to show progress bars
  # @param io [IO] where to write progress bars
  # @return [void]
  def type_check(show_progress: true, io: $stdout)
    io.puts "Type checking IDL code for #{@config.name}..."
    progressbar =
      if show_progress
        ProgressBar.create(title: "Instructions", total: instructions.size)
      end

    instructions.each do |inst|
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
        ProgressBar.create(title: "CSRs", total: csrs.size)
      end

    csrs.each do |csr|
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

    progressbar =
      if show_progress
        ProgressBar.create(title: "Functions", total: functions.size)
      end
    functions.each do |func|
      progressbar.increment if show_progress
      func.type_check(@symtab)
    end

    puts "done" if show_progress
  end

  # @return [Array<ExtensionParameterWithValue>] List of all parameters with one known value in the config
  def params_with_value
    return @params_with_value unless @params_with_value.nil?

    @params_with_value = []
    return @params_with_value if @config.unconfigured?

    if @config.fully_configured?
      transitive_implemented_extension_versions.each do |ext_version|
        ext = extension(ext_version.name)
        ext.params.each do |ext_param|
          next unless @config.param_values.key?(ext_param.name)

          @params_with_value << ExtensionParameterWithValue.new(
            ext_param,
            @config.param_values[ext_param.name]
          )
        end
      end
    elsif @config.partially_configured?
      mandatory_extension_reqs.each do |ext_requirement|
        ext = extension(ext_requirement.name)
        ext.params.each do |ext_param|
          # Params listed in the config always only have one value.
          next unless @config.param_values.key?(ext_param.name)

          @params_with_value << ExtensionParameterWithValue.new(
            ext_param,
            @config.param_values[ext_param.name]
          )
        end
      end
    else
      raise "ERROR: unexpected config type"
    end
    @params_with_value
  end

  # @return [Array<ExtensionParameter>] List of all available parameters without one known value in the config
  def params_without_value
    return @params_without_value unless @params_without_value.nil?

    @params_without_value = []
    extensions.each do |ext|
      ext.params.each do |ext_param|
        # Params listed in the config always only have one value.
        next if @config.param_values.key?(ext_param.name)

        @params_without_value << ext_param
      end
    end
    @params_without_value
  end

  # Returns a string representation of the object, suitable for debugging.
  # @return [String] A string representation of the object.
  def inspect = "ConfiguredArchitecture##{name}"

  # @return [Array<ExtensionVersion>] List of extension versions explictly marked as implemented in the config.
  #                                   Does *not* include extensions implied by explictly implemented extensions.
  def explicitly_implemented_extension_versions
    return @explicitly_implemented_extension_versions unless @explicitly_implemented_extension_versions.nil?

    unless fully_configured?
      raise ArgumentError, "implemented_extension_versions only valid for fully configured systems"
    end

    @explicitly_implemented_extension_versions ||=
      @config.implemented_extensions.map do |e|
        ExtensionVersion.new(e["name"], e["version"], self, fail_if_version_does_not_exist: true)
      end
  end

  # @return [Array<ExtensionVersion>] List of all extensions known to be implemented in this config, including transitive implications
  def transitive_implemented_extension_versions
    return @transitive_implemented_extension_versions unless @transitive_implemented_extension_versions.nil?

    raise "transitive_implemented_extension_versions is only valid for a fully configured definition" unless @config.fully_configured?

    @transitive_implemented_extension_versions = explicitly_implemented_extension_versions.dup

    added_ext_vers = []
    loop do
      @transitive_implemented_extension_versions.each do |ext_ver|
        ext_ver.implications.each do |implication|
          applies = implication[:cond].satisfied_by? do |ext_req|
            @transitive_implemented_extension_versions.any? do |inner_ext_ver|
              next false if ext_ver == inner_ext_ver

              ext_req.satisfied_by?(inner_ext_ver)
            end
          end
          if applies && !@transitive_implemented_extension_versions.include?(implication[:ext_ver])
            added_ext_vers << implication[:ext_ver]
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
  def mandatory_extension_reqs
    return @mandatory_extension_reqs unless @mandatory_extension_reqs.nil?

    @mandatory_extension_reqs ||=
      @config.mandatory_extensions.map do |e|
        ext = extension(e["name"])
        raise "Cannot find extension #{e['name']} in the architecture definition" if ext.nil?

        ExtensionRequirement.new(e["name"], *e["version"], presence: "mandatory", arch: self)
      end
  end

  # @return [Array<Extension>] List of extensions that are possibly supported
  def not_prohibited_extensions
    return @not_prohibited_extensions unless @not_prohibited_extensions.nil?

    @not_prohibited_extensions ||=
      if @config.fully_configured?
        transitive_implemented_extension_versions.map { |ext_ver| ext_ver.extension }.uniq
      elsif @config.partially_configured?
        # reject any extension in which all of the extension versions are prohibited
        extensions.reject { |ext| (ext.versions - transitive_prohibited_extension_versions).empty? }
      else
        extensions
      end
  end
  alias possible_extensions not_prohibited_extensions

  # @return [Array<ExtensionVersion>] List of all ExtensionVersions that are possible to support
  def not_prohibited_extension_versions
    return @not_prohibited_extension_versions unless @not_prohibited_extension_versions.nil?

    @not_prohibited_extension_versions ||=
      if @config.fully_configured?
        transitive_implemented_extension_versions
      elsif @config.partially_configured?
        extensions.map(&:versions).flatten.reject { |ext_ver| transitive_prohibited_extension_versions.include?(ext_ver) }
      else
        extensions.map(&:version).flatten
      end
  end
  alias possible_extension_versions not_prohibited_extension_versions

  # @return [Array<ExtensionVersion>] List of all extension versions that are prohibited.
  #                                   This includes extensions explicitly prohibited by the config file
  #                                   and extensions that conflict with a mandatory extension.
  def transitive_prohibited_extension_versions
    return @transitive_prohibited_extension_versions unless @transitive_prohibited_extension_versions.nil?

    @transitive_prohibited_extension_versions = []

    if @config.partially_configured?
      add_ext_ver_and_conflicts = lambda do |ext_ver|
        @transitive_prohibited_extension_versions << ext_ver
        ext_ver.conflicts.each do |conflict_ext_ver|
          add_ext_ver_and_conflicts.call(conflict_ext_ver)
        end
      end

      @transitive_prohibited_extension_versions =
        @config.prohibited_extensions.map do |ext_req_data|
          ext_req = ExtensionRequirement.new(ext_req_data["name"], ext_req_data["version"], cfg_arch: self)
          ext_req.satisfying_versions.each { |ext_ver| add_ext_ver_and_conflicts.call(ext_ver) }
        end

      # now add any extensions that are prohibited by a mandatory extension
      mandatory_extension_reqs.each do |ext_req|
        ext_req.satisfying_versions do |ext_ver|
          add_ext_ver_and_conflicts.call(ext_ver)
        end
      end

      # now add everything that is not mandatory or implied by mandatory, if addtional extensions are not allowed
      unless @config.additional_extensions_allowed?
        extensions.each do |ext|
          ext.versions.each do |ext_ver|
            next if mandatory_extension_reqs.any? { |ext_req| ext_req.satisfied_by?(ext_ver) }
            next if mandatory_extension_reqs.any? { |ext_req| ext_req.extension.implies.include?(ext_ver) }

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
  def prohibited_ext?(ext)
    if ext.is_a?(ExtensionVersion)
      transitive_prohibited_extension_versions.include?(ext_ver)
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
  def ext?(ext_name, *ext_version_requirements)
    @ext_cache ||= {}
    cached_result = @ext_cache[[ext_name, ext_version_requirements]]
    return cached_result unless cached_result.nil?

    result =
      if @config.fully_configured?
        transitive_implemented_extension_versions.any? do |e|
          if ext_version_requirements.empty?
            e.name == ext_name.to_s
          else
            requirement = ExtensionRequirement.new(ext_name, *ext_version_requirements, arch: self)
            requirement.satisfied_by?(e)
          end
        end
      elsif @config.partially_configured?
        mandatory_extension_reqs.any? do |e|
          if ext_version_requirements.empty?
            e.name == ext_name.to_s
          else
            requirement = ExtensionRequirement.new(ext_name, *ext_version_requirements, arch: self)
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
  def implemented_exception_codes
    return @implemented_exception_codes unless @implemented_exception_codes.nil?

    @implemented_exception_codes =
      implemented_extensions.reduce([]) do |list, ext_version|
        ecodes = extension(ext_version.name)["exception_codes"]
        next list if ecodes.nil?

        ecodes.each do |ecode|
          # double check that all the codes are unique
          raise "Duplicate exception code" if list.any? { |e| e.num == ecode["num"] || e.name == ecode["name"] || e.var == ecode["var"] }

          unless ecode.dig("when", "version").nil?
            # check version
            next unless ext?(ext_version.name.to_sym, ecode["when"]["version"])
          end
          list << ExceptionCode.new(ecode["name"], ecode["var"], ecode["num"], self)
        end
        list
      end
  end

  # @return [Array<InteruptCode>] All interrupt codes known to be implemented
  def implemented_interrupt_codes
    return @implemented_interrupt_codes unless @implemented_interrupt_codes.nil?

    @implemented_interupt_codes =
      implemented_extensions.reduce([]) do |list, ext_version|
        icodes = extension(ext_version.name)["interrupt_codes"]
        next list if icodes.nil?

        icodes.each do |icode|
          # double check that all the codes are unique
          raise "Duplicate interrupt code" if list.any? { |i| i.num == icode["num"] || i.name == icode["name"] || i.var == icode["var"] }

          unless ecode.dig("when", "version").nil?
            # check version
            next unless ext?(ext_version.name.to_sym, ecode["when"]["version"])
          end
          list << InterruptCode.new(icode["name"], icode["var"], icode["num"], self)
        end
        list
      end
  end

  # @return [Array<Idl::FunctionBodyAst>] List of all functions defined by the architecture
  def functions
    @functions ||= @global_ast.functions
  end

  # @return [Idl::FetchAst] Fetch block
  def fetch
    @fetch ||= @global_ast.fetch
  end

  # @return [Array<Idl::GlobalAst>] List of globals
  def globals
    return @globals unless @globals.nil?

    @globals = @global_ast.globals
  end

  # @return [Array<Csr>] List of all implemented CSRs
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
  def not_prohibited_csrs
    @not_prohibited_csrs =
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
  def not_prohibited_instructions
    return @not_prohibited_instructions unless @not_prohibited_instructions.nil?

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
  def implemented_functions
    return @implemented_functions unless @implemented_functions.nil?

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
    raise "?" unless @implemented_functions.is_a?(Array)
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
      elsif instruction(name)
        "%%LINK%inst;#{name};#{name}%%"
      elsif extension(name)
        "%%LINK%ext;#{name};#{name}%%"
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
  def erb_env
    return @env unless @env.nil?

    @env = Class.new
    @env.instance_variable_set(:@cfg, @cfg)
    @env.instance_variable_set(:@cfg_arch, self)
    @env.instance_variable_set(:@params, @params)

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
      def ext?(ext_name, ext_requirement = ">= 0")
        @cfg_arch.ext?(ext_name.to_s, ext_requirement)
      end

      # @return [Array<Integer>] List of possible XLENs for any implemented mode
      def possible_xlens
        @cfg_arch.possible_xlens
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

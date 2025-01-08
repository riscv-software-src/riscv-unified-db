# frozen_string_literal: true

# Many classes have an "cfg_arch" member which is an ConfiguredArchitecture (not DatabaseObjectect) class.
# The "cfg_arch" member contains the "database" of RISC-V standards including extensions, instructions,
# CSRs, Profiles, and Certificates.
#
# The cfg_arch member has methods such as:
#   extensions()                Array<Extension> of all extensions known to the database (even if not implemented).
#   extension(name)             Extension object for "name" and nil if none.
#   parameters()                Array<ExtensionParameter> of all parameters defined in the architecture
#   param(name)                 ExtensionParameter object for "name" and nil if none.
#   csrs()                      Array<Csr> of all CSRs defined by RISC-V, whether or not they are implemented
#   csr(name)                   Csr object for "name" and nil if none.
#   instructions()              Array<Instruction> of all instructions, whether or not they are implemented
#   inst(name)                  Instruction object for "name" and nil if none.
#   profile_classes             Array<ProfileClass> of all known profile classes.
#   profile_class(class_name)   ProfileClass object for "class_name" and nil if none.
#   profile_releases            Array<ProfileRelease> of all profile releases for all profile classes
#   profile_release(release_name) ProfileRelease object for "release_name" and nil if none.
#   profiles                    Array<Profile> of all profiles in all releases in all classes
#   profile(name)               Profile object for profile "name" and nil if none.
#   cert_classes                Array<CertClass> of all known certificate classes
#   cert_class(name)            CertClass object for "name" and nil if none.
#   cert_models                 Array<CertModel> of all known certificate models across all classes.
#   cert_model(name)            CertModel object for "name" and nil if none.

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
  # @param config_name [#to_s] The name of a configuration, which must correspond
  #                            to a folder name under cfg_path
  def initialize(config_name, arch_path, overlay_path: nil, cfg_path: "#{$root}/cfgs")
    super(arch_path)

    @name = config_name.to_s.freeze
    @name_sym = @name.to_sym.freeze

    @obj_cache = {}

    @config = Config.create("#{cfg_path}/#{config_name}/cfg.yaml")
    @mxlen = @config.mxlen
    @mxlen.freeze

    @idl_compiler = Idl::Compiler.new

    @symtab = Idl::SymbolTable.new(self)
    custom_globals_path = overlay_path.nil? ? Pathname.new("/does/not/exist") : overlay_path / "isa" / "globals.isa"
    idl_path = File.exist?(custom_globals_path) ? custom_globals_path : $root / "arch" / "isa" / "globals.isa"
    @global_ast = @idl_compiler.compile_file(
      idl_path
    )
    @global_ast.add_global_symbols(@symtab)
    @symtab.deep_freeze
    @global_ast.freeze_tree(@symtab)
  end

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
        inst.type_checked_operation_ast(@idl_compiler, @symtab, 32) if inst.rv32?
      elsif @mxlen == 64
        inst.type_checked_operation_ast(@idl_compiler, @symtab, 64) if inst.rv64?
        inst.type_checked_operation_ast(@idl_compiler, @symtab, 32) if possible_xlens.include?(32) && inst.rv32?
      end
    end

    progressbar =
      if show_progress
        ProgressBar.create(title: "CSRs", total: csrs.size)
      end

    csrs.each do |csr|
      progressbar.increment if show_progress
      if csr.has_custom_sw_read?
        if (possible_xlens.include?(32) && csr.defined_in_base32?) || (possible_xlens.include?(64) && csr.defined_in_base64?)
          csr.type_checked_sw_read_ast(@symtab)
        end
      end
      csr.fields.each do |field|
        unless field.type_ast(@symtab).nil?
          if ((possible_xlens.include?(32) && csr.defined_in_base32? && field.defined_in_base32?) ||
              (possible_xlens.include?(64) && csr.defined_in_base64? && field.defined_in_base64?))
            field.type_checked_type_ast(@symtab)
          end
        end
        unless field.reset_value_ast(@symtab).nil?
          if ((possible_xlens.include?(32) && csr.defined_in_base32? && field.defined_in_base32?) ||
              (possible_xlens.include?(64) && csr.defined_in_base64? && field.defined_in_base64?))
            field.type_checked_reset_value_ast(@symtab) if csr.defined_in_base32? && field.defined_in_base32?
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

  # @return [Array<ExtensionParameterWithValue>] List of all available parameters with known values for the config
  def params_with_value
    return @params_with_value unless @params_with_value.nil?

    @params_with_value = []
    return @params_with_value if @config.unconfigured?

    if @config.fully_configured?
      transitive_implemented_extensions.each do |ext_version|
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
      mandatory_extensions.each do |ext_requirement|
        ext = extension(ext_requirement.name)
        ext.params.each do |ext_param|
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

  # @return [Array<ExtensionParameter>] List of all available parameters without known values for the config
  def params_without_value
    return @params_without_value unless @params_without_value.nil?

    @params_without_value = []
    extensions.each do |ext|
      ext.params.each do |ext_param|
        next if @config.param_values.key?(ext_param.name)

        @params_without_value << ext_param
      end
    end
    @params_without_value
  end

  # Returns a string representation of the object, suitable for debugging.
  # @return [String] A string representation of the object.
  def inspect = "ConfiguredArchitecture##{name}"

  def implemented_extensions
    @implemented_extensions ||=
      @config.implemented_extensions.map do |e|
        ExtensionVersion.new(e["name"], e["version"], self, fail_if_version_does_not_exist: true)
      end
  end

  # @return [Array<ExtensionVersion>] List of all extensions known to be implemented in this config, including transitive implications
  def transitive_implemented_extensions
    return @transitive_implemented_extensions unless @transitive_implemented_extensions.nil?

    raise "implemented_extensions is only valid for a fully configured definition" unless @config.fully_configured?

    list = implemented_extensions
    list.each do |e|
      implications = e.transitive_implications
      list.concat(implications) unless implications.empty?
    end
    @transitive_implemented_extensions = list.uniq.sort
  end

  # @return [Array<ExtensionRequirement>] List of all mandatory extension requirements
  def mandatory_extensions
    @mandatory_extensions ||=
      @config.mandatory_extensions.map do |e|
        ext = extension(e["name"])
        raise "Cannot find extension #{e['name']} in the architecture definition" if ext.nil?

        ExtensionRequirement.new(e["name"], *e["version"], presence: "mandatory", cfg_arch: self)
      end
  end

  # @return [Array<ExtensionRequirement>] List of all extensions that are prohibited.
  #                                       This includes extensions explicitly prohibited by the config file
  #                                       and extensions that conflict with a mandatory extension.
  def prohibited_extensions
    return @prohibited_extensions unless @prohibited_extensions.nil?

    if @config.partially_configured?
      @prohibited_extensions =
        @config.prohibited_extensions.map do |e|
          ext = extension(e["name"])
          raise "Cannot find extension #{e['name']} in the architecture definition" if ext.nil?

          ExtensionRequirement.new(e["name"], *e["version"], presence: "mandatory", cfg_arch: self)
        end

      # now add any extensions that are prohibited by a mandatory extension
      mandatory_extensions.each do |ext_req|
        ext_req.extension.conflicts.each do |conflict|
          if @prohibited_extensions.none? { |prohibited_ext| prohibited_ext.name == conflict.name }
            @prohibited_extensions << conflict
          else
            # pick whichever requirement is more expansive
            p = @prohibited_extensions.find { |prohibited_ext| prohibited_ext.name == conflict.name }
            if p.version_requirement.subsumes?(conflict.version_requirement)
              @prohibited_extensions.delete(p)
              @prohibited_extensions << conflict
            end
          end
        end
      end

      @prohibited_extensions
    elsif @config.fully_configured?
      prohibited_ext_versions = []
      extensions.each do |ext|
        ext.versions.each do |ext_ver|
          prohibited_ext_versions << ext_ver unless transitive_implemented_extensions.include?(ext_ver)
        end
      end
      @prohibited_extensions = []
      prohibited_ext_versions.group_by(&:name).each_value do |ext_ver_list|
        if ext_ver_list.sort == ext_ver_list[0].ext.versions.sort
          # excludes every version
          @prohibited_extensions <<
            ExtensionRequirement.new(
              ext_ver_list[0].ext.name, ">= #{ext_ver_list.min.version_spec.canonical}",
              presence: "prohibited", cfg_arch: self
            )
        elsif ext_ver_list.size == (ext_ver_list[0].ext.versions.size - 1)
          # excludes all but one version
          allowed_version_list = (ext_ver_list[0].ext.versions - ext_ver_list)
          raise "Expected only a single element" unless allowed_version_list.size == 1

          allowed_version = allowed_version_list[0]
          @prohibited_extensions <<
            ExtensionRequirement.new(
              ext_ver_list[0].ext.name, "!= #{allowed_version.version_spec.canonical}",
              presence: "prohibited", cfg_arch: self
            )
        else
          # need to group
          raise "TODO"
        end
      end
    else
      @prohibited_extensions = []
    end
    @prohibited_extensions
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
  def prohibited_ext?(ext)
    if ext.is_a?(ExtensionVersion)
      prohibited_extensions.any? { |ext_req| ext_req.satisfied_by?(ext) }
    elsif ext.is_a?(String) || ext.is_a?(Symbol)
      prohibited_extensions.any? { |ext_req| ext_req.name == ext.to_s }
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
  #     cfg_arch.ext?(:S, ">= 1.12")
  #   @example Checking extension presence with multiple version requirements
  #     cfg_arch.ext?(:S, ">= 1.12", "< 1.15")
  #   @example Checking extension precsence with a precise version requirement
  #     cfg_arch.ext?(:S, 1.12)
  def ext?(ext_name, *ext_version_requirements)
    @ext_cache ||= {}
    cached_result = @ext_cache[[ext_name, ext_version_requirements]]
    return cached_result unless cached_result.nil?

    result =
      if @config.fully_configured?
        transitive_implemented_extensions.any? do |e|
          if ext_version_requirements.empty?
            e.name == ext_name.to_s
          else
            requirement = ExtensionRequirement.new(ext_name, *ext_version_requirements, cfg_arch: self)
            requirement.satisfied_by?(e)
          end
        end
      elsif @config.partially_configured?
        mandatory_extensions.any? do |e|
          if ext_version_requirements.empty?
            e.name == ext_name.to_s
          else
            requirement = ExtensionRequirement.new(ext_name, *ext_version_requirements, cfg_arch: self)
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
    return @functions unless @functions.nil?

    @functions = @global_ast.functions
  end

  # @return [Array<Csr>] List of all implemented CSRs
  def transitive_implemented_csrs
    @transitive_implemented_csrs ||=
      transitive_implemented_extensions.map(&:implemented_csrs).flatten.uniq.sort
  end

  # @return [Array<Instruction>] List of all implemented instructions
  def transitive_implemented_instructions
    @transitive_implemented_instructions ||=
      transitive_implemented_extensions.map(&:implemented_instructions).flatten.uniq.sort
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
            (inst.reachable_functions(symtab, 32) +
             inst.reachable_functions(symtab, 64))
          else
            inst.reachable_functions(symtab, mxlen)
          end
        else
          inst.reachable_functions(symtab, inst.base)
        end
    end
    raise "?" unless @implemented_functions.is_a?(Array)
    @implemented_functions = @implemented_functions.flatten
    @implemented_functions.uniq!(&:name)

    puts "  Finding all reachable functions from CSR operations"

    transitive_implemented_csrs.each do |csr|
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

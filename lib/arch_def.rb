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
require_relative "arch_obj_models/manual"
require_relative "arch_obj_models/profile"
require_relative "arch_obj_models/csr_field"
require_relative "arch_obj_models/csr"
require_relative "arch_obj_models/instruction"
require_relative "arch_obj_models/extension"
require_relative "arch_obj_models/csc_crd"

class ArchDef
  # @return [Idl::Compiler] The IDL compiler
  attr_reader :idl_compiler

  # @return [Idl::IsaAst] Abstract syntax tree of global scope
  attr_reader :global_ast

  # @return [String] Name of this definition. Special names are:
  #                  * '_'   - The generic architecture, with no configuration settings.
  #                  * '_32' - A generic RV32 architecture, with only one parameter set (XLEN == 32)
  #                  * '_64' - A generic RV64 architecture, with only one parameter set (XLEN == 64)
  attr_reader :name

  # @return [Hash<String, Object>] A hash mapping parameter name to value for any parameter that has been configured with a value. May be empty.
  attr_reader :param_values

  # @return [Integer] 32 or 64, the XLEN in M-mode
  # @return [nil] if the XLEN in M-mode is not configured
  attr_reader :mxlen

  # hash for Hash lookup
  def hash = @name_sym.hash

  # @return [Idl::SymbolTable] Symbol table with global scope
  # @return [nil] if the architecture is not configured (use symtab_32 or symtab_64)
  def symtab
    raise NotImplementedError, "Un-configured ArchDefs have no symbol table" if @symtab.nil?

    @symtab
  end

  def fully_configured? = @arch_def["type"] == "fully configured"
  def partially_configured? = @arch_def["type"] == "partially configured"
  def unconfigured? = @arch_def["type"] == "unconfigured"
  def configured? = @arch_def["type"] != "unconfigured"
  def type = @arch_def["type"]

  # Initialize a new configured architecture defintiion
  #
  # @param config_name [#to_s] The name of a configuration, which must correspond
  #                            to a folder under $root/cfgs
  def initialize(config_name, arch_def_path, overlay_path: nil)
    @name = config_name.to_s.freeze
    @name_sym = @name.to_sym.freeze

    @idl_compiler = Idl::Compiler.new(self)

    validator = Validator.instance
    begin
      validator.validate_str(arch_def_path.read, type: :arch)
    rescue Validator::SchemaValidationError => e
      warn "While parsing unified architecture definition at #{arch_def_path}"
      raise e
    end

    @arch_def = YAML.load_file(arch_def_path, permitted_classes: [Date]).freeze
    @param_values = (@arch_def.key?("params") ? @arch_def["params"] : {}).freeze
    @mxlen = @arch_def.dig("params", "XLEN") # might be nil

    unless @mxlen.nil?
      # need at least XLEN specified to have a full architecture definition
      # to populate the symbol table.
      #
      # if this is the fully generic config ("_"), then you need to use
      # either symtab_32 or symtab_64
      @symtab = Idl::SymbolTable.new(self)
      custom_globals_path = overlay_path.nil? ? Pathname.new("/does/not/exist") : overlay_path / "isa" / "globals.isa"
      idl_path = File.exist?(custom_globals_path) ? custom_globals_path : $root / "arch" / "isa" / "globals.isa"
      @global_ast = @idl_compiler.compile_file(
        idl_path
      )
      @global_ast.add_global_symbols(@symtab)
      @symtab.deep_freeze
      @global_ast.freeze_tree(@symtab)
      @mxlen.freeze
    else
      # parse globals
      @global_ast = @idl_compiler.compile_file(
        $root / "arch" / "isa" / "globals.isa"
      )
      @global_ast.add_global_symbols(symtab_32)
      symtab_32.deep_freeze
      @global_ast.freeze_tree(symtab_32)

      # do it again for rv64, but we don't need the ast this time
      global_ast_64 = @idl_compiler.compile_file(
        $root / "arch" / "isa" / "globals.isa"
      )
      global_ast_64.add_global_symbols(symtab_64)
      symtab_64.deep_freeze
      global_ast_64.freeze_tree(symtab_64)
    end
  end

  # type check all IDL, including globals, instruction ops, and CSR functions
  #
  # @param show_progress [Boolean] whether to show progress bars
  # @param io [IO] where to write progress bars
  # @return [void]
  def type_check(show_progress: true, io: $stdout)
    io.puts "Type checking IDL code for #{name}..."
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
          field.type_checked_sw_write_ast(@symtab, 64) if possible_xlens.include?(64) &&  csr.defined_in_base64? && field.defined_in_base64?
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
        ext?(:S) && (@param_values["SXLEN"] == 3264)
      elsif partially_configured?
        return false if prohibited_ext?(:S)

        return true unless ext?(:S) # if S is not known to be implemented, we can't say anything about it

        return true unless @param_values.key?("SXLEN")

        @param_values["SXLEN"] == 3264
      else
        raise "Unexpected configuration state"
      end
    when "U"
      return false if prohibited_ext?(:U)

      return true if unconfigured?

      if fully_configured?
        ext?(:U) && (@param_values["UXLEN"] == 3264)
      elsif partially_configured?
        return true unless ext?(:U) # if U is not known to be implemented, we can't say anything about it

        return true unless @param_values.key?("UXLEN")

        @param_values["UXLEN"] == 3264
      else
        raise "Unexpected configuration state"
      end
    when "VS"
      return false if prohibited_ext?(:H)

      return true if unconfigured?

      if fully_configured?
        ext?(:H) && (@param_values["VSXLEN"] == 3264)
      elsif partially_configured?
        return true unless ext?(:H) # if H is not known to be implemented, we can't say anything about it

        return true unless @param_values.key?("VSXLEN")

        @param_values["VSXLEN"] == 3264
      else
        raise "Unexpected configuration state"
      end
    when "VU"
      return false if prohibited_ext?(:H)

      return true if unconfigured?

      if fully_configured?
        ext?(:H) && (@param_values["VUXLEN"] == 3264)
      elsif partially_configured?
        return true unless ext?(:H) # if H is not known to be implemented, we can't say anything about it

        return true unless @param_values.key?("VUXLEN")

        @param_values["VUXLEN"] == 3264
      else
        raise "Unexpected configuration state"
      end
    else
      raise ArgumentError, "Bad mode"
    end
  end

  # @return [Array<Integer>] List of possible XLENs in any mode for this config
  def possible_xlens = multi_xlen? ? [32, 64] : [mxlen]

  # @return [Array<ExtensionParameterWithValue>] List of all available parameters with known values for the config
  def params_with_value
    return @params_with_value unless @params_with_value.nil?

    @params_with_value = []
    extensions.each do |ext_version|
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

  # @return [Array<ExtensionParameter>] List of all available parameters without known values for the config
  def params_without_value
    return @params_without_value unless @params_without_value.nil?

    @params_without_value = []
    extensions.each do |ext_version|
      ext = extension(ext_version.name)
      ext.params.each do |ext_param|
        unless param_values.key?(ext_param.name)
          @params_without_value << ext_param
        end
      end
    end
    @params_without_value
  end

  # Returns a string representation of the object, suitable for debugging.
  # @return [String] A string representation of the object.
  def inspect = "ArchDef##{name}"

  # @return [Array<Extension>] List of all extensions, even those that are't implemented
  def extensions
    return @extensions unless @extensions.nil?

    @extensions = []
    @arch_def["extensions"].each_value do |ext_data|
      @extensions << Extension.new(ext_data, self)
    end
    @extensions
  end

  # may be overridden by subclass
  # @return [Array<ExtensionVersion>] List of all extensions known to be implemented in this architecture
  def implemented_extensions
    return @implemented_extensions unless @implemented_extensions.nil?

    @implemented_extensions = []
    if @arch_def.key?("implemented_extensions")
      @arch_def["implemented_extensions"].each do |e|
        @implemented_extensions << ExtensionVersion.new(e["name"], e["version"])
      end
    end
    @implemented_extensions
  end

  # @return [Array<ExtensionRequirement>] List of extensions that are explicitly prohibited by an arch def
  def prohibited_extensions
    return @prohibited_extensions unless @prohibited_extensions.nil?

    @prohibited_extensions = []
    if @arch_def.key?("prohibited_extensions")
      @arch_def["prohibited_extensions"].each do |e|
        if e.is_a?(String)
          @prohibited_extensions << ExtensionRequirement.new(e, nil)
        else
          @prohibited_extensions << ExtensionRequirement.new(e["name"], e["requirements"])
        end
      end
    end
    @prohibited_extensions
  end

  def prohibited_ext?(ext_name)
    prohibited_extensions.any? { |ext_req| ext_req.name == ext_name.to_s }
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

  # @return [Array<ExtensionRequirement>] Array of all extensions that are prohibited because they are excluded by an implemented extension
  def conflicting_extensions
    extensions.map(&:conflicts).flatten
  end

  # @return [Boolean] whether or not ext_name is prohibited because it is excluded by an implemented extension
  def conflicting_ext?(ext_name)
    prohibited_extensions.include? { |ext_req| ext_req.name == ext_name }
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
      Instruction.new(inst_data, self)
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
  alias instruction inst

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

  # @return [Array<Manual>] List of all manuals defined by the architecture
  def manuals
    return @manuals unless @manuals.nil?

    @manuals = []
    @arch_def["manuals"].each_value do |manual_data|
      @manuals << Manual.new(manual_data, self)
    end
    @manuals
  end

  # @return [Hash<String, Manual>] All manuals, indexed by name
  def manuals_hash
    return @manuals_hash unless @manuals_hash.nil?

    @manuals_hash = {}
    manuals.each do |manual|
      @manuals_hash[manual.name] = manual
    end
    @manuals_hash
  end

  # @return [Manual,nil] A manual named +name+, or nil if it doesn't exist
  def manual(name) = manuals_hash[name]

  # @return [Array<ProfileFamily>] All known profile families
  def profile_families
    return @profile_families unless @profile_families.nil?

    @profile_families = []
    @arch_def["profile_families"].each_value do |family_data|
      @profile_families << ProfileFamily.new(family_data, self)
    end
    @profile_families
  end

  # @return [Hash<String, ProfileFamily>] Profile families, indexed by name
  def profile_families_hash
    return @profile_families_hash unless @profile_families_hash.nil?

    @profile_families_hash = {}
    profile_families.each do |family|
      @profile_families_hash[family.name] = family
    end
    @profile_families_hash
  end

  # @return [ProfileFamily] The profile family named +name+
  # @return [nil] if the profile family does not exist
  def profile_family(name) = profile_families_hash[name]

  # @return [Profile] List of all defined profiles
  def profiles
    return @profiles unless @profiles.nil?

    @profiles = []
    @arch_def["profiles"].each_value do |profile_data|
      @profiles << Profile.new(profile_data, self)
    end
    @profiles
  end

  # @return [Hash<String, Profile>] Profiles, indexed by name
  def profiles_hash
    return @profiles_hash unless @profiles_hash.nil?

    @profiles_hash = {}
    profiles.each do |profile|
      @profiles_hash[profile.name] = profile
    end
    @profiles_hash
  end

  # @return [Profile] The profile named +name+
  # @return [nil] if the profile does not exist
  def profile(name) = profiles_hash[name]

  def csc_crd_families
    return @csc_crd_families unless @csc_crd_families.nil?

    @csc_crd_families = []
    @arch_def["csc_crd_families"].each_value do |family_data|
      @csc_crd_families << CscCrdFamily.new(family_data, self)
    end
    @csc_crd_families
  end

  def csc_crd_famlies_hash
    return @csc_crd_families_hash unless @csc_crd_families_hash.nil?

    @csc_crd_families_hash = {}
    csc_crd_families.each do |family|
      @csc_crd_families_hash[family.name] = family
    end
    @csc_crd_families_hash
  end

  def csc_crd_family(name) = csc_crd_famlies_hash[name]

  def csc_crds
    return @csc_crds unless @csc_crds.nil?

    @csc_crds = []
    @arch_def["csc_crds"].each_value do |csc_crd_data|
      @csc_crds << CscCrd.new(csc_crd_data, self)
    end
    @csc_crds
  end

  def csc_crds_hash
    return @csc_crds_hash unless @csc_crds_hash.nil?

    @csc_crds_hash = {}
    csc_crds.each do |csc_crd|
      @csc_crds_hash[csc_crd.name] = csc_crd
    end
    @csc_crds_hash
  end

  def csc_crd(name) = csc_crds_hash[name]

  # @return [Array<ExceptionCode>] All exception codes defined by RISC-V
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

  # @return [Hash] The raw architecture defintion data structure
  def data
    @arch_def
  end

  # @return [Array<Csr>] List of all implemented CSRs
  def implemented_csrs
    return @implemented_csrs unless @implemented_csrs.nil?

    @implemented_csrs = 
      if @arch_def.key?("implemented_csrs")
        csrs.select { |c| @arch_def["implemented_csrs"].include?(c.name) }
      else
        []
      end
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

    @implemented_instructions =
      if @arch_def.key?("implemented_instructions")
        @arch_def["implemented_instructions"].map do |inst_name|
          instruction_hash[inst_name]
        end
      else
        []
      end
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
      elsif inst(name)
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
    @env.instance_variable_set(:@arch_gen, self)

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

      # @returns [Hash<Integer, String>] architecturally-defined exception codes and their names
      def implemented_exception_codes
        @arch_gen.implemented_exception_codes
      end

      # returns [Hash<Integer, String>] architecturally-defined interrupt codes and their names
      def implemented_interrupt_codes
        @arch_gen.implemented_interrupt_codes
      end
    end

    @env
  end
  private :erb_env

  # passes _erb_template_ through ERB within the content of this config
  #
  # @param erb_template [String] ERB source
  # @return [String] The rendered text
  def render_erb(erb_template, what='')
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
    @name.freeze
    @var = var
    @num = number
    @ext = ext
  end
end

# all the same informatin as ExceptinCode, but for interrupts
InterruptCode = Class.new(ExceptionCode)

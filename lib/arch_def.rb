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

  # Returns a string representation of the object, suitable for debugging.
  # @return [String] A string representation of the object.
  def inspect = "ArchDef"

  # @return [Array<Extension>] List of all extensions, even those that are't implemented
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

    @env.instance_exec do
      # method to check if a given extension (with an optional version number) is present
      #
      # @param ext_name [String,#to_s] Name of the extension
      # @param ext_requirement [String, #to_s] Version string, as a Gem Requirement (https://guides.rubygems.org/patterns/#pessimistic-version-constraint)
      # @return [Boolean] whether or not extension +ext_name+ meeting +ext_requirement+ is implemented in the config
      def ext?(ext_name, ext_requirement = ">= 0")
        true # ?
      end

      # @return [Array<Integer>] List of possible XLENs for any implemented mode
      def possible_xlens
        [32, 64]
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
    rescue Validator::SchemaValidationError => e
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

# frozen_string_literal: true

# The Design class is used when exporting information from the Architecture class.
# The Architecture represents the "front-end" with objects providing access to the architecture database
# in the /arch directory YAML files. It is the Ruby API to access the architecture database.
# The Design contains common code such as IDL and ERB support used by multiple "back-ends" to
# export the "front-end" architecture database to various types of documents.
# The Design adds the concept of an mxlen which isn't present in the Architecture.
#
# A Design provides support when exporting any of the following to ASCIIDOC/HTML/PDF:
#   - Entire RISC-V ISA manual
#   - Config (under /cfg directory) with a possible overlay
#   - Profile release
#   - Certificate
#   - Extension
#
# The Design class contains an Architecture object but isn't inherited from it.
# This was done so code that only needs an Architecture object can make this clear
# by using the Architecture object instead of the Design object (i.e., to support encapsulation).
#
# This Design class is an abstract base class for designs using either a config (under /cfg) or a
# portfolio (profile release or certificate).
# Abstract methods all call raise() if not overriden by a child class. These methods are all grouped
# together in this Ruby file to make it easier to find them.

require "ruby-prof"
require "tilt"

require_relative "architecture"

require_relative "idl"
require_relative "idl/passes/find_return_values"
require_relative "idl/passes/gen_adoc"
require_relative "idl/passes/prune"
require_relative "idl/passes/reachable_exceptions"
require_relative "idl/passes/reachable_functions"

require_relative "template_helpers"

include TemplateHelpers

class Design
  # @return [String] Name of design
  attr_reader :name

  # @return [Architecture] The RISC-V architecture
  attr_reader :arch

  # @return [Idl::Compiler] The IDL compiler
  attr_reader :idl_compiler

  # @return [Idl::IsaAst] Abstract syntax tree of global scope
  attr_reader :global_ast

  # @return [Idl::SymbolTable] Symbol table with global scope
  # Don't use attr_reader so this can be clearly overridden by child class.
  def symtab = @symtab

  # hash for Hash lookup
  def hash = @name_sym.hash

  # @param name [#to_s] The design name
  # @param arch [Architecture] The entire architecture
  # @param overlay_path [String] Optional path to a directory that overlays the architecture
  def initialize(name, arch, overlay_path: nil)
    raise ArgumentError, "arch must be an Architecture but is a #{arch.class}" unless arch.is_a?(Architecture)

    @name = name.to_s.freeze
    @name_sym = @name.to_sym.freeze
    @arch = arch

    @idl_compiler = Idl::Compiler.new
    @symtab = Idl::SymbolTable.new(self)
    custom_globals_path = overlay_path.nil? ? Pathname.new("/does/not/exist") : overlay_path / "isa" / "globals.isa"

    idl_path = File.exist?(custom_globals_path) ? custom_globals_path : $root / "arch" / "isa" / "globals.isa"
    @global_ast = @idl_compiler.compile_file(idl_path)
    @global_ast.add_global_symbols(@symtab)
    @symtab.deep_freeze
    @global_ast.freeze_tree(@symtab)
  end

  # Returns a string representation of the object, suitable for debugging.
  # @return [String] A string representation of the object.
  def inspect = "Design##{name}"

  ####################
  # ABSTRACT METHODS #
  ####################

  # @return [Integer] 32, 64, or nil (if dynamic or unconfigured)
  def mxlen
    raise "Abstract Method: Must be provided in child class"
  end

  # Returns whether or not it may be possible to switch XLEN in +mode+ given this definition.
  # @param mode [String] mode to check. One of "M", "S", "U", "VS", "VU"
  # @return [Boolean] true if might execute in multiple xlen environments in +mode+
  #                   (e.g., that in some mode the effective xlen can be either 32 or 64, depending on CSR values)
  def multi_xlen_in_mode?(mode)
    raise "Abstract Method: Must be provided in child class"
  end

  # @return [Hash<String, String>] Fully-constrained parameter values (those with just one possible value for this design)
  def param_values
    raise "Abstract Method: Must be provided in child class"
  end

  # @return [Array<ExtensionParameterWithValue>] List of all parameters fully-constrained to one specific value
  def params_with_value
    raise "Abstract Method: Must be provided in child class"
  end

  # @return [Array<ExtensionParameter>] List of all available parameters not yet full-constrained to one specific value
  def params_without_value
    raise "Abstract Method: Must be provided in child class"
  end

  # @return [Array<ExtensionVersion>] List of all implemented extension versions.
  def implemented_ext_vers
    raise "Abstract Method: Must be provided in child class"
  end

  # @return [Array<ExtensionRequirement>] List of all mandatory extension requirements
  def mandatory_ext_reqs
    raise "Abstract Method: Must be provided in child class"
  end

  # @return [Array<ExtensionRequirement>] List of all extensions that are prohibited.
  #                                       This includes extensions explicitly prohibited by the design
  #                                       and extensions that conflict with a mandatory extension.
  def prohibited_ext_reqs
    raise "Abstract Method: Must be provided in child class"
  end

  # @return [Boolean] True if all parameters are fully-constrained in the design
  def fully_configured?
    raise "Abstract Method: Must be provided in child class"
  end

  # @return [Boolean] True if some parameters aren't fully-constrained yet in the design
  def partially_configured?
    raise "Abstract Method: Must be provided in child class"
  end

  # @return [Boolean] True if all parameters aren't constrained at all in the design
  def unconfigured?
    raise "Abstract Method: Must be provided in child class"
  end

  # @return [Boolean] True if not unconfigured (so either fully_configured or partially_configured).
  # This isn't an abstract method but is located here for clarity.
  def configured? = !unconfigured?

  # @overload ext?(ext_name)
  #   @param ext_name [#to_s] Extension name (case sensitive)
  #   @return [Boolean] True if the extension `name` must be implemented
  #
  # @overload ext?(ext_name, ext_version_requirements)
  #   @param ext_name [#to_s] Extension name (case sensitive)
  #   @param ext_version_requirements [Number,String,Array] Extension version requirements
  #   @return [Boolean] True if the extension `name` meeting `ext_version_requirements` must be implemented
  #
  #   @example Checking extension presence with a version requirement
  #     Design.ext?(:S, ">= 1.12")
  #   @example Checking extension presence with multiple version requirements
  #     Design.ext?(:S, ">= 1.12", "< 1.15")
  #   @example Checking extension presence with a precise version requirement
  #     Design.ext?(:S, 1.12)
  def ext?(ext_name, *ext_version_requirements)
    raise "Abstract Method: Must be provided in child class"
  end

  ###################
  # REGULAR METHODS #
  ###################

  # Returns whether or not it may be possible to switch XLEN given this definition.
  #
  # There are three cases when this will return true:
  #   1. A mode (e.g., U) is known to be implemented, and the CSR bit that controls XLEN in that mode is known to be writeable.
  #   2. A mode is known to be implemented, but the writability of the CSR bit that controls XLEN in that mode is not known.
  #   3. It is not known if the mode is implemented.
  #
  #
  # @return [Boolean] true if might execute in multiple xlen environments
  #                   (e.g., that in some mode the effective xlen can be either 32 or 64, depending on CSR values)
  def multi_xlen?
    return true if @mxlen.nil?

    ["S", "U", "VS", "VU"].any? { |mode| multi_xlen_in_mode?(mode) }
  end

  # @return [Array<Integer>] List of possible XLENs in any mode for this design
  def possible_xlens = multi_xlen? ? [32, 64] : [mxlen]

  # type check all IDL, including globals, instruction ops, and CSR functions
  #
  # @param show_progress [Boolean] whether to show progress bars
  # @param io [IO] where to write progress bars
  # @return [void]
  def type_check(show_progress: true, io: $stdout)
    io.puts "Type checking IDL code for #{@name}..."
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

  # @return [Array<ExtensionVersion>] List of all extensions known to be implemented in this design, including transitive implications
  def transitive_implemented_ext_vers
    return @transitive_implemented_ext_vers unless @transitive_implemented_ext_vers.nil?

    list = implemented_ext_vers
    list.each do |e|
      implications = e.transitive_implications
      list.concat(implications) unless implications.empty?
    end
    @transitive_implemented_ext_vers = list.uniq.sort
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
      prohibited_ext_reqs.any? { |ext_req| ext_req.satisfied_by?(ext) }
    elsif ext.is_a?(String) || ext.is_a?(Symbol)
      prohibited_ext_reqs.any? { |ext_req| ext_req.name == ext.to_s }
    else
      raise ArgumentError, "Argument to prohibited_ext? should be an ExtensionVersion or a String"
    end
  end

  # @return [Array<ExceptionCode>] All exception codes known to be implemented
  def implemented_exception_codes
    return @implemented_exception_codes unless @implemented_exception_codes.nil?

    @implemented_exception_codes =
      implemented_ext_vers.reduce([]) do |list, ext_version|
        ecodes = extension(ext_version.name)["exception_codes"]
        next list if ecodes.nil?

        ecodes.each do |ecode|
          # double check that all the codes are unique
          raise "Duplicate exception code" if list.any? { |e| e.num == ecode["num"] || e.name == ecode["name"] || e.var == ecode["var"] }

          unless ecode.dig("when", "version").nil?
            # check version
            next unless ext?(ext_version.name.to_sym, ecode["when"]["version"])
          end
          list << ExceptionCode.new(ecode["name"], ecode["var"], ecode["num"], arch)
        end
        list
      end
  end

  # @return [Array<InteruptCode>] All interrupt codes known to be implemented
  def implemented_interrupt_codes
    return @implemented_interrupt_codes unless @implemented_interrupt_codes.nil?

    @implemented_interupt_codes =
      implemented_ext_vers.reduce([]) do |list, ext_version|
        icodes = extension(ext_version.name)["interrupt_codes"]
        next list if icodes.nil?

        icodes.each do |icode|
          # double check that all the codes are unique
          raise "Duplicate interrupt code" if list.any? { |i| i.num == icode["num"] || i.name == icode["name"] || i.var == icode["var"] }

          unless ecode.dig("when", "version").nil?
            # check version
            next unless ext?(ext_version.name.to_sym, ecode["when"]["version"])
          end
          list << InterruptCode.new(icode["name"], icode["var"], icode["num"], arch)
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
      transitive_implemented_ext_vers.map(&:implemented_csrs).flatten.uniq.sort
  end

  # @return [Array<Instruction>] List of all implemented instructions
  def transitive_implemented_instructions
    @transitive_implemented_instructions ||=
      transitive_implemented_ext_vers.map(&:implemented_instructions).flatten.uniq.sort
  end

  # @return [Array<FuncDefAst>] List of all reachable IDL functions for the design
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
    @implemented_functions = @implemented_functions.flatten.uniq(&:name)

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
      csr = arch.csr(csr_name)
      if !field_name.nil? && !csr.nil? && csr.field?(field_name)
        "%%LINK%csr_field;#{csr_name}.#{field_name};#{csr_name}.#{field_name}%%"
      elsif !csr.nil?
        "%%LINK%csr;#{csr_name};#{csr_name}%%"
      elsif arch.instruction(name)
        "%%LINK%inst;#{name};#{name}%%"
      elsif arch.extension(name)
        "%%LINK%ext;#{name};#{name}%%"
      else
        match
      end
    end
  end

  # Returns an environment hash suitable for the render() function in ERB templates.
  #
  # This method returns a hash containing the architecture definition and other
  # relevant data that can be used to generate ERb templates.
  #
  # @return [Hash] An environment hash suitable for use with ERb templates.
  def render_erb_env
    return @env unless @env.nil?

    @env = Class.new
    @env.instance_variable_set(:@design, design)
    @env.instance_variable_set(:@params, @param_values)
    @env.instance_variable_set(:@arch, arch)

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
      # @return [Boolean] whether or not extension +ext_name+ meeting +ext_requirement+ is implemented in the design
      def ext?(ext_name, ext_requirement = ">= 0")
        @design.ext?(ext_name.to_s, ext_requirement)
      end

      # @return [Array<Integer>] List of possible XLENs for any implemented mode
      def possible_xlens
        @design.possible_xlens
      end

      # insert a hyperlink to an object
      # At this point, we insert a placeholder since it will be up
      # to the backend to create a specific link
      #
      # @param type [Symbol] Type (:section, :csr, :inst, :ext)
      # @param name [#to_s] Name of the object
      def link_to(type, name)
        "%%LINK%#{type};#{name}%%"
      end

      # info on interrupt and exception codes

      # @returns [Hash<Integer, String>] architecturally-defined exception codes and their names
      def exception_codes
        @arch.exception_codes
      end

      # returns [Hash<Integer, String>] architecturally-defined interrupt codes and their names
      def interrupt_codes
        @arch.interrupt_codes
      end

      # @returns [Hash<Integer, String>] architecturally-defined exception codes and their names
      def implemented_exception_codes
        @design.implemented_exception_codes
      end

      # returns [Hash<Integer, String>] architecturally-defined interrupt codes and their names
      def implemented_interrupt_codes
        @design.implemented_interrupt_codes
      end
    end

    @env
  end
  private :render_erb_env

  # Passes _erb_template_ through ERB within the content of this render_erb_env
  #
  # @param erb_template [String] ERB source
  # @return [String] The rendered text
  def render_erb(erb_template, what = "")
    t = Tempfile.new("template")
    t.write erb_template
    t.flush
    begin
      Tilt["erb"].new(t.path, trim: "-").render(render_erb_env)
    rescue
      warn "While rendering ERB template: #{what}"
      raise
    ensure
      t.close
      t.unlink
    end
  end
end

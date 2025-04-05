# frozen_string_literal: true

# The Design class assists backends when exporting information from the database.
# It contains common code such as IDL and ERB support used by multiple backends.
#
# A Design provides support when exporting any of the following to ASCIIDOC/HTML/PDF:
#   - Entire RISC-V ISA manual
#   - Individual Extension
#   - Profile Release
#   - CRD (Certificate Requirements Document)
#   - CTP (Certificate Test Plan)
#
# The Design class contains ConfiguredArchitecture since many other Ruby routines in
# UDB like the IDL routines require a ConfiguredArchitecture object.
#
# This Design class is an abstract base class for designs using either a config (under /cfg) or a
# portfolio (profile release or certificate).  The abstract methods exist in the IDesign base class
# and call raise() if not overriden by a child class.

require "ruby-prof"
require "tilt"
require "forwardable"

require_relative "idesign"
require_relative "cfg_arch"

require_relative "idl"
require_relative "idl/passes/find_return_values"
require_relative "idl/passes/gen_adoc"
require_relative "idl/passes/prune"
require_relative "idl/passes/reachable_exceptions"
require_relative "idl/passes/reachable_functions"

require_relative "backend_helpers"

include TemplateHelpers

class Design < IDesign
  extend Forwardable

  # Calls to these methods on Design are handled by the ConfiguredArchitecture object.
  # Avoids having to call design.cfg_arch.<method> (just call design.<method>).
  def_delegators :@cfg_arch,
    :ext?,
    :multi_xlen?,
    :multi_xlen_in_mode?,
    :params_without_value,
    :possible_xlens,
    :type_check,
    :transitive_implemented_extension_versions,
    :prohibited_ext?,
    :implemented_exception_codes,
    :implemented_interrupt_codes,
    :functions,
    :transitive_implemented_csrs,
    :transitive_implemented_instructions,
    :implemented_functions

  # @return [ConfiguredArchitecture] The RISC-V architecture
  attr_reader :cfg_arch

  # Provided for backwards-compatibility
  def arch = @cfg_arch

  # @return [Integer] 32, 64, or nil for dynamic
  attr_reader :mxlen

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
  # @param cfg_arch [ConfiguredArchitecture] The entire architecture
  # @param mxlen [Integer] 32, 64, or nil for dynamic
  # @param overlay_path [String] Optional path to a directory that overlays the architecture
  def initialize(name, cfg_arch, mxlen, overlay_path: nil)
    super(name)

    raise ArgumentError, "cfg_arch must be an ConfiguredArchitecture but is a #{cfg_arch.class}" unless cfg_arch.is_a?(ConfiguredArchitecture)
    @cfg_arch = cfg_arch

    @mxlen = mxlen
    @mxlen.freeze

    @idl_compiler = Idl::Compiler.new
    @symtab = Idl::SymbolTable.new(cfg_arch)
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

  # Returns an environment hash suitable for the render_erb() function in ERB templates.
  #
  # @return [Hash] An environment hash suitable for use with ERb templates.
  def render_erb_env
    return @env unless @env.nil?

    @env = Class.new
    @env.instance_variable_set(:@design, self)
    @env.instance_variable_set(:@params, @param_values)
    @env.instance_variable_set(:@cfg_arch, @cfg_arch)
    @env.instance_variable_set(:@arch, @arch) # Provided for backwards-compatibility

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
      def link_to_udb(type, name)
        "%%UDB_DOC_LINK%#{type};#{name}%%"
      end

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

  # Passes _erb_template_ through ERB within the content of the render_erb_env
  #
  # @param erb_template [String] ERB template source string
  # @param what [String] ???
  # @return [String] The rendered text
  def render_erb(erb_template, what = "")
    t = Tempfile.new("template")
    t.write erb_template
    t.flush
    begin
      template = Tilt["erb"].new(t.path, trim: "-")
      template.render(render_erb_env)
    rescue
      warn "While rendering ERB template #{erb_template}: #{what}"
      raise
    ensure
      t.close
      t.unlink
    end
  end
end

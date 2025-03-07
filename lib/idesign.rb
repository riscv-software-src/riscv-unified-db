# frozen_string_literal: true

# The IDesign class (Interface Design) contains the abstract methods for the Design class.
# Putting these methods into IDesign rather than Design allows unit-level tests to create
# a MockDesign class that only has to implement the require abstract interfaces without all
# the other baggage that a Design class adds (e.g., having an Architecture object).

class IDesign
  # @return [String] Name of design
  attr_reader :name

  # @param name [#to_s] The design name
  def initialize(name)
    @name = name.to_s.freeze
    @name_sym = @name.to_sym.freeze
  end

  # @return [Boolean] True if not unconfigured (so either fully_configured or partially_configured).
  def configured? = !unconfigured?

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

  # @return [Array<ParameterWithValue>] List of all parameters fully-constrained to one specific value
  def params_with_value
    raise "Abstract Method: Must be provided in child class"
  end

  # @return [Array<Parameter>] List of all available parameters not yet full-constrained to one specific value
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

  # Given an adoc string, find names of CSR/Instruction/Extension enclosed in `monospace`
  # and replace them with links to the relevant object page.
  # See backend_helpers.rb for a definition of the proprietary link format.
  #
  # @param adoc [String] Asciidoc source
  # @return [String] Asciidoc source, with link placeholders
  def convert_monospace_to_links(adoc)
    raise "Abstract Method: Must be provided in child class"
  end
end

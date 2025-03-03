# frozen_string_literal: true

# Combines knowledge of the architecture database with one or more portfolios (profile or certificate).
#
# Used in portfolio-based ERB templates to gather information about the "design".
# The "design" corresponds to the file being created by the ERB template and facilitates
# sharing ERB template fragments between different kinds of portfolios (mostly in the appendices).
# For example, a processor certificate model has one portfolio but a profile release has multiple portfolios
# but they both have just one PortfolioDesign object.

require "ruby-prof"
require "tilt"

require_relative "architecture"
require_relative "design"
require_relative "arch_obj_models/portfolio"

class PortfolioDesign < Design
  # @param base_isa_name [#to_s] The name of the base ISA configuration (rv32 or rv64)
  # @param arch [Architecture] The database of RISC-V standards
  # @param mxlen [Integer] Comes from portfolio YAML "base" (either 32 or 64)
  # @param portfolios [Array<Portfolio>] Portfolios being converted to adoc
  # @param overlay_path [String] Optional path to a directory that overlays the architecture
  def initialize(base_isa_name, arch, portfolios, overlay_path: nil)
    raise ArgumentError, "arch must be an Architecture but is a #{arch.class}" unless arch.is_a?(Architecture)
    raise ArgumentError, "portfolios must be an Array<Portfolio> but is a #{portfolios.class}" unless portfolios.is_a?(Array)

    # The PortfolioGroup has an Array<Portfolio> inside it and forwards common Array methods to its internal Array.
    # Can call @portfolio_grp.each or @portfolio_grp.map and they are handled by the normal Array methods.
    @portfolio_grp = PortfolioGroup.new(portfolios)

    max_base = portfolios.map(&:base).max
    raise ArgumentError, "Calculated maximum base of #{max_base} across portfolios is not 32 or 64" unless max_base == 32 || max_base == 64

    super(base_isa_name, arch, max_base, overlay_path: overlay_path)
  end

  # Returns a string representation of the object, suitable for debugging.
  # @return [String] A string representation of the object.
  def inspect = "PortfolioDesign##{name}"

  ##################################
  # METHODS REQUIRED BY BASE CLASS #
  ##################################

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
  # @return [Boolean] true if might execute in multiple xlen environments in +mode+
  #                   (e.g., that in some mode the effective xlen can be either 32 or 64, depending on CSR values)
  #
  # Assume portfolios (profiles and certificates) don't need this ISA feature.
  def multi_xlen_in_mode?(mode) = false

  # @return [Array<ExtensionParameterWithValue>] List of all parameters fully-constrained to one specific value
  def params_with_value
    return @params_with_value unless @params_with_value.nil?

    @params_with_value = []

    in_scope_ext_reqs.each do |ext_req|
      ext_req.extension.params.each do |ext_param|
        next unless param_values.key?(ext_param.name)

        @params_with_value << ExtensionParameterWithValue.new(ext_param, param_values[ext_param.name])
      end
    end

    @params_with_value
  end

  # @return [Array<ExtensionParameter>] List of all available parameters not yet full-constrained to one specific value
  def params_without_value
    return @params_without_value unless @params_without_value.nil?

    @params_without_value = []
    arch.extensions.each do |ext|
      ext.params.each do |ext_param|
        next if param_values.key?(ext_param.name)

        @params_without_value << ext_param
      end
    end
    @params_without_value
  end

  def implemented_ext_vers
    # Only supported by fully-configured configurations and a portfolio corresponds to a
    # partially-configured configuration. See the Config class for details.
    raise "Not supported for portfolio #{name}"
  end

  # @return [Array<ExtensionRequirement>] List of all extensions that are prohibited.
  #                                       This includes extensions explicitly prohibited by the design
  #                                       and extensions that conflict with a mandatory extension.
  #
  # TODO: Assume there are none of these in a portfolio for now.
  def prohibited_ext_reqs = []

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
  #     PortfolioDesign.ext?(:S, ">= 1.12")
  #   @example Checking extension presence with multiple version requirements
  #     PortfolioDesign.ext?(:S, ">= 1.12", "< 1.15")
  #   @example Checking extension presence with a precise version requirement
  #     PortfolioDesign.ext?(:S, 1.12)
  def ext?(ext_name, *ext_version_requirements)
    @ext_cache ||= {}
    cached_result = @ext_cache[[ext_name, ext_version_requirements]]
    return cached_result unless cached_result.nil?

    result =
      mandatory_ext_reqs.any? do |ext_req|
        if ext_version_requirements.empty?
          ext_req.name == ext_name.to_s
        else
          requirement = ExtensionRequirement.new(ext_name, *ext_version_requirements, arch)
          ext_req.satisfying_versions.all? do |ext_ver|
            requirement.satisfied_by?(ext_ver)
          end
        end
      end

    @ext_cache[[ext_name, ext_version_requirements]] = result
  end

  #
  # A Portfolio corresponds to a partially-configured design.
  # See the Config class for details.
  #
  # @return [Boolean] True if all parameters are fully-constrained in the design
  def fully_configured? = false

  # @return [Boolean] True if some parameters aren't fully-constrained yet in the design
  def partially_configured? = true

  # @return [Boolean] True if all parameters aren't constrained at all in the design
  def unconfigured? = false

  #####################################
  # METHODS HANDLED BY PortfolioGroup #
  #####################################

  # @return [Array<ExtensionRequirement>] List of all mandatory extension requirements
  def mandatory_ext_reqs = @portfolio_grp.mandatory_ext_reqs

  # @return [Hash<String, String>] Fully-constrained parameter values (those with just one possible value for this design).
  def param_values = @portfolio_grp.param_values

  # @return [Array<Extension>] List of all mandatory or optional extensions referenced by this design.
  def in_scope_extensions = @portfolio_grp.in_scope_extensions

  # @return [Array<ExtensionRequirement>] List of all mandatory or optional extension requirements referenced by this design.
  def in_scope_ext_reqs = @portfolio_grp.in_scope_ext_reqs

  # @return [Array<Instruction>] Sorted list of all instructions associated with extensions listed as
  #                              mandatory or optional in portfolio. Uses instructions provided by the
  #                              minimum version of the extension that meets the extension requirement.
  #                              Factors in things like XLEN in design.
  def in_scope_instructions = @portfolio_grp.in_scope_instructions(self)

  # @return [Array<Csr>] Unsorted list of all CSRs associated with extensions listed as
  #                      mandatory or optional in portfolio. Uses CSRs provided by the
  #                      minimum version of the extension that meets the extension requirement.
  #                      Factors in things like XLEN in design.
  def in_scope_csrs = @portfolio_grp.in_scope_csrs(self)

  # @return [Array<ExceptionCode>] Unsorted list of all in-scope exception codes.
  def in_scope_exception_codes = @portfolio_grp.in_scope_exception_codes(self)

  # @return [Array<ExceptionCode>] Unsorted list of all in-scope interrupt codes.
  def in_scope_interrupt_codes = @portfolio_grp.in_scope_interrupt_codes(self)

  # @return [String] Given an extension +ext_name+, return the presence as a string.
  #                  Returns the greatest presence string across all portfolios in this design.
  #                  If the extension name isn't found in this design, return "-".
  def extension_presence(ext_name) = @portfolio_grp.extension_presence(ext_name)
end

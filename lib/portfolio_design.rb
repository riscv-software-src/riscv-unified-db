# frozen_string_literal: true

# Combines knowledge of the architecture database with one or more portfolios (profile or certificate).
#
# Used in portfolio-based ERB templates to gather information about the "design".
# The "design" corresponds to the file being created by the ERB template and facilitates
# sharing ERB template fragments between different kinds of portfolios (mostly in the appendices).
# For example, a processor certificate model has one portfolio but a profile release has multiple portfolios
# but they both have just one PortfolioDesign object.

require "ruby-prof"

require_relative "cfg_arch"
require_relative "design"
require_relative "arch_obj_models/portfolio"

class PortfolioDesign < Design
  # @return [PortfolioClass] Portfolio class for all the portfolios in this design
  attr_reader :portfolio_class

  # @return [String] Kind of portfolio for all portfolios in this design
  attr_reader :portfolio_kind

  # @return [String] Type of design suitable for human readers.
  attr_reader :portfolio_design_type

  # Class methods
  def self.profile_release_type = "Profile Release"
  def self.proc_crd_type = "Certification Requirements Document"
  def self.proc_ctp_type = "Certification Test Plan"
  def self.portfolio_design_types = [profile_release_type, proc_crd_type, proc_ctp_type]

  # @param name [#to_s] The name of the portfolio design (i.e., backend filename without a suffix)
  # @param cfg_arch [ConfiguredArchitecture] The database of RISC-V standards for a particular configuration
  # @param portfolio_design_type [String] Type of portfolio design associated with this design
  # @param mxlen [Integer] Comes from portfolio YAML "base" (either 32 or 64)
  # @param portfolios [Array<Portfolio>] Portfolios being converted to adoc
  # @param portfolio_class [PortfolioClass] PortfolioClass for all the Portfolios
  # @param overlay_path [String] Optional path to a directory that overlays the architecture
  def initialize(name, cfg_arch, portfolio_design_type, portfolios, portfolio_class, overlay_path: nil)
    raise ArgumentError, "cfg_arch must be an ConfiguredArchitecture but is a #{cfg_arch.class}" unless cfg_arch.is_a?(ConfiguredArchitecture)
    raise ArgumentError, "portfolio_design_type of #{portfolio_design_type} unknown" unless PortfolioDesign.portfolio_design_types.include?(portfolio_design_type)
    raise ArgumentError, "portfolios must be an Array<Portfolio> but is a #{portfolios.class}" unless portfolios.is_a?(Array)
    raise ArgumentError, "portfolio_class must be a PortfolioClass but is a #{portfolio_class.class}" unless portfolio_class.is_a?(PortfolioClass)

    @portfolio_design_type = portfolio_design_type

    # The PortfolioGroup has an Array<Portfolio> inside it and forwards common Array methods to its internal Array.
    # Can call @portfolio_grp.each or @portfolio_grp.map and they are handled by the normal Array methods.
    @portfolio_grp = PortfolioGroup.new(name, portfolios)

    @portfolio_class = portfolio_class
    @portfolio_kind = portfolios[0].kind

    max_base = portfolios.map(&:base).max
    raise ArgumentError, "Calculated maximum base of #{max_base} across portfolios is not 32 or 64" unless max_base == 32 || max_base == 64

    super(name, cfg_arch, max_base, overlay_path: overlay_path)
  end

  # Returns a string representation of the object, suitable for debugging.
  # @return [String] A string representation of the object.
  def inspect = "PortfolioDesign##{name}"

  ##################################
  # METHODS REQUIRED BY BASE CLASS #
  ##################################

  # @return [Array<ParameterWithValue>] List of all parameters fully-constrained to one specific value
  def params_with_value
    return @params_with_value unless @params_with_value.nil?

    @params_with_value = []

    in_scope_ext_reqs.each do |ext_req|
      ext_req.extension.params.each do |param|
        next unless param_values.key?(param.name)

        @params_with_value << ParameterWithValue.new(param, param_values[param.name])
      end
    end

    @params_with_value
  end

  def implemented_ext_vers
    # Only supported by fully-configured configurations and a portfolio corresponds to a
    # partially-configured configuration. See the Config class for details.
    raise "Not supported for portfolio #{name}"
  end

  # Given an adoc string, find names of CSR/Instruction/Extension enclosed in `monospace`
  # and replace them with links to the relevant object page.
  # See backend_helpers.rb for a definition of the proprietary link format.
  #
  # @param adoc [String] Asciidoc source
  # @return [String] Asciidoc source, with link placeholders
  def convert_monospace_to_links(adoc)
    adoc.gsub(/`([\w.]+)`/) do |match|
      name = Regexp.last_match(1)
      csr_name, field_name = name.split(".")
      csr = in_scope_csrs.find { |c| c.name == csr_name }
      if !field_name.nil? && !csr.nil? && csr.field?(field_name)
        link_to_udb_doc_csr_field(csr_name, field_name)
      elsif !csr.nil?
        link_to_udb_doc_csr(csr_name)
      elsif in_scope_instructions.any? { |inst| inst.name == name }
        link_to_udb_doc_inst(name)
      elsif in_scope_extensions.any? { |ext| ext.name == name }
        link_to_udb_doc_ext(name)
      else
        match
      end
    end
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

  # @return [String] Given an instruction +ext_name+, return the presence as a string.
  #                  Returns the greatest presence string across all portfolios in this design.
  #                  If the instruction name isn't found in this design, return "-".
  def instruction_presence(inst_name) = @portfolio_grp.instruction_presence(inst_name)

  # @return [Array<InScopeParameter>] Sorted list of parameters specified by any extension in portfolio.
  def all_in_scope_params = @portfolio_grp.all_in_scope_params

  # @param [ExtensionRequirement]
  # @return [Array<InScopeParameter>] Sorted list of extension parameters from portfolio for given extension.
  def in_scope_params(ext_req) = @portfolio_grp.in_scope_params(ext_req)

  # @return [Array<Parameter>] Sorted list of parameters out of scope across all in scope extensions.
  def all_out_of_scope_params = @portfolio_grp.all_out_of_scope_params

  # @param ext_name [String] Extension name
  # @return [Array<Parameter>] Sorted list of parameters that are out of scope for named extension.
  def out_of_scope_params(ext_name) = @portfolio_grp.out_of_scope_params(ext_name)

  # @param param [Parameter]
  # @return [Array<Extension>] Sorted list of all in-scope extensions that define this parameter
  #                            in the database and the parameter is in-scope.
  def all_in_scope_exts_with_param(param) = @portfolio_grp.all_in_scope_exts_with_param(param)

  # @param param [Parameter]
  # @return [Array<Extension>] List of all in-scope extensions that define this parameter in the
  #                            database but the parameter is out-of-scope.
  def all_in_scope_exts_without_param(param) = @portfolio_grp.all_in_scope_exts_without_param(param)

  #################
  # EXTRA METHODS #
  #################

  # @param extra_inputs [Hash<String, Object>] Any extra inputs to be passed to ERB template.
  # @return [Hash<String, Object>] Hash of objects available to ERB templates and
  #                                ERB fragments included in the main ERB template.
  # Put this in a method so it can be easily overridden by subclasses.
  def erb_env(extra_inputs = {})
    raise ArgumentError, "extra_inputs must be an Hash but is a #{extra_inputs.class}" unless extra_inputs.is_a?(Hash)

    h = {
      arch: cfg_arch,
      design: self,
      portfolio_design: self,
      portfolio_design_type: @portfolio_design_type,
      portfolio_class: @portfolio_class,
      portfolio_kind: @portfolio_kind,
      portfolios: @portfolio_grp.portfolios
    }

    h.merge!(extra_inputs)
  end

  # Called from tasks.rake file to add standard set of objects available to ERB templates.
  def init_erb_binding(erb_binding)
    raise ArgumentError, "Expected Binding object but got #{erb_binding.class}" unless erb_binding.is_a?(Binding)

    erb_env.each do |key, obj|
      erb_binding.local_variable_set(key, obj)
    end
  end

  # Include a partial ERB template into a full ERB template.
  #
  # @param template_path [String] Name of template file located in backends/portfolio/templates
  # @param extra_inputs [Hash<String, Object>] Any extra inputs to be passed to ERB template.
  # @return [String] Result of ERB evaluation of the template file
  def include_erb(template_name, extra_inputs = {})
    template_pname = "portfolio/templates/#{template_name}"
    puts "UPDATE: #{portfolio_design_type} processing ERB partial template '#{template_pname}'"
    partial(template_pname, erb_env(extra_inputs))
  end
end

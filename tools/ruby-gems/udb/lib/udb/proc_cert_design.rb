# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

# Inherits from PortfolioDesign and contains content shared by
# all processor certificate-based designs.

require_relative "portfolio_design"

module Udb

class ProcCertDesign < PortfolioDesign
  # @return [ProcCertModel] The processor certificate model object from the architecture database
  attr_reader :proc_cert_model

  # @return [ProcCertClass] The processor certificate class object from the architecture database
  attr_reader :proc_cert_class

  # @param name [#to_s] The name of the portfolio design (i.e., backend filename without a suffix)
  # @param cfg_arch [ConfiguredArchitecture] The database of RISC-V standards for a particular configuration
  # @param portfolio_design_type [String] Type of portfolio design associated with this design
  # @param portfolios [Array<Portfolio>] Portfolios being converted to adoc
  # @param portfolio_class [PortfolioClass] PortfolioClass for all the Portfolios
  # @param normative_rule_tags [NormativeRuleTags] Some proc_cert_design objects have access to anchor text in stds docs
  def initialize(name, cfg_arch, portfolio_design_type, proc_cert_model, proc_cert_class, normative_rule_tags)
    raise ArgumentError, "name must be a String" unless name.is_a?(String)
    raise ArgumentError, "cfg_arch must be a ConfiguredArchitecture" unless cfg_arch.is_a?(ConfiguredArchitecture)
    raise ArgumentError, "portfolio_design_type must be a String" unless portfolio_design_type.is_a?(String)
    raise ArgumentError, "proc_cert_model must be a ProcCertModel" unless proc_cert_model.is_a?(ProcCertModel)
    raise ArgumentError, "proc_cert_class must be a ProcCertClass" unless proc_cert_class.is_a?(ProcCertClass)
    raise ArgumentError, "normative_rule_tags must be a NormativeRuleTags but is a #{normative_rule_tags.class}" unless normative_rule_tags.is_a?(NormativeRuleTags)

    @proc_cert_model = proc_cert_model
    @proc_cert_class = proc_cert_class

    super(name, cfg_arch, portfolio_design_type, [proc_cert_model], proc_cert_class, normative_rule_tags)
  end

  # Returns a string representation of the object, suitable for debugging.
  # @return [String] A string representation of the object.
  def inspect = "ProcCertDesign##{name}"

  # @param extra_inputs [Array<Hash>] Any extra inputs to be passed to ERB template.
  # @return [Hash<String, Object>] Hash of objects to be used in ERB templates
  # Add certificate-specific objects to the parent hash.
  def erb_env(*extra_inputs)
    raise ArgumentError, "extra_inputs must be an Array but is a #{extra_inputs.class}" unless extra_inputs.is_a?(Array)

    h = super   # Call parent method with whatever args I got

    h[:proc_cert_design] = self
    h[:proc_cert_model] = proc_cert_model
    h[:proc_cert_class] = proc_cert_class

    h
  end

  # Include a partial ERB template into a full ERB template. Can be either in
  # the portfolio or proc_cert backends (but not both).
  #
  # @param template_path [String] Name of template file located in backends/portfolio/templates
  #                               or in backends/proc_cert/templates
  # @param extra_inputs [Hash<String, Object>] Any extra inputs to be passed to ERB template.
  # @return [String] Result of ERB evaluation of the template file
  def include_erb(template_name, extra_inputs = {})
    proc_cert_template_pname = "proc_cert/templates/#{template_name}"
    proc_cert_template_path = Pathname.new($root / "backends" / proc_cert_template_pname)

    portfolio_template_pname = "portfolio/templates/#{template_name}"
    portfolio_template_path = Pathname.new($root / "backends" / portfolio_template_pname)

    if proc_cert_template_path.exist? && portfolio_template_path.exist?
      raise "Both #{proc_cert_template_pname} and #{portfolio_template_pname} exist. Need unique names."
    elsif proc_cert_template_path.exist?
      partial(proc_cert_template_pname, erb_env(extra_inputs))
    elsif portfolio_template_path.exist?
      partial(portfolio_template_pname, erb_env(extra_inputs))
    else
      raise "Can't find file #{template_name} in either #{proc_cert_template_pname} or #{portfolio_template_pname}."
    end
  end
end
end

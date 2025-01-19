# frozen_string_literal: true
#
# Contains common methods called from certification backend tasks.rake files.

require "pathname"
require "asciidoctor-pdf"
require "asciidoctor-diagram"

# @param erb_template_pname [String] Path to ERB template file
# @param target_pname [String] Full name of adoc file being generated
# @param model_name [String] Name of the processor certificate model
def proc_cert_create_adoc(erb_template_pname, target_pname, model_name)
  arch = pf_create_arch

  # Create ProcCertModel for specific processor certificate model as specified in its arch YAML file.
  # The Architecture object also creates all other portfolio-related class instances from their arch YAML files.
  # None of these objects are provided with a Design object when created.
  puts "UPDATE: Creating ProcCertModel object for #{model_name}"
  proc_cert_model = arch.proc_cert_model(model_name)
  proc_cert_class = proc_cert_model.proc_cert_class

  # Create the one PortfolioDesign object required for the ERB evaluation.
  puts "UPDATE: Creating PortfolioDesign object using processor certificate model #{model_name}"
  portfolio_design = PortfolioDesign.new(model_name, arch, PortfolioDesign.proc_ctp_type, [proc_cert_model], proc_cert_class)

  # Create empty binding and then specify explicitly which variables the ERB template can access.
  # Seems to use this method name in stack backtraces (hence its name).
  def evaluate_erb
    binding
  end
  erb_binding = evaluate_erb
  portfolio_design.init_erb_binding(erb_binding)
  erb_binding.local_variable_set(:proc_cert_model, proc_cert_model)
  erb_binding.local_variable_set(:proc_cert_class, proc_cert_class)

  pf_create_adoc(erb_template_pname, erb_binding, target_pname, portfolio_design)
end

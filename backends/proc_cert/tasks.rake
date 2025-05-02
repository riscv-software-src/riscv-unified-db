# frozen_string_literal: true
#
# Contains common methods called from certification backend tasks.rake files.

require "pathname"

# @param erb_template_pname [String] Path to ERB template file
# @param target_pname [String] Full name of adoc file being generated
# @param model_name [String] Name of the processor certificate model
def proc_cert_create_adoc(erb_template_pname, target_pname, model_name)
  # Create Architecture object without any knowledge of certificate model.
  $logger.info "Creating Architecture object for #{model_name}"
  arch = pf_create_arch

  # Create ProcCertModel for specific processor certificate model as specified in its arch YAML file.
  # The Architecture object also creates all other portfolio-related class instances from their arch YAML files.
  # None of these objects are provided with a AbstractConfig or Design object when created.
  $logger.info "Creating ProcCertModel with only an Architecture object for #{model_name}"
  proc_cert_model_with_arch = arch.proc_cert_model(model_name)

  # Create the ConfiguredArchitecture object with knowledge of the ProcCertModel.
  # Needs a PortfolioGroup object so just create one with just one ProcCertModel (which is a child of Portfolio).
  cfg_arch = pf_create_cfg_arch(PortfolioGroup.new(model_name, [proc_cert_model_with_arch]))

  $logger.info "Creating ProcCertModel with a ConfiguredArchitecture object for #{model_name}"
  proc_cert_model_with_cfg_arch = cfg_arch.proc_cert_model(model_name)

  # Create the one ProcCertDesign object required for the ERB evaluation using the cfg_arch.
  $logger.info "Creating ProcCertDesign object using processor certificate model #{model_name}"
  proc_cert_design = ProcCertDesign.new(model_name, cfg_arch, ProcCertDesign.proc_ctp_type, proc_cert_model_with_cfg_arch,
    proc_cert_model_with_cfg_arch.proc_cert_class)

  # Create empty binding and then specify explicitly which variables the ERB template can access.
  # Seems to use this method name in stack backtraces (hence its name).
  def evaluate_erb
    binding
  end
  erb_binding = evaluate_erb
  proc_cert_design.init_erb_binding(erb_binding)

  pf_create_adoc(erb_template_pname, erb_binding, target_pname, proc_cert_design)
end

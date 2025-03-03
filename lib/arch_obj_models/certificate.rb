# Classes for certificates.
# Each processor certificate model is a member of a processor certificate class.

require_relative "portfolio"

###################
# ProcCertClass Class #
###################

# Holds information from processor certificate class YAML file.
# The inherited "data" member is the database of extensions, instructions, CSRs, etc.
class ProcCertClass < PortfolioClass
  def mandatory_priv_modes = @data["mandatory_priv_modes"]
end

###################
# ProcCertModel Class #
###################

# Holds information about a processor certificate model YAML file.
# The inherited "data" member is the database of extensions, instructions, CSRs, etc.
class ProcCertModel < Portfolio
  # @param obj_yaml [Hash<String, Object>] Contains contents of Certificate Model yaml file (put in @data)
  # @param data_path [String] Path to yaml file
  # @param arch [Architecture] Database of RISC-V standards
  def initialize(obj_yaml, yaml_path, arch)
    super # Calls parent class with the same args I got

    puts "UPDATE:   Creating ProcCertModel object for #{name} using arch #{arch.name}"
  end

  def unpriv_isa_manual_revision = @data["unpriv_isa_manual_revision"]
  def priv_isa_manual_revision = @data["priv_isa_manual_revision"]
  def debug_manual_revision = @data["debug_manual_revision"]

  def tsc_profile
    return nil if @data["tsc_profile"].nil?

    profile = arch.profile(@data["tsc_profile"])

    raise "No profile '#{@data["tsc_profile"]}'" if profile.nil?

    profile
  end

  # @return [ProcCertClass] The certification class that this model belongs to.
  def proc_cert_class
    proc_cert_class = @arch.ref(@data["class"]['$ref'])
    raise "No processor certificate class named '#{@data["class"]}'" if proc_cert_class.nil?

    proc_cert_class
  end

  #####################
  # Requirement Class #
  #####################

  # Holds extra requirements not associated with extensions or their parameters.
  class Requirement
    def initialize(data, arch)
      @data = data
      @arch = arch
    end

    def name = @data["name"]

    def description = @data["description"]

    def when = @data["when"]

    def when_pretty
      @data["when"].keys.map do |key|
        case key
        when "xlen"
          "XLEN == #{@data["when"]["xlen"]}"
        when "param"
          @data["when"]["param"].map do |param_name, param_value|
            "Parameter #{param_name} == #{param_value}"
          end
        else
          raise "Type #{key} not implemented"
        end
      end.flatten.join(" and ")
    end
  end

  ##########################
  # RequirementGroup Class #
  ##########################

  # Holds a group of Requirement objects to provide a one-level group.
  # Can't nest RequirementGroup objects to make multi-level group.
  class RequirementGroup
    def initialize(data, arch)
      @data = data
      @arch = arch
    end

    def name = @data["name"]

    def description = @data["description"]

    def when = @data["when"]

    def when_pretty
      @data["when"].keys.map do |key|
        case key
        when "xlen"
          "XLEN == #{@data["when"]["xlen"]}"
        when "param"
          @data["when"]["param"].map do |param_name, param_value|
            "Parameter #{param_name} == #{param_value}"
          end
        else
          raise "Type #{key} not implemented"
        end
      end.flatten.join(" and ")
    end

    def requirements
      return @requirements unless @requirements.nil?

      @requirements = []
      @data["requirements"].each do |req|
        @requirements << Requirement.new(req, @arch)
      end
      @requirements
    end
  end

  def requirement_groups
    return @requirement_groups unless @requirement_groups.nil?

    @requirement_groups = []
    @data["requirement_groups"]&.each do |req_group|
      @requirement_groups << RequirementGroup.new(req_group, @arch)
    end
    @requirement_groups
  end
end

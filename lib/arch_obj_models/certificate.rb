# Classes for certificates.
# Each certificate model is a member of a certificate class.

require_relative "portfolio"

###################
# CertClass Class #
###################

# Holds information from certificate class YAML file.
# The inherited "data" member is the database of extensions, instructions, CSRs, etc.
class CertClass < PortfolioClass
  def mandatory_priv_modes = @data["mandatory_priv_modes"]
end

###################
# CertModel Class #
###################

# Holds information about a certificate model YAML file.
# The inherited "data" member is the database of extensions, instructions, CSRs, etc.
class CertModel < PortfolioInstance
  def unpriv_isa_manual_revision = @data["unpriv_isa_manual_revision"]
  def priv_isa_manual_revision = @data["priv_isa_manual_revision"]
  def debug_manual_revision = @data["debug_manual_revision"]

  def tsc_profile
    return nil if @data["tsc_profile"].nil?

    profile = arch_def.profile(@data["tsc_profile"])

    raise "No profile '#{@data["tsc_profile"]}'" if profile.nil?

    profile
  end

  # @return [CertClass] The certification class that this model belongs to.
  def cert_class
    cert_class = @arch_def.ref(@data["class"]['$ref'])
    raise "No certificate class named '#{@data["class"]}'" if cert_class.nil?

    cert_class
  end

  #####################
  # Requirement Class #
  #####################

  # Holds extra requirements not associated with extensions or their parameters.
  class Requirement
    def initialize(data, arch_def)
      @data = data
      @arch_def = arch_def
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
          raise "TODO: when type #{key} not implemented"
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
    def initialize(data, arch_def)
      @data = data
      @arch_def = arch_def
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
          raise "TODO: when type #{key} not implemented"
        end
      end.flatten.join(" and ")
    end

    def requirements
      return @requirements unless @requirements.nil?

      @requirements = []
      @data["requirements"].each do |req|
        @requirements << Requirement.new(req, @arch_def)
      end
      @requirements
    end
  end

  def requirement_groups
    return @requirement_groups unless @requirement_groups.nil?

    @requirement_groups = []
    @data["requirement_groups"]&.each do |req_group|
      @requirement_groups << RequirementGroup.new(req_group, @arch_def)
    end
    @requirement_groups
  end
end

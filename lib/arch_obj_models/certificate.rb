# Classes for certificates.
# Each processor certificate model is a member of a processor certificate class.

require_relative "portfolio"

#######################
# ProcCertClass Class #
#######################

# Holds information from processor certificate class YAML file.
# The inherited "data" member is the database of extensions, instructions, CSRs, etc.
class ProcCertClass < PortfolioClass
end

#######################
# ProcCertModel Class #
#######################

# Holds information about a processor certificate model YAML file.
# The inherited "data" member is the database of extensions, instructions, CSRs, etc.
class ProcCertModel < Portfolio
  # @param obj_yaml [Hash<String, Object>] Contains contents of Certificate Model yaml file (put in @data)
  # @param data_path [String] Path to yaml file
  # @param arch [Architecture] Database of RISC-V standards
  def initialize(obj_yaml, yaml_path, arch)
    super # Calls parent class with the same args I got
  end

  def unpriv_isa_manual_revision = @data["unpriv_isa_manual_revision"]
  def priv_isa_manual_revision = @data["priv_isa_manual_revision"]
  def debug_manual_revision = @data["debug_manual_revision"]

  def tsc_profile_release
    return nil if @data["tsc_profile_release"].nil?

    profile_release = @arch.ref(@data["tsc_profile_release"]['$ref'])

    raise "No profile release called '#{@data["tsc_profile_release"]}' exists" if profile_release.nil?

    profile_release
  end

  def in_scope_priv_modes = @data["in_scope_priv_modes"]

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
    # @param data [Hash<String, Object>] Data from yaml
    # @param arch [Architecture] Architecture standards
    def initialize(data, arch)
      raise ArgumentError, "Bad data" unless data.is_a?(Hash)
      raise ArgumentError, "Need Architecture class but it's a #{arch.class}" unless arch.is_a?(Architecture)

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
    # @param data [Hash<String, Object>] Data from yaml
    # @param arch [Architecture] Architecture standards
    def initialize(data, arch)
      unless data.is_a?(Hash)
        raise ArgumentError, "Bad data" unless data.is_a?(Hash)
      end
      raise ArgumentError, "Need Architecture class but it's a #{arch.class}" unless arch.is_a?(Architecture)

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

    # @return [Array<Requirement>] The list of requirements in this group.
    def requirements
      return @requirements unless @requirements.nil?

      @requirements = []
      @data["requirements"].each do |req|
        @requirements << Requirement.new(req, @arch)
      end
      @requirements
    end
  end

  # @return [Array<RequirementGroup>] The list of requirement groups
  def requirement_groups
    return @requirement_groups unless @requirement_groups.nil?

    @requirement_groups = []
    @data["requirement_groups"]&.each do |req_key, req_group|
      @requirement_groups << RequirementGroup.new(req_group, @arch) unless req_key == "$child_of"
    end
    @requirement_groups
  end

  ###################################
  # Routines using InScopeParameter #
  ###################################

  # @return [Array<InScopeParameter>] Sorted list of parameters specified by any extension in portfolio.
  # These are always IN-SCOPE by definition (since they are listed in the portfolio).
  # Can have multiple array entries with the same parameter name since multiple extensions may define
  # the same parameter.
  def all_in_scope_params
    return @all_in_scope_params unless @all_in_scope_params.nil?

    @all_in_scope_params = []

    @data["extensions"].each do |ext_name, ext_data|
      next if ext_name[0] == "$"

      # Find Extension object from database
      ext = @arch.extension(ext_name)
      if ext.nil?
        raise "Cannot find extension named #{ext_name}"
      end

      ext_data["param_constraints"]&.each do |param_name, param_data|
        param = ext.params.find { |p| p.name == param_name }
        raise "There is no param '#{param_name}' in extension '#{ext_name}" if param.nil?

        next unless ext.versions.any? do |ext_ver|
          ver_req = ext_data["version"] || ">= #{ext.min_version.version_spec}"
          ExtensionRequirement.new(ext_name, ver_req, @arch).satisfied_by?(ext_ver) &&
            param.defined_in_extension_version?(ext_ver)
        end

        @all_in_scope_params << InScopeParameter.new(param, param_data["schema"], param_data["note"])
      end
    end
    @all_in_scope_params.sort!
  end

  # @param [ExtensionRequirement]
  # @return [Array<InScopeParameter>] Sorted list of extension parameters from portfolio for given extension.
  # These are always IN SCOPE by definition (since they are listed in the portfolio).
  def in_scope_params(ext_req)
    raise ArgumentError, "Expecting ExtensionRequirement" unless ext_req.is_a?(ExtensionRequirement)

    params = []    # Local variable, no caching

    # Get extension information from portfolio YAML for passed in extension requirement.
    ext_data = @data["extensions"][ext_req.name]
    raise "Cannot find extension named #{ext_req.name}" if ext_data.nil?

    # Find Extension object from database
    ext = @arch.extension(ext_req.name)
    raise "Cannot find extension named #{ext_req.name}" if ext.nil?

    # Loop through an extension's parameter constraints (hash) from the certificate model.
    # Note that "&" is the Ruby safe navigation operator (i.e., skip do loop if nil).
    ext_data["param_constraints"]&.each do |param_name, param_data|
      # Find Parameter object from database
      param = ext.params.find { |p| p.name == param_name }
      raise "There is no param '#{param_name}' in extension '#{ext_req.name}" if param.nil?

      next unless ext.versions.any? do |ext_ver|
        ext_req.satisfied_by?(ext_ver) && param.defined_in_extension_version?(ext_ver)
      end

      params << InScopeParameter.new(param, param_data["schema"], param_data["note"])
    end

    params.sort!
  end

  # @return [Array<Parameter>] Sorted list of parameters out of scope across all in scope extensions
  #                                     (those listed as mandatory or optional in the certificate model).
  def all_out_of_scope_params
    return @all_out_of_scope_params unless @all_out_of_scope_params.nil?

    @all_out_of_scope_params = []
    in_scope_ext_reqs.each do |ext_req|
      ext = @arch.extension(ext_req.name)
      ext.params.each do |param|
        next if all_in_scope_params.any? { |c| c.param.name == param.name }

        next unless ext.versions.any? do |ext_ver|
                      ext_req.satisfied_by?(ext_ver) &&
                      param.defined_in_extension_version?(ext_ver)
                    end

        @all_out_of_scope_params << param
      end
    end
    @all_out_of_scope_params.sort!
  end

  # @param ext_name [String] Extension name
  # @return [Array<Parameter>] Sorted list of parameters that are out of scope for named extension.
  def out_of_scope_params(ext_name)
    all_out_of_scope_params.select{ |param| param.exts.any? { |ext| ext.name == ext_name } }.sort
  end

  # @param param [Parameter]
  # @return [Array<Extension>] Sorted list of all in-scope extensions that define this parameter
  #                            in the database and the parameter is in-scope.
  def all_in_scope_exts_with_param(param)
    raise ArgumentError, "Expecting Parameter" unless param.is_a?(Parameter)

    exts = []

    # Iterate through all the extensions in the architecture database that define this parameter.
    param.exts.each do |ext|
      found = false

      in_scope_extensions.each do |potential_ext|
        if ext.name == potential_ext.name
          found = true
          next
        end
      end

      if found
        # Only add extensions that exist in this certificate model.
        exts << ext
      end
    end

    # Return intersection of extension names
    exts.sort_by!(&:name)
  end

  # @param param [Parameter]
  # @return [Array<Extension>] List of all in-scope extensions that define this parameter in the
  #                            database but the parameter is out-of-scope.
  def all_in_scope_exts_without_param(param)
    raise ArgumentError, "Expecting Parameter" unless param.is_a?(Parameter)

    exts = []   # Local variable, no caching

    # Iterate through all the extensions in the architecture database that define this parameter.
    param.exts.each do |ext|
      found = false

      in_scope_extensions.each do |potential_ext|
        if ext.name == potential_ext.name
          found = true
          next
        end
      end

      if found
          # Only add extensions that are in-scope (i.e., exist in this certificate model).
          exts << ext
      end
    end

    # Return intersection of extension names
    exts.sort_by!(&:name)
  end
end

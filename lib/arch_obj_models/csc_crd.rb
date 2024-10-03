# Classes for CRD (Certification Requirements Documents).
# Each CRD is a member of a CRD family (e.g., Microcontroller).
#
# Some classes inherit from the ArchDefObject class. This provides facilities for accessing
# the contents of a CRD family or CRD YAML definition via the "data" member (hash holding YAML file contents).
# A variable name with a "_crd" suffix indicates it is from the CRD family/member YAML file.
#
# The "archdef" member is an ArchDef class containing the "database" of RISC-V standards
# including extensions, instructions, CSRs, Profiles, and CRDs.
# A variable name with a "_db" suffix indicates it is from the archdef.

class CscCrdFamily < ArchDefObject
  class Revision < ArchDefObject
    def initialize(data)
      super(data)
    end

    def version
      @data["version"]
    end

    def date
      @data["date"]
    end

    def changes
      @data["changes"]
    end
  end
end

class CscCrdFamily < ArchDefObject
  attr_reader :arch_def

  def initialize(data, arch_def)
    super(data)
    @arch_def = arch_def
  end

  def mandatory_priv_modes = @data["mandatory_priv_modes"]

  def revisions
    return @revisions unless @revisions.nil?

    @revisions = []
    @data["revision_history"].each do |rev|
      @revisions << Revision.new(rev)
    end
    @revisions
  end

  def introduction = @data["introduction"]

  def naming_scheme = @data["naming_scheme"]

  def eql?(other)
    other.is_a?(CscCrdFamily) && other.name == name
  end

  def crds
    return @crds unless @version.nil?

    @crds = []
    arch_def.csc_crds.each do |csc_crd|
      @crds << csc_crd if csc_crd.famly == self
    end
    @crds
  end
end

class CscCrd < ArchDefObject
  attr_reader :arch_def

  def initialize(data, arch_def)
    super(data)
    @arch_def = arch_def
  end

  def version = @data["version"]

  def family
    return @family unless @family.nil?

    fam = @arch_def.csc_crd_family(@data["family"])
    raise "No CSC CRD family named '#{@data["family"]}'" if fam.nil?

    @family = fam
  end

  def tsc_profile
    return nil if @data["tsc_profile"].nil?

    profile = arch_def.profile(@data["tsc_profile"])

    raise "No profile '#{@data["tsc_profile"]}'" if profile.nil?

    profile
  end

  def unpriv_isa_manual_revision = @data["unpriv_isa_manual_revision"]

  def priv_isa_manual_revision = @data["priv_isa_manual_revision"]

  def debug_manual_revision = @data["debug_manual_revision"]

  def description = @data["description"]

  # @return [Array<ExtensionRequirements>] - # Extensions with their CRD information.
  def extension_reqs
    return @extension_reqs_crd unless @extension_reqs_crd.nil?

    @extension_reqs_crd = []
    [ "mandatory", "optional"].each do |status|
      @data["extensions"][status]&.each do |ext_crd|
        @extension_reqs_crd << 
          ExtensionRequirement.new(ext_crd["name"], ext_crd["version"], 
            note: ext_crd["note"], req_id: "REQ-EXT-" + ext_crd["name"], status: status)
      end
    end
    @extension_reqs_crd
  end

  # @return [Array<Extension>] List of extensions
  def extensions
    extension_reqs.map do |er|
      obj = arch_def.extension(er.name)

      # @todo: change this to raise once all the profile extensions
      #        are defined
      warn "Extension #{er.name} is not defined" if obj.nil?

      obj
    end.reject(&:nil?)
  end

  # Holds an extension's parameter schema constraint from the CRD YAML.
  class CrdParameterConstraint
    attr_reader :param_db  # ExtensionParameter object (from the architecture database)
    attr_reader :note

    def initialize(param_db, schema_constraint, note)
      raise ArgumentError, "Expecting ExtensionParameter" unless param_db.is_a?(ExtensionParameter)

      @param_db = param_db
      @schema_constraint = schema_constraint
      @note = note
    end

    def single_value?
      !@schema_constraint.nil? && @schema_constraint.key?("const")
    end

    def value
      raise "Parameter schema_constraint for #{@param_db.name} is not a single value" unless single_value?

      @schema_constraint["const"]
    end

    def schema_constraint_pretty
      return "Unconstrained" if (@schema_constraint.nil? or @schema_constraint == "")
      if @schema_constraint.key?("const")
        "#{@schema_constraint["const"]}"
      elsif @schema_constraint.key?("enum")
        "One of: [#{@schema_constraint["enum"].join(', ')}]"
      else
        raise "TODO: Pretty schema for #{@schema_constraint}"
      end
    end

    # sorts by name
    def <=>(other)
      raise ArgumentError, 
        "CrdParameterConstraint are only comparable to other parameter constraints" unless other.is_a?(CrdParameterConstraint)
      @param_db.name <=> other.param_db.name
    end
  end

  # @return [Array<CrdParameterConstraint>] List of parameters constraints from CRD extension information.
  # These are always IN SCOPE by definition (since they are listed in the CRD).
  def param_constraints(ext_req_crd)
    param_constraints = []    # Local variable, no caching

    # Get extension information from CRD YAML for passed in extension requirement.
    ext_crd = @data["extensions"][ext_req_crd.status].find {|ext| ext["name"] == ext_req_crd.name}
    raise "Cannot find extension named #{ext_req_crd.name}" if ext_crd.nil?
    
    # Find Extension object from database
    ext_db = @arch_def.extension(ext_crd["name"])
    raise "Cannot find extension named #{ext_crd["name"]}" if ext_db.nil?

    # Loop through an extension's parameter constraints (hash) from the CRD.
    # Note that "&" is the Ruby safe navigation operator (i.e., skip do loop if nil).
    ext_crd["param_constraints"]&.each do |param_name, param_data|
        # Find ExtensionParameter object from database
        ext_param_db = ext_db.params.find { |p| p.name == param_name }
        raise "There is no param '#{param_name}' in extension '#{ext_crd["name"]}" if ext_param_db.nil?

        param_constraints << CrdParameterConstraint.new(ext_param_db, param_data["schema"], param_data["note"])
    end

    param_constraints
  end

  # @return [Array<CrdParameterConstraint>] List of parameters constraints specified by any extension in CRD.
  # These are always IN SCOPE by definition (since they are listed in the CRD).
  def all_parameter_constraints
    return @all_parameter_constraints unless @all_parameter_constraints.nil?

    @all_parameter_constraints = []

    [ "mandatory", "optional"].each do |status|
      @data["extensions"][status].each do |ext_crd| 
        # Find Extension object from database
        ext_db = @arch_def.extension(ext_crd["name"])
        raise "Cannot find extension named #{ext_crd["name"]}" if ext_db.nil?
  
        ext_crd["param_constraints"]&.each do |param_name, param_data|
          param_db = ext_db.params.find { |p| p.name == param_name }
          raise "There is no param '#{param_name}' in extension '#{ext_crd["name"]}" if param_db.nil?
  
          @all_parameter_constraints << CrdParameterConstraint.new(param_db, param_data["schema"], param_data["note"])
        end
      end
    end
    @all_parameter_constraints
  end

  # @return [Array<ExtensionParameter>] List of parameters that are out of scope across all extensions.
  def all_out_of_scope_params
    return @all_out_of_scope_params unless @all_out_of_scope_params.nil?
 
    @all_out_of_scope_params = []
    extension_reqs.each do |ext_req_crd|
      @arch_def.extension(ext_req_crd.name).params.each do |param_db|
        next if all_parameter_constraints.any? { |c| c.param_db.name == param_db.name }
        @all_out_of_scope_params << param_db
      end
    end
    @all_out_of_scope_params
  end

  # @return [Array<ExtensionParameter>] List of parameters that are out of scope for named extension.
  def out_of_scope_params(ext_name)
    all_out_of_scope_params.select{|param_db| param_db.exts.any? {|ext| ext.name == ext_name} } 
  end

  class Requirement < ArchDefObject
    def initialize(data, arch_def)
      super(data)
      @arch_def = arch_def
    end

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

  class RequirementGroup < ArchDefObject
    def initialize(data, arch_def)
      super(data)
      @arch_def = arch_def
    end

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
    @data["requirement_groups"].each do |req_group|
      @requirement_groups << RequirementGroup.new(req_group, @arch_def)
    end
    @requirement_groups
  end
end

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
    return @versions unless @version.nil?

    @versions = []
    arch_def.csc_crds.each do |csc_crd|
      @versions << csc_crd if csc_crd.famly == self
    end
    @versions
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

  def extension_reqs
    return @extension_reqs unless @extension_reqs.nil?

    @extension_reqs = []
    [ "mandatory", "optional"].each do |status|
      @data["extensions"][status]&.each do |ext|
        @extension_reqs << 
          ExtensionRequirement.new(ext["name"], ext["version"], note: ext["note"], req_id: "REQ-EXT-" + ext["name"],
            status: status)
      end
    end
    @extension_reqs
  end

  class ParameterConstraint
    attr_reader :param  # ExtensionParameter object
    attr_reader :note

    def initialize(param, constraint, note)
      raise ArgumentError, "Expecting ExtensionParameter" unless param.is_a?(ExtensionParameter)

      @param = param
      @schema_constraint = constraint
      @note = note
    end

    def single_value?
      !@schema_constraint.nil? && @schema_constraint.key?("const")
    end

    def value
      raise "Parameter constraint for #{@param.name} is not a single value" unless single_value?

      @schema_constraint["const"]
    end

    def schema_constraint_pretty
      return "" if @schema_constraint.nil?
      if @schema_constraint.key?("const")
        "== #{@schema_constraint["const"]}"
      elsif @schema_constraint.key?("enum")
        "One of: [#{@schema_constraint["enum"].join(', ')}]"
      else
        raise "TODO: Pretty schema for #{@schema_constraint}"
      end
    end
  end

  # @return [Array<ParameterConstraint>] List of parameters constraints specified by an extension requirement.
  def param_constraints(ext_req)
    param_constraints = []    # Local variable, no caching

    ext_data = @data["extensions"][ext_req.status].find {|ext| ext["name"] == ext_req.name}
    raise "Cannot find extension named #{ext_req.name}" if ext_data.nil?
    
    # Find Extension object from database
    ext_db = @arch_def.extension(ext_data["name"])
    raise "Cannot find extension named #{ext_data["name"]}" if ext_db.nil?

    # & is the safe navigation operator
    ext_data["param_constraints"]&.each do |param_name, param_data|
        # Find ExtensionParameter object from database
        ext_param_db = ext_db.params.find { |p| p.name == param_name }
        raise "There is no param '#{param_name}' in extension '#{ext_data["name"]}" if ext_param_db.nil?

        param_constraints << ParameterConstraint.new(ext_param_db, param_data["schema"], param_data["note"])
    end

    param_constraints
  end

  # @return [Array<ParameterConstraint>] List of parameters constraints specified by any extension.
  def in_scope_param_constraints
    return @in_scope_param_constraints unless @in_scope_param_constraints.nil?

    @in_scope_param_constraints = []

    # XXX - Only looks at mandatory
    @data["extensions"]["mandatory"].each do |ext_data| 
      # Find Extension object from database
      ext_db = @arch_def.extension(ext_data["name"])
      raise "Cannot find extension named #{ext_data["name"]}" if ext_db.nil?

      next if ext_data["param_constraints"].nil?

      ext_data["param_constraints"].each do |param_name, param_data|
        param = ext_db.params.find { |p| p.name == param_name }
        raise "There is no param '#{param_name}' in extension '#{ext_data["name"]}" if param.nil?

        @in_scope_param_constraints << ParameterConstraint.new(param, param_data["schema"], param_data["note"])
      end
    end
    @in_scope_param_constraints
  end

  # @return [Array<ParameterConstraint>] List of parameters that are out of scope across all extensions.
  def out_of_scope_param_constraints
    return @out_of_scope_param_constraints unless @out_of_scope_param_constraints.nil?
 
    @out_of_scope_param_constraints = []
    extension_reqs.each do |ext_req|
      @arch_def.extension(ext_req.name).params.each do |param|
        next if in_scope_param_constraints.any? { |c| c.param.name == param.name }
        @out_of_scope_param_constraints << param
      end
    end
    @out_of_scope_param_constraints
  end

  # @return [Array<ExtensionParameter>] List of parameters that are out of scope
  def extension_out_of_scope_param_constraints(ext_req)
    out_of_scope_param_constraints.select{|param| param.exts.any? {|ext| ext.name == ext_req.name} } 
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

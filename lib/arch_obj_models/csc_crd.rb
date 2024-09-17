
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

  def overview = @data["overview"]

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

  def mandatory_extensions
    return @mandatory_extensions unless @mandatory_extensions.nil?

    @mandatory_extensions = []
    @data["mandatory_extensions"].each do |ext|
      @mandatory_extensions << ExtensionRequirement.new(ext["name"], ext["version"])
    end
    @mandatory_extensions
  end

  def optional_extensions
    return @optional_extensions unless @optional_extensions.nil?

    @optional_extensions = []
    return @optional_extensions if @data["optional_extensions"].nil?
    @data["optional_extensions"].each do |ext|
      @optional_extensions << ExtensionRequirement.new(ext["name"], ext["version"])
    end
    @optional_extensions
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

  class ParameterConstraint
    attr_reader :note
    attr_reader :param

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

  def in_scope_param_constraints
    return @param_constraints unless @param_constraints.nil?

    @param_constraints = []
    @data["in_scope_params"].each do |param_name, param_data| 
      from_ext = @arch_def.extensions.find { |ext| ext.params.any?{ |p| p.name == param_name } }
      raise "Cannot find extension definition that has a parameter named '#{param_name}'" if from_ext.nil?

      param = from_ext.params.find { |p| p.name == param_name }
      @param_constraints << ParameterConstraint.new(param, param_data["schema"], param_data["note"])
    end
    @param_constraints
  end

  # @return [Array<ExtensionParameter>] List of parameters that are out of scope
  def out_of_scope_param_constraints
    return @out_of_scope_param_constraints unless @out_of_scope_param_constraints.nil?
 
    @out_of_scope_param_constraints = []
    mandatory_extensions.each do |ext|
      @arch_def.extension(ext.name).params.each do |param|
        next if in_scope_param_constraints.any? { |c| c.param.name == param.name }
        @out_of_scope_param_constraints << param
      end
    end
    @out_of_scope_param_constraints
  end
end

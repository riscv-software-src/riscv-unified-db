# Classes for CRD (Certification Requirements Documents).
# Each CRD is a member of a CRD family (e.g., Microcontroller).
#
# Many classes inherit from the ArchDefObject class. This provides facilities for accessing the contents of a
# CRD family YAML or CRD YAML file via the "data" member (hash holding releated YAML file contents).
#
# Many classes have an "arch_def" member which is an ArchDef (not ArchDefObject) class.
# The "arch_def" member contains the "database" of RISC-V standards including extensions, instructions, CSRs, Profiles, and CRDs. 
# The arch_def member has methods such as:
#   extensions()          Array<Extension> of all extensions known to the database (even if not implemented).
#   extension(name)       Extension object for "name" and nil if none.
#   parameters()          Array<ExtensionParameter> of all parameters defined in the architecture
#   param(name)           ExtensionParameter object for "name" and nil if none.
#   csrs()                Array<Csr> of all CSRs defined by RISC-V, whether or not they are implemented
#   csr(name)             Csr object for "name" and nil if none.
#   instructions()        Array<Instruction> of all instructions, whether or not they are implemented
#   inst(name)            Instruction object for "name" and nil if none.
#   profile_families      Array<ProfileFamily> of all known profile families
#   profile_family(name)  ProfileFamily object for "name" and nil if none.
#   profiles              Array<Profile> of all known profiles.
#   profile(name)         Profile object for "name" and nil if none.
#   crd_families          Array<CrdFamily> of all known CRD families
#   crd_family(name)      CrdFamily object for "name" and nil if none.
#   crds                  Array<Crd> of all known CRDs.
#   crd(name)             Crd object for "name" and nil if none.
#
# A variable name with a "_crd" suffix indicates it is from the CRD family/member YAML file.
# A variable name with a "_db" suffix indicates it is an object reference from the arch_def database.

require_relative "schema"

###################
# CrdFamily Class #
###################

# Holds information from CRD family YAML file.
# The inherited "data" member is the database of extensions, instructions, CSRs, etc.
class CrdFamily < ArchDefObject
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

class CrdFamily < ArchDefObject
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
    other.is_a?(CrdFamily) && other.name == name
  end

  def crds
    return @crds unless @version.nil?

    @crds = []
    arch_def.crds.each do |crd|
      @crds << crd if crd.famly == self
    end
    @crds
  end
end

#############
# Crd Class #
#############

# Holds information about a CRD YAML file.
# The inherited "data" member is the database of extensions, instructions, CSRs, etc.
class Crd < ArchDefObject
  attr_reader :arch_def

  def initialize(data, arch_def)
    super(data)
    @arch_def = arch_def
  end

  def version = @data["version"]

  def family
    return @family unless @family.nil?

    fam = @arch_def.crd_family(@data["family"])
    raise "No CRD family named '#{@data["family"]}'" if fam.nil?

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

  # @return [Extension] - # Returns named Extension object from database (nil if not found).
  def extension_from_db(name)
    @arch_def.extension(name)
  end

  # @return [Array<Extension>] List of all extensions listed as mandatory or optional in CRD.
  def in_scope_extensions
    in_scope_ext_reqs.map do |er|
      obj = arch_def.extension(er.name)

      # @todo: change this to raise once all the profile extensions
      #        are defined
      warn "Extension #{er.name} is not defined" if obj.nil?

      obj
    end.reject(&:nil?)
  end

  # @return [Array<ExtensionRequirements>] - # Extensions with their CRD information.
  # If desired_presence is provided, only returns extensions with that presence.
  def in_scope_ext_reqs(desired_presence = nil)
    in_scope_ext_reqs = []
    @data["extensions"]&.each do |ext_crd|
      actual_presence = ext_crd["presence"]
      raise "Missing extension presence for extension #{ext_crd["name"]}" if actual_presence.nil?

      if (actual_presence != "mandatory") && (actual_presence != "optional")
        raise "Unknown extension presence of #{actual_presence} for extension #{ext_crd["name"]}" 
      end

      add = false

      if desired_presence.nil?
        add = true
      elsif desired_presence == actual_presence
        add = true
      end

      if add
        in_scope_ext_reqs << 
          ExtensionRequirement.new(ext_crd["name"], ext_crd["version"], presence: actual_presence,
            note: ext_crd["note"], req_id: "REQ-EXT-" + ext_crd["name"])
      end
    end
    in_scope_ext_reqs
  end

  ###################################
  # InScopeExtensionParameter Class #
  ###################################

  # Holds extension parameter information from the CRD.
  class InScopeExtensionParameter
    attr_reader :param_db  # ExtensionParameter object (from the architecture database)
    attr_reader :note

    def initialize(param_db, schema_hash, note)
      raise ArgumentError, "Expecting ExtensionParameter" unless param_db.is_a?(ExtensionParameter)

      if schema_hash.nil?
        schema_hash = {}
      else
        raise ArgumentError, "Expecting schema_hash to be a hash" unless schema_hash.is_a?(Hash)
      end

      @param_db = param_db
      @schema_crd = Schema.new(schema_hash)
      @note = note
    end

    def single_value?
      @schema_crd.single_value?
    end

    def name
      @param_db.name
    end

    def idl_type
      @param_db.type
    end

    def value
      raise "Parameter schema_crd for #{name} is not a single value" unless single_value?

      @schema_crd.value
    end

    # @return [String] - # What parameter values are allowed by the CRD.
    #
    # Old implementation:
    #   def schema_pretty_crd_merged_with_param_db
    #     Schema.new(@param_db.schema).merge!(@schema_crd).to_pretty_s
    #   end
    def allowed_values
      if (@schema_crd.empty?)
        # CRD doesn't add any constraints on parameter's value.
        return "Any"
      end

      # Create a Schema object just using information in the parameter database.
      schema_obj = @param_db.schema

      # Merge in constraints imposed by the CRD on the parameter.
      schema_obj.merge!(@schema_crd)

      # Create string showing allowed values of parameter with CRD constraints added
      schema_obj.to_pretty_s
    end

    # sorts by name
    def <=>(other)
      raise ArgumentError, 
        "InScopeExtensionParameter are only comparable to other parameter constraints" unless other.is_a?(InScopeExtensionParameter)
      @param_db.name <=> other.param_db.name
    end
  end # class InScopeExtensionParameter

  ############################################
  # Routines using InScopeExtensionParameter #
  ############################################

  # @return [Array<InScopeExtensionParameter>] List of parameters specified by any extension in CRD.
  # These are always IN SCOPE by definition (since they are listed in the CRD).
  # Can have multiple array entries with the same parameter name since multiple extensions may define
  # the same parameter.
  def all_in_scope_ext_params
    return @all_in_scope_ext_params unless @all_in_scope_ext_params.nil?

    @all_in_scope_ext_params = []

    @data["extensions"].each do |ext_crd| 
      # Find Extension object from database
      ext_db = @arch_def.extension(ext_crd["name"])
      raise "Cannot find extension named #{ext_crd["name"]}" if ext_db.nil?

      ext_crd["parameters"]&.each do |param_name, param_data|
        param_db = ext_db.params.find { |p| p.name == param_name }
        raise "There is no param '#{param_name}' in extension '#{ext_crd["name"]}" if param_db.nil?

        next unless ext_db.versions.any? do |ver|
          Gem::Requirement.new(ext_crd["version"]).satisfied_by?(Gem::Version.new(ver["version"])) &&
            param_db.defined_in_extension_version?(ver["version"])
        end

        @all_in_scope_ext_params << 
          InScopeExtensionParameter.new(param_db, param_data["schema"], param_data["note"])
      end
    end
    @all_in_scope_ext_params
  end

  # @return [Array<InScopeExtensionParameter>] List of extension parameters from CRD for given extension.
  # These are always IN SCOPE by definition (since they are listed in the CRD).
  def in_scope_ext_params(ext_req)
    raise ArgumentError, "Expecting ExtensionRequirement" unless ext_req.is_a?(ExtensionRequirement)

    ext_params = []    # Local variable, no caching

    # Get extension information from CRD YAML for passed in extension requirement.
    ext_crd = @data["extensions"].find {|ext| ext["name"] == ext_req.name}
    raise "Cannot find extension named #{ext_req.name}" if ext_crd.nil?
    
    # Find Extension object from database
    ext_db = @arch_def.extension(ext_crd["name"])
    raise "Cannot find extension named #{ext_crd["name"]}" if ext_db.nil?

    # Loop through an extension's parameter constraints (hash) from the CRD.
    # Note that "&" is the Ruby safe navigation operator (i.e., skip do loop if nil).
    ext_crd["parameters"]&.each do |param_name, param_data|
        # Find ExtensionParameter object from database
        ext_param_db = ext_db.params.find { |p| p.name == param_name }
        raise "There is no param '#{param_name}' in extension '#{ext_crd["name"]}" if ext_param_db.nil?

        next unless ext_db.versions.any? do |ver|
          Gem::Requirement.new(ext_crd["version"]).satisfied_by?(Gem::Version.new(ver["version"])) &&
            ext_param_db.defined_in_extension_version?(ver["version"])
        end

        ext_params << 
          InScopeExtensionParameter.new(ext_param_db, param_data["schema"], param_data["note"])
    end

    ext_params
  end

  # @return [Array<ExtensionParameter>] Parameters out of scope across all in scope extensions (those listed in the CRD).
  def all_out_of_scope_params
    return @all_out_of_scope_params unless @all_out_of_scope_params.nil?
 
    @all_out_of_scope_params = []
    in_scope_ext_reqs.each do |ext_req|
      ext_db = @arch_def.extension(ext_req.name)
      ext_db.params.each do |param_db|
        next if all_in_scope_ext_params.any? { |c| c.param_db.name == param_db.name }

        next unless ext_db.versions.any? do |ver|
          Gem::Requirement.new(ext_req.version_requirement).satisfied_by?(Gem::Version.new(ver["version"])) &&
            param_db.defined_in_extension_version?(ver["version"])
        end

        @all_out_of_scope_params << param_db
      end
    end
    @all_out_of_scope_params
  end

  # @return [Array<ExtensionParameter>] Parameters that are out of scope for named extension.
  def out_of_scope_params(ext_name)
    all_out_of_scope_params.select{|param_db| param_db.exts.any? {|ext| ext.name == ext_name} } 
  end

  # @return [Array<Extension>]
  # All the in-scope extensions (those in the CRD) that define this parameter in the database 
  # and the parameter is in-scope (listed in that extension's list of parameters in the CRD).
  def all_in_scope_exts_with_param(param_db)
    raise ArgumentError, "Expecting ExtensionParameter" unless param_db.is_a?(ExtensionParameter)

    exts = []

    # Interate through all the extensions in the architecture database that define this parameter.
    param_db.exts.each do |ext_in_db|
      found = false

      in_scope_extensions.each do |in_scope_ext|
        if ext_in_db.name == in_scope_ext.name
          found = true
          next
        end
      end

      if found
          # Only add extensions that exist in this CRD.
          exts << ext_in_db
      end
    end

    # Return intersection of extension names
    exts
  end

  # @return [Array<Extension>]
  # All the in-scope extensions (those in the CRD) that define this parameter in the database 
  # but the parameter is out-of-scope (not listed in that extension's list of parameters in the CRD).
  def all_in_scope_exts_without_param(param_db)
    raise ArgumentError, "Expecting ExtensionParameter" unless param_db.is_a?(ExtensionParameter)

    exts = []   # Local variable, no caching

    # Interate through all the extensions in the architecture database that define this parameter.
    param_db.exts.each do |ext_in_db|
      found = false

      in_scope_extensions.each do |in_scope_ext|
        if ext_in_db.name == in_scope_ext.name
          found = true
          next
        end
      end

      if found
          # Only add extensions that are in-scope (i.e., exist in this CRD).
          exts << ext_in_db
      end
    end

    # Return intersection of extension names
    exts
  end

  #####################
  # Requirement Class #
  #####################

  # Holds extra requirements not associated with extensions or their parameters.
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

  ##########################
  # RequirementGroup Class #
  ##########################

  # Holds a group of Requirement objects to provide a one-level group.
  # Can't nest RequirementGroup objects to make multi-level group.
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
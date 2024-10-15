# frozen_string_literal: true

require_relative "obj"

# representation of a specific profile for a Family, Mode, and Base
class Profile < ArchDefObject
  # @return [ArchDef] The defining ArchDef
  attr_reader :arch_def

  def initialize(data, arch_def)
    super(data)
    @arch_def = arch_def
  end

  def family = arch_def.profile_family(@data["family"])

  # @return [Profile] Profile that this profile inherits from
  # @return [nil] if this profile has no parent
  def inherits_from = arch_def.profile(@data["inherits"])

  # @return ["M", "S", "U", "VS", "VU"] Privilege mode for the profile
  def mode
    if @data["mode"].nil?
      raise "No mode specified and no inheritance for profile '#{name}'" if inherits_from.nil?
      inherits_from.mode
    else
      @data["mode"]
    end
  end

  # @return [32, 64] The base XLEN for the profile
  def base
    if @data["base"].nil?
      raise "No base specified and no inheritance for profile '#{name}'" if inherits_from.nil?

      inherits_from.base
    else
      @data["base"]
    end
  end

  # @return [Gem::Version] Semantic version of the Profile within the ProfileLineage
  def version = Gem::Version.new(@data["version"])

  # @return [String] The marketing name of the Profile
  def marketing_name = @data["marketing_name"]

  # @return [String] State of the profile spec
  def state = @data["state"]

  # @return [Date] Ratification date
  # @return [nil] if the profile is not ratified
  def ratification_date
    return nil if @data["ratification_date"].nil?

    Date.parse(@data["ratification_date"])
  end

  # @return [Array<Person>] Contributors to the profile spec
  def contributors
    @data["contributors"].map { |data| Person.new(data) }
  end

  # @return [String] Given an extension +ext_name+, return the presence
  def extension_presence(ext_name)
    if mandatory?(ext_name)
      req = mandatory_extension_requirements.find do |req|
        req.name == ext_name
      end.version_requirement
      "Mandatory, #{req}"
    elsif optional?(ext_name)
      req = optional_extension_requirements.find do |req|
        req.name == ext_name
      end.version_requirement
      "Optional, #{req}"
    else
      "-"
    end
  end

  # @return [String] The note associated with extension +ext_name+
  # @return [nil] if there is no note for +ext_name+
  def extension_note(ext_name)
    ext = @data["extensions"].find { |e| e["name"] == ext_name }
    return ext["note"] unless ext.nil?
  end

  # @return [Array<ExtensionRequirement>] List of mandatory extensions for the profile
  def mandatory_extension_requirements
    return @mandatory_ext_reqs unless @mandatory_ext_reqs.nil?

    @mandatory_ext_reqs = []
    @mandatory_ext_reqs += inherits_from.mandatory_extension_requirements unless inherits_from.nil?

    # we need to remove anything that was changed from inheritance
    unless @data["extensions"].nil?
      @mandatory_ext_reqs.delete_if { |ext_req|
        @data["extensions"]&.any? { |opt| opt["name"] == ext_req.name }
      }

      @data["extensions"]&.each do |ext_req|
        if ext_req["presence"] == "mandatory"
          @mandatory_ext_reqs << ExtensionRequirement.new(ext_req["name"], ext_req["version"], presence: "mandatory")
        end
      end
    end

    @mandatory_ext_reqs
  end

  # @return [Array<Extension>] List of mandatory extensions
  def mandatory_extensions
    mandatory_extension_requirements.map do |e|
      obj = arch_def.extension(e.name)

      # @todo: change this to raise once all the profile extensions
      #        are defined
      warn "Extension #{e.name} is not defined" if obj.nil?

      obj
    end.reject(&:nil?)
  end

  # @return [Boolean] whether or not +ext_name+ is mandatory in the prfoile
  def mandatory?(ext_name)
    mandatory_extension_requirements.any? { |ext| ext.name == ext_name }
  end

  # @return [Array<ExtensionRequirement>] List of optional extensions for the profile
  def optional_extension_requirements
    return @optional_ext_reqs unless @optional_ext_reqs.nil?

    @optional_ext_reqs = []
    @optional_ext_reqs += inherits_from.optional_extension_requirements unless inherits_from.nil?

    # we need to remove anything that was changed from inheritance
    unless @data["extensions"].nil?
      @optional_ext_reqs.delete_if { |ext_req|
        @data["extensions"]&.any? { |opt| opt["name"] == ext_req.name }
      }

      @data["extensions"]&.each do |ext_ver|
        if ext_ver["presence"] == "optional"
          @optional_ext_reqs << ExtensionRequirement.new(ext_ver["name"], ext_ver["version"], presence: "optional")
        end
      end
    end

    @optional_ext_reqs
  end

  # @return [Array<Extension>] List of optional extensions
  def optional_extensions
    optional_extension_requirements.map do |e|
      obj = arch_def.extension(e.name)

      # @todo: change this to raise once all the profile extensions
      #        are defined
      warn "Extension #{e.name} is not defined" if obj.nil?

      obj
    end.reject(&:nil?)
  end

  # @return [Boolean] whether or not +ext_name+ is optional in the prfoile
  def optional?(ext_name)
    optional_extension_requirements.any? { |ext| ext.name == ext_name }
  end

end

# A profile family is a set of profiles that share a common goal or lineage
#
# For example, the RVA family is a set of profiles for application processors
class ProfileFamily < ArchDefObject
  # @return [ArchDef] The defining ArchDef
  attr_reader :arch_def

  # @return [String] Name of the family
  def name = @data["name"]

  # @return [String] Name of the family
  def marketing_name = @data["marketing_name"]

  # @param arch_def [ArchDef] Architecture spec
  # @param profile_family_data [Hash<String, Object>] The data from YAML
  def initialize(profile_family_data, arch_def)
    super(profile_family_data)
    @arch_def = arch_def
  end

  def description = @data["description"]

  # @return [Array<String>] Privilege modes that this family defines profiles for
  def modes = @data["modes"]

  # @return [Array<Profile>] Defined profiles in this family
  def profiles
    return @profiles unless @profiles.nil?

    @profiles = arch_def.profiles.select { |profile| profile.data["family"] == name }
  end

  # @return [Date] The most recent ratification date of any profile in the family
  # @return [nil] if there are no ratified profiles in the family
  def ratification_date
    date = nil
    profiles.each do |profile|
      date = profile.ratification_date if !profile.ratification_date.nil? && profile.ratification_date < date
    end
    date
  end

  # @return [Array<Extension>] List of all extensions referenced by the family
  def referenced_extensions
    return @referenced_extensions unless @referenced_extensions.nil?

    @referenced_extensions = []
    profiles.each do |profile|
      @referenced_extensions += profile.mandatory_extensions
      @referenced_extensions += profile.optional_extensions
    end

    @referenced_extensions.uniq!(&:name)
  end

  # @return [Company] Company that created the profile
  def company = Company.new(@data["company"])

  # @return [License] Documentation license
  def doc_license
    License.new(@data["doc_license"])
  end
end

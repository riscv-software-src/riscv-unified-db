# frozen_string_literal: true

require_relative "obj"

# representation of a specific profile for a Family, Mode, and Base
class Profile < ArchDefObject
  # @return [ProfileFamily] The family this profile belongs to
  attr_reader :family

  # @return [ArchDef] The defining ArchDef
  def arch_def = @family.arch_def

  # @return ["M", "S", "U", "VS", "VU"] Privilege mode for the profile
  def mode = @data["mode"]

  # @return [32, 64] The base XLEN for the profile
  def base = @data["base"]

  # @return [Gem::Version] Semantic version of the Profile within the ProfileLineage
  def version = Gem::Version.new(@data["version"])

  # @return ["development", "ratified"] The current status of the definition
  def status = @data["status"]

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

  def initialize(profile_version_data, lineage)
    super(profile_version_data)
    @lineage = lineage
  end

  # @return [Profile] The Profile this one inherits
  # @return [nil] if this profile does not inherit from another
  def parent
    return @parent unless @parent.nil?

    if @data["inherits"].nil?
      nil
    else
      @parent = arch_def.profile(
        @data["inherits"]["name"],
        @data["inherits"]["version"]
      )
    end
  end

  # @return [Array<ExtensionRequirement>] List of mandatory extensions for the profile
  def mandatory_extension_requirements
    return @mandatory_extensions unless @mandatory_extensions.nil?

    @mandatory_extensions = []
    @mandatory_extensions += parent.mandatory_extension_requirements unless parent.nil?

    # we need to remove anything that was changed from inheritance
    unless @data["extensions"].nil?
      @mandatory_extensions.delete_if { |ext_req|
        @data["extensions"]["optional"]&.any? { |opt| opt["name"] == ext_req.name } ||
          @data["extensions"]["removed"]&.any? { |opt| opt["name"] == ext_req.name } ||
          @data["extensions"]["mandatory"]&.any? { |opt| opt["name"] == ext_req.name }
      }

      @data["extensions"]["mandatory"]&.each do |ext_ver|
        @mandatory_extensions << ExtensionRequirement.new(ext_ver["name"], ext_ver["version"])
      end
    end

    @mandatory_extensions
  end

  # @return [Array<Extension>] List of mandatory extensions
  def mandatory_extensions = mandatory_extension_requirements.map { |e| arch_def.extension(e.name) }

  # @return [Array<ExtensionRequirement>] List of optional extensions for the profile
  def optional_extension_requirements
    return @optional_extensions unless @optional_extensions.nil?

    @optional_extensions = []
    @optional_extensions += parent.optional_extension_requirements unless parent.nil?

    # we need to remove anything that was changed from inheritance
    unless @data["extensions"].nil?
      @optional_extensions.delete_if { |ext_req|
        @data["extensions"]["optional"]&.any? { |opt| opt["name"] == ext_req.name } ||
          @data["extensions"]["removed"]&.any? { |opt| opt["name"] == ext_req.name } ||
          @data["extensions"]["mandatory"]&.any? { |opt| opt["name"] == ext_req.name }
      }

      @data["extensions"]["optional"]&.each do |ext_ver|
        @optional_extensions << ExtensionRequirement.new(ext_ver["name"], ext_ver["version"])
      end
    end

    @optional_extensions
  end
end

# A profile family is a set of profiles that share a common goal or lineage
#
# For example, the RVA family is a set of profiles for application processors
class ProfileFamily < ArchDefObject
  # @return [ArchDef] The defining ArchDef
  attr_reader :arch_def

  # @return [String] Name of the family
  def name = @data["family"]["name"]

  # @return [String] Name of the family
  def marketing_name = @data["family"]["marketing_name"]

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

    @profiles = []
    @data["profiles"].each do |profile_data|
      @profiles << Profile.new(profile_data, self)
    end
    @profiles
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

  # @return [Company] Company that created the profile
  def company = Company.new(@data["family"]["company"])

  # @return [License] Documentation license
  def doc_license
    License.new(@data["family"]["doc_license"])
  end
end

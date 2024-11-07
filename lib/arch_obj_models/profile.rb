# frozen_string_literal: true

require_relative "portfolio"

# A profile family is a set of profiles that share a common goal or lineage
#
# For example, the RVA family is a set of profiles for application processors
class ProfileFamily < PortfolioFamily
  # @param data [Hash<String, Object>] The data from YAML
  # @param arch_def [ArchDef] Architecture spec
  def initialize(data, arch_def)
    super(data, arch_def)
  end

  # @return [String] Name of the family
  def marketing_name = @data["marketing_name"]

  # @return [Array<String>] Privilege modes that this family defines profiles for
  def modes = @data["modes"]

  # @return [Company] Company that created the profile
  def company = Company.new(@data["company"])

  # @return [License] Documentation license
  def doc_license
    License.new(@data["doc_license"])
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

  # @return [Array<Profile>] Defined profiles in this family
  def profiles
    return @profiles unless @profiles.nil?

    @profiles = arch_def.profiles.select { |profile| profile.data["family"] == name }

    @profiles
  end

  # @return [Array<Extension>] List of all extensions referenced by the family
  def referenced_extensions
    return @referenced_extensions unless @referenced_extensions.nil?

    @referenced_extensions = []
    profiles.each do |profile|
      @referenced_extensions += profile.in_scope_extensions
    end

    @referenced_extensions.uniq!(&:name)

    @referenced_extensions
  end

end

# representation of a specific profile for a Family, Mode, and Base
class Profile < Portfolio
  def initialize(data, arch_def)
    super(data, arch_def)
  end

  # @return [String] The marketing name of the Profile
  def marketing_name = @data["marketing_name"]

  # @return [String] State of the profile spec
  def state = @data["state"]

  # @return [ProfileFamily] The profile family specified by this profile.
  def family
    family = @arch_def.profile_family(@data["family"])
    raise "No profile family named '#{@data["family"]}'" if family.nil?

    family
  end

  # @return ["M", "S", "U", "VS", "VU"] Privilege mode for the profile
  def mode
    @data["mode"]
  end

  # @return [32, 64] The base XLEN for the profile
  def base
    @data["base"]
  end

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
end

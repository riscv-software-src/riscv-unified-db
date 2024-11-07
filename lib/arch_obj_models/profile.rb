# frozen_string_literal: true

require_relative "portfolio"

# A profile class consists of a number of releases each with set of profiles.
# For example, the RVA profile class has releases such as RVA20, RVA22, RVA23
# that each include an unprivileged profile (e.g., RVA20U64) and one more
# privileged profiles (e.g., RVA20S64).
class ProfileClass < PortfolioClass
  # @param data [Hash<String, Object>] The data from YAML
  # @param arch_def [ArchDef] Architecture spec
  def initialize(data, arch_def)
    super(data, arch_def)
  end

  # @return [String] Name of the class
  def marketing_name = @data["marketing_name"]

  # @return [Company] Company that created the profile
  def company = Company.new(@data["company"])

  # @return [License] Documentation license
  def doc_license
    License.new(@data["doc_license"])
  end

  # @return [Array<ProfileRelease>] Defined profile releases in this profile class
  def profile_releases
    return @profile_releases unless @profile_releases.nil?

    @profile_releases = @arch_def.profile_releases.select { |pr| pr.profile_class.name == name }

    @profile_releases
  end

  # @return [Array<Profile>] All profiles in this profile class (for all releases).
  def profiles
    return @profiles unless @profiles.nil?

    puts " 2a: profiles for class #{name} called."

    @profiles = []
    @arch_def.profiles.each do |profile|
      if profile.profile_class.name == name
        @profiles << profile
      end
    end

    @profiles
  end

  # @return [Array<Extension>] List of all extensions referenced by the class
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

# A profile release consists of a number of releases each with one or more profiles.
# For example, the RVA20 profile release has profiles RVA20U64 and RVA20S64.
# Note there is no Portfolio* base class for a ProfileRelease to inherit from since there is no
# equivalent to a ProfileRelease in a Certificate so no potential for a shared base class.
class ProfileRelease < ArchDefObject
  # @param data [Hash<String, Object>] The data from YAML
  # @param arch_def [ArchDef] Architecture spec
  def initialize(data, arch_def)
    super(data)
    @arch_def = arch_def
  end

  def marketing_name = @data["marketing_name"]
  def introduction = @data["introduction"]
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

  # @return [ProfileClass] Profile Class that this ProfileRelease belongs to
  def profile_class
    profile_class = @arch_def.profile_class(@data["class"])
    raise "No profile class named '#{@data["class"]}'" if profile_class.nil?

    profile_class
  end

  # @return [Array<Profile>] All profiles in this profile release
  def profiles
    return @profiles unless @profiles.nil?

    @profiles = []
    @arch_def.profiles.each do |profile|
      if profile.profile_release.name == name
        @profiles << profile
      end
    end
    @profiles
  end

  # @return [Array<Extension>] List of all extensions referenced by the release
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

# Representation of a specific profile in a profile release.
class Profile < PortfolioInstance
  def initialize(data, arch_def)
    super(data, arch_def)
  end

  # @return [String] The marketing name of the Profile
  def introduction = @data["introduction"]
  def marketing_name = @data["marketing_name"]

  # @return [ProfileRelease] The profile release this profile belongs to
  def profile_release
    profile_release = @arch_def.profile_release(@data["release"])
    raise "No profile release named '#{@data["release"]}'" if profile_release.nil?

    profile_release
  end

  # @return [ProfileClass] The profile class this profile belongs to
  def profile_class = profile_release.profile_class

  # @return ["M", "S", "U", "VS", "VU"] Privilege mode for the profile
  def mode
    @data["mode"]
  end

  # @return [32, 64] The base XLEN for the profile
  def base
    @data["base"]
  end

  # @return [Array<Extension>] List of all extensions referenced by the profile
  def referenced_extensions = in_scope_extensions
end
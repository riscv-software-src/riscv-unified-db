# typed: false
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require_relative "portfolio"

module Udb
# A profile class consists of a number of releases each with set of profiles.
# For example, the RVA profile family has releases such as RVA20, RVA22, RVA23
# that each include an unprivileged profile (e.g., RVA20U64) and one more
# privileged profiles (e.g., RVA20S64).
  class ProfileFamily < PortfolioClass
    # @return [String] Naming scheme for profile family
    def naming_scheme = @data["naming_scheme"]

    # @return [String] Name of the class
    def marketing_name = @data["marketing_name"]

    # @return [Company] Company that created the profile
    def company = Company.new(@data["company"])

    # @return [License] Documentation license
    def doc_license
      License.new(@data["doc_license"])
    end

    # @return [Array<ProfileRelease>] Defined profile releases in this profile family
    def profile_releases
      return @profile_releases unless @profile_releases.nil?

      @profile_releases = @arch.profile_releases.select { |pr| pr.profile_family.name == name }

      @profile_releases
    end

    # @return [Array<ProfileRelease>] Defined profile releases of this processor class
    def profile_releases_matching_processor_kind
      return @profile_releases_matching_processor_kind unless @profile_releases_matching_processor_kind.nil?

      matching_classes = portfolio_classes_matching_portfolio_kind_and_processor_kind

      # Look for all profile releases that are from any of the matching classes.
      @profile_releases_matching_processor_kind = @arch.profile_releases.select { |pr|
        matching_classes.any? { |matching_class| matching_class.name == pr.profile_family.name }
      }

      @profile_releases_matching_processor_kind
    end

    # @return [Array<Profile>] All profiles in this profile family (for all releases).
    def profiles
      return @profiles unless @profiles.nil?

      @profiles = @arch.profiles.select { |profile| profile.profile_family.name == name }
    end

    # @return [Array<Profile>] All profiles in database matching my processor kind
    def profiles_matching_processor_kind
      return @profiles_matching_processor_kind unless @profiles_matching_processor_kind.nil?

      @profiles_matching_processor_kind = @arch.profiles.select { |profile| profile.profile_family.processor_kind == processor_kind }
    end

    # @return [Array<Extension>] Sorted list of all mandatory or optional extensions across the profile releases belonging
    #                            to the profile family
    def in_scope_extensions
      return @in_scope_extensions unless @in_scope_extensions.nil?

      @in_scope_extensions = []
      profiles.each do |profile|
        @in_scope_extensions += profile.in_scope_extensions
      end

      @in_scope_extensions = @in_scope_extensions.uniq(&:name).sort_by(&:name)
    end

    # @return [Array<Extension>] Sorted list of all potential extensions with my processor kind
    def in_scope_extensions_matching_processor_kind
      return @in_scope_extensions_matching_processor_kind unless @in_scope_extensions_matching_processor_kind.nil?

      @in_scope_extensions_matching_processor_kind = []
      profiles_matching_processor_kind.each do |profile|
        @in_scope_extensions_matching_processor_kind += profile.in_scope_extensions
      end

      @in_scope_extensions_matching_processor_kind =
        @in_scope_extensions_matching_processor_kind.uniq(&:name).sort_by(&:name)
    end
  end

# A profile release consists of a number of releases each with one or more profiles.
# For example, the RVA20 profile release has profiles RVA20U64 and RVA20S64.
# Note there is no Portfolio base class for a ProfileRelease to inherit from since there is no
# equivalent to a ProfileRelease in a Certificate so no potential for a shared base class.
  class ProfileRelease < TopLevelDatabaseObject
    def marketing_name = @data["marketing_name"]

    # @return [String] Small enough (~1 paragraph) to be suitable immediately after a higher-level heading.
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
      return nil if @data["contributors"].nil?

      @data["contributors"].map { |data| Person.new(data) }
    end

    # @return [ProfileFamily] Profile Family that this ProfileRelease belongs to
    def profile_family
      profile_family = @arch.ref(@data["family"]["$ref"])
      raise "No profile family named '#{@data["family"]}'" if profile_family.nil?

      profile_family
    end

    # @return [Array<Profile>] All profiles in this profile release
    def profiles
      return @profiles unless @profiles.nil?

      @profiles = []
      @data["profiles"].each do |profile_ref|
        @profiles << @arch.ref(profile_ref["$ref"])
      end
      @profiles
    end

    # @return [PortfolioGroup] All portfolios in this profile release
    def portfolio_grp
      return @portfolio_grp unless @portfolio_grp.nil?

      @portfolio_grp = PortfolioGroup.new(marketing_name, profiles)
    end

    #####################################
    # METHODS HANDLED BY PortfolioGroup #
    #####################################

    # @return [Array<Extension>] List of all mandatory or optional extensions referenced by this profile release.
    def in_scope_extensions = portfolio_grp.in_scope_extensions

    # @return [String] Given an extension +ext_name+, return the presence as a string.
    #                  Returns the greatest presence string across all profiles in the release.
    #                  If the extension name isn't found in the release, return "-".
    def extension_presence(ext_name) = portfolio_grp.extension_presence(ext_name)

    # @return [String] Given an instruction +inst_name+, return the presence as a string.
    #                  Returns the greatest presence string across all profiles in the release.
    #                  If the instruction name isn't found in the release, return "-".
    def instruction_presence(inst_name) = portfolio_grp.instruction_presence(inst_name)

    # @return [String] Given a CSR +csr_name+, return the presence as a string.
    #                  Returns the greatest presence string across all profiles in the release.
    #                  If the CSR name isn't found in the release, return "-".
    def csr_presence(csr_name) = portfolio_grp.csr_presence(csr_name)
  end

# Representation of a specific profile in a profile release.
  class Profile < Portfolio
    # @return [String] The marketing name of the Profile
    def marketing_name = @data["marketing_name"]

    # @return [ProfileRelease] The profile release this profile belongs to
    def profile_release
      profile_release = @arch.ref(@data["release"]["$ref"])
      raise "No profile release named '#{@data["release"]["$ref"]}'" if profile_release.nil?

      profile_release
    end

    # @return [ProfileFamily] The profile family this profile belongs to
    def profile_family = profile_release.profile_family

    # @return ["M", "S", "U", "VS", "VU"] Privilege mode for the profile
    def mode
      @data["mode"]
    end

    # @return [32, 64] The base XLEN for the profile
    def base
      @data["base"]
    end

    # Too complicated to put in profile ERB template.
    # @param presence_type [String]
    # @param heading_level [Integer]
    # @return [Array<String>] Each array entry is a line
    def extensions_to_adoc(presence_type, heading_level)
      ret = []

      presence_ext_reqs = in_scope_ext_reqs(presence_type)
      plural = (presence_ext_reqs.size == 1) ? "" : "s"
      ret << "The #{marketing_name} Profile has #{presence_ext_reqs.size} #{presence_type} extension#{plural}."
      ret << ""

      unless presence_ext_reqs.empty?
        if (presence_type == Presence.optional) && uses_optional_types?
          # Iterate through each optional type. Use object version (not string) to get
          # precise comparisons (i.e., presence string and optional type string).
          Presence.optional_types_obj.each do |optional_type_obj|
            optional_type_ext_reqs = in_scope_ext_reqs(optional_type_obj)
            unless optional_type_ext_reqs.empty?
              ret << ""
              ret << ("=" * heading_level) + " #{optional_type_obj.optional_type.capitalize} Options"
              optional_type_ext_reqs.each do |ext_req|
                ret << ext_req_to_adoc(ext_req)
                ret << ext_note_to_adoc(ext_req.name)
              end # each ext_req
            end # unless optional_type_ext_reqs empty

            # Add extra notes that just belong to just this optional type.
            extra_notes_for_presence(optional_type_obj)&.each do |extra_note|
              ret << "NOTE: #{extra_note.text}"
              ret << ""
            end # each extra_note
          end # each optional_type_obj
        else # don't bother with optional types
          presence_ext_reqs.each do |ext_req|
            ret << ext_req_to_adoc(ext_req)
            ret << ext_note_to_adoc(ext_req.name)
          end # each ext_req
        end # checking for optional types
      end # presence_ext_reqs isn't empty

      # Add extra notes that just belong to this presence.
      # Use object version (not string) of presence to avoid adding extra notes
      # already added for optional types if they are in use.
      extra_notes_for_presence(Presence.new(presence_type))&.each do |extra_note|
        ret << "NOTE: #{extra_note.text}"
        ret << ""
      end # each extra_note

      ret
    end

    # @param ext_req [ExtensionRequirement]
    # @return [Array<String>]
    def ext_req_to_adoc(ext_req)
      ret = []

      ext = arch.extension(ext_req.name)
      ret << "* *#{ext_req.name}* " + (ext.nil? ? "" : ext.long_name)
      ret << "+"
      ret << "Version #{ext_req.requirement_specs_to_s_pretty}"

      ret
    end

    # @param ext_name [String]
    # @return [Array<String>]
    def ext_note_to_adoc(ext_name)
      ret = []

      unless extension_note(ext_name).nil?
        ret << "+"
        ret << "[NOTE]"
        ret << "--"
        ret << extension_note(ext_name)
        ret << "--"
      end

      ret
    end
  end
end

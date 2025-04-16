# Classes for Portfolios which form a common base class for profiles and certificates.
# A "Portfolio" is a named & versioned grouping of extensions (each with a name and version).
# Each Portfolio is a member of a Portfolio Class:
#   RVA20U64 and MC100 are examples of portfolios
#   RVA and MC are examples of portfolio classes
#
# Many classes inherit from the DatabaseObject class. This provides facilities for accessing the contents of a
# Portfolio Class YAML or Portfolio Model YAML file via the "data" member (hash holding related YAML file contents).
#
# A variable name with a "_data" suffix indicates it is the raw hash data from the portfolio YAML file.

require "tmpdir"

require_relative "obj"
require_relative "schema"

##################
# PortfolioClass #
##################

# Holds information from Portfolio class YAML file (certificate class or profile class).
# The inherited "data" member is the database of extensions, instructions, CSRs, etc.
class PortfolioClass < DatabaseObject
  # @return [String] What kind of processor portfolio is this?
  def processor_kind = @data["processor_kind"]

  # @return [String] Small enough (~1 paragraph) to be suitable immediately after a higher-level heading.
  def introduction = @data["introduction"]

  # @return [String] Large enough to need its own heading (generally one level deeper than the "introduction").
  def description = @data["description"]

  # Returns true if other is the same class (not a derived class) and has the same name.
  def eql?(other)
    other.instance_of?(self.class) && other.name == name
  end

  # @return [Array<PortfolioClass] All portfolio classes that have the same portfolio kind and same processor kind.
  def portfolio_classes_matching_portfolio_kind_and_processor_kind
    arch.portfolio_classes.select {|portfolio_class|
      (portfolio_class.kind == kind) && (portfolio_class.processor_kind == processor_kind)}
  end
end

#############
# Portfolio #
#############

# Holds information about a Portfolio (certificate or profile).
# The inherited "data" member is the database of extensions, instructions, CSRs, etc.
class Portfolio < DatabaseObject
  # @param obj_yaml [Hash<String, Object>] Contains contents of Portfolio yaml file (put in @data)
  # @param data_path [String] Path to yaml file
  # @param arch [Architecture] Entire database of RISC-V architecture standards
  def initialize(obj_yaml, yaml_path, arch: nil)
    super # Calls parent class with same args I got
  end

  # @return [String] Small enough (~1 paragraph) to be suitable immediately after a higher-level heading.
  def introduction = @data["introduction"]

  # @return [String] Large enough to need its own heading (generally one level deeper than the "introduction").
  def description = @data["description"]

  # @return [Gem::Version] Semantic version of the Portfolio
  def version = Gem::Version.new(@data["version"])

  # @return [ExtensionPresence] Given an extension +ext_name+, return the presence.
  #                             If the extension name isn't found in the portfolio, return nil.
  def extension_presence_obj(ext_name)
    # Get extension information from YAML for passed in extension name.
    ext_data = @data["extensions"][ext_name]

    ext_data.nil? ? nil : ExtensionPresence.new(ext_data["presence"])
  end

  # @return [String] Given an extension +ext_name+, return the presence as a string.
  #                  If the extension name isn't found in the portfolio, return "-".
  def extension_presence(ext_name)
    ext_presence_obj = extension_presence_obj(ext_name)

    ext_presence_obj.nil? ? "-" : ext_presence_obj.to_s
  end

  # Returns the greatest presence string for each of the specified versions.
  # @param ext_name [String]
  # @param ext_versions [Array<ExtensionVersion>]
  # @return [Array<String>]
  def version_greatest_presence(ext_name, ext_versions)
    presences = []

    # See if any extension requirement in this profile lists this version as either mandatory or optional.
    ext_versions.map do |v|
      greatest_presence = nil

      in_scope_ext_reqs.each do |ext_req|
        if ext_req.satisfied_by?(v)
          presence = extension_presence_obj(ext_name)

          unless presence.nil?
            if greatest_presence.nil?
              greatest_presence = presence
            elsif presence > greatest_presence
              greatest_presence = presence
            end
          end
        end
      end

      presences << (greatest_presence.nil? ? "-" : greatest_presence.to_s_concise)
    end

    presences
  end

  # @return [String] The note associated with extension +ext_name+
  # @return [nil] if there is no note for +ext_name+
  def extension_note(ext_name)
    # Get extension information from YAML for passed in extension name.
    ext_data = @data["extensions"][ext_name]
    raise "Cannot find extension named #{ext_name}" if ext_data.nil?

    return ext_data["note"] unless ext_data.nil?
  end

  def mandatory_ext_reqs = in_scope_ext_reqs(ExtensionPresence.mandatory)
  def optional_ext_reqs = in_scope_ext_reqs(ExtensionPresence.optional)
  def optional_type_ext_reqs = in_scope_ext_reqs(ExtensionPresence.optional)

  # @param desired_presence [String, Hash, ExtensionPresence]
  # @return [Array<ExtensionRequirements>] - # Extensions with their portfolio information.
  # If desired_presence is provided, only returns extensions with that presence.
  # If desired_presence is a String, only the presence portion of an ExtensionPresence is compared.
  def in_scope_ext_reqs(desired_presence = nil)
    in_scope_ext_reqs = []

    # Convert desired_present argument to ExtensionPresence object if not nil.
    desired_presence_converted =
      desired_presence.nil?                     ? nil :
      desired_presence.is_a?(String)            ? desired_presence :
      desired_presence.is_a?(ExtensionPresence) ? desired_presence :
      ExtensionPresence.new(desired_presence)

    missing_ext = false

    @data["extensions"]&.each do |ext_name, ext_data|
      next if ext_name[0] == "$"

      # Does extension even exist?
      # If not, don't raise an error right away so we can find all of the missing extensions and report them all.
      ext = arch.extension(ext_name)
      if ext.nil?
        puts "Extension #{ext_name} for #{name} not found in database"
        missing_ext = true
      else
        actual_presence = ext_data["presence"]    # Could be a String or Hash
        raise "Missing extension presence for extension #{ext_name}" if actual_presence.nil?

        # Convert presence String or Hash to object.
        actual_presence_obj = ExtensionPresence.new(actual_presence)

        match =
          if desired_presence.nil?
            true # Always match
          else
            actual_presence_obj == desired_presence_converted
          end

        if match
          in_scope_ext_reqs <<
            if ext_data.key?("version")
              ExtensionRequirement.new(
                ext_name, ext_data["version"], arch: @arch,
                presence: actual_presence_obj, note: ext_data["note"], req_id: "REQ-EXT-#{ext_name}")
            else
              ExtensionRequirement.new(
                ext_name, arch: @arch,
                presence: actual_presence_obj, note: ext_data["note"], req_id: "REQ-EXT-#{ext_name}")
            end
        end
      end
    end

    raise "One or more extensions referenced by #{name} missing in database" if missing_ext

    in_scope_ext_reqs
  end

  # @return [Array<Instruction>] Sorted list of all instructions associated with extensions listed as
  #                              mandatory or optional in portfolio. Uses minimum version of
  #                              extension version that meets extension requirement specified in portfolio.
  def in_scope_instructions
    return @in_scope_instructions unless @in_scope_instructions.nil?

    # XXX
    # @in_scope_instructions = in_scope_ext_reqs.map { |ext_req| ext_req.instructions }.flatten.uniq.sort
    @in_scope_instructions = in_scope_extensions.map { |ext| ext.instructions }.flatten.uniq.sort
  end

  # @return [Array<Extension>] List of all extensions listed in portfolio.
  def in_scope_extensions
    return @in_scope_extensions unless @in_scope_extensions.nil?

    @in_scope_extensions = in_scope_ext_reqs.map do |ext_req|
      arch.extension(ext_req.name)
    end.reject(&:nil?)  # Filter out extensions that don't exist yet.

    @in_scope_extensions
  end

  # @return [Boolean] Does the profile differentiate between different types of optional.
  def uses_optional_types?
    return @uses_optional_types unless @uses_optional_types.nil?

    @uses_optional_types = false

    # Iterate through different kinds of optional using the "object" version (not the string version).
    ExtensionPresence.optional_types_obj.each do |optional_type_obj|
      # See if any extension reqs have this type of optional.
      unless in_scope_ext_reqs(optional_type_obj).empty?
        @uses_optional_types = true
      end
    end

    @uses_optional_types
  end

  # Called by rakefile when generating a portfolio.
  # Creates an in-memory data structure used by all portfolio routines that access a cfg_arch.
  #
  # @return [ConfiguredArchitecture] A partially-configured architecture definition corresponding to this portfolio.
  def to_cfg_arch
    return @generated_cfg_arch unless @generated_cfg_arch.nil?

    # build up a config for the portfolio
    config_data = {
      "$schema" => "config_schema.json",
      "type" => "partially configured",
      "kind" => "architecture configuration",
      "name" => name,
      "description" => "A partially configured architecture definition corresponding to the #{name} portfolio.",
      "mandatory_extensions" => mandatory_ext_reqs.map do |ext_req|
        {
          "name" => ext_req.name,
          "version" => ext_req.requirement_specs.map(&:to_s)
        }
      end,
      "params" => all_in_scope_ext_params.select(&:single_value?).map { |p| [p.name, p.value] }.to_h
    }

    # TODO: Add list of prohibited_extensions
    gen_dir = $root / "gen" / "cfgs"
    FileUtils.mkdir_p gen_dir
    File.write("#{gen_dir}/#{name}.yaml", YAML.safe_dump(config_data, permitted_classes: [Date]))

    @generated_cfg_arch = ConfiguredArchitecture.new(name, @arch.path)
  end

  ###################################
  # InScopeExtensionParameter Class #
  ###################################

  # Holds extension parameter information from the portfolio.
  class InScopeExtensionParameter
    attr_reader :param  # ExtensionParameter object (from the architecture database)
    attr_reader :note

    def initialize(param, schema_hash, note)
      raise ArgumentError, "Expecting ExtensionParameter" unless param.is_a?(ExtensionParameter)

      if schema_hash.nil?
        schema_hash = {}
      else
        raise ArgumentError, "Expecting schema_hash to be a hash" unless schema_hash.is_a?(Hash)
      end

      @param = param
      @schema_portfolio = Schema.new(schema_hash)
      @note = note
    end

    def name = @param.name
    def idl_type = @param.type
    def single_value? = @schema_portfolio.single_value?

    def value
      raise "Parameter schema_portfolio for #{name} is not a single value" unless single_value?

      @schema_portfolio.value
    end

    # @return [String] - # What parameter values are allowed by the portfolio.
    def allowed_values
      if (@schema_portfolio.empty?)
        # Portfolio doesn't add any constraints on parameter's value.
        return "Any"
      end

      # Create a Schema object just using information in the parameter database.
      schema_obj = @param.schema

      # Merge in constraints imposed by the portfolio on the parameter and then
      # create string showing allowed values of parameter with portfolio constraints added.
      schema_obj.merge(@schema_portfolio).to_pretty_s
    end

    # sorts by name
    def <=>(other)
      raise ArgumentError,
        "InScopeExtensionParameter are only comparable to other parameter constraints" unless other.is_a?(InScopeExtensionParameter)
      @param.name <=> other.param.name
    end
  end # class InScopeExtensionParameter

  ############################################
  # Routines using InScopeExtensionParameter #
  ############################################

  # @return [Array<InScopeExtensionParameter>] List of parameters specified by any extension in portfolio.
  # These are always IN-SCOPE by definition (since they are listed in the portfolio).
  # Can have multiple array entries with the same parameter name since multiple extensions may define
  # the same parameter.
  def all_in_scope_ext_params
    return @all_in_scope_ext_params unless @all_in_scope_ext_params.nil?

    @all_in_scope_ext_params = []

    @data["extensions"].each do |ext_name, ext_data|
      next if ext_name[0] == "$"

      # Find Extension object from database
      ext = @arch.extension(ext_name)
      raise "Cannot find extension named #{ext_name}" if ext.nil?

      ext_data["parameters"]&.each do |param_name, param_data|
        param = ext.params.find { |p| p.name == param_name }
        raise "There is no param '#{param_name}' in extension '#{ext_name}" if param.nil?

        next unless ext.versions.any? do |ext_ver|
                      ver_req = ext_data["version"] || ">= #{ext.min_version.version_spec}"
                      ExtensionRequirement.new(ext_name, ver_req, arch: @arch).satisfied_by?(ext_ver) &&
                      param.defined_in_extension_version?(ext_ver)
                    end

        @all_in_scope_ext_params <<
          InScopeExtensionParameter.new(param, param_data["schema"], param_data["note"])
      end
    end
    @all_in_scope_ext_params
  end

  # @return [Array<InScopeExtensionParameter>] List of extension parameters from portfolio for given extension.
  # These are always IN SCOPE by definition (since they are listed in the portfolio).
  def in_scope_ext_params(ext_req)
    raise ArgumentError, "Expecting ExtensionRequirement" unless ext_req.is_a?(ExtensionRequirement)

    ext_params = []    # Local variable, no caching

    # Get extension information from portfolio YAML for passed in extension requirement.
    ext_data = @data["extensions"][ext_req.name]
    raise "Cannot find extension named #{ext_req.name}" if ext_data.nil?

    # Find Extension object from database
    ext = @arch.extension(ext_req.name)
    raise "Cannot find extension named #{ext_req.name}" if ext.nil?

    # Loop through an extension's parameter constraints (hash) from the portfolio.
    # Note that "&" is the Ruby safe navigation operator (i.e., skip do loop if nil).
    ext_data["parameters"]&.each do |param_name, param_data|
      # Find ExtensionParameter object from database
      ext_param = ext.params.find { |p| p.name == param_name }
      raise "There is no param '#{param_name}' in extension '#{ext_req.name}" if ext_param.nil?

      next unless ext.versions.any? do |ext_ver|
                    ext_req.satisfied_by?(ext_ver) &&
                    ext_param.defined_in_extension_version?(ext_ver)
                  end

      ext_params <<
        InScopeExtensionParameter.new(ext_param, param_data["schema"], param_data["note"])
    end

    ext_params
  end

  # @return [Array<ExtensionParameter>] Parameters out of scope across all in scope extensions (those listed in the portfolio).
  def all_out_of_scope_params
    return @all_out_of_scope_params unless @all_out_of_scope_params.nil?

    @all_out_of_scope_params = []
    in_scope_ext_reqs.each do |ext_req|
      ext = @arch.extension(ext_req.name)
      ext.params.each do |param|
        next if all_in_scope_ext_params.any? { |c| c.param.name == param.name }

        next unless ext.versions.any? do |ext_ver|
                      ext_req.satisfied_by?(ext_ver) &&
                      param.defined_in_extension_version?(ext_ver)
                    end

        @all_out_of_scope_params << param
      end
    end
    @all_out_of_scope_params
  end

  # @return [Array<ExtensionParameter>] Parameters that are out of scope for named extension.
  def out_of_scope_params(ext_name)
    all_out_of_scope_params.select{ |param| param.exts.any? { |ext| ext.name == ext_name } }
  end

  # @return [Array<Extension>]
  # All the in-scope extensions (those in the portfolio) that define this parameter in the database
  # and the parameter is in-scope (listed in that extension's list of parameters in the portfolio).
  def all_in_scope_exts_with_param(param)
    raise ArgumentError, "Expecting ExtensionParameter" unless param.is_a?(ExtensionParameter)

    # Iterate through all the extensions in the architecture database that define this parameter.
    param.exts.select { |ext| in_scope_extensions.include?(ext) }
  end

  # @return [Array<Extension>]
  # All the in-scope extensions (those in the portfolio) that define this parameter in the database
  # but the parameter is out-of-scope (not listed in that extension's list of parameters in the portfolio).
  def all_in_scope_exts_without_param(param)
    raise ArgumentError, "Expecting ExtensionParameter" unless param.is_a?(ExtensionParameter)

    exts = []   # Local variable, no caching

    # Iterate through all the extensions in the architecture database that define this parameter.
    param.exts.each do |ext|
      found = false

      in_scope_extensions.each do |in_scope_ext|
        if ext.name == in_scope_ext.name
          found = true
          next
        end
      end

      if found
          # Only add extensions that are in-scope (i.e., exist in this portfolio).
          exts << ext
      end
    end

    # Return intersection of extension names
    exts
  end

  ############################
  # RevisionHistory Subclass #
  ############################

  # Tracks history of portfolio document.  This is separate from its version since
  # a document may be revised several times before a new version is released.

  class RevisionHistory
    def initialize(data)
      @data = data
    end

    def revision = @data["revision"]
    def date = @data["date"]
    def changes = @data["changes"]
  end

  def revision_history
    return @revision_history unless @revision_history.nil?

    @revision_history = []
    @data["revision_history"].each do |rev|
      @revision_history << RevisionHistory.new(rev)
    end
    @revision_history
  end

  ######################
  # ExtraNote Subclass #
  ######################

  class ExtraNote
    def initialize(data)
      @data = data

      @presence_obj = ExtensionPresence.new(@data["presence"])
    end

    def presence_obj = @presence_obj
    def text = @data["text"]
  end

  def extra_notes
    return @extra_notes unless @extra_notes.nil?

    @extra_notes = []
    @data["extra_notes"]&.each do |extra_note|
      @extra_notes << ExtraNote.new(extra_note)
    end
    @extra_notes
  end

  # @param desired_presence [ExtensionPresence]
  # @return [String] Note for desired_presence
  # @return [nil] No note for desired_presence
  def extra_notes_for_presence(desired_presence_obj)
    raise ArgumentError, "Expecting ExtensionPresence but got a #{desired_presence_obj.class}" unless desired_presence_obj.is_a?(ExtensionPresence)

    extra_notes.select {|extra_note| extra_note.presence_obj == desired_presence_obj}
  end

  ###########################
  # Recommendation Subclass #
  ###########################

  class Recommendation
    def initialize(data)
      @data = data
    end

    def text = @data["text"]
  end

  def recommendations
    return @recommendations unless @recommendations.nil?

    @recommendations = []
    @data["recommendations"]&.each do |recommendation|
      @recommendations << Recommendation.new(recommendation)
    end
    @recommendations
  end
end

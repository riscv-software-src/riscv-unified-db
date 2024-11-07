# Classes for Porfolios which form a common base class for profiles and certificates.
# A "Portfolio" is a named & versioned grouping of extensions (each with a name and version).
# Each Portfolio Instance is a member of a Portfolio Class:
#   RVA20U64 and MC100 are examples of portfolio instances
#   RVA and MC are examples of portfolio classes 
#
# Many classes inherit from the ArchDefObject class. This provides facilities for accessing the contents of a
# Portfolio Class YAML or Portfolio Model YAML file via the "data" member (hash holding releated YAML file contents).
#
# A variable name with a "_portfolio" suffix indicates it is from the porfolio YAML file.
# A variable name with a "_db" suffix indicates it is an object reference from the arch_def database.

require_relative "obj"
require_relative "schema"

##################
# PortfolioClass #
##################

# Holds information from Portfolio class YAML file (certificate class or profile class).
# The inherited "data" member is the database of extensions, instructions, CSRs, etc.
class PortfolioClass < ArchDefObject
  # @return [ArchDef] The defining ArchDef
  attr_reader :arch_def

  # @param data [Hash<String, Object>] The data from YAML
  # @param arch_def [ArchDef] Architecture spec
  def initialize(data, arch_def)
    super(data)
    @arch_def = arch_def
  end

  def introduction = @data["introduction"]
  def naming_scheme = @data["naming_scheme"]
  def description = @data["description"]

  # Returns true if other is the same class (not a derived class) and has the same name.
  def eql?(other)
    other.instance_of?(self.class) && other.name == name
  end
end

#####################
# PortfolioInstance #
#####################

# Holds information about a PortfolioInstance YAML file (certificate or profile).
# The inherited "data" member is the database of extensions, instructions, CSRs, etc.
class PortfolioInstance < ArchDefObject
  # @return [ArchDef] The defining ArchDef
  attr_reader :arch_def

  # @param data [Hash<String, Object>] The data from YAML
  # @param arch_def [ArchDef] Architecture spec
  def initialize(data, arch_def)
    super(data)
    @arch_def = arch_def
  end

  def description = @data["description"]

  # @return [Gem::Version] Semantic version of the PortfolioInstance
  def version = Gem::Version.new(@data["version"])

  # @return [Extension] - Returns named Extension object from database (nil if not found).
  def extension_from_db(ext_name)
    @arch_def.extension(ext_name)
  end

  # @return [Extension] - Returns named Extension object from portfolio (error if not found).
  def extension_from_portfolio(ext_name)
    # Get extension information from YAML for passed in extension name.
    ext_portfolio = @data["extensions"].find {|ext| ext["name"] == ext_name}
    raise "Cannot find extension named #{ext_name}" if ext_portfolio.nil?

    ext_portfolio
  end

  # @return [String] Given an extension +ext_name+, return the presence.
  #                  If the extension name isn't found in the portfolio, return "-".
  def extension_presence(ext_name)
    # Get extension information from YAML for passed in extension name.
    ext_portfolio = @data["extensions"].find {|ext| ext["name"] == ext_name}

    ext_portfolio.nil? ? "-" : ext_portfolio["presence"]
  end

  # @return [String] The note associated with extension +ext_name+
  # @return [nil] if there is no note for +ext_name+
  def extension_note(ext_name)
    ext = extension_from_portfolio(ext_name)

    return ext["note"] unless ext.nil?
  end

  # @return [Array<ExtensionRequirements>] - # Extensions with their portfolio information.
  # If desired_presence is provided, only returns extensions with that presence.
  def in_scope_ext_reqs(desired_presence = nil)
    in_scope_ext_reqs = []
    @data["extensions"]&.each do |ext_portfolio|
      actual_presence = ext_portfolio["presence"]
      raise "Missing extension presence for extension #{ext_portfolio["name"]}" if actual_presence.nil?

      if (actual_presence != "mandatory") && (actual_presence != "optional")
        raise "Unknown extension presence of #{actual_presence} for extension #{ext_portfolio["name"]}" 
      end

      add = false

      if desired_presence.nil?
        add = true
      elsif desired_presence == actual_presence
        add = true
      end

      if add
        in_scope_ext_reqs << 
          ExtensionRequirement.new(ext_portfolio["name"], ext_portfolio["version"], presence: actual_presence,
            note: ext_portfolio["note"], req_id: "REQ-EXT-" + ext_portfolio["name"])
      end
    end
    in_scope_ext_reqs
  end

  # @return [Array<Extension>] List of all extensions listed in portfolio.
  def in_scope_extensions
    return @in_scope_extensions unless @in_scope_extensions.nil?

    @in_scope_extensions = in_scope_ext_reqs.map do |er|
      obj = arch_def.extension(er.name)

      # @todo: change this to raise once all the profile extensions
      #        are defined
      warn "Extension #{er.name} is not defined" if obj.nil?

      obj
    end.reject(&:nil?)

    @in_scope_extensions
  end

  ###################################
  # InScopeExtensionParameter Class #
  ###################################

  # Holds extension parameter information from the portfolio.
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
      @schema_portfolio = Schema.new(schema_hash)
      @note = note
    end

    def single_value?
      @schema_portfolio.single_value?
    end

    def name
      @param_db.name
    end

    def idl_type
      @param_db.type
    end

    def value
      raise "Parameter schema_portfolio for #{name} is not a single value" unless single_value?

      @schema_portfolio.value
    end

    # @return [String] - # What parameter values are allowed by the portfolio.
    def allowed_values
      if (@schema_portfolio.empty?)
        # PortfolioInstance doesn't add any constraints on parameter's value.
        return "Any"
      end

      # Create a Schema object just using information in the parameter database.
      schema_obj = @param_db.schema

      # Merge in constraints imposed by the portfolio on the parameter and then
      # create string showing allowed values of parameter with portfolio constraints added.
      schema_obj.merge(@schema_portfolio).to_pretty_s
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

  # @return [Array<InScopeExtensionParameter>] List of parameters specified by any extension in portfolio.
  # These are always IN-SCOPE by definition (since they are listed in the portfolio).
  # Can have multiple array entries with the same parameter name since multiple extensions may define
  # the same parameter.
  def all_in_scope_ext_params
    return @all_in_scope_ext_params unless @all_in_scope_ext_params.nil?

    @all_in_scope_ext_params = []

    @data["extensions"].each do |ext_portfolio| 
      # Find Extension object from database
      ext_db = @arch_def.extension(ext_portfolio["name"])
      raise "Cannot find extension named #{ext_portfolio["name"]}" if ext_db.nil?

      ext_portfolio["parameters"]&.each do |param_name, param_data|
        param_db = ext_db.params.find { |p| p.name == param_name }
        raise "There is no param '#{param_name}' in extension '#{ext_portfolio["name"]}" if param_db.nil?

        next unless ext_db.versions.any? do |ver_hash|
          Gem::Requirement.new(ext_portfolio["version"]).satisfied_by?(Gem::Version.new(ver_hash["version"])) &&
            param_db.defined_in_extension_version?(ver_hash["version"])
        end

        @all_in_scope_ext_params << 
          InScopeExtensionParameter.new(param_db, param_data["schema"], param_data["note"])
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
    ext_portfolio = @data["extensions"].find {|ext| ext["name"] == ext_req.name}
    raise "Cannot find extension named #{ext_req.name}" if ext_portfolio.nil?
    
    # Find Extension object from database
    ext_db = @arch_def.extension(ext_portfolio["name"])
    raise "Cannot find extension named #{ext_portfolio["name"]}" if ext_db.nil?

    # Loop through an extension's parameter constraints (hash) from the portfolio.
    # Note that "&" is the Ruby safe navigation operator (i.e., skip do loop if nil).
    ext_portfolio["parameters"]&.each do |param_name, param_data|
        # Find ExtensionParameter object from database
        ext_param_db = ext_db.params.find { |p| p.name == param_name }
        raise "There is no param '#{param_name}' in extension '#{ext_portfolio["name"]}" if ext_param_db.nil?

        next unless ext_db.versions.any? do |ver_hash|
          Gem::Requirement.new(ext_portfolio["version"]).satisfied_by?(Gem::Version.new(ver_hash["version"])) &&
            ext_param_db.defined_in_extension_version?(ver_hash["version"])
        end

        ext_params <<
          InScopeExtensionParameter.new(ext_param_db, param_data["schema"], param_data["note"])
    end

    ext_params
  end

  # @return [Array<ExtensionParameter>] Parameters out of scope across all in scope extensions (those listed in the portfolio).
  def all_out_of_scope_params
    return @all_out_of_scope_params unless @all_out_of_scope_params.nil?
 
    @all_out_of_scope_params = []
    in_scope_ext_reqs.each do |ext_req|
      ext_db = @arch_def.extension(ext_req.name)
      ext_db.params.each do |param_db|
        next if all_in_scope_ext_params.any? { |c| c.param_db.name == param_db.name }

        next unless ext_db.versions.any? do |ver_hash|
          Gem::Requirement.new(ext_req.version_requirement).satisfied_by?(Gem::Version.new(ver_hash["version"])) &&
            param_db.defined_in_extension_version?(ver_hash["version"])
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
  # All the in-scope extensions (those in the portfolio) that define this parameter in the database 
  # and the parameter is in-scope (listed in that extension's list of parameters in the portfolio).
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
          # Only add extensions that exist in this portfolio.
          exts << ext_in_db
      end
    end

    # Return intersection of extension names
    exts
  end

  # @return [Array<Extension>]
  # All the in-scope extensions (those in the portfolio) that define this parameter in the database 
  # but the parameter is out-of-scope (not listed in that extension's list of parameters in the portfolio).
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
          # Only add extensions that are in-scope (i.e., exist in this portfolio).
          exts << ext_in_db
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

  class RevisionHistory < ArchDefObject
    def initialize(data)
      super(data)
    end

    def revision
      @data["revision"]
    end

    def date
      @data["date"]
    end

    def changes
      @data["changes"]
    end
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

  class ExtraNote < ArchDefObject
    def initialize(data)
      super(data)
    end

    def presence
      @data["presence"]
    end

    def text
      @data["text"]
    end
  end

  def extra_notes
    return @extra_notes unless @extra_notes.nil?

    @extra_notes = []
    @data["extra_notes"]&.each do |extra_note|
      @extra_notes << ExtraNote.new(extra_note)
    end
    @extra_notes
  end

  def extra_notes_for_presence(desired_presence)
    extra_notes.select {|extra_note| extra_note.presence == desired_presence}
  end

  ###########################
  # Recommendation Subclass #
  ###########################

  class Recommendation < ArchDefObject
    def initialize(data)
      super(data)
    end

    def text
      @data["text"]
    end
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
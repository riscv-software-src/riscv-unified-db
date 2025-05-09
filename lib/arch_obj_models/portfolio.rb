# frozen_string_literal: true

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

require "forwardable"

require_relative "database_obj"
require_relative "schema"

##################
# PortfolioClass #
##################

# Holds information from Portfolio class YAML file (processor certificate class or profile class).
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

##################
# PortfolioGroup #
##################

# A portfolio group consists of a one or more profiles.
# Contains common code to aggregrate multiple portfolios for Profile Releases and PortfolioDesign classes.
# This not the base class for ProfileRelease but it does contain one of these.
# This is not a DatabaseObject.
class PortfolioGroup
  extend Forwardable

  attr_reader :name

  # Calls to these methods on PortfolioGroup are handled by the Array class.
  # Avoids having to call portfolio_grp.portfolios.<array_method> (just call portfolio_grp.<array_method>).
  def_delegators :@portfolios, :each, :map, :select

  # @param portfolios [Array<Portfolio>]
  def initialize(name, portfolios)
    raise ArgumentError, "name is a class #{name.class} but must be a String" unless name.is_a?(String)
    raise ArgumentError, "Need at least one portfolio" if portfolios.empty?

    @name = name
    @portfolios = portfolios
  end

  # @return [Array<Portfolio>] All portfolios in this portfolio group
  def portfolios = @portfolios

  # @return [Hash<String, String>] Fully-constrained parameter values (those with just one possible value for this design).
  def param_values
    return @param_values unless @param_values.nil?

    @param_values = {}
    portfolios.each do |portfolio|
      @param_values.merge!(portfolio.all_in_scope_params.select(&:single_value?).map { |p| [p.name, p.value] }.to_h)
    end

    @param_values
  end

  # @return [Integer] Maximum base value (32 or 64) of all portfolios in group.
  def max_base
    base = portfolios.map(&:base).max

    raise "All portfolios in config have a nil base" if base.nil?
    raise ArgumentError, "Calculated maximum base of #{base} across portfolios is not 32 or 64" unless base == 32 || base == 64

    return base
  end

  # @return [Array<ExtensionRequirement>] Sorted list of all extension requirements listed by the group.
  def in_scope_ext_reqs
    return @in_scope_ext_reqs unless @in_scope_ext_reqs.nil?

    @in_scope_ext_reqs = []
    portfolios.each do |portfolio|
      @in_scope_ext_reqs += portfolio.in_scope_ext_reqs
    end

    @in_scope_ext_reqs = @in_scope_ext_reqs.uniq(&:name).sort_by(&:name)
  end

  # @return [Array<ExtensionRequirement>] Sorted list of all mandatory extension requirements listed by the group.
  def mandatory_ext_reqs
    return @mandatory_ext_reqs unless @mandatory_ext_reqs.nil?

    @mandatory_ext_reqs = []
    portfolios.each do |portfolio|
      @mandatory_ext_reqs += portfolio.mandatory_ext_reqs
    end

    @mandatory_ext_reqs = @mandatory_ext_reqs.uniq(&:name).sort_by(&:name)
  end

  # @return [Array<ExtensionRequirement>] Sorted list of all optional extension requirements listed by the group.
  def optional_ext_reqs
    return @optional_ext_reqs unless @optional_ext_reqs.nil?

    @optional_ext_reqs = []
    portfolios.each do |portfolio|
      @optional_ext_reqs += portfolio.optional_ext_reqs
    end

    @optional_ext_reqs = @optional_ext_reqs.uniq(&:name).sort_by(&:name)
  end

  # @return [Array<Extension>] Sorted list of all mandatory or optional extensions referenced by the group.
  def in_scope_extensions
    return @in_scope_extensions unless @in_scope_extensions.nil?

    @in_scope_extensions = []
    portfolios.each do |portfolio|
      @in_scope_extensions += portfolio.in_scope_extensions
    end

    @in_scope_extensions = @in_scope_extensions.uniq(&:name).sort_by(&:name)

  end

  # @param design [Design] The design
  # @return [Array<Instruction>] Sorted list of all instructions associated with extensions listed as
  #                              mandatory or optional in portfolio. Uses instructions provided by the
  #                              minimum version of the extension that meets the extension requirement.
  def in_scope_instructions(design)
    raise ArgumentError, "Require an PortfolioDesign object but got a #{design.class} object" unless design.is_a?(PortfolioDesign)

    return @in_scope_instructions unless @in_scope_instructions.nil?

    @in_scope_instructions = []
    portfolios.each do |portfolio|
      @in_scope_instructions += portfolio.in_scope_instructions(design)
    end

    @in_scope_instructions =
      @in_scope_instructions.uniq(&:name).sort_by(&:name)
  end

  # @param design [Design] The design
  # @return [Array<Csr>] Unsorted list of all CSRs associated with extensions listed as
  #                      mandatory or optional in portfolio. Uses CSRs provided by the
  #                      minimum version of the extension that meets the extension requirement.
  def in_scope_csrs(design)
    raise ArgumentError, "Require an PortfolioDesign object but got a #{design.class} object" unless design.is_a?(PortfolioDesign)

    return @in_scope_csrs unless @in_scope_csrs.nil?

    @in_scope_csrs = []
    portfolios.each do |portfolio|
      @in_scope_csrs += portfolio.in_scope_csrs(design)
    end

    @in_scope_csrs.uniq(&:name)
  end

  # @param design [Design] The design
  # @return [Array<ExceptionCode>] Unsorted list of all in-scope exception codes.
  def in_scope_exception_codes(design)
    raise ArgumentError, "Require an PortfolioDesign object but got a #{design.class} object" unless design.is_a?(PortfolioDesign)

    return @in_scope_exception_codes unless @in_scope_exception_codes.nil?

    @in_scope_exception_codes = []
    portfolios.each do |portfolio|
      @in_scope_exception_codes += portfolio.in_scope_exception_codes(design)
    end

    @in_scope_exception_codes.uniq(&:name)
  end

  # @param design [Design] The design
  # @return [Array<InterruptCode>] Unsorted list of all in-scope interrupt codes.
  def in_scope_interrupt_codes(design)
    raise ArgumentError, "Require an PortfolioDesign object but got a #{design.class} object" unless design.is_a?(PortfolioDesign)

    return @in_scope_interrupt_codes unless @in_scope_interrupt_codes.nil?

    @in_scope_interrupt_codes = []
    portfolios.each do |portfolio|
      @in_scope_interrupt_codes += portfolio.in_scope_interrupt_codes(design)
    end

    @in_scope_interrupt_codes.uniq(&:name)
  end

  # @return [String] Given an extension +ext_name+, return the presence as a string.
  #                  Returns the greatest presence string across all profiles in the group.
  #                  If the extension name isn't found in the release, return "-".
  def extension_presence(ext_name)
    greatest_presence = nil

    portfolios.each do |portfolio|
      presence = portfolio.extension_presence_obj(ext_name)

      unless presence.nil?
        if greatest_presence.nil?
          greatest_presence = presence
        elsif presence > greatest_presence
          greatest_presence = presence
        end
      end
    end

    greatest_presence.nil? ? "-" : greatest_presence.to_s_concise
  end

  # @return [String] Given an instruction +inst_name+, return the presence as a string.
  #                  Returns the greatest presence string across all profiles in the group.
  #                  If the instruction name isn't found in the release, return "-".
  def instruction_presence(inst_name)
    greatest_presence = nil

    portfolios.each do |portfolio|
      presence = portfolio.instruction_presence_obj(inst_name)

      unless presence.nil?
        if greatest_presence.nil?
          greatest_presence = presence
        elsif presence > greatest_presence
          greatest_presence = presence
        end
      end
    end

    greatest_presence.nil? ? "-" : greatest_presence.to_s_concise
  end

  # @return [String] Given an CSR +csr_name+, return the presence as a string.
  #                  Returns the greatest presence string across all profiles in the group.
  #                  If the CSR name isn't found in the release, return "-".
  def csr_presence(csr_name)
    greatest_presence = nil

    portfolios.each do |portfolio|
      presence = portfolio.csr_presence_obj(csr_name)

      unless presence.nil?
        if greatest_presence.nil?
          greatest_presence = presence
        elsif presence > greatest_presence
          greatest_presence = presence
        end
      end
    end

    greatest_presence.nil? ? "-" : greatest_presence.to_s_concise
  end

  # @return [Array<InScopeParameter>] Sorted list of parameters specified by any extension in portfolio.
  def all_in_scope_params
    @ret = []
    portfolios.each do |portfolio|
      @ret += portfolio.all_in_scope_params
    end

    @ret = @ret.uniq.sort
  end

  # @param [ExtensionRequirement]
  # @return [Array<InScopeParameter>] Sorted list of extension parameters from portfolio for given extension.
  def in_scope_params(ext_req)
    @ret = []
    portfolios.each do |portfolio|
      @ret += portfolio.in_scope_params(ext_req)
    end

    @ret = @ret.uniq.sort
  end

  # @return [Array<Parameter>] Sorted list of parameters out of scope across all in scope extensions.
  def all_out_of_scope_params
    @ret = []
    portfolios.each do |portfolio|
      @ret += portfolio.all_out_of_scope_params
    end

    @ret = @ret.uniq.sort
  end

  # @param ext_name [String] Extension name
  # @return [Array<Parameter>] Sorted list of parameters that are out of scope for named extension.
  def out_of_scope_params(ext_name)
    @ret = []
    portfolios.each do |portfolio|
      @ret += portfolio.out_of_scope_params(ext_name)
    end

    @ret = @ret.uniq.sort
  end

  # @param param [Parameter]
  # @return [Array<Extension>] Sorted list of all in-scope extensions that define this parameter
  #                            in the database and the parameter is in-scope.
  def all_in_scope_exts_with_param(param)
    @ret = []
    portfolios.each do |portfolio|
      @ret += portfolio.all_in_scope_exts_with_param(param)
    end

    @ret = @ret.uniq.sort
  end

  # @param param [Parameter]
  # @return [Array<Extension>] List of all in-scope extensions that define this parameter in the
  #                            database but the parameter is out-of-scope.
  def all_in_scope_exts_without_param(param)
    @ret = []
    portfolios.each do |portfolio|
      @ret += portfolio.all_in_scope_exts_without_param(param)
    end

    @ret = @ret.uniq.sort
  end
end

#############
# Portfolio #
#############

# Holds information about a Portfolio (certificate or profile).
# The inherited "data" member is YAML data from the architecture for this portfolio object.
class Portfolio < DatabaseObject
  # @param obj_yaml [Hash<String, Object>] Contains contents of Portfolio yaml file (put in @data)
  # @param data_path [String] Path to yaml file
  # @param arch [Architecture] Entire database of RISC-V architecture standards
  sig { params(obj_yaml: T::Hash[String, Object], yaml_path: T.any(String, Pathname), arch: ConfiguredArchitecture).void }
  def initialize(obj_yaml, yaml_path, arch)
    super # Calls parent class with same args I got
  end

  # @return [String] Small enough (~1 paragraph) to be suitable immediately after a higher-level heading.
  def introduction = @data["introduction"]

  # @return [String] Large enough to need its own heading (generally one level deeper than the "introduction").
  def description = @data["description"]

  # @return [Integer] 32 or 64
  def base = @data["base"]

  # @return [Gem::Version] Semantic version of the Portfolio
  def version = Gem::Version.new(@data["version"])

  # @return [Presence] Given an extension +ext_name+, return the presence.
  #                    If the extension name isn't found in the portfolio, return nil.
  def extension_presence_obj(ext_name)
    # Get extension information from YAML for passed in extension name.
    ext_data = @data["extensions"][ext_name]

    ext_data.nil? ? nil : Presence.new(ext_data["presence"])
  end

  # @return [String] Given an extension +ext_name+, return the presence as a string.
  #                  If the extension name isn't found in the portfolio, return "-".
  def extension_presence(ext_name)
    presence_obj = extension_presence_obj(ext_name)

    presence_obj.nil? ? "-" : presence_obj.to_s
  end

  # @return [Presence] Given an instruction +inst_name+, return the presence.
  #                    If the instruction name isn't found in the portfolio, return nil.
  def instruction_presence_obj(inst_name)
    @instruction_presence_obj ||= {}

    return @instruction_presence_obj[inst_name] unless @instruction_presence_obj[inst_name].nil?

    inst = arch.instruction(inst_name)

    raise "Can't find instruction object '#{inst_name}' in arch class" if inst.nil?

    is_mandatory = mandatory_ext_reqs.any? do |ext_req|
      ext_versions = ext_req.satisfying_versions
      ext_versions.any? { |ext_ver| inst.defined_by_condition.possibly_satisfied_by?(ext_ver) }
    end

    is_optional = optional_ext_reqs.any? do |ext_req|
      ext_versions = ext_req.satisfying_versions
      ext_versions.any? { |ext_ver| inst.defined_by_condition.possibly_satisfied_by?(ext_ver) }
    end

    @instruction_presence_obj[inst_name] =
      if is_mandatory
        Presence.new(Presence.mandatory)
      elsif is_optional
        Presence.new(Presence.optional)
      else
        nil
      end
  end

  # @return [String] Given an instruction +inst_name+, return the presence as a string.
  #                  If the instruction name isn't found in the portfolio, return "-".
  def instruction_presence(inst_name)
    @instruction_presence ||= {}

    return @instruction_presence[inst_name] unless @instruction_presence[inst_name].nil?

    presence_obj = instruction_presence_obj(inst_name)

    @instruction_presence[inst_name] = presence_obj.nil? ? "-" : presence_obj.to_s
  end

  # @return [Presence] Given an CSR +csr_name+, return the presence.
  #                    If the CSR name isn't found in the portfolio, return nil.
  def csr_presence_obj(csr_name)
    @csr_presence_obj ||= {}

    return @csr_presence_obj[csr_name] unless @csr_presence_obj[csr_name].nil?

    csr = arch.csr(csr_name)

    raise "Can't find CSR object '#{csr_name}' in arch class" if csr.nil?

    is_mandatory = mandatory_ext_reqs.any? do |ext_req|
      ext_versions = ext_req.satisfying_versions
      ext_versions.any? { |ext_ver| csr.defined_by_condition.possibly_satisfied_by?(ext_ver) }
    end

    is_optional = optional_ext_reqs.any? do |ext_req|
      ext_versions = ext_req.satisfying_versions
      ext_versions.any? { |ext_ver| csr.defined_by_condition.possibly_satisfied_by?(ext_ver) }
    end

    @csr_presence_obj[csr_name] =
      if is_mandatory
        Presence.new(Presence.mandatory)
      elsif is_optional
        Presence.new(Presence.optional)
      else
        nil
      end
  end

  # @return [String] Given an CSR +csr_name+, return the presence as a string.
  #                  If the CSR name isn't found in the portfolio, return "-".
  def csr_presence(csr_name)
    @csr_presence ||= {}

    return @csr_presence[csr_name] unless @csr_presence[csr_name].nil?

    presence_obj = csr_presence_obj(csr_name)

    @csr_presence[csr_name] = presence_obj.nil? ? "-" : presence_obj.to_s
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

  def mandatory_ext_reqs = in_scope_ext_reqs(Presence.mandatory)
  def optional_ext_reqs = in_scope_ext_reqs(Presence.optional)
  def optional_type_ext_reqs = in_scope_ext_reqs(Presence.optional)

  # @param desired_presence [String, Hash, Presence]
  # @return [Array<ExtensionRequirements>] Sorted list of extensions with their portfolio information.
  # If desired_presence is provided, only returns extensions with that presence.
  # If desired_presence is a String, only the presence portion of an Presence is compared.
  def in_scope_ext_reqs(desired_presence = nil)
    in_scope_ext_reqs = []

    # Convert desired_present argument to Presence object if not nil.
    desired_presence_converted =
      desired_presence.nil?            ? nil :
      desired_presence.is_a?(String)   ? desired_presence :
      desired_presence.is_a?(Presence) ? desired_presence :
                                         Presence.new(desired_presence)

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
        actual_presence_obj = Presence.new(actual_presence)

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

    in_scope_ext_reqs.sort_by!(&:name)
  end

  # @return [Array<Extension>] Sorted list of all mandatory or optional extensions in portfolio.
  #                            Each extension can have multiple versions (contains ExtensionVersion array).
  def in_scope_extensions
    return @in_scope_extensions unless @in_scope_extensions.nil?

    @in_scope_extensions = in_scope_ext_reqs.map do |ext_req|
      ext_req.extension
    end.reject(&:nil?)  # Filter out extensions that don't exist yet.

    @in_scope_extensions.sort_by!(&:name)
  end

  # @return [ExtensionVersion] List of all mandatory or optional extensions listed in portfolio.
  #                            The minimum version of each extension that satisfies the extension requirements is provided.
  def in_scope_min_satisfying_extension_versions
    return @in_scope_min_satisfying_extension_versions unless @in_scope_min_satisfying_extension_versions.nil?

    @in_scope_min_satisfying_extension_versions = in_scope_ext_reqs.map do |ext_req|
      ext_req.satisfying_versions.min
    end.reject(&:nil?)  # Filter out extensions that don't exist yet.

    @in_scope_min_satisfying_extension_versions
  end

  # @param design [Design] The design
  # @return [Array<Instruction>] Sorted list of all instructions associated with extensions listed as
  #                              mandatory or optional in portfolio. Uses instructions provided by the
  #                              minimum version of the extension that meets the extension requirement.
  def in_scope_instructions(design)
    raise ArgumentError, "Require an PortfolioDesign object but got a #{design.class} object" unless design.is_a?(PortfolioDesign)

    return @in_scope_instructions unless @in_scope_instructions.nil?

    @in_scope_instructions =
      in_scope_min_satisfying_extension_versions.map {|ext_ver| ext_ver.in_scope_instructions(design) }.flatten.uniq.sort
  end

  # @param design [Design] The design
  # @return [Array<Csr>] Unsorted list of all CSRs associated with extensions listed as
  #                      mandatory or optional in portfolio. Uses CSRs provided by the
  #                      minimum version of the extension that meets the extension requirement.
  def in_scope_csrs(design)
    raise ArgumentError, "Require an PortfolioDesign object but got a #{design.class} object" unless design.is_a?(PortfolioDesign)

    return @in_scope_csrs unless @in_scope_csrs.nil?

    @in_scope_csrs =
      in_scope_min_satisfying_extension_versions.map {|ext_ver| ext_ver.in_scope_csrs(design) }.flatten.uniq
  end

  # @param design [Design] The design
  # @return [Array<ExceptionCode>] Unsorted list of all in-scope exception codes.
  # TODO: See https://github.com/riscv-software-src/riscv-unified-db/issues/291
  # TODO: Still needs work and haven't created in_scope_interrupt_codes yet.
  # TODO: Extensions should provide conditional information ("when" statements?)
  #       that we evaluate here to determine if a particular exception code can
  #       actually be generated in a design.
  #       Also, probably shouldn't be calling "ext?" since that doesn't the in_scope lists of extensions.
  def in_scope_exception_codes(design)
    raise ArgumentError, "Require an PortfolioDesign object but got a #{design.class} object" unless design.is_a?(PortfolioDesign)

    return @in_scope_exception_codes unless @in_scope_exception_codes.nil?

    @in_scope_exception_codes =
      in_scope_min_satisfying_extension_versions.reduce([]) do |list, ext_version|
        ecodes = ext_version.ext["exception_codes"]
        next list if ecodes.nil?

        ecodes.each do |ecode|
          # Require all exception codes be unique in a given portfolio.
          raise "Duplicate exception code" if list.any? { |e| e.num == ecode["num"] || e.name == ecode["name"] || e.var == ecode["var"] }

          unless ecode.dig("when", "version").nil?
            # check version
            next unless design.ext?(ext_version.name.to_sym, ecode["when"]["version"])
          end
          list << ExceptionCode.new(ecode["name"], ecode["var"], ecode["num"], arch)
        end
        list
      end
  end

  # @param design [Design] The design
  # @return [Array<InterruptCode>] Unsorted list of all in-scope interrupt codes.
  # TODO: Actually implement this to use Design. See in_scope_exception_codes() above.
  def in_scope_interrupt_codes(design) = arch.interrupt_codes

  # @return [Boolean] Does the profile differentiate between different types of optional.
  def uses_optional_types?
    return @uses_optional_types unless @uses_optional_types.nil?

    @uses_optional_types = false

    in_scope_ext_reqs(Presence.optional)&.each do |ext_req|
      if ext_req.presence.uses_optional_types?
        @uses_optional_types = true
      end
    end

    @uses_optional_types
  end

  ###########################################################################
  # Portfolio types that supported the concept of in-scope and out-of-scope #
  # parameter have to override the following methods.                       #
  ###########################################################################

  # @return [Array<InScopeParameter>] List of parameters specified by any extension in portfolio.
  def all_in_scope_params = []

  # @param [ExtensionRequirement]
  # @return [Array<InScopeParameter>] Sorted list of extension parameters from portfolio for given extension.
  def in_scope_params(ext_req) = []

  # @return [Array<Parameter>] Sorted list of parameters out of scope across all in scope extensions.
  def all_out_of_scope_params = []

  # @param ext_name [String] Extension name
  # @return [Array<Parameter>] Sorted list of parameters that are out of scope for named extension.
  def out_of_scope_params(ext_name) = []

  # @param param [Parameter]
  # @return [Array<Extension>] Sorted list of all in-scope extensions that define this parameter
  #                            in the database and the parameter is in-scope.
  def all_in_scope_exts_with_param(param) = []

  # @param param [Parameter]
  # @return [Array<Extension>] List of all in-scope extensions that define this parameter in the
  #                            database but the parameter is out-of-scope.
  def all_in_scope_exts_without_param(param) = []

  ##########################
  # InScopeParameter Class #
  ##########################

  class InScopeParameter
    # @return [Parameter] Parameter object (from the architecture database)
    attr_reader :param

    # @return [String] Optional note associated with the parameter
    attr_reader :note

    def initialize(param, schema_hash, note)
      raise ArgumentError, "Expecting Parameter" unless param.is_a?(Parameter)

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
        "InScopeParameter are only comparable to other parameter constraints" unless other.is_a?(InScopeParameter)
      @param.name <=> other.param.name
    end
  end # class InScopeParameter

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

      @presence_obj = Presence.new(@data["presence"])
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

  # @param desired_presence [Presence]
  # @return [String] Note for desired_presence
  # @return [nil] No note for desired_presence
  def extra_notes_for_presence(desired_presence_obj)
    raise ArgumentError, "Expecting Presence but got a #{desired_presence_obj.class}" unless desired_presence_obj.is_a?(Presence)

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

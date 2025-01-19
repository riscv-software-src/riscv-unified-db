# frozen_string_literal: true

# Combines knowledge of the RISC-V Architecture with a particular configuration.
# The architecture is an instance of the Architecture object representing yaml files in the /arch directory.
# A configuration is an instance of the Config object representing yaml files in the /cfg directory.

require "forwardable"
require "ruby-prof"

require_relative "architecture"
require_relative "design"
require_relative "config"

class ConfiguredArchitecture < Design
  extend Forwardable

  # Calls to these methods on ConfiguredArchitecture are handled by the @config method of the same name.
  # Kind of like inheritence but not quite.
  def_delegators \
    :@config, \
    :fully_configured?, :partially_configured?, :unconfigured?, :configured?, :param_values

  # @param config_name [#to_s] The configuration name which corresponds to a folder name under cfg_path
  # @param arch_dir [String,Pathname] Path to a directory with a fully merged/resolved architecture definition
  # @param overlay_path [String] Optional path to a directory that overlays the architecture
  # @param cfg_path [String] Optional path to where to find configuration file
  def initialize(config_name, arch_dir, overlay_path: nil, cfg_path: "#{$root}/cfgs")
    @config = Config.create("#{cfg_path}/#{config_name}/cfg.yaml")
    super(config_name, Architecture.new(config_name, arch_dir), @config.mxlen, overlay_path: overlay_path)
  end

  # Returns a string representation of the object, suitable for debugging.
  # @return [String] A string representation of the object.
  def inspect = "ConfiguredArchitecture##{name}"

  ###########################################
  # OVERRIDEN ABSTRACT METHODS              #
  #                                         #
  # These raise an error in the base class. #
  ###########################################

  # Returns whether or not it may be possible to switch XLEN in +mode+ given this definition.
  #
  # There are three cases when this will return true:
  #   1. +mode+ (e.g., U) is known to be implemented, and the CSR bit that controls XLEN in +mode+ is known to be writeable.
  #   2. +mode+ is known to be implemented, but the writability of the CSR bit that controls XLEN in +mode+ is not known.
  #   3. It is not known if +mode+ is implemented.
  #
  # Will return false if +mode+ is not possible (e.g., because U is a prohibited extension)
  #
  # @param mode [String] mode to check. One of "M", "S", "U", "VS", "VU"
  # @return [Boolean] true if this configuration might execute in multiple xlen environments in +mode+
  #                   (e.g., that in some mode the effective xlen can be either 32 or 64, depending on CSR values)
  def multi_xlen_in_mode?(mode)
    return false if @mxlen == 32

    case mode
    when "M"
      @mxlen.nil?
    when "S"
      return true if unconfigured?

      if fully_configured?
        ext?(:S) && (param_values["SXLEN"] == 3264)
      elsif partially_configured?
        return false if prohibited_ext?(:S)

        return true unless ext?(:S) # if S is not known to be implemented, we can't say anything about it

        return true unless param_values.key?("SXLEN")

        param_values["SXLEN"] == 3264
      else
        raise "Unexpected configuration state"
      end
    when "U"
      return false if prohibited_ext?(:U)

      return true if unconfigured?

      if fully_configured?
        ext?(:U) && (param_values["UXLEN"] == 3264)
      elsif partially_configured?
        return true unless ext?(:U) # if U is not known to be implemented, we can't say anything about it

        return true unless param_values.key?("UXLEN")

        param_values["UXLEN"] == 3264
      else
        raise "Unexpected configuration state"
      end
    when "VS"
      return false if prohibited_ext?(:H)

      return true if unconfigured?

      if fully_configured?
        ext?(:H) && (param_values["VSXLEN"] == 3264)
      elsif partially_configured?
        return true unless ext?(:H) # if H is not known to be implemented, we can't say anything about it

        return true unless param_values.key?("VSXLEN")

        param_values["VSXLEN"] == 3264
      else
        raise "Unexpected configuration state"
      end
    when "VU"
      return false if prohibited_ext?(:H)

      return true if unconfigured?

      if fully_configured?
        ext?(:H) && (param_values["VUXLEN"] == 3264)
      elsif partially_configured?
        return true unless ext?(:H) # if H is not known to be implemented, we can't say anything about it

        return true unless param_values.key?("VUXLEN")

        param_values["VUXLEN"] == 3264
      else
        raise "Unexpected configuration state"
      end
    else
      raise ArgumentError, "Bad mode"
    end
  end

  # @return [Array<ParameterWithValue>] List of all parameters with one known value in the config
  def params_with_value
    return @params_with_value unless @params_with_value.nil?

    @params_with_value = []
    return @params_with_value if @config.unconfigured?

    if @config.fully_configured?
      transitive_implemented_ext_vers.each do |ext_version|
        ext_version.ext.params.each do |param|
          next unless @config.param_values.key?(param.name)

          @params_with_value << ParameterWithValue.new(
            param,
            @config.param_values[param.name]
          )
        end
      end
    elsif @config.partially_configured?
      mandatory_ext_reqs.each do |ext_req|
        ext_req.extension.params.each do |param|
          # Params listed in the config always only have one value.
          next unless @config.param_values.key?(param.name)

          @params_with_value << ParameterWithValue.new(
            param,
            @config.param_values[param.name]
          )
        end
      end
    else
      raise "ERROR: unexpected config type"
    end
    @params_with_value
  end

  # @return [Array<Parameter>] List of all available parameters without one known value in the config
  def params_without_value
    return @params_without_value unless @params_without_value.nil?

    @params_without_value = []
    arch.extensions.each do |ext|
      ext.params.each do |param|
        # Params listed in the config always only have one value.
        next if @config.param_values.key?(param.name)

        @params_without_value << param
      end
    end
    @params_without_value
  end

  # @return [Array<ExtensionVersion>] List of all implemented extension versions.
  def implemented_ext_vers
    return @implemented_ext_vers unless @implemented_ext_vers.nil?

    @implemented_ext_vers = @config.implemented_extensions.map do |e|
      ExtensionVersion.new(e["name"], e["version"], arch, fail_if_version_does_not_exist: true)
    end
  end

  # @return [Array<ExtensionRequirement>] List of all mandatory extension requirements
  def mandatory_ext_reqs
    return @mandatory_ext_reqs unless @mandatory_ext_reqs.nil?

    @mandatory_ext_reqs = @config.mandatory_extensions.map do |e|
      ext = arch.extension(e["name"])
      raise "Cannot find extension #{e['name']} in the architecture definition" if ext.nil?

      ExtensionRequirement.new(e["name"], *e["version"], arch, presence: "mandatory")
    end
  end

  # @return [Array<ExtensionRequirement>] List of all extensions that are prohibited.
  #                                       This includes extensions explicitly prohibited by the config file
  #                                       and extensions that conflict with a mandatory extension.
  def prohibited_ext_reqs
    return @prohibited_ext_reqs unless @prohibited_ext_reqs.nil?

    if @config.partially_configured?
      @prohibited_ext_reqs =
        @config.prohibited_extensions.map do |e|
          ext = arch.extension(e["name"])
          raise "Cannot find extension #{e['name']} in the architecture definition" if ext.nil?

          ExtensionRequirement.new(e["name"], *e["version"], arch, presence: "mandatory")
        end

      # now add any extensions that are prohibited by a mandatory extension
      mandatory_ext_reqs.each do |ext_req|
        ext_req.extension.conflicts.each do |conflict|
          if @prohibited_ext_reqs.none? { |prohibited_ext_req| prohibited_ext_req.name == conflict.name }
            @prohibited_ext_reqs << conflict
          else
            # pick whichever requirement is more expansive
            p = @prohibited_ext_reqs.find { |prohibited_ext_req| prohibited_ext_req.name == confict.name }
            if p.version_requirement.subsumes?(conflict.version_requirement)
              @prohibited_ext_reqs.delete(p)
              @prohibited_ext_reqs << conflict
            end
          end
        end
      end

      @prohibited_ext_reqs
    elsif @config.fully_configured?
      prohibited_ext_vers = []
      arch.extensions.each do |ext|
        ext.versions.each do |ext_ver|
          prohibited_ext_vers << ext_ver unless transitive_implemented_ext_vers.include?(ext_ver)
        end
      end
      @prohibited_ext_reqs = []
      prohibited_ext_vers.group_by(&:name).each_value do |ext_ver_list|
        if ext_ver_list.sort == ext_ver_list[0].ext.versions.sort
          # excludes every version
          @prohibited_ext_reqs <<
            ExtensionRequirement.new(
              ext_ver_list[0].ext.name, ">= #{ext_ver_list.min.version_spec.canonical}",
              arch, presence: "prohibited"
            )
        elsif ext_ver_list.size == (ext_ver_list[0].ext.versions.size - 1)
          # excludes all but one version
          allowed_version_list = (ext_ver_list[0].ext.versions - ext_ver_list)
          raise "Expected only a single element" unless allowed_version_list.size == 1

          allowed_version = allowed_version_list[0]
          @prohibited_ext_reqs <<
            ExtensionRequirement.new(
              ext_ver_list[0].ext.name, "!= #{allowed_version.version_spec.canonical}", arch,
              presence: "prohibited"
            )
        else
          # need to group
          raise "TODO"
        end
      end
    else
      @prohibited_ext_reqs = []
    end
    @prohibited_ext_reqs
  end

  # @overload ext?(ext_name)
  #   @param ext_name [#to_s] Extension name (case sensitive)
  #   @return [Boolean] True if the extension `name` must be implemented
  #
  # @overload ext?(ext_name, ext_version_requirements)
  #   @param ext_name [#to_s] Extension name (case sensitive)
  #   @param ext_version_requirements [Number,String,Array] Extension version requirements
  #   @return [Boolean] True if the extension `name` meeting `ext_version_requirements` must be implemented
  def ext?(ext_name, *ext_version_requirements)
    @ext_cache ||= {}
    cached_result = @ext_cache[[ext_name, ext_version_requirements]]
    return cached_result unless cached_result.nil?

    result =
      if @config.fully_configured?
        transitive_implemented_ext_vers.any? do |e|
          if ext_version_requirements.empty?
            e.name == ext_name.to_s
          else
            requirement = ExtensionRequirement.new(ext_name, *ext_version_requirements, arch)
            requirement.satisfied_by?(e)
          end
        end
      elsif @config.partially_configured?
        mandatory_ext_reqs.any? do |e|
          if ext_version_requirements.empty?
            e.name == ext_name.to_s
          else
            requirement = ExtensionRequirement.new(ext_name, *ext_version_requirements, arch)
            e.satisfying_versions.all? do |ext_ver|
              requirement.satisfied_by?(ext_ver)
            end
          end
        end
      else
        raise "unexpected type" unless unconfigured?

        false
      end
    @ext_cache[[ext_name, ext_version_requirements]] = result
  end

  # Given an adoc string, find names of CSR/Instruction/Extension enclosed in `monospace`
  # and replace them with links to the relevant object page.
  # See backend_helpers.rb for a definition of the proprietary link format.
  #
  # @param adoc [String] Asciidoc source
  # @return [String] Asciidoc source, with link placeholders
  def convert_monospace_to_links(adoc)
    adoc.gsub(/`([\w.]+)`/) do |match|
      name = Regexp.last_match(1)
      csr_name, field_name = name.split(".")
      csr = arch.csr(csr_name)
      if !field_name.nil? && !csr.nil? && csr.field?(field_name)
        link_to_udb_doc_csr_field(csr_name, field_name)
      elsif !csr.nil?
        link_to_udb_doc_csr(csr_name)
      elsif arch.instruction(name)
        link_to_udb_doc_inst(name)
      elsif arch.extension(name)
        link_to_udb_doc_ext(name)
      else
        match
      end
    end
  end

  #####################################
  # METHODS RESTRICTING PARENT METHOD #
  #####################################

  # @return [Array<ExtensionVersion>] List of all extensions known to be implemented in this config, including transitive implications
  def transitive_implemented_ext_vers
    raise "transitive_implemented_ext_vers is only valid for a fully configured definition" unless @config.fully_configured?
    super
  end

  # Override base class to reject a nil value.
  # @return [Idl::SymbolTable] Symbol table with global scope
  def symtab
    raise NotImplementedError, "Un-configured ConfiguredArchitectures have no symbol table" if @symtab.nil?
    super
  end
end

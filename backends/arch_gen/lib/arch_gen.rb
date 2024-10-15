# frozen_string_literal: true

require "English"
require "erb"
require "pathname"
require "rake/application"
require "rubygems/requirement"
require "tilt"
require "yaml"

require_relative "#{$lib}/validate"
require_relative "#{$lib}/arch_def"

$root = Pathname.new(__FILE__).dirname.dirname.realpath if $root.nil?

# Class to help parse parameterized arch definitions and generate a unified configuration
#
# ArchGen is initialized with a config name, which *must* be the name of a
# directory under cfgs/
#
class ArchGen
  # configuration name
  attr_reader :name

  # path where the result will be written
  attr_reader :gen_dir

  # trace a message if Rake's tracing is turned on
  def trace(msg)
    Rake.application.trace msg if Rake.application.options.trace
  end
  private :trace

  def gen_params_schema
    return if @gen_params_schema_complete == true

    schema = {
      "type" => "object",
      "required" => ["params"],
      "properties" => {
        "params" => {
          "type" => "object",
          "required" => ["NAME"],
          "properties" => {
            "NAME" => { "type" => "string", "enum" => [@name] },
            "XLEN" => { "type" => "intger", "enum" => [32, 64] }
          },
          "additionalProperties" => false
        }
      },
      "additionalProperties" => false
    }
    @implemented_extensions.each do |ext|
      ext_name = ext["name"]
      gen_ext_path = @gen_dir / "arch" / "ext" / "#{ext_name}.yaml"
      ext_yaml = YAML.safe_load gen_ext_path.read
      unless ext_yaml[ext_name]["params"].nil?
        ext_yaml[ext_name]["params"].each do |param_name, param_data|
          schema["properties"]["params"]["required"] << param_name
          schema["properties"]["params"]["properties"][param_name] = {
            "description" => param_data["description"]
          }.merge(param_data["schema"])
        end
      end
    end
    schema["properties"]["params"]["required"].uniq!

    FileUtils.mkdir_p @params_schema_path.dirname
    @params_schema_path.write JSON.dump(schema)
    @gen_params_schema_complete = true
  end

  # Initialize an Architecture Generator
  #
  # @param config_name [#to_s] The name of config located in the cfgs/ directory,
  def initialize(config_name)
    @validator = Validator.instance

    @name = config_name.to_s
    @cfg_dir = $root / "cfgs" / @name
    @gen_dir = $root / "gen" / @name

    raise "No config named '#{@name}'" unless File.exist?(@cfg_dir)

    @cfg_params_path = @cfg_dir / "params.yaml"
    raise "No params.yaml file in #{@cfg_dir}" unless @cfg_params_path.exist?

    cfg_impl_ext_path = @cfg_dir / "implemented_exts.yaml"
    raise "No implemented_exts.yaml file in #{@cfg_dir}" unless cfg_impl_ext_path.exist?

    @cfg_impl_ext = @validator.validate(cfg_impl_ext_path)["implemented_extensions"]
    raise "Validation failed" if @cfg_impl_ext.nil?

    cfg_opts_path = @cfg_dir / "cfg.yaml"
    @cfg_opts = YAML.load_file(cfg_opts_path)
    raise "Validation failed" if @cfg_opts.nil?
    raise "Validation failed: bad type" unless ["partially configured", "fully configured"].include?(@cfg_opts["type"])


    @params_schema_path = @gen_dir / "schemas" / "params_schema.json"

    @ext_gen_complete = false

  end

  # @return [Hash<String, Object>] Hash of parameter names to values
  def params
    return @params unless @params.nil?

    gen_params_schema

    # use validator to pick up defaults
    @params =
      Validator.instance.validate_str(
        File.read(@cfg_params_path),
        schema_path: @params_schema_path
      )["params"]
  end

  def assert(cond)
    raise "Assertion Failed" unless cond
  end
  private :assert

  def ext?(name)
    @implemented_extensions.any? { |ext| ext["name"] == name.to_s }
  end
  private :ext?

  # checks any "extra_validation" given by parameter definitions
  def params_extra_validation
    fork do
      # add parameters as a constant
      params.each do |key, value|
        self.class.const_set(key, value)
      end

      @implemented_extensions.each do |ext|
        ext_name = ext["name"]
        gen_ext_path = @gen_dir / "arch" / "ext" / "#{ext_name}.yaml"
        ext_yaml = YAML.safe_load gen_ext_path.read
        unless ext_yaml[ext_name]["params"].nil?
          ext_yaml[ext_name]["params"].each do |param_name, param_data|
            next unless param_data.key?("extra_validation")
            begin
              eval param_data["extra_validation"]
            rescue StandardError => e
              warn "While checking extension parameter #{ext_name}::#{param_name}.extra_validation"
              warn param_data["extra_validation"]
              warn e
              exit 1
            end
          end
        end
      end
    end
    Process.wait
    exit 1 unless $CHILD_STATUS.success?
  end
  private :params_extra_validation

  # validate the params.yaml file of a config.
  # 
  # This does several things:
  #
  #  * Generates a config-specific schmea based on:
  #  ** the extensions a config implements
  #  ** the parameters an implemented extension requires
  #  * Validates params.yaml against that configuration-specific schema
  #  * Checks any extra validation specified by 'extra_validation'
  def validate_params
    gen_ext_def
    add_implied_extensions
    check_extension_dependencies

    gen_params_schema
    @validator.validate @cfg_params_path

    params_extra_validation
  end

  # generate the architecture definition into the gen directory
  #
  # After calling this, gen/CFG_NAME/arch will be populated with up-to-date
  # parsed (with ERB) and merged (with overlay) architecture files.
  def generate
    # extensions need to be parsed first since we pull, e.g., exception codes from them
    gen_ext_def
    add_implied_extensions
    check_extension_dependencies

    gen_params_schema
    validate_params

    gen_csr_def

    gen_inst_def

    gen_arch_def

    @generate_done = true
  end

  def check_extension_dependencies
    @implemented_extensions.each do |ext|
      requirements = @required_ext_map[[ext["name"], ext["version"]]]
      satisfied = requirements.satisfied_by? do |req|
        @implemented_extensions.any? do |ext2|
          (ext2["name"] == req.name) && Gem::Requirement.new(req.version_requirement).satisfied_by?(Gem::Version.new(ext2["version"]))
        end
      end
      unless satisfied
        warn "Extension '#{ext}' requires extension '#{r}'; it must also be implemented"
        exit 1
      end
    end
  end

  # transitively adds any implied extensions to the @implemented_extensions list
  def add_implied_extensions
    return if @add_implied_extensions_complete == true

    @implemented_extensions.each do |ext|
      extras = @implied_ext_map[[ext["name"], ext["version"]]]
      next if extras.nil? || extras.empty?

      # turn it into an array if it isn't already
      extras = [extras] unless extras[0].is_a?(Array)
      extras.each do |extra_ext|
        unless all_known_exts.include?(extra_ext[0])
          raise "Implied extension '#{extra_ext}' for '#{ext}' is not defined"
        end

        next if @implemented_extensions.include?({
          "name" => extra_ext[0],
          "version" => extra_ext[1]
        })

        @implemented_extensions << {
          "name" => extra_ext[0],
          "version" => extra_ext[1]
        }
      end
    end

    @add_implied_extensions_complete = true
  end
  private :add_implied_extensions

  # @return [Array<String>] List of all implemented CSRs
  def implemented_csrs
    generate unless @generate_done
    @implemented_csrs
  end

  # @return [Array<String>] List of all implemented instructions
  def implemented_instructions
    generate unless @generate_done
    @implemented_instructions
  end

  # @return [Array<String>] List of all implemented extensions
  def implemented_extensions
    generate unless @generate_done
    @implemented_extensions
  end

  # Generate the config-specific, unified architecture spec data structure
  #
  def gen_arch_def
    csr_hash = Dir.glob(@gen_dir / "arch" / "csr" / "**" / "*.yaml").map do |f|
      csr_obj = YAML.load_file(f)
      csr_name = csr_obj.keys[0]
      [csr_name, csr_obj[csr_name]]
    end.to_h
    inst_hash = Dir.glob(@gen_dir / "arch" / "inst" / "**" / "*.yaml").map do |f|
      inst_obj = YAML.load_file(f)
      inst_name = inst_obj.keys[0]
      [inst_name, inst_obj[inst_name]]
    end.to_h
    ext_hash = Dir.glob(@gen_dir / "arch" / "ext" / "**" / "*.yaml").map do |f|
      ext_obj = YAML.load_file(f)
      ext_name = ext_obj.keys[0]
      [ext_name, ext_obj[ext_name]]
    end.to_h
    profile_family_hash = Dir.glob($root / "arch" / "profile_family" / "**" / "*.yaml").map do |f|
      profile_obj = YAML.load_file(f)
      profile_name = profile_obj.keys[0]
      profile_obj[profile_name]["name"] = profile_name
      profile_obj[profile_name]["__source"] = f
      [profile_name, profile_obj[profile_name]]
    end.to_h
    profile_hash = Dir.glob($root / "arch" / "profile" / "**" / "*.yaml").map do |f|
      profile_obj = YAML.load_file(f)
      profile_name = profile_obj.keys[0]
      profile_obj[profile_name]["name"] = profile_name
      profile_obj[profile_name]["__source"] = f
      [profile_name, profile_obj[profile_name]]
    end.to_h
    manual_hash = {}
    Dir.glob($root / "arch" / "manual" / "**" / "contents.yaml").map do |f|
      manual_version = YAML.load_file(f)
      manual_id = manual_version["manual"]
      unless manual_hash.key?(manual_id)
        manual_info_files = Dir.glob($root / "arch" / "manual" / "**" / "#{manual_id}.yaml")
        raise "Could not find manual info '#{manual_id}'.yaml, needed by #{f}" if manual_info_files.empty?
        raise "Found multiple manual infos '#{manual_id}'.yaml, needed by #{f}" if manual_info_files.size > 1
  
        manual_info_file = manual_info_files.first
        manual_hash[manual_id] = YAML.load_file(manual_info_file)
        manual_hash[manual_id]["__source"] = manual_info_file
        # TODO: schema validation
      end
  
      manual_hash[manual_id]["versions"] ||= []
      manual_hash[manual_id]["versions"] << YAML.load_file(f)
      # TODO: schema validation
      manual_hash[manual_id]["versions"].last["__source"] = f
    end
    crd_family_hash = Dir.glob($root / "arch" / "crd_family" / "**" / "*.yaml").map do |f|
      family_obj = YAML.load_file(f, permitted_classes: [Date])
      family_name = family_obj.keys[0]
      family_obj[family_name]["name"] = family_name
      family_obj[family_name]["__source"] = f
      [family_name, family_obj[family_name]]
    end.to_h
    crd_hash = Dir.glob($root / "arch" / "crd" / "**" / "*.yaml").map do |f|
      crd_obj = YAML.load_file(f, permitted_classes: [Date])
      crd_name = crd_obj.keys[0]
      crd_obj[crd_name]["name"] = crd_name
      crd_obj[crd_name]["__source"] = f
      [crd_name, crd_obj[crd_name]]
    end.to_h

    arch_def = {
      "type" => @cfg_opts["type"],
      "params" => params,
      "instructions" => inst_hash,
      "implemented_instructions" => @implemented_instructions,
      "extensions" => ext_hash,
      "implemented_extensions" => @implemented_extensions,
      "csrs" => csr_hash,
      "implemented_csrs" => @implemented_csrs,
      "profile_families" => profile_family_hash,
      "profiles" => profile_hash,
      "manuals" => manual_hash,
      "crd_families" => crd_family_hash,
      "crds" => crd_hash
    }

    yaml = YAML.dump(arch_def)
    arch_def_yaml = "# yaml-language-server: $schema=../../../arch/arch_schema.json\n\n#{yaml}"
    abs_arch_def_path = @gen_dir / "arch" / "arch_def.yaml"

    # return early if this arch_def hasn't changed
    # return if abs_arch_def_path.exist? && (abs_arch_def_path.read == arch_def_yaml)

    File.write(abs_arch_def_path, arch_def_yaml)

    # make sure it passes validation
    # begin
    #   @validator.validate_str(YAML.dump(arch_def), type: :arch)
    # rescue Validator::SchemaValidationError => e
    #   warn "While validating the unified architecture defintion at #{abs_arch_def_path}"
    #   raise e
    # end
  end
  private :gen_arch_def

  # @return [Object] An object that has a method (lowercase) or constant (uppercase) for every config option
  #                  so that obj.param_name or obj.PARAM_NAME gets you the value
  def env
    return @env unless @env.nil?

    @env = Class.new
    @env.instance_variable_set(:@cfg, @cfg)
    @env.instance_variable_set(:@params, @params)
    @env.instance_variable_set(:@arch_gen, self)

    # add each parameter, either as a method (lowercase) or constant (uppercase)
    @params.each do |key, value|
      if key[0].upcase == key[0]
        @env.const_set(key, value)
      else
        @env.class.define_method(key) { value }
      end
    end

    @cfg.each do |key, value|
      next if key == "params"

      if key[0].upcase == key[0]
        @env.const_set(key, value)
      else
        @env.class.define_method(key) { value }
      end
    end

    # add an asset_map function to get access to the artifact mapper
    @env.class.define_method(:asset_map) do
      return @asset_map unless @asset_map.nil?

      @asset_map = Class.new { extend AssetMap }
      @asset_map
    end

    @env.instance_exec do
      # method to check if a given extension (with an optional version number) is present
      #
      # @param ext_name [String,#to_s] Name of the extension
      # @param ext_requirement [String, #to_s] Version string, as a Gem Requirement (https://guides.rubygems.org/patterns/#pessimistic-version-constraint)
      # @return [Boolean] whether or not extension +ext_name+ meeting +ext_requirement+ is implemented in the config
      def ext?(ext_name, ext_requirement = ">= 0")
        if ext_requirement.nil?
          @cfg_impl_ext.any? do |e|
            e[0] == ext_name.to_s
          end
        else
          requirement = Gem::Requirement.create(ext_requirement.to_s)
          @cfg_impl_ext.any? do |e|
            e[0] == ext_name.to_s && requirement.satisfied_by?(Gem::Version.new(e[1]))
          end
        end
      end

      # @return [Array<Integer>] List of possible XLENs for any implemented mode
      def possible_xlens
        possible = [@params["XLEN"]]
        possible << 32 if ext?('S') && [32, 3264].include?(@params["SXLEN"])
        possible << 64 if ext?('S') && [32, 3264].include?(@params["SXLEN"])
        possible << 32 if ext?('U') && [32, 3264].include?(@params["UXLEN"])
        possible << 64 if ext?('U') && [32, 3264].include?(@params["UXLEN"])
        possible << 32 if ext?('H') && [32, 3264].include?(@params["VSXLEN"])
        possible << 64 if ext?('H') && [32, 3264].include?(@params["VSXLEN"])
        possible << 32 if ext?('H') && [32, 3264].include?(@params["VUXLEN"])
        possible << 64 if ext?('H') && [32, 3264].include?(@params["VUXLEN"])
        possible.uniq
      end

      # insert a hyperlink to an object
      # At this point, we insert a placeholder since it will be up
      # to the backend to create a specific link
      #
      # @params type [Symbol] Type (:section, :csr, :inst, :ext)
      # @params name [#to_s] Name of the object
      def link_to(type, name)
        "%%LINK%#{type};#{name}%%"
      end

      # info on interrupt and exception codes

      # @returns [Hash<Integer, String>] architecturally-defined exception codes and their names
      def exception_codes
        @arch_gen.exception_codes
      end

      # returns [Hash<Integer, String>] architecturally-defined interrupt codes and their names
      def interrupt_codes
        @arch_gen.interrupt_codes
      end
    end

    @env
  end
  private :env

  def merge_helper(base_obj, updates, path_so_far)
    obj = path_so_far.empty? ? updates : updates.dig(*path_so_far)
    obj.each do |key, value|
      if value.is_a?(Hash)
        merge_helper(base_obj, updates, (path_so_far + [key]))
      else
        (path_so_far + [key]).each_with_index do |k, idx|
          base_obj[k] ||= {}
          if idx != path_so_far.size
            base_obj = base_obj[k]
          else
            base_obj[k] = value
          end
        end
      end
    end
  end
  private :merge_helper

  # overwrites base_obj with any data in update
  #
  # @param base_obj [Hash] Base object
  # @param updates [Hash] Object with overlays
  # @return [Hash] Updated object
  def merge(base_obj, updates) = merge_helper(base_obj, updates, [])
  private :merge

  # @param type [Symbol] Type of the object (@see Validator::SCHEMA_PATHS)
  # @param name [#to_s] Name of the object
  # @return [Pathname,nil] Path to architecture definition template for a given type:name, or nil if none exists
  def arch_path_for(type, name)
    source_matches = Dir.glob($root / "arch" / type.to_s / "**" / "#{name}.yaml")
    raise "Multiple source matches: #{source_matches} for #{type}:#{name}" if source_matches.size > 1
    return nil if source_matches.empty? # not an error, might be a full overlay

    Pathname.new(source_matches[0])
  end
  private :arch_path_for

  # @param type [Symbol] Type of the object (@see Validator::SCHEMA_PATHS)
  # @param name [#to_s] Name of the object
  # @return [Pathname,nil] Path to architecture overlay for a given type:name, or nil if none exists
  def arch_overlay_path_for(type, name)
    source_matches = Dir.glob(@cfg_dir / "arch_overlay" / type.to_s / "**" / "#{name}.yaml")
    raise "Multiple source matches in overlay: #{source_matches} for #{type}:#{name}" if source_matches.size > 1
    return nil if source_matches.empty? # not an error, might be a full overlay

    Pathname.new(source_matches[0])
  end
  private :arch_overlay_path_for

  # @param type [Symbol] Type of the object (@see Validator::SCHEMA_PATHS)
  # @return [Pathname,nil] Path to schema for type
  def schema_path_for(type) = Validator::SCHEMA_PATHS[type]
  private :schema_path_for

  # Render a architecture definition file and save it to gen_dir / .rendered_arch
  #
  # Will not re-render if rendered file already exists and sources have not changed
  #
  # @param type [Symbol] Type of the object (@see Validator::SCHEMA_PATHS)
  # @param name [#to_s] Name of the object
  # @param extra_env [Hash,NilObject] Optional hash with extra enviornment variables for the render
  # @return [Pathname,nil] Path to generated file, or nil if there is no (valid) definition for type,name
  def gen_rendered_arch_def(type, name, extra_env = {})
    gen_path = @gen_dir / ".rendered_arch" / type.to_s / "#{name}.yaml"

    source_path = arch_path_for(type, name)
    return nil if source_path.nil?

    schema_path = schema_path_for(type)

    if gen_path.exist?
      # this already exists...see if we need to regenerate it
      dep_mtime = [File.mtime(__FILE__), source_path.mtime, schema_path.mtime].max
      return gen_path if gen_path.mtime >= dep_mtime # no update needed
    end

    trace "Rendering architecture file for #{type}:#{name}"

    # render the source template
    current_env = env.clone
    extra_env&.each { |k, v| current_env.define_singleton_method(k) { v } }
    rendered_def = Tilt["erb"].new(source_path, trim: "-").render(current_env)

    # see if the rendering was empty, meaning that the def isn't valid in this config
    return nil if rendered_def.nil?

    # write the object
    FileUtils.mkdir_p gen_path.dirname
    File.write(gen_path, rendered_def)

    # verify
    begin
      @validator.validate_str(rendered_def, type:)
    rescue Validator::SchemaValidationError => e
      warn "#{type} definition in #{source_path} did not validate"
      raise e
    end

    def_obj = YAML.safe_load(rendered_def)

    raise "#{type} name ('#{name}') must match key in defintion ('#{def_obj.keys[0]}')" if name.to_s != def_obj.keys[0]

    # return path to generated file
    gen_path
  end
  private :gen_rendered_arch_def

  # Render a architecture overlay definition file and save it to gen_dir / .rendered_overlay_arch
  #
  # Will not re-render if rendered file already exists and sources have not changed
  #
  # @param type [Symbol] Type of the object (@see Validator::SCHEMA_PATHS)
  # @param name [#to_s] Name of the object
  # @param extra_env [Hash,NilObject] Optional hash with extra enviornment variables for the render
  # @return [Pathname] Path to generated file
  def gen_rendered_arch_overlay_def(type, name, extra_env = {})
    gen_path = @gen_dir / ".rendered_overlay_arch" / type.to_s / "#{name}.yaml"

    source_path = arch_overlay_path_for(type, name)
    return nil if source_path.nil?

    if gen_path.exist?
      # this already exists...see if we need to regenerate it
      dep_mtime = [File.mtime(__FILE__), source_path.mtime].max
      return gen_path if gen_path.mtime >= dep_mtime # no update needed
    end

    trace "Rendering overlay file for #{type}:#{name}"

    # render the source template
    current_env = env.clone
    extra_env&.each { |k, v| current_env.define_singleton_method(k) { v } }
    rendered_def = Tilt["erb"].new(source_path, trim: "-").render(current_env)

    def_obj = YAML.safe_load(rendered_def)

    raise "#{type} name (#{name}) must match key in defintion (#{def_obj.keys[0]})" if name.to_s != def_obj.keys[0]

    # write the object
    FileUtils.mkdir_p gen_path.dirname
    File.write(gen_path, YAML.dump(def_obj))

    # return path to generated file
    gen_path
  end
  private :gen_rendered_arch_overlay_def

  # generate a merged definition from rendered arch and overlay, and write it to gen / .merged_arch
  #
  # Skips if gen file already exists and sources are older
  #
  # @param type [Symbol] Type of the object (@see Validator::SCHEMA_PATHS)
  # @param arch_path [Pathname,nil] Path to rendered arch defintion, or nil if none
  # @param overlay_path [Pathname,nil] Path to rendered overlay, or nil if none
  # @return [Pathname] Path to generated merged definition
  def gen_merged_def(type, arch_path, overlay_path)
    raise "Must have at least one of arch_path or overlay_path" if arch_path.nil? && overlay_path.nil?

    name = arch_path.nil? ? overlay_path.basename(".yaml") : arch_path.basename(".yaml")

    merged_path = @gen_dir / ".merged_arch" / type.to_s / "#{name}.yaml"

    if merged_path.exist?
      arch_time = arch_path.nil? ? Time.new(0) : arch_path.mtime
      overlay_time = overlay_path.nil? ? Time.new(0) : overlay_path.mtime
      dep_mtime = [arch_time, overlay_time].max
      return merged_path if merged_path.mtime >= dep_mtime
    end

    trace "Rendering merged file for #{type}:#{name}"

    FileUtils.mkdir_p merged_path.dirname
    if overlay_path.nil?
      # no overlay, just copy arch
      FileUtils.cp arch_path, merged_path
    elsif arch_path.nil?
      # no arch, overlay is arch
      FileUtils.cp overlay_path, merged_path
    else
      # arch and overlay, do the merge
      arch_obj = YAML.load_file(arch_path)
      overlay_obj = YAML.load_file(overlay_path)

      merge(arch_obj, overlay_obj)
      merged_path.write YAML.dump(arch_obj)
    end

    begin
      @validator.validate_str(merged_path.read, type:)
    rescue Validator::SchemaValidationError => e
      warn "Merged #{type} definition in #{merged_path} did not validate"
      raise e
    end

    merged_path
  end
  private :gen_merged_def

  # given a CSR name, determine if it is supposed to exist in the config, and, if so,
  # render the result and add it to the running list of extant CSRs
  #
  # @param csr_name [#to_s] CSR name
  # @param extra_env [Hash] Extra enviornment variables to be used when parsing the CSR definition template
  def maybe_add_csr(csr_name, extra_env = {})
    arch_path         = arch_path_for(:csr, csr_name) # gen_rendered_arch_def(:csr, csr_name, extra_env)
    arch_overlay_path = arch_overlay_path_for(:csr, csr_name) # gen_rendered_arch_overlay_def(:csr, csr_name, extra_env)

    # return immediately if this CSR isn't defined in this config
    raise "No arch or overlay for sr #{csr_name}" if arch_path.nil? && arch_overlay_path.nil?

    merged_path = gen_merged_def(:csr, arch_path, arch_overlay_path)

    merged_content = File.read(merged_path)
    arch_content = arch_path.nil? ? "" : File.read(arch_path)
    arch_overlay_content = arch_path.nil? ? "" : File.read(arch_path)

    # figure out where the original file can be found:
    #   * arch_path if there is no contribution from arch_overlay
    #   * arch_overlay_path if there is no contribution from arch (i.e., a custom instruction)
    #   * merged_path if there are contributions from both
    og_path =
      if arch_content == merged_content
        arch_path_for(:csr, csr_name)
      elsif arch_overlay_content == merged_content
        arch_overlay_path_for(:csr, csr_name)
      else
        merged_path
      end

    # get the csr data (not including the name key), which is redundant at this point
    csr_data = YAML.load_file(merged_path)[csr_name]
    csr_data["name"] = csr_name
    csr_data["fields"].each { |n, f| f["name"] = n }
    csr_data["__source"] = og_path.to_s

    csr_yaml = YAML.dump({ csr_name => csr_data})
    begin
      csr_data = @validator.validate_str(csr_yaml, type: :csr)
    rescue Validator::SchemaValidationError => e
      warn "Instruction definition in #{merged_path} did not validate"
      raise e
    end

    csr_obj = Csr.new(csr_data[csr_name])
    belongs =
      csr_obj.exists_in_cfg?(
        possible_xlens,
        @cfg_impl_ext.map { |e| ExtensionVersion.new(e[0], e[1]) }
      )

    @implemented_csrs ||= []
    @implemented_csrs << csr_name if belongs

    gen_csr_path = @gen_dir / "arch" / "csr" / csr_obj.primary_defined_by / "#{csr_name}.yaml"
    FileUtils.mkdir_p gen_csr_path.dirname
    gen_csr_path.write csr_yaml
  end
  private :maybe_add_csr

  # return list of all known CSR names, even those not part of this config
  # Includes both CSRs defined in arch/ and those added through an overlay of the config
  #
  # @return [Array<String>] List of all known CSR names
  def all_known_csrs
    (
      Dir.glob($root / "arch" / "csr" / "**" / "*.yaml") +          # CSRs in arch/
      Dir.glob(@cfg_dir / "arch_overlay" / "csr" / "**" / "*.yaml") # CSRs in cfg/arch_overlay/
    ).map do |f|
      File.basename(f, ".yaml")
    end
  end
  private :all_known_csrs

  # generate all CSR definitions for the config
  def gen_csr_def
    csr_list = all_known_csrs

    csr_list.each do |csr_name|
      maybe_add_csr(csr_name)
    end
  end
  private :gen_csr_def

  # return list of all known extension names, even those not part of this config
  # Includes both extensions defined in arch/ and those added through an overlay of the config
  #
  # @return [Array<String>] List of all known extension names
  def all_known_exts
    (
      Dir.glob($root / "arch" / "ext" / "**" / "*.yaml") +          # exts in arch/
      Dir.glob(@cfg_dir / "arch_overlay" / "ext" / "**" / "*.yaml") # exts in cfg/arch_overlay/
    ).map do |f|
      File.basename(f, ".yaml")
    end
  end

  def maybe_add_ext(ext_name)
    arch_path         = arch_path_for(:ext, ext_name) # gen_rendered_arch_def(:ext, ext_name)
    arch_overlay_path = arch_overlay_path_for(:ext, ext_name) # gen_rendered_arch_overlay_def(:ext, ext_name)

    # return immediately if this ext isn't defined
    return if arch_path.nil? && arch_overlay_path.nil?

    merged_path = gen_merged_def(:ext, arch_path, arch_overlay_path)

    ext_obj = YAML.load_file(merged_path)[ext_name]
    ext_obj["name"] = ext_name

    @implied_ext_map ||= {}
    @required_ext_map ||= {}

    ext_obj["versions"].each do |v|
      implies = case v["implies"]
                when nil
                  []
                when Array
                  v["implies"][0].is_a?(Array) ? v["implies"] : [v["implies"]]
                end
      requires = case v["requires"]
                 when nil
                   AlwaysTrueSchemaCondition.new
                 when Hash
                   SchemaCondition.new(v["requires"])
                 else
                   SchemaCondition.new({"oneOf" => [v["requires"]]})
                 end
      raise "Bad condition" if requires.nil?

      @implied_ext_map[[ext_name, v["version"].to_s]] = implies.map { |i| [i[0], i[1].to_s] }
      @required_ext_map[[ext_name, v["version"].to_s]] = requires
    end

    belongs =
      @cfg_impl_ext.any? { |e| e[0] == ext_name }
    @implemented_extensions ||= []
    if belongs
      @implemented_extensions << {
        "name" => ext_name,
        "version" => @cfg_impl_ext.select { |e| e[0] == ext_name }[0][1].to_s
      }
    end

    if belongs
      # check that the version number exists, too
      cfg_ext = @cfg_impl_ext.select { |e| e[0] == ext_name }[0]

      if ext_obj["versions"].select { |v| v["version"] == cfg_ext[1] }.empty?
        raise "Configured version for extension #{extension_name} not defined"
      end
    end

    gen_ext_path = @gen_dir / "arch" / "ext" / "#{ext_name}.yaml"
    FileUtils.mkdir_p gen_ext_path.dirname
    gen_ext_path.write YAML.dump({ ext_name => ext_obj })
  end
  private :maybe_add_ext

  # generate parsed and merged definitions for all extensions
  def gen_ext_def
    return if @ext_gen_complete == true

    ext_list = all_known_exts

    ext_list.each do |ext_name|
      maybe_add_ext(ext_name)
    end

    @ext_gen_complete = true
  end
  private :gen_ext_def

  # Returns mapping of exception codes to text name.
  #
  # @return [Hash<Integer, String>] Mapping of exception code number to text name
  def exception_codes
    return @exception_codes unless @exception_codes.nil?

    gen_ext_def unless @ext_gen_complete

    @exception_codes = {}
    Dir.glob(@gen_dir / "arch" / "ext" / "*.yaml") do |ext_path|
      ext_obj = YAML.load_file(ext_path)
      ext_obj = ext_obj[ext_obj.keys[0]]
      if ext_obj.key?("exception_codes")
        ext_obj["exception_codes"].each do |exception_code|
          @exception_codes[exception_code["num"]] = exception_code["name"]
        end
      end
    end
    @exception_codes
  end

  # Returns mapping of interrupt codes to text name.
  #
  # @return [Hash<Integer, String>] Mapping of interrupt code number to text name
  def interrupt_codes
    return @interrupt_codes unless @interrupt_codes.nil?

    gen_ext_def unless @ext_gen_complete

    @interrupt_codes = {}
    Dir.glob(@gen_dir / "arch" / "ext" / "*.yaml") do |ext_path|
      ext_obj = YAML.load_file(ext_path)
      ext_obj = ext_obj[ext_obj.keys[0]]
      if ext_obj.key?("interrupt_codes")
        ext_obj["interrupt_codes"].each do |interrupt_code|
          @interrupt_codes[interrupt_code["num"]] = interrupt_code["name"]
        end
      end
    end
    @interrupt_codes
  end

  def possible_xlens
    possible_xlens = [params["XLEN"]]
    if @cfg_impl_ext.any? { |e| e[0] == "S" }
      possible_xlens << 32 if [32, 3264].include?(params["SXLEN"])
      possible_xlens << 64 if [64, 3264].include?(params["SXLEN"])
    end
    if @cfg_impl_ext.any? { |e| e[0] == "U" }
      possible_xlens << 32 if [32, 3264].include?(params["UXLEN"])
      possible_xlens << 64 if [64, 3264].include?(params["UXLEN"])
    end
    if @cfg_impl_ext.any? { |e| e[0] == "H" }
      possible_xlens << 32 if [32, 3264].include?(params["VSXLEN"])
      possible_xlens << 32 if [32, 3264].include?(params["VUXLEN"])
      possible_xlens << 64 if [64, 3264].include?(params["VSXLEN"])
      possible_xlens << 64 if [64, 3264].include?(params["VUXLEN"])
    end
    possible_xlens
  end
  private :possible_xlens

  # add an instruction to the running list of instructions for this config if it should be included
  #
  # @param inst_name [#to_s] instruction name
  # @param extra_env [Hash] Extra options to add into the rendering enviornment
  def maybe_add_inst(inst_name, extra_env = {})
    arch_path         = arch_path_for(:inst, inst_name) # gen_rendered_arch_def(:inst, inst_name, extra_env)
    arch_overlay_path = arch_overlay_path_for(:inst, inst_name) # gen_rendered_arch_overlay_def(:inst, inst_name, extra_env)

    # return immediately if inst isn't defined in this config
    raise "No arch or overlay for instruction #{inst_name}" if arch_path.nil? && arch_overlay_path.nil?

    merged_path = gen_merged_def(:inst, arch_path, arch_overlay_path)

    merged_content = File.read(merged_path)
    arch_content = arch_path.nil? ? "" : File.read(arch_path)
    arch_overlay_content = arch_path.nil? ? "" : File.read(arch_path)

    # figure out where the original file can be found:
    #   * arch_path if there is no contribution from arch_overlay
    #   * arch_overlay_path if there is no contribution from arch (i.e., a custom instruction)
    #   * merged_path if there are contributions from both
    og_path =
      if arch_content == merged_content
        arch_path_for(:inst, inst_name)
      elsif arch_overlay_content == merged_content
        arch_overlay_path_for(:inst, inst_name)
      else
        merged_path
      end

    # get the inst data (not including the name key), which is redundant at this point
    inst_data = YAML.load_file(merged_path)
    raise "The first and only key of #{arch_path} must be '#{inst_name}" unless inst_data.key?(inst_name)
    inst_data = inst_data[inst_name]

    inst_data["name"] = inst_name
    inst_data["__source"] = og_path.to_s

    inst_yaml = YAML.dump({ inst_name => inst_data})
    begin
      inst_data = @validator.validate_str(inst_yaml, type: :inst)
    rescue Validator::SchemaValidationError => e
      warn "Instruction definition in #{gen_inst_path} did not validate"
      raise e
    end

    inst_obj = Instruction.new(inst_data[inst_name], nil)
    possible_xlens = [params["XLEN"]]
    if @cfg_impl_ext.any? { |e| e[0] == "S" }
      possible_xlens << 32 if [32, 3264].include?(params["SXLEN"])
      possible_xlens << 64 if [64, 3264].include?(params["SXLEN"])
    end
    if @cfg_impl_ext.any? { |e| e[0] == "U" }
      possible_xlens << 32 if [32, 3264].include?(params["UXLEN"])
      possible_xlens << 64 if [64, 3264].include?(params["UXLEN"])
    end
    if @cfg_impl_ext.any? { |e| e[0] == "H" }
      possible_xlens << 32 if [32, 3264].include?(params["VSXLEN"])
      possible_xlens << 32 if [32, 3264].include?(params["VUXLEN"])
      possible_xlens << 64 if [64, 3264].include?(params["VSXLEN"])
      possible_xlens << 64 if [64, 3264].include?(params["VUXLEN"])
    end
    belongs =
      inst_obj.exists_in_cfg?(
        possible_xlens.uniq,
        @cfg_impl_ext.map { |e| ExtensionVersion.new(e[0], e[1]) }
      )

    @implemented_instructions ||= []
    @implemented_instructions << inst_name if belongs

    raise "?" if inst_obj.primary_defined_by.nil?
    gen_inst_path = @gen_dir / "arch" / "inst" / inst_obj.primary_defined_by / "#{inst_name}.yaml"
    FileUtils.mkdir_p gen_inst_path.dirname
    gen_inst_path.write inst_yaml


    # @instructions << inst_def
    # @inst_hash ||= {}
    # @inst_hash[inst_name] = @instructions.last
  end
  private :maybe_add_inst

  # return list of all known instruction names, even those not part of this config
  # Includes both instructionss defined in arch/ and those added through an overlay of the config
  #
  # @return [Array<String>] List of all known instruction names
  def all_known_insts
    (
      Dir.glob($root / "arch" / "inst" / "**" / "*.yaml") +          # instructions in arch/
      Dir.glob(@cfg_dir / "arch_overlay" / "inst" / "**" / "*.yaml") # instructions in cfg/arch_overlay/
    ).map do |f|
      File.basename(f, ".yaml")
    end
  end
  private :all_known_insts

  # generate all parsed / merged instruction definitions
  def gen_inst_def
    inst_list = all_known_insts

    inst_list.each do |inst_name|
      maybe_add_inst(inst_name)
    end
  end
  private :gen_inst_def

end

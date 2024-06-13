# frozen_string_literal: true

require "erb"
require "pathname"
require "rake/application"
require "rubygems/requirement"
require "tilt"
require "yaml"

require_relative "validate"

$root = Pathname.new(__FILE__).dirname.dirname.realpath if $root.nil?

# Class to help parse parameterized arch definitions and generate a unified configuration
#
# ArchGen is initialized with a config name, which *must* be the name of a
# directory under cfgs/
#
# The unified config is returned from {ArchGen.arch_def}.
#
# You can also get:
#
#  * An array of CSR definitions from {ArchGen.csrs}
#  * An array of Instruction definitions from {ArchGen.instructions}
#  * An array of Extension definitions from {ArchGen.extensions}
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

  # Initialize an Architecture Generator
  #
  # @param config_name [#to_s] The name of config located in the cfgs/ directory,
  def initialize(config_name)
    @validator = Validator.new

    @name = config_name.to_s
    @cfg_dir = $root / "cfgs" / @name
    @gen_dir = $root / "gen" / @name

    raise "No config named '#{@name}'" unless File.exist?(@cfg_dir)

    cfg_params_path = "#{@cfg_dir}/params.yaml"
    @cfg = @validator.validate_str(File.read(cfg_params_path), type: :config)
    @params = @cfg.fetch("params")

    unless @params["NAME"] == @name
      raise "Config name (#{@params['NAME']}) in params.yaml does not match directory path (#{@name})"
    end

    @opcode_data = YAML.load_file("#{$root}/ext/riscv-opcodes/instr_dict.yaml")
    @ext_gen_complete = false
  end

  # generate the architecture definition into the gen directory
  #
  # After calling this, gen/CFG_NAME/arch will be populated with up-to-date
  # parsed (with ERB) and merged (with overlay) architecture files.
  def generate
    # extensions need to be parsed first since we pull, e.g., exception codes from them
    gen_ext_def
    gen_csr_def
    gen_inst_def

    gen_arch_def
  end

  # Generate the config-specific, unified architecture spec data structure
  #
  def gen_arch_def
    csr_hash = Dir.glob(@gen_dir / "arch" / "csr" / "**" / "*.yaml").map { |f|
      csr_obj = YAML.load_file(f)
      csr_name = csr_obj.keys[0]
      [csr_name, csr_obj[csr_name]]
    }.to_h
    inst_hash = Dir.glob(@gen_dir / "arch" / "inst" / "**" / "*.yaml").map { |f|
      inst_obj = YAML.load_file(f)
      inst_name = inst_obj.keys[0]
      [inst_name, inst_obj[inst_name]]
    }.to_h
    ext_hash = Dir.glob(@gen_dir / "arch" / "ext" / "**" / "*.yaml").map { |f|
      ext_obj = YAML.load_file(f)
      ext_name = ext_obj.keys[0]
      [ext_name, ext_obj[ext_name]]
    }.to_h

    arch_def = {
      "params" => params,
      "instructions" => inst_hash,
      "implemented_instructions" => @implemented_instructions,
      "extensions" => ext_hash,
      "implemented_extensions" => @implemented_extensions,
      "csrs" => csr_hash,
      "implemented_csrs" => @implemented_csrs
    }

    pp @implemented_csrs
    yaml = YAML.dump(arch_def)
    arch_def_yaml = "# yaml-language-server: $schema=../../../arch/arch_schema.json\n\n#{yaml}"
    abs_arch_def_path = @gen_dir / "arch" / "arch_def.yaml"

    # return early if this arch_def hasn't changed
    # return if abs_arch_def_path.exist? && (abs_arch_def_path.read == arch_def_yaml)

    File.write(abs_arch_def_path, arch_def_yaml)

    # make sure it passes validation
    begin
      @validator.validate_str(YAML.dump(arch_def), type: :arch)
    rescue Validator::ValidationError => e
      warn "While validating the unified architecture defintion at #{abs_arch_def_path}"
      raise e
    end
  end

  # @return [Object] An object that has a method (lowercase) or constant (uppercase) for every config option
  #                  so that obj.param_name or obj.PARAM_NAME gets you the value
  def env
    return @env unless @env.nil?

    @env = Class.new
    @env.instance_variable_set(:@cfg, @cfg)
    @env.instance_variable_set(:@arch_gen, self)

    # add each parameter, either as a method (lowercase) or constant (uppercase)
    @params.each do |key, value|
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
      # @param [String,Symbol] Name of the extension
      # @param [String] Version string, as a Gem Requirement (https://guides.rubygems.org/patterns/#pessimistic-version-constraint)
      # @return [Boolean] whether or not extension 'ext_name' is implemented in the config
      def ext?(ext_name, ext_version = nil)
        if ext_version.nil?
          @cfg["extensions"].any? do |e|
            e[0] == ext_name.to_s
          end
        else
          requirement = Gem::Requirement.create(ext_version)
          @cfg["extensions"].any? do |e|
            e[0] == ext_name.to_s && requirement.satisfied_by?(e[1])
          end
        end
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
  def merge(base_obj, updates)
    merge_helper(base_obj, updates, [])
  end
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
  def schema_path_for(type)
    Validator::SCHEMA_PATHS[type]
  end
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

    trace "Rendering architecture file for #{type}:#{name}" # #{[File.mtime(__FILE__), source_path.mtime, schema_path.mtime].max} #{gen_path.mtime}"

    # render the source template
    current_env = env.clone
    extra_env&.each { |k, v| current_env.define_singleton_method(k) { v } }
    rendered_def = Tilt["erb"].new(source_path, trim: "-").render(current_env)

    # see if the rendering was empty, meaning that the def isn't valid in this config
    return nil if rendered_def.nil?

    # verify
    begin
      @validator.validate_str(rendered_def, type: type)
    rescue Validator::ValidationError => e
      warn "#{type} definition in #{source_path} did not validate"
      raise e
    end

    def_obj = YAML.safe_load(rendered_def)

    raise "#{type} name must match key in defintion" if name.to_s != def_obj.keys[0]

    # write the object
    FileUtils.mkdir_p gen_path.dirname
    File.write(gen_path, YAML.dump(def_obj))

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

    raise "#{type} name must match key in defintion" if name.to_s != def_obj.keys[0]

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

    name = arch_path.nil? ? overlay_path.basename('.yaml') : arch_path.basename('.yaml')

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
      @validator.validate_str(merged_path.read, type: type)
    rescue Validator::ValidationError => e
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
    arch_path         = gen_rendered_arch_def(:csr, csr_name, extra_env)
    arch_overlay_path = gen_rendered_arch_overlay_def(:csr, csr_name, extra_env)

    # return immediately if this CSR isn't defined in this config
    raise "No arch or overlay for sr #{csr_name}" if arch_path.nil? && arch_overlay_path.nil?

    merged_path = gen_merged_def(:csr, arch_path, arch_overlay_path)

    # get the csr data (not including the name key), which is redundant at this point
    csr_obj = YAML.load_file(merged_path)[csr_name]

    # filter fields to exclude any definedBy an extension not supported in this config
    csr_obj["fields"].select! do |_field_name, field_data|
      break true if field_data["definedBy"].nil?

      field_defined_by = field_data["definedBy"]
      field_defined_by = [field_defined_by] unless field_defined_by.is_a?(Array)

      field_defined_by.each do |ext_name|
        break true if @cfg["extensions"].any? { |ext| ext[0] == ext_name }
      end
      false
    end

    # add the CSR, unless it is from an extension not supported in this config
    csr_defined_by = csr_obj["definedBy"]
    csr_defined_by = [csr_defined_by] unless csr_defined_by.is_a?(Array) # turn into an array if needed

    # add the name in just for convienence
    csr_obj["name"] = csr_name

    belongs =
      # check that the defining extension is implemented in the config
      csr_defined_by.any? { |ext_name| !@cfg["extensions"].select { |ext| ext[0] == ext_name }.empty? } &&
      # and that we have the right base, if the CSR exists in only one
      (csr_obj["base"].nil? || csr_obj["base"] == @params["XLEN"])
    @implemented_csrs ||= []
    @implemented_csrs << csr_name if belongs

    gen_csr_path = @gen_dir / "arch" / "csr" / csr_obj["definedBy"] / "#{csr_name}.yaml"
    FileUtils.mkdir_p gen_csr_path.dirname
    gen_csr_path.write YAML.dump({ csr_name => csr_obj})
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
    ).map { |f|
      File.basename(f, ".yaml")
    }
  end
  private :all_known_csrs

  # generate all CSR definitions for the config
  def gen_csr_def
    csr_list = all_known_csrs

    csr_list.each do |csr_name|
      maybe_add_csr(csr_name)
    end
  end

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
    arch_path         = gen_rendered_arch_def(:ext, ext_name)
    arch_overlay_path = gen_rendered_arch_overlay_def(:ext, ext_name)

    # return immediately if this CSR isn't defined in this config
    return if arch_path.nil? && arch_overlay_path.nil?

    merged_path = gen_merged_def(:ext, arch_path, arch_overlay_path)

    ext_obj = YAML.load_file(merged_path)[ext_name]

    belongs =
      @cfg["extensions"].any? { |e| e[0] == ext_name }
    @implemented_extensions ||= []
    @implemented_extensions << { "name" => ext_name, "version" => @cfg["extensions"].select { |e| e[0] == ext_name }[0][1]} if belongs

    if belongs
      # check that the version number exists, too
      cfg_ext = @cfg["extensions"].select { |e| e[0] == ext_name }[0]

      if ext_obj["versions"].select { |v| v["version"] == cfg_ext[1] }.empty?
        raise "Configured version for extension #{extension_name} not defined"
      end
    end

    gen_ext_path = @gen_dir / "arch" / "ext" / "#{ext_name}.yaml"
    FileUtils.mkdir_p gen_ext_path.dirname
    FileUtils.cp merged_path, gen_ext_path
  end
  private :maybe_add_ext

  # generate parsed and merged definitions for all extensions
  def gen_ext_def
    ext_list = all_known_exts

    ext_list.each do |ext_name|
      maybe_add_ext(ext_name)
    end

    @ext_gen_complete = true
  end

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

  # add an instruction to the running list of instructions for this config if it should be included
  #
  # @param inst_name [#to_s] instruction name
  # @param extra_env [Hash] Extra options to add into the rendering enviornment
  def maybe_add_inst(inst_name, extra_env = {})
    arch_path         = gen_rendered_arch_def(:inst, inst_name, extra_env)
    arch_overlay_path = gen_rendered_arch_overlay_def(:inst, inst_name, extra_env)

    # return immediately if inst isn't defined in this config
    raise "No arch or overlay for instruction #{inst_name}" if arch_path.nil? && arch_overlay_path.nil?

    merged_path = gen_merged_def(:inst, arch_path, arch_overlay_path)

    # get the inst data (not including the name key), which is redundant at this point
    inst_obj = YAML.load_file(merged_path)[inst_name]
    inst_obj["name"] = inst_name

    raise "no riscv-opcode data for #{inst_obj['name']}" unless @opcode_data.key?(inst_obj["name"].tr(".", "_"))

    opcode_str = @opcode_data[inst_obj["name"].tr(".", "_")]["extension"][0]

    raise "Bad opcode string" unless opcode_str =~ /rv((32)|(64))?_([a-zA-Z0-9]+)/

    base = ::Regexp.last_match(1)
    defined_in = ::Regexp.last_match(4)

    inst_obj["definedBy"] = defined_in.capitalize
    inst_obj["base"] = base.to_i unless base.nil?

    # add the instruction, unless it is from an extension not supported in this config
    belongs =
      (base.nil? || (base.to_i == @params["XLEN"])) &&
      @cfg["extensions"].any? { |e| e[0].downcase == defined_in }
    @implemented_instructions ||= []
    @implemented_instructions << inst_name if belongs

    gen_inst_path = @gen_dir / "arch" / "inst" / inst_obj["definedBy"] / "#{inst_name}.yaml"
    FileUtils.mkdir_p gen_inst_path.dirname
    gen_inst_path.write YAML.dump({ inst_name => inst_obj})

    begin
      @validator.validate_str(File.read(gen_inst_path), type: :inst)
    rescue Validator::ValidationError => e
      warn "Instruction definition in #{gen_inst_path} did not validate"
      raise e
    end

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
    ).map { |f|
      File.basename(f, ".yaml")
    }
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

  # @return [Hash<String, Object>] Hash of parameters for the config
  def params
    @params.select { |k, _v| k.upcase == k }
  end
end

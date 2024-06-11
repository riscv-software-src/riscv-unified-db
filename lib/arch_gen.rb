# frozen_string_literal: true

require "erb"
require "pathname"
require "rubygems/requirement"
require "tilt"
require "yaml"

require_relative "validate"

$root = Pathname.new(__FILE__).dirname.dirname.realpath if $root.nil?

# Class with utilities to help parse parameterized arch definitions
# and generate a unified configuration
class ArchGen
  # configuration name
  attr_reader :name

  # path where the result will be written
  attr_reader :gen_dir

  # Initialize a config
  # @param config_name_or_path [String] The name of config located in the cfgs/ directory,
  def initialize(config_name)
    @validator = Validator.new

    @name = config_name
    @cfg_dir = $root / "cfgs" / config_name
    @gen_dir = $root / "gen" / config_name / "arch"

    raise "No config named '#{config_name}'" unless File.exist?(@cfg_dir)

    cfg_params_path = "#{@cfg_dir}/params.yaml"
    @cfg = @validator.validate_str(File.read(cfg_params_path), type: :config)
    @params = @cfg.fetch("params")

    unless @params["NAME"] == config_name.to_s
      raise "Config name (#{@params['NAME']}) must match directory path (#{config_name})"
    end

    # get overrides
    @overrides = {
      inst: {},
      csr: {},
      ext: {}
    }
    if (@cfg_dir / "overrides").exist?
      (@cfg_dir / "overrides").children.each do |child|
        next unless child.directory?

        case child.basename.to_s
        when "inst", "csr", "ext"
          override_files = Dir.glob(child / "*.yaml") + Dir.glob(child / "**" / "*.yaml")
          override_files.each do |f|
            data = YAML.safe_load(File.read(f))
            unless data.is_a?(Hash) && data.size == 1
              raise "Bad #{child.basename} override; must be a hash with the #{child.basename} name as the only key"
            end

            @overrides[child.basename.to_s.to_sym][data.keys[0]] = data[data.keys[0]]
          end
        else
          raise "Override must be in a config subdirectory named 'inst', 'csr', or 'ext' (got '#{child.basename}')"
        end
      end
    end

    @opcode_data = YAML.load_file("#{$root}/ext/riscv-opcodes/instr_dict.yaml")

    @inst_path_map = {}
  end

  # generate the architecture definition for the config, writing result to
  # $root / gen / config_name
  #
  # @params overwrite_same [Boolean]
  #   If false, files will be overwritten even if they would be written with identical content
  #   (affecting, e.g., make dependency resolution)
  def generate(overwrite_same: false)
    instructions.each do |inst|
      defining_ext_name = inst["definedBy"].is_a?(Array) ? inst["definedBy"].first : inst["definedBy"]
      abs_inst_path = @gen_dir / defining_ext_name / "#{inst['name']}.yaml"
      FileUtils.mkdir_p abs_inst_path.dirname
      inst_yaml = YAML.dump(inst)
      if !abs_inst_path.exist? || overwrite_same || (abs_inst_path.read != inst_yaml)
        File.write(abs_inst_path, inst_yaml)
      end
    end

    csrs.each do |csr|
      defining_ext_name = csr["definedBy"].is_a?(Array) ? csr["definedBY"][0] : csr["definedBy"]
      abs_csr_path = @gen_dir / "csr" / defining_ext_name / "#{csr['name']}.yaml"
      FileUtils.mkdir_p abs_csr_path.dirname
      csr_yaml = YAML.dump({ csr["name"] => csr })
      if !abs_csr_path.exist? || overwrite_same || (abs_csr_path.read != csr_yaml)
        File.write(abs_csr_path, csr_yaml)
      end
    end

    extensions.each do |ext|
      abs_ext_path = @gen_dir / "ext" / "#{ext['name']}.yaml"
      FileUtils.mkdir_p abs_ext_path.dirname
      ext_yaml = YAML.dump(ext)
      if !abs_ext_path.exist? || overwrite_same || (abs_ext_path.read != ext_yaml)
        File.write(abs_ext_path, ext_yaml)
      end
    end

    arch_def_yaml = "# yaml-language-server: $schema=../../../arch/arch_schema.json\n#{YAML.dump(arch_def)}"
    abs_arch_def_path = @gen_dir / "arch_def.yaml"
    if !abs_arch_def_path.exist? || overwrite_same || (abs_arch_def_path.read != arch_def_yaml)
      File.write(abs_arch_def_path, arch_def_yaml)
    end
  end

  # @param csr_name [#to_s] CSR name
  # @return [Pathname] relative (to arch/) location of the base (not an override) definition of a CSR
  def csr_path(csr_name)
    raise "No CSR '#{csr_name}' in config" unless @csr_path_map.key?(csr_name.to_s)

    @csr_path_map[csr_name.to_s]
  end

  # @return [Hash] a configured, unified architecture definition that conforms to the schema at
  #                arch/arch_schema.json
  def arch_def
    return @arch_def unless @arch_def.nil?

    @arch_def = {
      "params" => params,
      "instructions" => instructions,
      "extensions" => extensions,
      "csrs" => csrs.map { |csr| [csr["name"], csr] }.to_h,
      "exception_codes" => exception_codes
    }

    return @arch_def

    # make sure it passes validation
    begin
      @validator.validate_str(YAML.dump(@arch_def), type: :arch)
    rescue Validator::ValidationError => e
      warn "While validating the unified architecture defintion"
      raise e
    end

    @arch_def
  end

  # @return [Object] An object that has a method (lowercase) or constant (uppercase) for every config option
  #                  so that obj.param_name or obj.PARAM_NAME gets you the value
  def env
    return @env unless @env.nil?

    @env = Class.new
    @env.instance_variable_set(:@cfg, self)

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
          @cfg.extensions.any? do |e|
            e["name"] == ext_name.to_s
          end
        else
          requirement = Gem::Requirement.create(ext_version)
          @cfg.extensions.any? do |e|
            e["name"] == ext_name.to_s && requirement.satisfied_by?(e["version"])
          end
        end
      end

      # info on interrupt and exception codes

      # @returns [Array<Array<Integer, String>>] architecturally-defined exception codes as a [number, description] pair
      def architectural_exception_codes
        @cfg.exception_codes
      end

      # returns array of architecturally-defined exception codes as a [number, description] pair
      def architectural_interrupt_codes
        codes = [
          [1, 'Supervisor software interrupt'],
          [3, 'Machine software interrupt'],
          [5, 'Supervisor timer interrupt'],
          [7, 'Machine timer interrupt'],
          [9, 'Supervisor external interrupt'],
          [11, 'Machine external interrupt'],
        ]
        if ext?(:H)
          codes << [2,  'Virtual supervisor software interrupt']
          codes << [6,  'Virtual supervisor timer interrupt']
          codes << [10,  'Virtual supervisor external interrupt']
          codes << [12,  'Supervisor guest external interrupt']
        end
        codes.sort { |a, b| a[0] <=> b[0] }
      end
    end

    @env
  end
  private :env

  # @return [Pathname] path to the exception code definition for this config
  def exception_codes_def_path
    override_path = @cfg_dir / "misc/exception_codes.yaml"
    override_path.exist? ? override_path : $root / "arch" / "misc" / "exception_codes.yaml"
  end

  def exception_codes
    return @exception_codes unless @exception_codes.nil?

    parsed_def = Tilt["erb"].new(exception_codes_def_path, trim: "-").render(env.clone)
    begin
      @exception_codes = @validator.validate_str(parsed_def, type: :exception_codes)
    rescue Validator::ValidationError => e
      warn "Exception code definition in #{exception_codes_def_path} did not validate"
      raise e
    end
    @exception_codes.transform_keys!(&:to_i)
  end

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

  # overwrites base_obj with any data in update
  #
  # @param base_obj [Hash] Base object
  # @param updates [Hash] Object with overrides
  # @return [Hash] Updated object
  def merge(base_obj, updates)
    merge_helper(base_obj, updates, [])
  end
  private :merge

  # given a CSR definition template, render the result and add it to the running list of extant CSRs
  # if it is supposed to exist in the config
  #
  # @param csr_def_path [Pathname] Path to a CSR definition
  # @param extra_env [Hash] Extra enviornment variables to be used when parsing the CSR definition template
  def maybe_add_csr(csr_def_path, extra_env = {})
    current_env = env.clone
    extra_env.each { |k, v| current_env.define_singleton_method(k) { v } }
    parsed_def = Tilt['erb'].new(csr_def_path, trim: '-').render(current_env)

    begin
      @validator.validate_str(parsed_def, type: :csr)
    rescue Validator::ValidationError => e
      warn "Csr definition in #{csr_def_path} did not validate"
      raise e
    end

    csr_def = YAML.safe_load(parsed_def)
    csr_name = csr_def.keys[0]
    csr_def = csr_def[csr_name]

    # check for an override
    merge(csr_def, @overrides[:csr][csr_name]) if @overrides[:csr].key?(csr_name)

    # filter fields to exclude any definedBy an extension not supported in this config
    csr_def['fields'].select! do |field_name, field_data|
      break true if field_data['definedBy'].nil?

      field_defined_by = field_data['definedBy']
      field_defined_by = [field_defined_by] unless field_defined_by.is_a?(Array)

      field_defined_by.each do |ext_name|
        break true if extensions.any? { |ext| ext['name'] == ext_name }
      end
      false
    end

    # add the CSR, unless it is from an extension not supported in this config
    csr_defined_by = csr_def['definedBy']
    csr_defined_by = [csr_defined_by] unless csr_defined_by.is_a?(Array) # turn into an array if needed

    csr_def["name"] = csr_name
    @csrs << csr_def if csr_defined_by.any? { |ext_name| extensions.map { |ext| ext['name'] == ext_name } }
    @csr_hash ||= {}
    @csr_hash[csr_name] = @csrs.last
  end
  private :maybe_add_csr

  # Get list of Csrs defined by this config
  #
  # @return [Array<Hash>] List of CSR defintions defined by this config
  def csrs
    @csrs unless @csrs.nil?

    @csrs = []

    Dir.glob("#{$root}/arch/csr/*.yaml") do |f|
      csr_name = File.basename(f, '.yaml')
      if ['mhpmcounterN', 'mhpmeventN'].any?(csr_name)
        # special case, gets reused 29 times
        (3..31).each do |hpm_num|
          maybe_add_csr(Pathname.new(f), hpm_num: hpm_num)
        end
      elsif csr_name == 'pmpcfgN'
        # special case, gets reused
        rounded_num_entries =
          if @params['NUM_PMP_ENTRIES'].zero?
            0
          elsif @params['NUM_PMP_ENTRIES'] <= 16
            16
          else
            64
          end

        n_cfg_regs = rounded_num_entries / 8

        n_cfg_regs.times do |i|
          maybe_add_csr(Pathname.new(f), pmpcfg_num: i*2)
        end
      elsif csr_name == 'pmpaddrN'
        # special case, gets reused
        rounded_num_entries =
          if @params['NUM_PMP_ENTRIES'].zero?
            0
          elsif @params['NUM_PMP_ENTRIES'] <= 16
            16
          else
            64
          end
        rounded_num_entries.times do |i|
          maybe_add_csr(Pathname.new(f), pmpaddr_num: i)
        end
      else
        maybe_add_csr(Pathname.new(f))
      end
    end

    # now add any CSRs that are only defined in the overrides
    csr_override_dir = $root / "cfgs" / name / "overrides" / "csr"

    # override can be right under cfg/NAME or in a subdirectory
    csr_override_paths = Dir.glob(csr_override_dir / "*.yaml") + Dir.glob(csr_override_dir / "**" / "*.yaml")
    csr_override_paths.each do |csr_def_path|
      data = YAML.load_file(csr_def_path)
      maybe_add_csr(csr_def_path) if csr(data.keys[0]).nil?
    end
    @csrs
  end

  # @return [Hash, NilObject] Csr definition for CSR 'name', or nil if CSR does not exist in the config
  def csr(name)
    @csr_hash[name]
  end

  # get list of extensions defined in this config
  #
  # return [Array<Hash>] List of extensions defined in this config
  def extensions
    @extensions unless @extensions.nil?

    @extensions = []

    @cfg["extensions"].each do |e|
      ext_name = e[0]
      ext_version = e[1]

      f = "#{$root}/arch/ext/#{ext_name}.yaml"
      unless File.exist?(f)
        f = $root / "cfg" / name / "overrides" / "ext" / "#{ext_name}.yaml"
        raise "No extension defintion for #{ext_name}" unless File.exist?(f)
      end

      parsed_def = Tilt["erb"].new(f, trim: "-").render(env)

      begin
        @validator.validate_str(parsed_def, type: :extension)
      rescue Validator::ValidationError => e
        warn "Extension definition in #{f} did not validate"
        raise e
      end

      ext_def = YAML.safe_load(parsed_def, permitted_classes: [Date])
      raise "Extension name (#{ext_def.keys[0]}) must match file name (#{f})" unless ext_def.key?(ext_name)

      ext_def = ext_def[ext_name]
      ext_def["name"] = ext_name

      versions = ext_def["versions"]
      matches = versions.select { |v| v["version"] == ext_version }

      raise "Multiple version matches for [#{ext_name}, #{ext_version}]" if matches.size > 1

      raise "No version match for [#{ext_name}, #{ext_version}]" if matches.empty?

      version_data = matches[0]

      ext_def.delete("versions")
      ext_def.merge!(version_data)
      @extensions << ext_def
    end

    @extensions
  end

  # add an instruction to the running list of instructions for this config if it should be included
  #
  # @param inst_def_path [Pathname] Path to an instruction definition template
  def maybe_add_inst(inst_def_path, extra_env = {})
    current_env = env.clone
    extra_env.each { |k, v| current_env.define_singleton_method(k) { v } }
    parsed_def = Tilt["erb"].new(inst_def_path, trim: "-").render(current_env)

    begin
      inst_def = YAML.safe_load(parsed_def)
    rescue Psych::SyntaxError => e
      warn "While parsing #{inst_def_path}"
      raise e
    end

    raise "Bad inst" unless inst_def.is_a?(Hash) && inst_def.size == 1

    inst_name = inst_def.keys[0]

    # check for an override
    merge(inst_def, @overrides[:inst][inst_name]) if @overrides[:inst].key?(inst_name)
    inst_def = inst_def[inst_name]
    inst_def["name"] = inst_name

    raise "no riscv-opcode data for #{inst_def['name']}" unless @opcode_data.key?(inst_def["name"].tr(".", "_"))

    opcode_str = @opcode_data[inst_def["name"].tr(".", "_")]["extension"][0]

    raise "Bad opcode string" unless opcode_str =~ /rv((32)|(64))?_([a-zA-Z0-9]+)/

    base = ::Regexp.last_match(1)
    defined_in = ::Regexp.last_match(4)

    inst_def["definedBy"] = defined_in.capitalize
    inst_def["base"] = base.to_i unless base.nil?

    begin
      @validator.validate_str(JSON.dump({ inst_name => inst_def}), type: :inst)
    rescue Validator::ValidationError => e
      warn "Instruction definition in #{inst_def_path} did not validate"
      raise e
    end

    # add the instruction, unless it is from an extension not supported in this config
    unless (base.nil? || (base.to_i == @params["XLEN"])) && extensions.any? { |e| e["name"].downcase == defined_in }
      return
    end

    @instructions << inst_def
    @inst_hash ||= {}
    @inst_hash[inst_name] = @instructions.last
  end
  private :maybe_add_inst

  # get a list of instructions included in this config
  #
  # @return [Array<Hash>] List of instruction definitions included in this config
  def instructions
    @instructions unless @instructions.nil?

    @instructions = []

    Dir.glob("#{$root}/arch/inst/**/*.yaml") do |f|
      maybe_add_inst(Pathname.new(f))
    end

    # now add any insts that are only defined in the overrides
    inst_override_dir = $root / "cfgs" / name / "overrides" / "inst"

    # override can be right under cfg/NAME or in a subdirectory
    inst_override_paths = Dir.glob(inst_override_dir / "*.yaml") + Dir.glob(inst_override_dir / "**" / "*.yaml")
    inst_override_paths.each do |inst_def_path|
      data = YAML.load_file(inst_def_path)
      maybe_add_inst(inst_def_path) if inst(data.keys[0]).nil?
    end

    raise "No instructions were found?" if @instructions.empty?

    @instructions
  end

  # return data for an instruction 'name'
  #
  # @param name [String] Instruction name
  # @return [Hash, NilObject] Instruction data or nil if instruction does not exist
  def inst(name)
    @inst_hash[name]
  end

  def params
    @params.select { |k, _v| k.upcase == k }
  end
end

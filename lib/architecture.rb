# frozen_string_literal: true

require "active_support/inflector/methods"

require "json"
require "json_schemer"
require "pathname"
require "yaml"

require_relative "idl"

require_relative "arch_obj_models/certificate"
require_relative "arch_obj_models/csr"
require_relative "arch_obj_models/csr_field"
require_relative "arch_obj_models/exception_code"
require_relative "arch_obj_models/extension"
require_relative "arch_obj_models/instruction"
require_relative "arch_obj_models/manual"
require_relative "arch_obj_models/portfolio"
require_relative "arch_obj_models/profile"

# Represents the entire RISC-V Architecture.
#
# Could be either the standard spec (defined by RISC-V International)
# of a custom spec (defined as an arch_overlay in cfgs/)
class Architecture
  # @return [Pathname] Path to the directory with the standard YAML files
  attr_reader :path

  # @param arch_dir [Sting,Pathname] Path to a directory with a fully merged/resolved architecture defintion
  def initialize(arch_dir)
    @arch_dir = Pathname.new(arch_dir)
    raise "Arch directory not found: #{arch_dir}" unless @arch_dir.exist?

    @arch_dir = @arch_dir.realpath
    @path = @arch_dir # alias
    @objects ||= {}
    @object_hashes ||= {}
  end

  # validate the architecture against JSON Schema and any object-specific verification
  # @param show_progress [Boolean] Whether to show a progress bar
  def validate(show_progress: true)
    progressbar = ProgressBar.create(total: objs.size) if show_progress

    objs.each do |obj|
      progressbar.increment if show_progress
      obj.validate
    end
  end

  # @!macro [attach] generate_obj_methods
  #   @method $1s
  #   @return [Array<$3>] List of all $1s defined in the standard
  #
  #   @method $1_hash
  #   @return [Hash<String, $3>] Hash of all $1s
  #
  #   @method $1
  #   @param name [String] The $1 name
  #   @return [$3] The $1
  #   @return [nil] if there is no $1 named +name+
  def self.generate_obj_methods(fn_name, arch_dir, obj_class)
    plural_fn = ActiveSupport::Inflector.pluralize(fn_name)

    define_method(plural_fn) do
      return @objects[arch_dir] unless @objects[arch_dir].nil?

      @objects[arch_dir] = []
      @object_hashes[arch_dir] = {}
      Dir.glob(@arch_dir / arch_dir / "**" / "*.yaml") do |obj_path|
        obj_yaml = YAML.load_file(obj_path, permitted_classes: [Date])
        @objects[arch_dir] << obj_class.new(obj_yaml, Pathname.new(obj_path).realpath, arch: self)
        @object_hashes[arch_dir][@objects[arch_dir].last.name] = @objects[arch_dir].last
      end
      @objects[arch_dir]
    end

    define_method("#{fn_name}_hash") do
      return @object_hashes[arch_dir] unless @object_hashes[arch_dir].nil?

      send(plural_fn) # create the hash

      @object_hashes[arch_dir]
    end

    define_method(fn_name) do |name|
      return @object_hashes[arch_dir][name] unless @object_hashes[arch_dir].nil?

      send(plural_fn) # create the hash

      @object_hashes[arch_dir][name]
    end
  end

  OBJS = [
    {
      fn_name: "extension",
      arch_dir: "ext",
      klass: Extension
    },
    {
      fn_name: "instruction",
      arch_dir: "inst",
      klass: Instruction
    },
    {
      fn_name: "csr",
      arch_dir: "csr",
      klass: Csr
    },
    {
      fn_name: "cert_class",
      arch_dir: "certificate_class",
      klass: CertClass
    },
    {
      fn_name: "cert_model",
      arch_dir: "certificate_model",
      klass: CertModel
    },
    {
      fn_name: "manual",
      arch_dir: "manual",
      klass: Manual
    },
    {
      fn_name: "manual_version",
      arch_dir: "manual_version",
      klass: ManualVersion
    },
    {
      fn_name: "profile_release",
      arch_dir: "profile_release",
      klass: ProfileRelease
    },
    {
      fn_name: "profile_class",
      arch_dir: "profile_class",
      klass: ProfileClass
    },
    {
      fn_name: "profile",
      arch_dir: "profile",
      klass: Profile
    }
  ].freeze

  OBJS.each do |obj_info|
    generate_obj_methods(obj_info[:fn_name], obj_info[:arch_dir], obj_info[:klass])
  end

  # @return [Array<DatabaseObjectect>] All known objects
  def objs
    return @objs unless @objs.nil?

    @objs = []
    OBJS.each do |obj_info|
      @objs.concat(send(ActiveSupport::Inflector.pluralize(obj_info[:fn_name])))
    end
    @objs.freeze
  end

  # @return [Array<ExtensionParameter>] Alphabetical list of all parameters defined in the architecture
  def params
    return @params unless @params.nil?

    @params = extensions.map(&:params).flatten.uniq(&:name).sort_by!(&:name)
  end

  # @return [Hash<String, ExtensionParameter>] Hash of all extension parameters defined in the architecture
  def params_hash
    return @params_hash unless @params_hash.nil?

    @params_hash = {}
    params.each do |param|
      @params_hash[param.name] = param
    end
    @param_hash
  end

  # @return [ExtensionParameter] Parameter named +name+
  # @return [nil] if there is no parameter named +name+
  def param(name)
    params_hash[name]
  end

  # @return [Array<ExceptionCode>] All exception codes defined by the spec
  def exception_codes
    return @exception_codes unless @exception_codes.nil?

    @exception_codes =
      extensions.reduce([]) do |list, ext_version|
        ecodes = extension(ext_version.name)["exception_codes"]
        next list if ecodes.nil?

        ecodes.each do |ecode|
          # double check that all the codes are unique
          raise "Duplicate exception code" if list.any? { |e| e.num == ecode["num"] || e.name == ecode["name"] || e.var == ecode["var"] }

          list << ExceptionCode.new(ecode["name"], ecode["var"], ecode["num"], self)
        end
        list
      end
  end

  # @return [Array<InteruptCode>] All interrupt codes defined by extensions
  def interrupt_codes
    return @interrupt_codes unless @interrupt_codes.nil?

    @interupt_codes =
      extensions.reduce([]) do |list, ext_version|
        icodes = extension(ext_version.name)["interrupt_codes"]
        next list if icodes.nil?

        icodes.each do |icode|
          # double check that all the codes are unique
          if list.any? { |i| i.num == icode["num"] || i.name == icode["name"] || i.var == icode["var"] }
            raise "Duplicate interrupt code"
          end

          list << InterruptCode.new(icode["name"], icode["var"], icode["num"], self)
        end
        list
      end
  end

  # given a `$ref` target, return the Ruby object
  #
  # @params uri [String] JSON Reference pointer
  # @return [Object] The pointed-to object
  def ref(uri)
    raise ArgumentError, "JSON Reference (#{uri}) must contain one '#'" unless uri.count("#") == 1

    file_path, obj_path = uri.split("#")
    obj =
      case file_path
      when /^certificate_class.*/
        cert_class_name = File.basename(file_path, ".yaml")
        cert_class(cert_class_name)
      when /^certificate_model.*/
        cert_model_name = File.basename(file_path, ".yaml")
        cert_model(cert_model_name)
      when /^csr.*/
        csr_name = File.basename(file_path, ".yaml")
        csr(csr_name)
      when /^ext.*/
        ext_name = File.basename(file_path, ".yaml")
        extension(ext_name)
      when /^inst.*/
        inst_name = File.basename(file_path, ".yaml")
        instruction(inst_name)
      when /^manual.*/
        manual_name = File.basename(file_path, ".yaml")
        manual(manual_name)
      when /^manual_version.*/
        manual_name = File.basename(file_path, ".yaml")
        manual_version(manual_name)
      when /^profile_class.*/
        profile_class_name = File.basename(file_path, ".yaml")
        profile_class(profile_class_name)
      when /^profile_release.*/
        profile_release_name = File.basename(file_path, ".yaml")
        profile_release(profile_release_name)
      when /^profile.*/
        profile_name = File.basename(file_path, ".yaml")
        profile(profile_name)
      else
        raise "Unhandled ref object: #{file_path}"
      end

    unless obj_path.nil?
      parts = obj_path.split("/")
      parts.each do |part|
        raise "Error in $ref. There is no method '#{part}' for a #{obj.class.name}" unless obj.respond_to?(part.to_sym)

        obj = obj.send(part)
      end
    end

    obj
  end
end

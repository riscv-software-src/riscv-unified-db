# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

# The Architecture class is the API to the architecture database.
# The "database" contains RISC-V standards including extensions, instructions,
# CSRs, Profiles, and Certificates.
# The Architecture class is used by backends to export the information in the
# architecture database to create various outputs.
#
# The Architecture class creates Ruby functions at runtime (see generate_obj_methods() and OBJS array).
#   1) Function to return Array<klass>              (every klass in database)
#   2) Function to return Hash<String name, klass>  (hash entry is nil if name doesn't exist)
#   3) Function to return Klass given name          (nil if name doesn't exist)
#
#   klass           Array<klass>        Hash<String name,klass> Klass func(String name)
#   =============== ==================  ======================= =========================
#   Extension       extensions()        extension_hash()        extension(name)
#   Instruction     instructions()      instruction_hash()      instruction(name)
#   Csr             csrs()              csr_hash()              csr(name)
#   ProcCertClass   proc_cert_classes() proc_cert_class_hash()  proc_cert_class(name)
#   ProcCertModel   proc_cert_models()  proc_cert_model_hash()  proc_cert_model(name)
#   ProfileFamily   profile_families()  profile_family_hash()   profile_family(name)
#   ProfileRelease  profile_releases()  profile_release_hash()  profile_release(name)
#   Profile         profiles()          profile_hash()          profile(name)
#   Manual          manuals()           manual_hash()           manual(name)
#   ManualVersion   manual_versions()   manual_version_hash()   manual_version(name)
#
# Normal Ruby functions:
#
#   klass               Array<klass>        Hash<String name,klass> Klass func(String name)
#   ==================  ==================  ======================= =========================
#   Parameter           params()            param_hash()            param(name)
#   PortfolioClass      portfolio_classes() portfolio_class_hash()  portfolio_class(name)
#   Portfolio           portfolios()        portfolio_hash()        portfolio(name)
#   ExceptionCodes      exception_codes()
#   InterruptCodes      interrupt_codes()

require "active_support/inflector/methods"

require "concurrent"
require "json"
require "json_schemer"
require "pathname"
require "sorbet-runtime"
require "yaml"

require_relative "obj/certificate"
require_relative "obj/csr"
require_relative "obj/csr_field"
require_relative "obj/exception_code"
require_relative "obj/extension"
require_relative "obj/instruction"
require_relative "obj/manual"
require_relative "obj/portfolio"
require_relative "obj/profile"

module Udb

  class Architecture
    extend T::Sig

    # @return [Pathname] Path to the directory with the standard YAML files
    attr_reader :path

    # @param arch_dir [String,Pathname] Path to a directory with a fully merged/resolved architecture definition
    def initialize(arch_dir)
      @arch_dir = Pathname.new(arch_dir)
      raise "Arch directory not found: #{arch_dir}" unless @arch_dir.exist?

      @arch_dir = @arch_dir.realpath
      @path = @arch_dir # alias
      @objects = Concurrent::Hash.new
      @object_hashes = Concurrent::Hash.new
    end

    # validate the architecture against JSON Schema and any object-specific verification
    # @param show_progress [Boolean] Whether to show a progress bar
    sig { params(resolver: Resolver, show_progress: T::Boolean).void }
    def validate(resolver, show_progress: true)
      progressbar = ProgressBar.create(total: objs.size) if show_progress

      objs.each do |obj|
        next unless obj.is_a?(TopLevelDatabaseObject)

        progressbar.increment if show_progress
        obj.validate(resolver)
      end
    end

    # These instance methods are create when this Architecture class is first loaded.
    # This is a Ruby "class" method and so self is the entire Architecture class, not an instance it.
    # However, this class method creates normal instance methods and when they are called
    # self is an instance of the Architecture class.
    #
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
    sig { params(fn_name: String, arch_dir: String, obj_class: T.class_of(DatabaseObject)).void }
    def self.generate_obj_methods(fn_name, arch_dir, obj_class)
      plural_fn = ActiveSupport::Inflector.pluralize(fn_name)

      define_method(plural_fn) do
        return @objects[arch_dir] unless @objects[arch_dir].nil?

        @objects[arch_dir] = Concurrent::Array.new
        @object_hashes[arch_dir] = Concurrent::Hash.new
        Dir.glob(@arch_dir / arch_dir / "**" / "*.yaml") do |obj_path|
          f = File.open(obj_path)
          f.flock(File::LOCK_EX)
          obj_yaml = YAML.load(f.read, filename: obj_path, permitted_classes: [Date])
          f.flock(File::LOCK_UN)
          @objects[arch_dir] << obj_class.new(obj_yaml, Pathname.new(obj_path).realpath, self)
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
        klass: Extension,
        kind: DatabaseObject::Kind::Extension
      },
      {
        fn_name: "instruction",
        arch_dir: "inst",
        klass: Instruction,
        kind: DatabaseObject::Kind::Instruction
      },
      {
        fn_name: "instruction_type",
        arch_dir: "inst_type",
        klass: InstructionType,
        kind: DatabaseObject::Kind::InstructionType
      },
      {
        fn_name: "instruction_subtype",
        arch_dir: "inst_subtype",
        klass: InstructionSubtype,
        kind: DatabaseObject::Kind::InstructionSubtype
      },
      {
        fn_name: "csr",
        arch_dir: "csr",
        klass: Csr,
        kind: DatabaseObject::Kind::Csr
      },
      {
        fn_name: "param",
        arch_dir: "param",
        klass: Parameter,
        kind: DatabaseObject::Kind::Parameter
      },
      {
        fn_name: "exception_code",
        arch_dir: "exception_code",
        klass: ExceptionCode,
        kind: DatabaseObject::Kind::ExceptionCode
      },
      {
        fn_name: "interrupt_code",
        arch_dir: "interrupt_code",
        klass: InterruptCode,
        kind: DatabaseObject::Kind::InterruptCode
      },
      {
        fn_name: "proc_cert_class",
        arch_dir: "proc_cert_class",
        klass: ProcCertClass,
        kind: DatabaseObject::Kind::ProcessorCertificateClass
      },
      {
        fn_name: "proc_cert_model",
        arch_dir: "proc_cert_model",
        klass: ProcCertModel,
        kind: DatabaseObject::Kind::ProcessorCertificateModel
      },
      {
        fn_name: "manual",
        arch_dir: "manual",
        klass: Manual,
        kind: DatabaseObject::Kind::Manual
      },
      {
        fn_name: "manual_version",
        arch_dir: "manual_version",
        klass: ManualVersion,
        kind: DatabaseObject::Kind::ManualVersion
      },
      {
        fn_name: "profile_release",
        arch_dir: "profile_release",
        klass: ProfileRelease,
        kind: DatabaseObject::Kind::ProfileRelease
      },
      {
        fn_name: "profile_family",
        arch_dir: "profile_family",
        klass: ProfileFamily,
        kind: DatabaseObject::Kind::ProfileFamily
      },
      {
        fn_name: "profile",
        arch_dir: "profile",
        klass: Profile,
        kind: DatabaseObject::Kind::Profile
      }
    ].freeze

    OBJS.each do |obj_info|
      generate_obj_methods(obj_info[:fn_name], obj_info[:arch_dir], obj_info[:klass])
    end

    # @return [Array<DatabaseObject>] All known objects
    sig { returns(T::Array[TopLevelDatabaseObject]) }
    def objs
      return @objs unless @objs.nil?

      @objs = []
      OBJS.each do |obj_info|
        @objs.concat(send(ActiveSupport::Inflector.pluralize(obj_info[:fn_name])))
      end
      @objs.freeze
    end

    # @return [Array<PortfolioClass>] Alphabetical list of all portfolio classes defined in the architecture
    def portfolio_classes
      return @portfolio_classes unless @portfolio_classes.nil?

      @portfolio_classes = profile_families.concat(proc_cert_classes).sort_by!(&:name)
    end

    # @return [Hash<String, PortfolioClass>] Hash of all portfolio classes defined in the architecture
    def portfolio_class_hash
      return @portfolio_class_hash unless @portfolio_class_hash.nil?

      @portfolio_class_hash = {}
      portfolio_classes.each do |portfolio_class|
        @portfolio_class_hash[portfolio_class.name] = portfolio_class
      end
      @portfolio_class_hash
    end

    # @return [PortfolioClass] Portfolio class named +name+
    # @return [nil] if there is no Portfolio class named +name+
    def portfolio_class(name) = portfolio_class_hash[name]

    # @return [Array<Portfolio>] Alphabetical list of all portfolios defined in the architecture
    def portfolios
      return @portfolios unless @portfolios.nil?

      @portfolios = @profiles.concat(@certificates).sort_by!(&:name)
    end

    # @return [Hash<String, Portfolio>] Hash of all portfolios defined in the architecture
    def portfolio_hash
      return @portfolio_hash unless @portfolio_hash.nil?

      @portfolio_hash = {}
      portfolios.each do |portfolio|
        @portfolio_hash[portfolio.name] = portfolio
      end
      @portfolio_hash
    end

    # @return [PortfolioClass] Portfolio named +name+
    # @return [nil] if there is no Portfolio named +name+
    def portfolio(name)
      portfolio_hash[name]
    end

    # given a `$ref` target, return the Ruby object
    #
    # @params uri [String] JSON Reference pointer
    # @return [Object] The pointed-to object
    sig { params(uri: String).returns(DatabaseObject) }
    def ref(uri)
      raise ArgumentError, "JSON Reference (#{uri}) must contain one '#'" unless uri.count("#") == 1

      file_path, obj_path = uri.split("#")
      obj =
        case file_path
        when /^proc_cert_class.*/
          proc_cert_class_name = File.basename(file_path, ".yaml")
          proc_cert_class(proc_cert_class_name)
        when /^proc_cert_model.*/
          proc_cert_model_name = File.basename(file_path, ".yaml")
          proc_cert_model(proc_cert_model_name)
        when /^csr.*/
          csr_name = File.basename(file_path, ".yaml")
          csr(csr_name)
        when /^ext.*/
          ext_name = File.basename(file_path, ".yaml")
          extension(ext_name)
        when %r{^inst/.*}
          inst_name = File.basename(file_path, ".yaml")
          instruction(inst_name)
        when /^manual.*/
          manual_name = File.basename(file_path, ".yaml")
          manual(manual_name)
        when /^manual_version.*/
          manual_name = File.basename(file_path, ".yaml")
          manual_version(manual_name)
        when /^profile_family.*/
          profile_family_name = File.basename(file_path, ".yaml")
          profile_family(profile_family_name)
        when /^profile_release.*/
          profile_release_name = File.basename(file_path, ".yaml")
          profile_release(profile_release_name)
        when /^profile.*/
          profile_name = File.basename(file_path, ".yaml")
          profile(profile_name)
        when %r{^inst_subtype/.*/.*}
          inst_subtype_name = File.basename(file_path, ".yaml")
          instruction_subtype(inst_subtype_name)
        when %r{^inst_type/[^/]+}
          # type
          inst_type_name = File.basename(file_path, ".yaml")
          instruction_type(inst_type_name)
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

end

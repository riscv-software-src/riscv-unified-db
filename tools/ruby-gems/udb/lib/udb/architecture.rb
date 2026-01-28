# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
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
require_relative "obj/register_file"
require_relative "obj/exception_code"
require_relative "obj/extension"
require_relative "obj/instruction"
require_relative "obj/manual"
require_relative "obj/portfolio"
require_relative "obj/profile"
require_relative "obj/prm"

module Udb

  class Architecture
    extend T::Sig

    # Path to the directory with the standard YAML files
    attr_reader :path

    # @param arch_dir [String,Pathname] Path to a directory with a fully merged/resolved architecture definition
    sig { params(arch_dir: T.any(Pathname, String)).void }
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
        fn_name: "register_file",
        arch_dir: "register",
        klass: RegisterFile,
        kind: DatabaseObject::Kind::RegisterFile
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
      },
      {
        fn_name: "prm",
        arch_dir: "prm",
        klass: Prm,
        kind: DatabaseObject::Kind::Prm
      }
    ].freeze

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

    # @return All known extension versions
    sig { returns(T::Array[ExtensionVersion]) }
    def extension_versions
      @extension_versions ||= extensions.map(&:versions).flatten.freeze
    end

    # @return Alphabetical list of all portfolio classes defined in the architecture
    sig { returns(T::Array[PortfolioClass]) }
    def portfolio_classes
      return @portfolio_classes unless @portfolio_classes.nil?

      @portfolio_classes = profile_families.concat(proc_cert_classes).sort_by!(&:name).freeze
    end

    # @return Hash of all portfolio classes defined in the architecture
    sig { returns(T::Hash[String, PortfolioClass]) }
    def portfolio_class_hash
      return @portfolio_class_hash unless @portfolio_class_hash.nil?

      @portfolio_class_hash = {}
      portfolio_classes.each do |portfolio_class|
        @portfolio_class_hash[portfolio_class.name] = portfolio_class
      end
      @portfolio_class_hash.freeze
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
    sig { params(uri: String).returns(T.untyped) }
    def ref(uri)
      raise ArgumentError, "JSON Reference (#{uri}) must contain one '#'" unless uri.count("#") == 1

      file_path, obj_path = uri.split("#")
      file_path = T.must(file_path)
      obj = T.let(nil, T.untyped)
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

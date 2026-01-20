# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "tty-exit"

require_relative "../common-opts"
require_relative "../defines"
require_relative "../template_helpers"

require "udb/obj/extension"

module UdbGen
  class GenExtPdfOptions < SubcommandWithCommonOptions
    include TTY::Exit
    include TemplateHelpers

    NAME="ext-doc"

    sig { void }
    def initialize
      super(name: NAME, desc: "Create documentation for an extension")
    end

    usage \
      command: NAME,
      desc:   "Generate documentation for an extension defined in UDB",
      example: <<~EXAMPLE
        Generate documentation for the Zba extension
          $ #{File.basename($PROGRAM_NAME)} #{NAME} -o Zba.pdf Zba

        Generate documentation for the B extension and all it's subextensions
          $ #{File.basename($PROGRAM_NAME)} #{NAME} -o B.pdf B Zba Zbb Zbss

        Generate documentation for the A extension version 2.1.0
          $ #{File.basename($PROGRAM_NAME)} #{NAME} -o A.pdf A@2.1.0

        Generate documentation for the A extension latest version
          $ #{File.basename($PROGRAM_NAME)} #{NAME} -o A.pdf A@latest

        Generate documentation for the A extension, all versions >= 2.1.0
          $ #{File.basename($PROGRAM_NAME)} #{NAME} -o A.pdf "A@>=2.1.0"
      EXAMPLE

    argument :extension do
      T.bind(self, TTY::Option::Parameter::Argument)
      arity one_or_more
      desc "Extension(s) to generate documentation for."
      validate ->(e) { e =~ /^(([A-WY])|([SXZ][a-z0-9]+))(@([0-9]+)(?:\.([0-9]+)(?:\.([0-9]+)(?:-(pre))?)?)?)?$/ }
      convert :list
    end

    flag :include_implies do
      T.bind(self, TTY::Option::Parameter::Option)
      short "-i"
      long "--implied_insts"
      desc "Include a list of implied instructions when describing extension(s)"
    end

    flag :exclude_csr_field_descriptions do
      T.bind(self, TTY::Option::Parameter::Option)
      long "--no-csr-field-desc"
      desc "Do not generate a long descrption of each CSR field (just a summary table)"
    end

    option :pseudo do
      T.bind(self, TTY::Option::Parameter::Option)
      short "-p"
      long "--p=type"
      desc "Which pdeudocode(s) to include in the documentation"
      permit ["sail", "idl", "both"]
      default "idl"
    end

    option :format do
      T.bind(self, TTY::Option::Parameter::Option)
      short "-f"
      long "--f=format"
      desc "Output format"
      permit ["pdf"]
      default "pdf"
    end

    option :output_dir do
      T.bind(self, TTY::Option::Parameter::Option)
      required
      short "-o"
      long "--out=directory"
      desc "Output directory"
      convert :path
    end

    option :output_basename do
      T.bind(self, TTY::Option::Parameter::Option)
      desc "Basename of the output files. Default is the name of the first listed extension"
      short "-b"
      long "--output-basename=basename"
    end

    option :theme do
      T.bind(self, TTY::Option::Parameter::Option)
      desc "Theme file for asciidoctor-pdf"
      long "--theme=path"
      convert :path
      default UdbGen.root / "riscv-docs-resources" / "themes" / "riscv-pdf.yml"
    end

    option :fonts do
      T.bind(self, TTY::Option::Parameter::Option)
      desc "Fonts directory"
      long "--fonts=path"
      convert :path
      default UdbGen.root / "riscv-docs-resources" / "fonts"
    end

    option :images do
      T.bind(self, TTY::Option::Parameter::Option)
      desc "Images directory"
      long "--images=path"
      convert :path
      default UdbGen.root / "riscv-docs-resources" / "images"
    end

    option :debug do
      T.bind(self, TTY::Option::Parameter::Option)
      desc "Set debug level"
      long "--debug=level"
      short "-d"
      default "info"
      permit ["debug", "info", "warn", "error", "fatal"]
    end

    def basename
      params[:output_basename].nil? ? params[:extension][0] : params[:output_basename]
    end

    def gen_adoc
      ext_reqs = T.let([], T::Array[Udb::ExtensionRequirement])
      Udb.log_level = Udb::LogLevel.deserialize(params[:debug])
      params[:extension].each do |ext_req_str|
        ext_name, req = ext_req_str.split("@")
        ext = cfg_arch.extension(ext_name)
        exit_with(:data_err, "No extension named '#{ext_name}'\n") if ext.nil?
        req =
          case req
          when nil
            ">=0"
          when "latest"
            "=#{ext.versions.max}"
          else
            "=#{req}"
          end
        ext_reqs << cfg_arch.extension_requirement(ext_name, req)
      end

      primary_ext = ext_reqs.fetch(0).extension

      template_path = Pathname.new(Gem.loaded_specs["udb-gen"].full_gem_path) / "templates" / "ext_pdf.adoc.erb"
      gen_filename = params[:output_dir] / "#{basename}.adoc"

      erb = ERB.new(template_path.read, trim_mode: "-")
      erb.filename = template_path.to_s

      FileUtils.mkdir_p params[:output_dir]
      File.write gen_filename, resolve_intermediate_links(cfg_arch, convert_monospace_to_links(cfg_arch, erb.result(binding)))

    end

    sig { void }
    def gen_pdf
      gen_adoc
      adoc_filename = params[:output_dir] / "#{basename}.adoc"
      pdf_filename = params[:output_dir] / "#{basename}.pdf"

      Udb.logger.info "Running asciidoctor-pdf"
      cmd = [
        "asciidoctor-pdf",
        "-w",
        "-v",
        "-a toc",
        "-a compress",
        "-a pdf-theme=#{params[:theme]}",
        "-a pdf-fontsdir=#{params[:fonts]}",
        "-a imagesdir=#{params[:images]}",
        "-r asciidoctor-diagram",
        "-r idl_highlighter",
        "-a wavedrom=/opt/node/node_modules/.bin/wavedrom-cli",
        "-o #{pdf_filename}",
        adoc_filename
      ].join(" ")

      Udb.logger.debug cmd
      system cmd

      puts "SUCCESS! Wrote result to #{pdf_filename}"
    end


    sig { override.params(argv: T::Array[String]).returns(T.noreturn) }
    def run(argv)
      parse(argv)

      if params[:help]
        print help
        exit_with(:success)
      end

      if params.errors.any?
        exit_with(:usage_error, "#{params.errors.summary}\n\n#{help}")
      end

      unless params.remaining.empty?
        exit_with(:usage_error, "Unknown arguments: #{params.remaining}\n")
      end

      gen_pdf

      exit_with(:success)
    end

  end
end

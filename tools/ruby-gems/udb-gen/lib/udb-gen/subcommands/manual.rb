# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "rake"
require "tty-exit"

require_relative "../common-opts"
require_relative "../defines"
require_relative "../template_helpers"

require "udb/obj/extension"

module UdbGen
  class ManualOptions < SubcommandWithCommonOptions
    include TTY::Exit
    include TemplateHelpers

    NAME = "manual"

    sig { void }
    def initialize
      super(name: NAME, desc: "Generate a manual")
    end

    usage \
      command: NAME,
      desc:   "Generate a manual",
      example: <<~EXAMPLE
        Generate ISA Manual, in HTML form
          $ #{File.basename($PROGRAM_NAME)} #{NAME} -f html -n isa -v all -c _
      EXAMPLE

    option :format do
      T.bind(self, TTY::Option::Parameter::Option)
      short "-f"
      long "--format"
      desc "Output format"
      permit ["html"]
      default "html"
    end

    option :versions do
      T.bind(self, TTY::Option::Parameter::Option)
      arity one_or_more
      short "-v"
      long "--versions=versions"
      desc "Version(s) to generate, or 'all' for all versions"
      convert :list
    end

    option :output_dir do
      T.bind(self, TTY::Option::Parameter::Option)
      desc "Output directory"
      short "-o"
      long "--output-directory=path"
      convert :path
      default Udb.repo_root / "gen" / "manual"
    end

    def gen_html
      app_class = Class.new(Rake::Application) do
        def initialize(gen_dir:, cfg_arch:, versions:, resolver:)
          super()
          @gen_dir = gen_dir
          @cfg_arch = cfg_arch
          @versions = versions
          @resolver = resolver
        end
        def gen_dir = @gen_dir
        def cfg_arch = @cfg_arch
        def versions = @versions
        def resolver = @resolver
      end

      app = app_class.new(
        gen_dir: params[:output_dir],
        cfg_arch:,
        versions: params[:versions],
        resolver:
      )
      Rake.with_application(app) do |rake|
        rake.init("manual", ["-f", "#{Pathname.new(__dir__).realpath}/manual/tasks.rake"])
        rake.load_rakefile
        puts rake.top_level_tasks
        rake.invoke_task("gen:html_manual")
      end
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

      if params[:versions].include?("all")
        if params[:versions].size > 1
          exit_with(:usage_error, "'all' must be specified alone\n")
        end
      end

      if params[:format] == "html"
        gen_html
      else
        exit_with(:usage_error, "Unknown format: '#{params[:format]}'\n\n#{help}")
      end

      exit_with(:success)
    end
  end
end

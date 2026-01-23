#!/usr/bin/env ruby
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"
require "tty-command"
require "tty-exit"
require "tty-table"
require "tty-option"
require "yaml"

include TTY::Exit

class Cli
  extend T::Sig
  include TTY::Option

  usage \
    command: "regress",
    desc: "Run regression tests",
    example: <<~EXAMPLES
      List all regressions
        $ regress --list

      Run a single regression
        $ regress --name regress-sorbet

      Run the "conditions" test of regress-udb-unit-test
        $ regress --name regress-udb-unit-test --matrix=test=conditions

      Run all smoke tests
        $ regress --tag smoke

      Run all regressions (takes a while)
        $ regress --all
    EXAMPLES

  flag :list do
    T.bind(self, TTY::Option::Parameter::Option)
    short "-l"
    long "--list"
    desc "List known regression tests and then exit"
  end

  flag :help do
    T.bind(self, TTY::Option::Parameter::Option)
    short "-h"
    long "--help"
    desc "Print usage"
  end

  option :test do
    T.bind(self, TTY::Option::Parameter::Option)
    short "-n"
    long "--name=test_name"
    desc "Run a single test"
  end

  option :matrix do
    T.bind(self, TTY::Option::Parameter::Option)
    short "-m"
    long "--matrix=category=value"
    desc "For tests that are matrixed, run just for the 'value' variant of category"
    validate "[^=]+=[^=]+"
  end

  option :tag do
    T.bind(self, TTY::Option::Parameter::Option)
    short "-t"
    long "--tag=tag_name"
    desc "Run all tests tagged with 'tag_name'"
  end

  flag :all do
    T.bind(self, TTY::Option::Parameter::Option)
    short "-a"
    long "--all"
    desc "Run all regression tests"
  end

  attr_reader :name
  attr_reader :desc

  sig { void }
  def initialize
    @name = "regress"
    @desc = "Run regression tests"
  end

  sig { returns(T::Hash[String, T.untyped]) }
  def test_data
    @test_data ||= YAML.load_file(Pathname.new(__dir__) / "regress-tests.yaml")
  end
  private :test_data

  sig { params(str: String, sub: T.nilable(T::Hash[String, String])).returns(String) }
  def gh_sub(str, sub: nil)
    str = str.gsub(/\${{\s*github\.workspace\s*}}/, (Pathname.new(__dir__) / ".." / "..").to_s)
    unless sub.nil?
      sub.each do |k, v|
        str = str.gsub(/\${{\s*#{k}\s*}}/, v)
      end
    end
    str
  end
  private :gh_sub

  sig { void }
  def cmd_list_tests
    tnames = test_data.fetch("tests").keys
    ttags = test_data.fetch("tests").map { |_, d| d.key?("tags") ? d["tags"].to_s : "" }
    tmatrix = test_data.fetch("tests").map { |_, d| d.key?("strategy") ? d["strategy"]["matrix"].map { |n, v| "#{n}: #{v}" }.to_s : "" }
    table = TTY::Table.new(header: ["Name", "Tags", "Matrix"], rows: tnames.size.times.map { |i| [tnames[i], ttags[i], tmatrix[i]] })
    puts table.render(:unicode)
  end

  sig { params(test_name: String).void }
  def cmd_run_single_test(test_name)
    unless test_data.fetch("tests").key?(test_name)
      warn "No test named '#{test_name}'"
      exit_with(:data_error)
    end

    test = test_data.fetch("tests").fetch(test_name)
    cmd = TTY::Command.new(uuid: false)
    test.fetch("test").each do |step|
      env = test.key?("env") ? test.fetch("env") : {}
      if step.key?("env")
        env.merge!(step.fetch("env"))
      end
      if test.key?("strategy")
        matrix = test.fetch("strategy").fetch("matrix")
        if params[:matrix]
          k, v = params[:matrix].split("=").map(&:strip)
          unless matrix.key?(k)
            warn "'#{k}' is not a matrix type"
            exit_with(:data_error)
          end
          unless matrix.fetch(k).include?(v)
            warn "'#{v}' is not an options for matrix '#{k}"
            exit_with(:data_error)
          end
          cmd.run env, "bash -c \"#{gh_sub(step.fetch("run"), sub: { "matrix.#{k}" => v })}\""
        else
          matrix.keys.each do |k|
            matrix.fetch(k).each do |v|
              cmd.run env, "bash -c \"#{gh_sub(step.fetch("run"), sub: { "matrix.#{k}" => v })}\""
            end
          end
        end
      else
        cmd.run env, "bash -c \"#{gh_sub(step.fetch("run"))}\""
      end
    end
  end

  sig { void }
  def cmd_run_all_tests
    test_data.fetch("tests").keys.each do |tname|
      cmd_run_single_test(tname)
    end
  end

  sig { params(argv: T::Array[String]).returns(T.noreturn) }
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

    if params[:list]
      cmd_list_tests
      exit_with(:success)
    end

    unless params[:test].nil?
      cmd_run_single_test(params[:test])
      exit_with(:success)
    end

    if params[:all]
      cmd_run_all_tests
      exit_with(:success)
    end

    # nothing specified
    help
    exit_with(:usage_error, "Missing required options\n")
  end
end

if __FILE__ == $0
  cli = Cli.new
  cli.run(ARGV)
end

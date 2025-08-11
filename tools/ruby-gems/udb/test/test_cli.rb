# typed: false
# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# frozen_string_literal: true

require "forwardable"
require "sorbet-runtime"
require "stringio"
require "timeout"
require "tmpdir"

require "minitest/autorun"
require "udb/cli"

class TestCli < Minitest::Test
  extend T::Sig

  def run_cmd(cmdline)
    Udb::Cli.start(cmdline.split(" "))
  end

  def run_cmd_io(cmdline, stdin, stdout)
    cli = Udb::Cli.new(cmdline.split(" "), { input: stdin, output: stdout })
    @cli_fiber = Fiber.new do
      cli.invoke_command(cli.class.all_commands[cmdline.split(" ")[0]], cmdline.split(" ")[1..])
    end
  end

  def test_list_extensions
    out, err = capture_io do
      run_cmd("list extensions")
    end
    assert_match /Zvkg/, out
    assert_empty err
  end

  def test_list_qc_iu_extensions
    out, err = capture_io do
      run_cmd("list extensions --config qc_iu")
    end
    assert_match /Xqci/, out
    assert_empty err
  end

  def test_list_params
    out, err = capture_io do
      run_cmd("list parameters")
    end
    assert_match /MXLEN/, out
    assert_empty err
  end

  def test_list_params_filtered
    out, err = capture_io do
      run_cmd("list parameters -e Sm H")
    end
    assert_match /MXLEN/, out
    refute_match /MUTABLE_ISA_S/, out
    assert_empty err
  end

  def test_list_params_yaml
    t = Tempfile.new
    _out, err = capture_io do
      run_cmd("list parameters -f yaml -o #{t.path}")
    end
    data = YAML.load_file(t.path)
    assert_equal data.any? { |p| p["name"] == "MXLEN" }, true
    assert_empty err
  end

  def test_disasm
    out, err = capture_io do
      run_cmd("disasm 0x00000037")
    end

    assert_match "  lui", out
    assert_empty err
  end

  def test_list_csrs
    num_listed = run_cmd("list csrs")

    repo_top = Udb.repo_root
    num_csr_yaml_files = `find #{repo_top}/spec/std/isa/csr/ -name '*.yaml' | wc -l`.to_i

    assert_equal num_csr_yaml_files, num_listed
  end

  class Unexpected < RuntimeError; end

  class TestInput
    def initialize
      @io = StringIO.new
      @pos = 0
    end

    def cli_fiber=(fiber)
      @cli_fiber = fiber
    end

    def tty? = false

    def puts(*args)
      @io.puts(*args)
    end

    def print(*args)
      @io.puts(*args)
    end

    def write(*args)
      @io.puts(*args)
    end

    def gets
      @io.seek @pos
      result = @io.gets
      @pos = @io.tell
      @io.seek(0, IO::SEEK_END)
      puts "gets: #{result}"
      result
    end

    def getc
      @io.seek @pos
      result = @io.getc
      @pos = @io.tell
      @io.seek(0, IO::SEEK_END)
      result
    end

    def wait_readable(*)
      true
    end

    def ioctl(*)
      80
    end
  end

  class TestOutput
    def initialize
      @io = StringIO.new
      @pos = 0
    end

    def puts(*args)
      @io.puts(*args)
      Fiber.yield
    end

    def print(*args)
      @io.print(*args)
      Fiber.yield
    end

    def write(*args)
      @io.write(*args)
      Fiber.yield
    end

    def sync=(*args)
      @io.sync = *args
    end

    def sync
      @io.sync
    end

    def gets
      @io.seek @pos
      result = @io.gets
      @pos = @io.tell
      @io.seek(0, IO::SEEK_END)
      result
    end
  end
  sig { params(io: TestOutput, pattern: Regexp).returns(String) }
  def expect_line(io, pattern)
    line = nil
    begin
      Timeout::timeout(5) do
        loop do
          @cli_fiber.resume if @cli_fiber.alive?
          line = io.gets
          unless line.nil?
            puts line.inspect
            puts pattern =~ line
            if pattern =~ line
              assert_match pattern, line # register that we passed a test
              return line
            end
          end
        end
      end
    rescue Timeout::Error
      assert_match pattern, line
    end
  end

  def do_inst_create_until_subtype(outdir, input, output)
    ENV["NO_COLOR"] = "1"
    ENV["SKIP_INFO"] = "1"
    fiber = run_cmd_io("create instruction -n #{outdir}", input, output)
    input.cli_fiber = fiber

    expect_line(output, %r{What copyright do you want to assign to newly created files?})

    input.puts "COPYRIGHT TEXT\n"

    expect_line(output, %r{What is the instruction mnemonic?})
    input.puts "add-new"

    expect_line(output, %r{Your answer is invalid})
    input.puts "add.new"

    expect_line(output, %r{What extension defines this instruction?})

    input.puts "Zfh"

    expect_line(output, %r{What is a short description of the instruction})
    input.puts ""
    expect_line(output, %r{Value must be provided})
    input.puts "A short description"

    ["U", "\\(H\\)S", "VS", "VU"].each do |mode|
      expect_line(output, %r{When is this instruction accessible in #{mode} mode?})
      input.puts ""
    end
    puts "UMMM"

    expect_line(output, %r{Is this instruction required to have data-independent timing})
    input.puts "yes"

    fiber

  end

  def test_create_inst
    input = TestInput.new
    output = TestOutput.new
    Dir.mktmpdir do |outdir|
      do_inst_create_until_subtype(outdir, input, output)

      expect_line(output, %r{What is the subtype of the instruction format?})
      input.puts "R-x"

      expect_line(output, %r{Is opcode 'funct7' a common/shared value among instructions})
      input.puts "unique"

      expect_line(output, %r{How should opcode 'funct7' be displayed in documentation})
      input.puts "ADD.NEW"

      expect_line(output, %r{What is the value of 'funct7' for 'add.new'})
      input.puts "011"

      expect_line(output, %r{Is opcode 'funct3' a common/shared value among instructions})
      input.puts "common"

      expect_line(output, %r{What is the opcode})
      input.puts "Create"

      expect_line(output, %r{What is the name of the opcode})
      input.puts "OP-NEW"

      expect_line(output, %r{What is the value of the opcode})
      input.puts "101"

      expect_line(output, %r{How should the opcode be displayed})
      input.puts

      expect_line(output, %r{Is opcode 'opcode' a common/shared value among instructions})
      input.puts "common"

      expect_line(output, %r{What is the opcode})
      input.puts "OP-32"

      expect_line(output, %r{Based on your answers, I've created the following file})
      expect_line(output, %r{#{outdir}/inst_opcode/OP-NEW\.yaml})
      expect_line(output, %r{#{outdir}/inst/Zfh/add\.new\.yaml})

      result = YAML.load_file("#{outdir}/inst/Zfh/add.new.yaml")
      assert_equal "add.new", result["name"]
      assert_equal "A short description", result["long_name"]
      assert_equal ({ "name" => "Zfh" }), result["definedBy"]
      assert_equal "ADD.NEW", result["format"]["opcodes"]["funct7"]["display_name"]
      assert_equal 0b011, result["format"]["opcodes"]["funct7"]["value"]
      assert_equal "inst_opcode/OP-NEW.yaml#/data", result["format"]["opcodes"]["funct3"]["$inherits"]
      assert_equal "inst_opcode/OP-32.yaml#/data", result["format"]["opcodes"]["opcode"]["$inherits"]
      assert_equal "always", result["access"]["s"]
      assert_equal "always", result["access"]["u"]
      assert_equal "always", result["access"]["vs"]
      assert_equal "always", result["access"]["vu"]
      assert result["data_independent_timing"]

    end # mktmpdir

  end

  def test_create_inst_with_new_subtype
    input = TestInput.new
    output = TestOutput.new
    Dir.mktmpdir do |outdir|
      do_inst_create_until_subtype(outdir, input, output)

      expect_line(output, %r{What is the subtype of the instruction format?})
      input.puts "Create"

      expect_line(output, %r{What instruction type does the new instruction subtype inherit from})
      input.puts "R"

      expect_line(output, %r{What is the subtype name})
      input.puts "R-new"

      expect_line(output, %r{What kind of variable is the 'rs2' slot})
      input.puts "xs2"

      expect_line(output, %r{What kind of variable is the 'rs1' slot})
      input.puts "xs1"

      expect_line(output, %r{What kind of variable is the 'rd' slot})
      input.puts "Create"

      expect_line(output, %r{What is the instruction var name})
      input.puts "new"

      expect_line(output, %r{What opcode field does this variable})
      input.puts "rd"

      expect_line(output, %r{What is the variable type})
      input.puts "x_dst_reg"

      expect_line(output, %r{How should this variable type be displayed})
      input.puts "new"
    end
  end

  def test_create_extension
    input = TestInput.new
    output = TestOutput.new
    Dir.mktmpdir do |outdir|
      ENV["NO_COLOR"] = "1"
      ENV["SKIP_INFO"] = "1"
      fiber = run_cmd_io("create extension -n #{outdir}", input, output)
      input.cli_fiber = fiber

      expect_line(output, %r{What copyright do you want to assign to newly created files?})
      input.puts "COPYRIGHT TEXT\n"

      expect_line(output, %r{Is this a RISC-V standard extension})
      input.puts "standard"

      expect_line(output, %r{What is the extension name})
      input.puts "Zibi"

      expect_line(output, %r{What is the state of the extension})
      input.puts "development"

      expect_line(output, %r{Is this an unprivileged})
      input.puts "unprivileged"

      expect_line(output, %r{What is a short description of the extension})
      input.puts "A short description"

      expect_line(output, %r{What is the initial version})
      input.puts "Version1"

      expect_line(output, %r{invalid})
      input.puts "0.1"

      expect_line(output, %r{Who is the first contributor})
      expect_line(output, %r{Full name})
      input.puts "Author One"
      expect_line(output, %r{Email})
      input.puts "author@riscv.org"
      expect_line(output, %r{Organization})
      input.puts "Org"

      expect_line(output, %r{Add another contributor})
      input.puts "y"
      expect_line(output, %r{Full name})
      input.puts "Author Two"
      expect_line(output, %r{Email})
      input.puts "author2@riscv.org"
      expect_line(output, %r{Organization})
      input.puts "Org"

      expect_line(output, %r{Add another contributor})
      input.puts "n"

      expect_line(output, %r{Based on your answers, I've created the following file})
      expect_line(output, %r{#{outdir}/ext/Zibi\.yaml})

      result = YAML.load_file("#{outdir}/ext/Zibi\.yaml")
      assert_equal "Zibi", result["name"]
      assert_equal "A short description", result["long_name"]
    end
  end
end

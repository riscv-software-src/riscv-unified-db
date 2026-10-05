# typed: true
# frozen_string_literal: true

require "sorbet-runtime"
T.bind(self, T.all(Rake::DSL, Object))
extend T::Sig

require "pathname"
require "erb"
require "tty-command"

Encoding.default_external = "UTF-8"

$jobs = ENV["JOBS"].nil? ? 1 : ENV["JOBS"].to_i
Rake.application.options.thread_pool_size = $jobs
puts "Running with #{Rake.application.options.thread_pool_size} job(s)"

require "etc"

$root = Pathname.new(__dir__).realpath
$rake_cmd_runner = TTY::Command.new
$lib = $root / "lib"

require "udb/resolver"
$resolver = Udb::Resolver.new($root)

require "logger"
require "ruby-progressbar"
require "yard"
require "minitest/test_task"

require "udb/architecture"

$logger = Logger.new(STDOUT, datetime_format: "%v %r")
$logger.level = Logger::INFO
$logger.formatter = proc do |severity, datetime, progname, msg|
  "[#{severity}] #{datetime.strftime('%F %T')}: #{msg}\n"
end

directory "#{$root}/.stamps"

# Load and execute Rakefile for each backend.
Dir.glob("#{$root}/backends/*/tasks.rake") do |rakefile|
  load rakefile
end

# Load and execute tools Rakefiles
Dir.glob("#{$root}/tools/*/tasks.rake") do |rakefile|
  load rakefile
end

directory "#{$root}/.stamps"

file "#{$root}/.stamps/dev_gems" => ["#{$root}/.stamps"] do |t|
  #sh "bundle exec yard config --gem-install-yri"
  sh "bundle exec yard gem"
  FileUtils.touch t.name
end

namespace :gen do
  desc "Generate documentation for the ruby tooling"
  task tool_doc: "#{$root}/.stamps/dev_gems" do
    Dir.chdir($root) do
      sh "bundle exec yard doc --yardopts cfg_arch.yardopts"
      sh "bundle exec yard doc --yardopts idl.yardopts"
    end
  end

  desc "Resolve the configuration CFG with spec/ and write it to gen/resolved_arch/<CFG>. Default CFG is the standard \"_\"."
  task "resolved_arch" do
    cfg = ENV["CFG"]
    if cfg.nil?
      cfg = "_"
    end
    if ENV.key?("COMPILE_IDL")
      resolver = Udb::Resolver.new($root, compile_idl: true)
      resolver.cfg_arch_for(cfg)
      Dir.glob(resolver.std_path / "isa" / "globals.isa") do |idl_file|
        compiler = Idl::Compiler.new
        ast = compiler.compile_file(Pathname.new(idl_file), {})
        dst = resolver.cfg_info(cfg).resolved_spec_path / Pathname.new(idl_file).relative_path_from(resolver.std_path)
        dst = dst.dirname / "#{dst.basename(".isa")}.yaml"
        File.write dst, YAML.dump(ast.to_h)
      end
    else
      $resolver.cfg_arch_for(cfg)
    end
  end

  desc "Resolve schema files and write them to gen/schemas/VERSION/SCHEMA with full $id URLs"
  task :schemas do
    sh "uv", "run", "--locked", "udb",
      "--schemas", ($root / "spec" / "schemas").to_s,
      "schemas", ($root / "gen" / "schemas").to_s
    puts "Resolved schema files written to gen/schemas/"
  end
end

namespace :serve do
  desc <<~DESC
    Start an HTML server to view the generated HTML documentation for the tool

    The default port is 8000, though it can be overridden with an argument
  DESC
  task :tool_doc, [:port] => "gen:tool_doc" do |_t, args|
    args.with_defaults(port: 8000)

    puts <<~MSG
      Server will come up on http://#{`hostname`.strip}:#{args[:port]}.
      It will regenerate the documentation on every access

    MSG
    sh "yard server -p #{args[:port]} --reload"
  end
end

sig { params(test_files: T::Array[String]).returns(String) }
def make_test_cmd(test_files)
  "-Ilib:test -w -e 'require \"minitest/autorun\"; #{test_files.map { |f| "require \"#{f}\"" }.join("; ")}' --"
end

namespace :test do

  # "Run the cross-validation against LLVM"
  task :llvm do
    begin
      sh "uv run pytest tools/python/auto-inst/test_parsing.py -v"
    rescue => e
      raise unless e.message.include?("status (5)") # don't fail on skipped tests
    end
  end
  # "Run the IDL compiler test suite"
  task :idl_compiler do
    test_files = Dir["#{$root}/lib/idl/tests/test_*.rb"]
    ruby make_test_cmd(test_files)
  end

  # "Run the Ruby library test suite"
  task :lib do
    test_files = Dir["#{$root}/lib/test/test_*.rb"]

    ruby make_test_cmd(test_files)
  end

  desc "Type-check the Ruby library"
  task :sorbet do
    Dir.chdir($root) do
      sh "./bin/bundle exec srb tc"
    end
  end
end

desc "Clean up all generated files"
task :clean do
  warn "Don't run clean using Rake. Run `./do clean` (alias for `./bin/clean`) instead."
end

desc "Clean up all generated files and container"
task :clobber do
  warn "Don't run clobber using Rake. Run `./do clobber` (alias for `./bin/clobber`) instead."
end


namespace :test do
  desc "Check that instruction encodings in the DB are consistent and do not conflict"
  task :inst_encodings do
    Udb.logger.info "Checking for conflicts in instruction encodings.."

    failed = T.let(false, T::Boolean)

    cfg_arch = $resolver.cfg_arch_for("_")
    insts = cfg_arch.instructions
    inst_names = T.let(Set.new, T::Set[String])
    insts.each do |i|
      if inst_names.include?(i.name)
        Udb.logger.warn "Duplicate instruction name: #{i.name}"
        failed = true
      end
      inst_names.add(i.name)
    end
    insts.each_with_index do |inst, idx|
      [32, 64].each do |xlen|
        next unless inst.defined_in_base?(xlen)

        (idx...insts.size).each do |other_idx|
          other_inst = T.must(insts[other_idx])
          next unless other_inst.defined_in_base?(xlen)
          next if other_inst == inst

          if inst.bad_encoding_conflict?(xlen, other_inst)
            warn "In RV#{xlen}: #{inst.name} (#{inst.encoding(xlen).format}) conflicts with #{other_inst.name} (#{other_inst.encoding(xlen).format})"
            failed = true
          end
        end
      end
    end
    if failed
      Udb.logger.error "Encoding test failed"
      exit 1
    end

    Udb.logger.info "Encoding test PASSED"
  end

  desc "Check that CSR definitions in the DB are consistent and do not conflict"
  task :csrs do
    print "Checking for conflicts in CSRs.."

    cfg_arch = $resolver.cfg_arch_for("_")
    csrs = cfg_arch.csrs
    failed = T.let(false, T::Boolean)
    csrs.each_with_index do |csr, idx|
      [32, 64].each do |xlen|
        next unless csr.defined_in_base?(xlen)

        (idx...csrs.size).each do |other_idx|
          other_csr = T.must(csrs[other_idx])
          next unless other_csr.defined_in_base?(xlen)
          next if other_csr == csr

          if csr.address == other_csr.address && !csr.address.nil?
            warn "CSRs #{csr.name} and #{other_csr.name} have conflicting addresses (#{csr.address})"
            failed = true
          end

          if csr.indirect? && other_csr.indirect? &&
              csr.priv_mode == other_csr.priv_mode &&
              csr.indirect_address == other_csr.indirect_address &&
              csr.indirect_slot == other_csr.indirect_slot
            warn "Indirect CSRs #{csr.name} and #{other_csr.name} have conflicting keys in RV#{xlen} " \
              "(priv_mode: #{csr.priv_mode}, indirect_address: 0x#{csr.indirect_address.to_s(16)}, " \
              "indirect_slot: #{csr.indirect_slot})"
            failed = true
          end
        end
      end
    end
    raise "CSR test failed" if failed

    puts "done"
  end

  task :schema do
    puts "Checking arch files against schema.."
    $resolver.cfg_arch_for("_").validate($resolver, show_progress: true)
    puts "All files validate against their schema"
  end

  task :idl do
    cfg = ENV["CFG"]
    raise "Missing CFG environment variable" if cfg.nil?

    print "Parsing IDL code for #{cfg}..."
    cfg_arch = $resolver.cfg_arch_for(cfg)
    puts "done"

    cfg_arch.type_check

    puts "All IDL passed type checking"
  end
end

namespace :gen do
  desc "Generate architecture files from layouts"
  task :arch do
    sh "mise", "exec", "--", "uv", "run", "udb", "generate-layouts", "--root", $root.to_s
  end

  desc "DEPRECATED -- Run `./bin/udb-gen ext-doc --help` instead"
  task :ext_pdf do
    warn "DEPRECATED     `./do gen:ext_pdf` was removed in favor of `./bin/generate ext-doc `"
    exit(1)
  end

  desc "Generate strict config files for profiles"
  task :cfg do
    sh ($root / "bin/python").to_s, "-m", "udb",
      "--path", ($root / "spec/std/isa").to_s,
      "--schemas", ($root / "spec/schemas").to_s,
      "generate", "profile-configs", "-o", ($resolver.cfgs_path / "profile").to_s
  end
end

namespace :test do
  task :unit do
    Udb.logger.warn "Running unit tests through do/Rake has been deprecated"
    Udb.logger.warn "Try `mise run check:unit` instead"
  end

  task :smoke do
    Udb.logger.warn "Running smoke through do/Rake has been deprecated"
    Udb.logger.warn "Try `mise run check:smoke` instead"
  end

  task :regress do
    Udb.logger.warn "Running regression through do/Rake has been deprecated"
    Udb.logger.warn "Try `mise run check:all` instead"
  end

  namespace :scripts do
    desc "Run unit tests for tools/scripts"
    task :unit do
      Dir.chdir($root) do
        sh "#{$root}/bin/ruby -Itools/scripts tools/scripts/test/run.rb"
      end
    end
  end
end

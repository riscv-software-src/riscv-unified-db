
require "active_support"
require "active_support/core_ext/string/inflections"

require_relative "lib/template_helpers"
require_relative "lib/csr_template_helpers"
require_relative "lib/gen_cpp"
require_relative "lib/decode_tree"
require_relative "../../lib/idl/passes/find_src_registers"

CPP_HART_GEN_SRC = $root / "backends" / "cpp_hart_gen"
CPP_HART_GEN_DST = $root / "gen" / "cpp_hart_gen"

# copy the includes to dst
rule %r{#{CPP_HART_GEN_DST}/.*/include/udb/.*\.hpp$} => proc { |tname|
  [(CPP_HART_GEN_SRC / "cpp" / "include" / "udb" / File.basename(tname)).to_s]
} do |t|
  src_path = CPP_HART_GEN_SRC / "cpp" / "include" / "udb" / File.basename(t.name)
  FileUtils.mkdir_p File.dirname(t.name)
  FileUtils.ln_s src_path, t.name
end

# copy the includes to dst
rule %r{#{CPP_HART_GEN_DST}/.*/include/udb/.*\.h$} => proc { |tname|
  [(CPP_HART_GEN_SRC / "c" / "include" / "udb" / File.basename(tname)).to_s]
} do |t|
  src_path = CPP_HART_GEN_SRC / "c" / "include" / "udb" / File.basename(t.name)
  FileUtils.mkdir_p File.dirname(t.name)
  FileUtils.ln_s src_path, t.name
end

# copy the srcs to dst
rule %r{#{CPP_HART_GEN_DST}/.*/src/.*\.cpp$} => proc { |tname|
  [(CPP_HART_GEN_SRC / "cpp" / "src" / File.basename(tname)).to_s]
} do |t|
  src_path = CPP_HART_GEN_SRC / "cpp" / "src" / File.basename(t.name)
  FileUtils.mkdir_p File.dirname(t.name)
  FileUtils.ln_s src_path, t.name
end

# copy the tests to dst
rule %r{#{CPP_HART_GEN_DST}/.*/test/.*\.cpp$} => proc { |tname|
  [(CPP_HART_GEN_SRC / "cpp" / "test" / File.basename(tname)).to_s]
} do |t|
  src_path = CPP_HART_GEN_SRC / "cpp" / "test" / File.basename(t.name)
  FileUtils.mkdir_p File.dirname(t.name)
  FileUtils.ln_s src_path, t.name
end

# rule for generating when the thing being generated is not config-specific
rule %r{#{CPP_HART_GEN_DST}/[^/]+/include/udb/[^/]+\.h(xx)?\.unformatted$} => proc { |tname|
  parts = tname.split("/")
  fname = parts[-1].sub(/\.unformatted$/, "")
  [
    "#{CPP_HART_GEN_SRC}/templates/#{fname}.erb",
    __FILE__
  ] + Dir.glob(CPP_HART_GEN_SRC / 'lib' / '**' / '*')
} do |t|
  configs, = configs_build_name
  config_name = configs[0]
  parts = t.name.split("/")
  fname = parts[-1].sub(/\.unformatted$/, "")

  cfg_arch = cfg_arch_for(config_name)

  template_path = CPP_HART_GEN_SRC / "templates" / "#{fname}.erb"
  erb = ERB.new(template_path.read, trim_mode: "-")
  erb.filename = template_path.to_s

  File.write(t.name, erb.result(CppHartGen::TemplateEnv.new(cfg_arch).get_binding))
end

# rule for generating when the thing being generated is not config-specific
rule %r{#{CPP_HART_GEN_DST}/[^/]+/src/[^/]+\.cxx\.unformatted$} => proc { |tname|
  # we just need one config for this, doesn't matter which one (enums are config-independent)
  parts = tname.split("/")
  fname = parts[-1].sub(/\.unformatted$/, "")
  [
    "#{CPP_HART_GEN_SRC}/templates/#{fname}.erb",
    __FILE__
  ]
} do |t|
  configs, = configs_build_name
  config_name = configs[0]
  parts = t.name.split("/")
  fname = parts[-1].sub(/\.unformatted$/, "")

  cfg_arch = cfg_arch_for(config_name)

  template_path = CPP_HART_GEN_SRC / "templates" / "#{fname}.erb"
  erb = ERB.new(template_path.read, trim_mode: "-")
  erb.filename = template_path.to_s

  File.write(t.name, erb.result(CppHartGen::TemplateEnv.new(cfg_arch).get_binding))
end

# a config-specifc generated header
rule %r{#{CPP_HART_GEN_DST}/.*/include/udb/cfgs/[^/]+/[^/]+\.h(xx)?\.unformatted$} => proc { |tname|
  parts = tname.split("/")
  filename = parts[-1].sub(/\.unformatted$/, "")
  config_name = parts[-2]
  [
    "#{$root}/.stamps/resolve-#{config_name}.stamp",
    "#{CPP_HART_GEN_SRC}/templates/#{filename}.erb",
    "#{CPP_HART_GEN_SRC}/lib/gen_cpp.rb",
    "#{$root}/lib/idl/passes/prune.rb",
    "#{CPP_HART_GEN_SRC}/lib/template_helpers.rb",
    "#{CPP_HART_GEN_SRC}/lib/csr_template_helpers.rb",
    __FILE__
  ]
} do |t|
  parts = t.name.split("/")
  filename = parts[-1].sub(/\.unformatted$/, "")
  config_name = parts[-2]

  cfg_arch = cfg_arch_for(config_name)

  template_path = CPP_HART_GEN_SRC / "templates" / "#{filename}.erb"
  erb = ERB.new(template_path.read, trim_mode: "-")
  erb.filename = template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write(t.name, erb.result(CppHartGen::TemplateEnv.new(cfg_arch).get_binding))
end

rule %r{#{CPP_HART_GEN_DST}/.*\.[ch](xx)?$} => proc { |tname|
  ["#{tname}.unformatted"]
} do |t|
  sh "clang-format #{t.name}.unformatted > #{t.name}"
end

rule %r{#{CPP_HART_GEN_DST}/.*/src/cfgs/[^/]+/[^/]+\.cxx\.unformatted$} => proc { |tname|
  parts = tname.split("/")
  filename = parts[-1].sub(/\.unformatted$/, "")
  config_name = parts[-2]
  [
    "#{$root}/.stamps/resolve-#{config_name}.stamp",
    "#{CPP_HART_GEN_SRC}/templates/#{filename}.erb",
    "#{CPP_HART_GEN_SRC}/lib/gen_cpp.rb",
    "#{$root}/lib/idl/passes/prune.rb",
    "#{CPP_HART_GEN_SRC}/lib/template_helpers.rb",
    "#{CPP_HART_GEN_SRC}/lib/csr_template_helpers.rb",
    __FILE__
  ]
} do |t|
  parts = t.name.split("/")
  filename = parts[-1].sub(/\.unformatted$/, "")
  config_name = parts[-2]

  cfg_arch = cfg_arch_for(config_name)

  template_path = CPP_HART_GEN_SRC / "templates" / "#{filename}.erb"
  erb = ERB.new(template_path.read, trim_mode: "-")
  erb.filename = template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write(t.name, erb.result(CppHartGen::TemplateEnv.new(cfg_arch).get_binding))
end

rule %r{#{CPP_HART_GEN_DST}/[^/]+/CMakeLists\.txt} => [
  "#{CPP_HART_GEN_SRC}/CMakeLists.txt",
  __FILE__
] do |t|
  FileUtils.mkdir_p File.dirname(t.name)
  FileUtils.cp t.prerequisites.first, t.name
end

rule %r{#{CPP_HART_GEN_DST}/[^/]+/build/Makefile} => [
  "#{CPP_HART_GEN_SRC}/CMakeLists.txt"
] do |t|
  build_name = t.name.split("/")[-3]
  cmd = [
    "cmake",
    "-S#{CPP_HART_GEN_DST}/#{build_name}",
    "-B#{CPP_HART_GEN_DST}/#{build_name}/build",
    "-DCONFIG_LIST=\"#{ENV['CONFIG'].gsub(',', ';')}\"",
    "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
    "-DCMAKE_BUILD_TYPE=#{cmake_build_type}"
  ].join(" ")

  sh cmd
end

rule %r{#{CPP_HART_GEN_DST}/[^/]+/include/udb/[^/]+\.hpp} do |t|
  FileUtils.mkdir_p File.dirname(t.name)
  fname = File.basename(t.name)
  FileUtils.ln_s "#{CPP_HART_GEN_SRC}/cpp/include/udb/#{fname}", t.name
end

def configs_build_name
  raise ArgumentError, "Missing required option CONFIG:\n#{help}" if ENV["CONFIG"].nil?

  configs = ENV["CONFIG"].split(",")
  build_type = cmake_build_type

  if configs.include?("all")
    raise ArgumentError, "'all' was specified with another config name" unless configs.size == 1

    configs = Dir.glob("#{$root}/cfgs/*").map { |path| File.basename(path, ".yaml") }
  end

  configs.each do |config|
    unless File.file?("#{$root}/cfgs/#{config}.yaml") || File.file?(config)
      raise ArgumentError, "No config named '#{config}'"
    end
  end

  config_names = configs.map do |config|
    cfg_arch_for(config).name
  end

  build_name =
    if ENV["BUILD_NAME"].nil?
      if configs.size != 1
        raise ArgumentError, "BUILD_NAME is required when there are multiple configs"
      end
      config_names[0]
    else
      ENV["BUILD_NAME"]
    end

  build_name += "_#{build_type}"

  [config_names, build_name]
end

OPTION_STR = <<~DESC_OPTIONS
Options:

  * CONFIG: Comma-separated list of configurations to generate.
            "rv32" is the generic RV32 architecture (i.e., no config).
            "rv64" is the generic RV64 architecture (i.e., no config).
            "all" will generate all configurations and the generic architecture.

            CONFIG can either be the name, excluding extension '.yaml', of a file under cfgs/
            or the (absolute or relative) path to a config file.
  * BUILD_NAME: Name of the build. Required if CONFIG is a list. Otherwise, BUILD_NAME will equal CONFIG.
DESC_OPTIONS

namespace :gen do
  help = <<~DESC
    Generate a C++ model of a hart(s) for configurations (./do --desc for more options)

    #{OPTION_STR}

    Examples:

      ./do gen:cpp_hart CONFIG=rv64                       # generate generic hart model
      ./do gen:cpp_hart CONFIG=example_rv64_with_overlay  # generate hart model for example_rv64_with_overlay config

      # generate hart model for example_rv64_with_overlay and custom_cfg
      ./do gen:cpp_hart CONFIG=example_rv64_with_overlay,custom_cfg BUILD_NAME=custom

  DESC
  desc help
  task :cpp_hart do
    configs, build_name = configs_build_name

    Dir.glob("#{CPP_HART_GEN_SRC}/cpp/include/udb/*.hpp").each do |inc|
      dst_path = CPP_HART_GEN_DST / build_name / "include" / "udb" / File.basename(inc)
      Rake::Task[dst_path].invoke
    end
    Dir.glob("#{CPP_HART_GEN_SRC}/c/include/udb/*.h").each do |inc|
      dst_path = CPP_HART_GEN_DST / build_name / "include" / "udb" / File.basename(inc)
      Rake::Task[dst_path].invoke
    end
    Dir.glob("#{CPP_HART_GEN_SRC}/cpp/src/*.cpp").each do |src|
      dst_path = CPP_HART_GEN_DST / build_name / "src" / File.basename(src)
      Rake::Task[dst_path].invoke
    end
    Dir.glob("#{CPP_HART_GEN_SRC}/cpp/test/*.cpp").each do |src|
      dst_path = CPP_HART_GEN_DST / build_name / "test" / File.basename(src)
      Rake::Task[dst_path].invoke
    end

    Rake::Task["#{CPP_HART_GEN_DST}/#{build_name}/CMakeLists.txt"].invoke

    generated_files = []
    generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/hart_factory.hxx"
    generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/db_data.hxx"
    generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/src/db_data.cxx"
    generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/enum.hxx"
    generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/src/enum.cxx"
    generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/bitfield.hxx"
    generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/libhart.h"

    configs.each do |config|
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/inst.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/inst_impl.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/params.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/src/cfgs/#{config}/params.cxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/hart.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/hart_impl.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/csrs.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/csrs_impl.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/csr_container.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/structs.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/func_prototypes.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/idl_funcs_impl.hxx"

      Dir.glob("#{CPP_HART_GEN_SRC}/cpp/include/udb/*.hpp") do |f|
        Rake::Task["#{CPP_HART_GEN_DST}/#{build_name}/include/udb/#{File.basename(f)}"].invoke
      end
    end

    generated_files.each { |fn| Rake::Task["#{fn}.unformatted"].invoke }

    multitask "__generate_formatted_cpp_#{build_name}" => generated_files
    Rake::MultiTask["__generate_formatted_cpp_#{build_name}"].invoke
  end
end

def cmake_build_type
  return "RelWithDebInfo" unless ENV.key?("BUILD_TYPE")

  case ENV["BUILD_TYPE"].upcase
  when "DEBUG"
    "Debug"
  when "FAST_DEBUG"
    "RelWithDebInfo"
  when "RELEASE", "", nil
    "Release"
  when "ASAN"
    "Asan"
  else
    raise "Bad BUILD_TYPE; must be DEBUG, FAST_DEBUG, ASAN, or RELEASE"
  end
end

namespace :build do
  help = <<~DESC
    Build a C++ model of a hart(s) for configurations (./do --desc for more options)

    #{OPTION_STR}

    Examples:

      ./do build:cpp_hart CONFIG=rv64                       # generate generic hart model
      ./do build:cpp_hart CONFIG=example_rv64_with_overlay  # generate hart model for example_rv64_with_overlay config

      # generate hart model for example_rv64_with_overlay and custom_cfg
      ./do gen:cpp_hart CONFIG=example_rv64_with_overlay,custom_cfg BUILD_NAME=custom

  DESC
  desc help
  task cpp_hart: ["gen:cpp_hart"] do
    _, build_name = configs_build_name

    Rake::Task["#{CPP_HART_GEN_DST}/#{build_name}/build/Makefile"].invoke
    Dir.chdir("#{CPP_HART_GEN_DST}/#{build_name}/build") do
      sh "make -j #{$jobs}"
    end
  end

  task renode_hart: ["gen:cpp_hart"] do
    _, build_name = configs_build_name

    Rake::Task["#{CPP_HART_GEN_DST}/#{build_name}/build/Makefile"].invoke
    Dir.chdir("#{CPP_HART_GEN_DST}/#{build_name}/build") do
      sh "make -j #{$jobs} hart_renode"
    end
  end
end

file "#{$root}/ext/riscv-tests/LICENSE" do
  sh "git submodule update --init ext/riscv-tests"
end

file "#{$root}/ext/riscv-tests/env/LICENSE" => ["#{$root}/ext/riscv-tests/LICENSE"] do
  Dir.chdir "#{$root}/ext/riscv-tests" do
    sh "git submodule update --init --recursive"
  end
end

task "checkout-riscv-tests" => "#{$root}/ext/riscv-tests/env/LICENSE"

file "#{CPP_HART_GEN_DST}/riscv-tests-build-64/Makefile" => "#{$root}/ext/riscv-tests/env/LICENSE" do |t|
  FileUtils.mkdir_p File.dirname(t.name)
  Dir.chdir File.dirname(t.name) do
    sh "#{$root}/ext/riscv-tests/configure --with-xlen=64"
  end
end

namespace :test do
  task cpp_hart: ["build:cpp_hart"] do
    _, build_name = configs_build_name

    Dir.chdir "#{CPP_HART_GEN_DST}/#{build_name}/build" do
      sh "ctest"
    end
  end
end

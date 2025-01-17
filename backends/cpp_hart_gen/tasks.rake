
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
rule %r{#{CPP_HART_GEN_DST}/.*/include/udb/.*\.hpp} do |t|
  src_path = CPP_HART_GEN_SRC / "cpp" / "include" / "udb" / File.basename(t.name)
  FileUtils.mkdir_p File.dirname(t.name)
  FileUtils.ln_s src_path, t.name
end

# copy the srcs to dst
rule %r{#{CPP_HART_GEN_DST}/.*/src/.*\.cpp} do |t|
  src_path = CPP_HART_GEN_SRC / "cpp" / "src" / File.basename(t.name)
  FileUtils.mkdir_p File.dirname(t.name)
  FileUtils.ln_s src_path, t.name
end

# copy the tests to dst
rule %r{#{CPP_HART_GEN_DST}/.*/test/.*\.cpp} do |t|
  src_path = CPP_HART_GEN_SRC / "cpp" / "test" / File.basename(t.name)
  FileUtils.mkdir_p File.dirname(t.name)
  FileUtils.ln_s src_path, t.name
end

rule %r{#{CPP_HART_GEN_DST}/[^/]+/include/udb/[^/]+\.hxx} => proc { |tname|
  # we just need one config for this, doesn't matter which one (enums are config-independent)
  fname = File.basename(tname)
  [
    "#{CPP_HART_GEN_SRC}/templates/#{fname}.erb",
    __FILE__
  ] + Dir.glob(CPP_HART_GEN_SRC / 'lib' / '*')
} do |t|
  config_name = ENV["CONFIG"].split(",").first.strip
  fname = File.basename(t.name)

  cfg_arch = cfg_arch_for(config_name)

  template_path = CPP_HART_GEN_SRC / "templates" / "#{fname}.erb"
  erb = ERB.new(template_path.read, trim_mode: "-")
  erb.filename = template_path.to_s

  File.write(t.name, erb.result(CppHartGen::TemplateEnv.new(cfg_arch).get_binding))
end

rule %r{#{CPP_HART_GEN_DST}/[^/]+/src/[^/]+\.cxx} => proc { |tname|
  # we just need one config for this, doesn't matter which one (enums are config-independent)
  fname = File.basename(tname)
  [
    "#{CPP_HART_GEN_SRC}/templates/#{fname}.erb",
    __FILE__
  ]
} do |t|
  config_name = ENV["CONFIG"].split(",").first.strip
  fname = File.basename(t.name)

  cfg_arch = cfg_arch_for(config_name)

  template_path = CPP_HART_GEN_SRC / "templates" / "#{fname}.erb"
  erb = ERB.new(template_path.read, trim_mode: "-")
  erb.filename = template_path.to_s

  File.write(t.name, erb.result(CppHartGen::TemplateEnv.new(cfg_arch).get_binding))
end

# a config-specifc generated header
rule %r{#{CPP_HART_GEN_DST}/.*/include/udb/cfgs/[^/]+/[^/]+\.hxx\.unformatted} => proc { |tname|
  parts = tname.split("/")
  filename = parts[-1].sub(/\.unformatted$/, "")
  [
    "#{CPP_HART_GEN_SRC}/templates/#{filename}.erb",
    "#{CPP_HART_GEN_SRC}/lib/gen_cpp.rb",
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

rule %r{#{CPP_HART_GEN_DST}/.*/include/udb/cfgs/[^/]+/[^/]+\.hxx} => proc { |tname|
  ["#{tname}.unformatted"]
} do |t|
  sh "clang-format #{t.name}.unformatted > #{t.name}"
end

rule %r{#{CPP_HART_GEN_DST}/.*/src/cfgs/[^/]+/[^/]+\.cxx} => proc { |tname|
  parts = tname.split("/")
  filename = parts[-1]
  [
    "#{CPP_HART_GEN_SRC}/templates/#{filename}.erb",
    "#{CPP_HART_GEN_SRC}/lib/gen_cpp.rb",
    "#{CPP_HART_GEN_SRC}/lib/template_helpers.rb",
    "#{CPP_HART_GEN_SRC}/lib/csr_template_helpers.rb",
    __FILE__
  ]
} do |t|
  parts = t.name.split("/")
  filename = parts[-1]
  config_name = parts[-2]

  cfg_arch = cfg_arch_for(config_name)

  template_path = CPP_HART_GEN_SRC / "templates" / "#{filename}.erb"
  erb = ERB.new(template_path.read, trim_mode: "-")
  erb.filename = template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write(t.name, erb.result(CppHartGen::TemplateEnv.new(cfg_arch).get_binding))
  sh "clang-format -i #{t.name}"
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
    "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON"
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

  if configs.include?("all")
    raise ArgumentError, "'all' was specified with another config name" unless configs.size == 1

    configs = Dir.glob("#{$root}/cfgs/*").map { |path| File.basename(path) }
  end

  configs.each do |config|
    raise ArgumentError, "No config named '#{config}'" unless File.directory?("#{$root}/cfgs/#{config}")
  end

  build_name =
    if ENV["BUILD_NAME"].nil?
      if configs.size != 1
        raise ArgumentError, "BUILD_NAME is required when there are multiple configs"
      end
      configs[0]
    else
      ENV["BUILD_NAME"]
    end

  [configs, build_name]
end

namespace :gen do
  help = <<~DESC
    Generate a C++ model of a hart(s) for configurations (./do --desc for more options)

    Options:

     * CONFIG: Comma-separated list of configurations to generate.
               "rv32" is the generic RV32 architecture (i.e., no config).
               "rv64" is the generic RV64 architecture (i.e., no config).
               "all" will generate all configurations and the generic architecture.
     * BUILD_NAME: Name of the build. Required if CONFIG is a list

    Examples:

      ./do gen:cpp_hart CONFIG=rv64        # generate generic hart model
      ./do gen:cpp_hart CONFIG=generic_rv  # generate hart model for generic_rv64 config

      # generate hart model for generic_rv64 and custom_cfg
      ./do gen:cpp_hart CONFIG=generic_rv,custom_cfg BUILD_NAME=custom

  DESC
  desc help
  task :cpp_hart do
    configs, build_name = configs_build_name

    Dir.glob("#{CPP_HART_GEN_SRC}/cpp/include/udb/*.hpp").each do |inc|
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
    generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/bitfield.hxx"

    configs.each do |config|
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/inst.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/src/cfgs/#{config}/decode.cxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/params.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/src/cfgs/#{config}/params.cxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/hart.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/src/cfgs/#{config}/hart.cxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/csrs.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/src/cfgs/#{config}/csrs.cxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/csr_container.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/structs.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/func_prototypes.hxx"
      generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/cfgs/#{config}/builtin_funcs.hxx"

      Dir.glob("#{CPP_HART_GEN_SRC}/cpp/include/udb/*.hpp") do |f|
        generated_files << "#{CPP_HART_GEN_DST}/#{build_name}/include/udb/#{File.basename(f)}"
      end
    end

    mt = Rake::MultiTask.define_task "__generate_cpp_#{build_name}" => generated_files
    mt.invoke
  end
end

namespace :cbuild do
  task cpp_hart: ["gen:cpp_hart"] do
    _, build_name = configs_build_name

    Dir.chdir("#{CPP_HART_GEN_DST}/#{build_name}/") do
      sh "make"
    end
  end
end


namespace :build do
  task cpp_hart: ["gen:cpp_hart"] do
    _, build_name = configs_build_name

    Rake::Task["#{CPP_HART_GEN_DST}/#{build_name}/build/Makefile"].invoke
    Dir.chdir("#{CPP_HART_GEN_DST}/#{build_name}/build") do
      sh "make"
    end
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

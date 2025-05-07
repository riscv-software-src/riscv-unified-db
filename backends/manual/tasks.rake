# frozen_string_literal: true

require "digest"

require_relative "#{$lib}/cfg_arch"

$root = Pathname.new(__FILE__).dirname.dirname.realpath if $root.nil?

MANUAL_GEN_DIR = $root / "gen" / "manual"

def versions_from_env(manual_name)
  versions = ENV["VERSIONS"].split(",")
  output_hash = nil
  if versions.include?("all")
    raise ArgumentError, "'all' was given as a version, so nothing else should be" unless versions.length == 1

    versions = []
    version_fns = Dir.glob("#{$root}/arch/manual_version/**/*.yaml")
    raise "Cannot find version files" if version_fns.empty?

    version_fns.each do |manual_version_fn|
      manual_version_obj = YAML.load_file(manual_version_fn, permitted_classes: [Date])
      versions << manual_version_obj["name"] if manual_version_obj["manual"]["$ref"] == "manual/#{manual_name}.yaml#"
    end
    output_hash = "all"
  else
    versions.each do |version|
      raise "No manual version #{version}" if Dir.glob("#{$root}/arch/manual_version/**/#{version}.yaml").empty?
    end
    output_hash = versions.size == 1 ? versions[0] : Digest::SHA2.hexdigest(versions.join(""))
  end

  [versions, output_hash]
end

directory MANUAL_GEN_DIR / "adoc"
directory MANUAL_GEN_DIR / "antora"
directory MANUAL_GEN_DIR / "html"

file MANUAL_GEN_DIR / "antora" / "antora.yml" => (MANUAL_GEN_DIR / "antora").to_s do |t|
  File.write t.name, <<~ANTORA
    name: riscv_manual
    version: #{cfg_arch.manual_version?}
    nav:
    - modules/nav.adoc
    title: RISC-V ISA Manual
  ANTORA
end

# Rule to create a chapter page in antora hierarchy
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/modules/chapters/pages/.*\.adoc} do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]
  version_name = parts[1]
  manual = cfg_arch_for("_").manual(parts[0])
  manual_version = manual.version(parts[1])
  chapter_name = File.basename(t.name, ".adoc")

  volume = manual_version.volumes.find { |v| !v.chapter(chapter_name).nil? }
  raise "Can't find any volume with chapter '#{chapter_name}'" if volume.nil?

  chapter = volume.chapter(chapter_name)

  FileUtils.mkdir_p File.dirname(t.name)
  FileUtils.ln_s chapter.fullpath, t.name
end

# Rule to create antora.yml for a manual version
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/antora.yml} => proc { |tname|
  parts = tname.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]
  version_name = parts[1]

  manual_yaml_path = $root / "arch" / "manual" / "#{manual_name}.yaml"
  version_paths = Dir.glob($root / "arch" / "manual_version" / "**" / "#{version_name}.yaml")
  raise "Cannot find version" unless version_paths.size == 1

  version_yaml_path = version_paths[0]

  raise "Cannot find #{manual_yaml_path}" unless manual_yaml_path.exist?

  [
    __FILE__,
    manual_yaml_path.to_s,
    version_yaml_path.to_s
  ]
} do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_version = cfg_arch_for("_").manual(parts[0])&.version(parts[1])

  raise "Can't find any manual version for '#{parts[0]}' '#{parts[1]}'" if manual_version.nil?

  File.write t.name, <<~ANTORA
    name: #{manual_version.manual.name}
    version: #{manual_version.name}
    display_version: #{manual_version.marketing_version}
    nav:
    - nav.adoc
    title: #{manual_version.manual.marketing_name}
  ANTORA
end

# Rule to create nav.adoc for a manual version
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/nav.adoc} => proc { |tname|
  parts = tname.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]
  version_name = parts[1]

  manual_yaml_path = $root / "arch" / "manual" / "#{manual_name}.yaml"
  version_paths = Dir.glob($root / "arch" / "manual_version" / "**" / "#{version_name}.yaml")
  raise "Cannot find version" unless version_paths.size == 1

  version_yaml_path = version_paths[0]
  nav_template_path = $root / "backends" / "manual" / "templates" / "#{manual_name}_nav.adoc.erb"

  raise "Cannot find #{manual_yaml_path}" unless manual_yaml_path.exist?

  FileList[
    __FILE__,
    manual_yaml_path.to_s,
    version_yaml_path.to_s,
    nav_template_path.to_s
  ]
} do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_version = cfg_arch_for("_").manual(parts[0])&.version(parts[1])

  raise "Can't find any manual version for '#{parts[0]}' '#{parts[1]}'" if manual_version.nil?

  nav_template_path = $root / "backends" / "manual" / "templates" / "#{parts[0]}_nav.adoc.erb"
  unless nav_template_path.exist?
    raise "There is no navigation file for manual '#{parts[0]}' at '#{nav_template_path}'"
  end

  raise "no cfg_arch" if manual_version.cfg_arch.nil?

  erb = ERB.new(nav_template_path.read, trim_mode: "-")
  erb.filename = nav_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AntoraUtils.resolve_links(erb.result(binding))
end

# Rule to create start page for a manual version
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/modules/ROOT/pages/index.adoc} => proc { |tname|
  parts = tname.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]
  version_name = parts[1]

  manual_yaml_path = $root / "arch" / "manual" / "#{manual_name}.yaml"
  version_paths = Dir.glob($root / "arch" / "manual_version" / "**" / "#{version_name}.yaml")
  raise "Cannot find version" unless version_paths.size == 1

  version_yaml_path = version_paths[0]

  version_index_template_path = $root / "backends" / "manual" / "templates" / "#{manual_name}_version_index.adoc.erb"

  raise "Cannot find #{manual_yaml_path}" unless manual_yaml_path.exist?
  raise "Cannot find #{version_index_template_path}" unless version_index_template_path.exist?

  FileList[
    __FILE__,
    manual_yaml_path.to_s,
    version_yaml_path.to_s,
    version_index_template_path.to_s
  ]
} do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_version = cfg_arch_for("_").manual(parts[0])&.version(parts[1])

  raise "Can't find any manual version for '#{parts[0]}' '#{parts[1]}'" if manual_version.nil?

  version_index_template_path = $root / "backends" / "manual" / "templates" / "#{parts[0]}_version_index.adoc.erb"
  unless version_index_template_path.exist?
    raise "There is no navigation file for manual '#{parts[0]}' at '#{version_index_template_path}'"
  end

  erb = ERB.new(version_index_template_path.read, trim_mode: "-")
  erb.filename = version_index_template_path.to_s
  puts erb.encoding

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, erb.result(binding)
end

# rule to create instruction appendix page
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/modules/insts/pages/.*.adoc} => [
  __FILE__,
  ($root / "backends" / "manual" / "templates" / "instruction.adoc.erb").to_s
] do |t|
  inst_name = File.basename(t.name, ".adoc")

  cfg_arch = cfg_arch_for("_")
  inst = cfg_arch.instruction(inst_name)
  raise "Can't find instruction '#{inst_name}'" if inst.nil?

  inst_template_path = $root / "backends" / "manual" / "templates" / "instruction.adoc.erb"
  erb = ERB.new(inst_template_path.read, trim_mode: "-")
  erb.filename = inst_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
end

# rule to create csr appendix page
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/modules/csrs/pages/.*\.adoc} => [
  __FILE__,
  "gen:arch",
  ($root / "backends" / "common_templates" / "adoc" / "csr.adoc.erb").to_s
] do |t|
  csr_name = File.basename(t.name, ".adoc")

  cfg_arch = cfg_arch_for("_")

  csr = cfg_arch.csr(csr_name)
  raise "Can't find csr '#{csr_name}'" if csr.nil?

  csr_template_path = $root / "backends" / "common_templates" / "adoc" / "csr.adoc.erb"
  erb = ERB.new(csr_template_path.read, trim_mode: "-")
  erb.filename = csr_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
end

# rule to create ext appendix page
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/modules/exts/pages/.*.adoc} => [
  __FILE__,
  ($root / "backends" / "manual" / "templates" / "ext.adoc.erb").to_s
] do |t|
  ext_name = File.basename(t.name, ".adoc")

  cfg_arch = cfg_arch_for("_")
  ext = cfg_arch.extension(ext_name)
  raise "Can't find extension '#{ext_name}'" if ext.nil?

  ext_template_path = $root / "backends" / "manual" / "templates" / "ext.adoc.erb"
  erb = ERB.new(ext_template_path.read, trim_mode: "-")
  erb.filename = ext_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
end

# rule to create IDL function appendix page
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/modules/funcs/pages/funcs.adoc} => [
  __FILE__,
  ($root / "backends" / "manual" / "templates" / "func.adoc.erb").to_s
] do |t|
  cfg_arch = cfg_arch_for("_")

  funcs_template_path = $root / "backends" / "manual" / "templates" / "func.adoc.erb"
  erb = ERB.new(funcs_template_path.read, trim_mode: "-")
  erb.filename = funcs_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
end

# rule to create IDL function appendix page
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/modules/params/pages/param_list.adoc} => [
  __FILE__,
  ($root / "backends" / "manual" / "templates" / "param_list.adoc.erb").to_s
] do |t|
  cfg_arch = cfg_arch_for("_")
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_version = cfg_arch.manual(parts[0])&.version(parts[1])

  param_list_template_path = $root / "backends" / "manual" / "templates" / "param_list.adoc.erb"
  erb = ERB.new(param_list_template_path.read, trim_mode: "-")
  erb.filename = param_list_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
end

rule %r{#{MANUAL_GEN_DIR}/.*/top/.*/antora/landing/antora.yml} => [
  __FILE__
] do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]

  cfg_arch = cfg_arch_for("_")
  manual = cfg_arch.manual(manual_name)
  raise "Can't find any manual version for '#{manual_name}'" if manual.nil?

  FileUtils.mkdir_p File.basename(t.name)
  File.write t.name, <<~ANTORA
    name: landing
    version: ~
    title: Home
  ANTORA
end

rule %r{#{MANUAL_GEN_DIR}/.*/top/.*/antora/landing/modules/ROOT/pages/index.adoc} => proc { |tname|
  parts = tname.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]
  versions, _ = versions_from_env(ENV["MANUAL_NAME"])
  version_files = Dir.glob($root / "arch" / "manual_version" / "**" / "*.yaml").select { |f| versions.include?(File.basename(f, ".yaml"))}
  FileList[
    __FILE__,
    ($root / "arch" / "manual" / "#{manual_name}.yaml").to_s,
    ($root / "backends" / "manual" / "templates" / "index.adoc.erb").to_s,
  ] + version_files
} do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]

  versions, output_hash = versions_from_env(manual_name)
  raise "unexpected mismatch" unless output_hash == parts[2]

  landing_template_path = $root / "backends" / "manual" / "templates" / "index.adoc.erb"
  erb = ERB.new(landing_template_path.read, trim_mode: "-")
  erb.filename = landing_template_path.to_s

  manual = cfg_arch_for("_").manual(manual_name)

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, erb.result(binding)
end

rule %r{#{MANUAL_GEN_DIR}/.*/top/.*/antora/playbook/playbook.yml} => proc { |tname|
  parts = tname.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]
  versions, _ = versions_from_env(ENV["MANUAL_NAME"])
  version_files = Dir.glob($root / "arch" / "manual_version" / "**" / "*.yaml").select { |f| versions.include?(File.basename(f, ".yaml"))}
  FileList[
    __FILE__,
    ($root / "arch" / "manual" / "#{manual_name}.yaml").to_s,
    ($root / "backends" / "manual" / "templates" / "playbook.yml.erb").to_s,
    ($root / "arch" / "manual" / manual_name / "**" / "contents.yaml").to_s
  ] + version_files
} do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]

  versions, output_hash = versions_from_env(manual_name)
  raise "unexpected mismatch" unless output_hash == parts[2]

  playbook_template_path = $root / "backends" / "manual" / "templates" / "playbook.yml.erb"
  erb = ERB.new(playbook_template_path.read, trim_mode: "-")
  erb.filename = playbook_template_path.to_s

  manual = cfg_arch_for("_").manual(manual_name)

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, erb.result(binding)
end

file $root / "ext" / "riscv-isa-manual" / "README.md" do
  sh "git submodule update --init ext/riscv-isa-manual 2>&1"
end

rule %r{#{MANUAL_GEN_DIR}/[^/]+/[^/]+/riscv-isa-manual/README.md} => ["#{$root}/ext/riscv-isa-manual/README.md"] do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/","").split("/")
  manual_version_name = parts[1]

  version_paths = Dir.glob("#{$root}/arch/manual_version/**/#{manual_version_name}.yaml")
  raise "No manual version named '#{manual_version_name}' found" unless version_paths.size == 1

  version_path = version_paths[0]

  version_obj = YAML.load_file(version_path, permitted_classes: [Date])
  raise "Not an isa manual version" unless version_obj["uses_isa_manual"] == true

  FileUtils.mkdir_p File.dirname(t.name)
  tree = version_obj["isa_manual_tree"]
  Dir.chdir($root / "ext" / "riscv-isa-manual") do
    Tempfile.create("isa-manual") do |tmpfile|
      sh "git archive --format=tar -o #{tmpfile.path} #{tree}"
      sh "tar xf #{tmpfile.path} -C #{File.dirname(t.name)}"
    end
  end
end

namespace :gen do
  desc File.read("#{File.dirname(__FILE__)}/README.adoc")
  task :html_manual do
    raise ArgumentError, "Missing required environment variable MANUAL_NAME\n\n#{html_manual_desc}" if ENV["MANUAL_NAME"].nil?
    raise ArgumentError, "Missing required environment variable VERSIONS\n\n#{html_manual_desc}" if ENV["VERSIONS"].nil?

    versions, output_hash = versions_from_env(ENV["MANUAL_NAME"])
    cfg_arch = cfg_arch_for("_")

    manual = cfg_arch.manual(ENV["MANUAL_NAME"])
    raise "No manual named '#{ENV['MANUAL_NAME']}" if manual.nil?


    # check out the correct version of riscv-isa-manual, if needed
    versions.each do |version|
      version_obj = cfg_arch.manual_version(version)

      manual.repo_path = MANUAL_GEN_DIR / ENV["MANUAL_NAME"] / version / "riscv-isa-manual"

      if version_obj.uses_isa_manual? == true \
         && !(MANUAL_GEN_DIR / ENV["MANUAL_NAME"] / version_obj.name / "riscv-isa-manual").exist?
        Rake::Task[MANUAL_GEN_DIR / ENV["MANUAL_NAME"] / version_obj.name / "riscv-isa-manual" / "README.md"].invoke
      end

      # create chapter pages in antora

      antora_path = MANUAL_GEN_DIR / ENV["MANUAL_NAME"] / version_obj.name / "antora"
      version_obj.volumes.each do |volume|
        volume.chapters.each do |chapter|
          Rake::Task[antora_path / "modules" / "chapters" / "pages" / "#{chapter.name}.adoc"].invoke
        end
      end
      Rake::Task[antora_path / "modules" / "funcs" / "pages" / "funcs.adoc"].invoke
      Rake::Task[antora_path / "modules" / "ROOT" / "pages" / "index.adoc"].invoke
      Rake::Task[antora_path / "antora.yml"].invoke
      Rake::Task[antora_path / "nav.adoc"].invoke

      $logger.info "Generating CSRs"
      version_obj.csrs.each do |csr|
        Rake::Task[antora_path / "modules" / "csrs" / "pages" / "#{csr.name}.adoc"].invoke
      end

      $logger.info "Generating Instructions"
      version_obj.instructions.each do |inst|
        Rake::Task[antora_path / "modules" / "insts" / "pages" / "#{inst.name}.adoc"].invoke
      end

      $logger.info "Generating Extensions"
      version_obj.extensions.each do |ext|
        Rake::Task[antora_path / "modules" / "exts" / "pages" / "#{ext.name}.adoc"].invoke
      end
      Rake::Task[antora_path / "modules" / "params" / "pages" / "param_list.adoc"].invoke
    end

    landing_page_path = MANUAL_GEN_DIR / ENV["MANUAL_NAME"] / "top" / output_hash / "antora" / "landing" / "modules" / "ROOT" / "pages" / "index.adoc"
    Rake::Task[landing_page_path].invoke

    landing_antora_path = MANUAL_GEN_DIR / ENV["MANUAL_NAME"] / "top" / output_hash / "antora" / "landing" / "antora.yml"
    Rake::Task[landing_antora_path].invoke

    playbook_path = MANUAL_GEN_DIR / ENV["MANUAL_NAME"] / "top" / output_hash / "antora" / "playbook" / "playbook.yml"
    Rake::Task[playbook_path].invoke

    $logger.info "Running Antora under npm for HTML site to create '#{MANUAL_GEN_DIR / ENV['MANUAL_NAME'] / output_hash / 'html'}'"

    sh [
      "npm exec -- antora",
      "--stacktrace",
      "generate",
      "--cache-dir=#{$root}/.home/.antora",
      "--to-dir=#{MANUAL_GEN_DIR}/#{ENV['MANUAL_NAME']}/top/#{output_hash}/html",
      "--log-level=all",
      "--fetch",
      playbook_path.to_s
    ].join(" ")

    $logger.info "Done running Antora under npm for HTML site to create '#{MANUAL_GEN_DIR / ENV['MANUAL_NAME'] / output_hash / 'html'}'"
  end
end

namespace :serve do
  desc "Serve an HTML site for one or more versions of the manual (gen:html_manual for options)"
  task :html_manual do
    Rake::Task["gen:html_manual"].invoke

    port = ENV.key?("PORT") ? ENV["PORT"] : 8000

    cfg_arch = cfg_arch_for("_")
    manual = cfg_arch.manuals.find { |m| m.name == ENV["MANUAL_NAME"] }
    raise "No manual '#{ENV['MANUAL_NAME']}'" if manual.nil?

    _, output_hash = versions_from_env(manual)

    html_dir = "#{MANUAL_GEN_DIR}/#{ENV['MANUAL_NAME']}/top/#{output_hash}/html"
    Dir.chdir(html_dir) do
      require "webrick"

      server = WEBrick::HTTPServer.new Port: port.to_i, DocumentRoot: html_dir.to_s
      trap("INT") { server.shutdown }
      puts "\n\nView server at http://#{`hostname`.strip}:#{port}\n\n"
      server.start
    end
  end
end

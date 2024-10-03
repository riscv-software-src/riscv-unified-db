# frozen_string_literal: true

require_relative "#{$lib}/arch_def"

$root = Pathname.new(__FILE__).dirname.dirname.realpath if $root.nil?

MANUAL_GEN_DIR = $root / "gen" / "manual"

def versions_from_env(manual)
  versions = ENV["VERSIONS"].split(",")
  output_hash = nil
  if versions.include?("all")
    raise ArgumentError, "'all' was given as a version, so nothing else should be" unless versions.length == 1

    versions = manual.versions
    output_hash = "all"
  else
    versions = versions.map { |vname| manual.versions.find { |v| v.name = vname } }
    if versions.any?(&:nil?)
      idx = versions.index(&:nil?)
      raise "No manual version '#{ENV['VERSIONS'].split(',')[idx]}' for '#{args[:manual_name]}'"
    end
    output_hash = versions.size == 1 ? versions[0] : versions.hash
  end

  [versions, output_hash]
end

directory MANUAL_GEN_DIR / "adoc"
directory MANUAL_GEN_DIR / "antora"
directory MANUAL_GEN_DIR / "html"

["inst", "csr", "ext"].each do |type|
  directory MANUAL_GEN_DIR / "antora" / "modules" / "#{type}s" / "pages"

  Dir.glob($root / "arch" / type / "**" / "*.yaml") do |fn|
    file MANUAL_GEN_DIR / "adoc" / "#{File.basename(fn, '.yaml')}.adoc" => [
      "gen:arch",
      (MANUAL_GEN_DIR / "adoc").to_s,
      ($root / "backends" / "manual" / "templates" / "#{type}.adoc.erb").to_s,
      __FILE__
    ] do |t|
      name = File.basename(t.name, ".adoc")

      arch_def = arch_def_for("_")
      erb = case type
            when "inst"
              inst = arch_def.instruction(name)
              raise "Could not find inst '#{name}'" if inst.nil?

              ERB.new(File.read($root / "backends" / "manual" / "templates" / "inst.adoc.erb"), trim_mode: "-")
            when "csr"
              csr = arch_def.csr(name)
              raise "Could not find inst '#{name}'" if csr.nil?

              ERB.new(File.read($root / "backends" / "manual" / "templates" / "csr.adoc.erb"), trim_mode: "-")
            when "ext"
              ext = arch_def.extension(name)
              raise "Could not find ext '#{name}'" if ext.nil?

              ERB.new(File.read($root / "backends" / "manual" / "templates" / "ext.adoc.erb"), trim_mode: "-")
            else
              raise "Unhandled type '#{type}'"
            end

      File.write(t.name, erb.result(binding))
    end

    file MANUAL_GEN_DIR / "antora" / "modules" / "#{type}s" / "pages" => [
      (MANUAL_GEN_DIR / "adoc" / "#{File.basename(fn, '.yaml')}.adoc").to_s,
      (MANUAL_GEN_DIR / "antora" / "modules" / "#{type}s" / "pages").to_s
    ] do |t|
      FileUtils.cp t.prerequisites.first, t.name
    end
  end
end

file MANUAL_GEN_DIR / "antora" / "antora.yml" => (MANUAL_GEN_DIR / "antora").to_s do |t|
  File.write t.name, <<~ANTORA
    name: riscv_manual
    version: #{arch_def.manual_version?}
    nav:
    - modules/nav.adoc
    title: RISC-V ISA Manual
  ANTORA
end

# Rule to create a chapter page in antora hierarchy
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/modules/chapters/pages/.*\.adoc} do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_version = arch_def_for("_").manual(parts[0]).version(parts[1])
  chapter_name = File.basename(t.name, ".adoc")

  volume = manual_version.volumes.find { |v| !v.chapter(chapter_name).nil? }
  raise "Can't find any volume with chapter '#{chapter_name}'" if volume.nil?

  chapter = volume.chapter(chapter_name)

  FileUtils.mkdir_p File.dirname(t.name)
  FileUtils.ln_s chapter.path, t.name
end

# Rule to create antora.yml for a manual version
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/antora.yml} => proc { |tname|
  parts = tname.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]
  version_name = parts[1]

  manual_yaml_path = $root / "arch" / "manual" / manual_name / "#{manual_name}.yaml"
  contents_path = $root / "arch" / "manual" / manual_name / version_name / "contents.yaml"

  raise "Cannot find #{manual_yaml_path}" unless manual_yaml_path.exist?
  raise "Cannot find #{contents_path}" unless contents_path.exist?

  [
    __FILE__,
    manual_yaml_path.to_s,
    contents_path.to_s
  ]
} do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_version = arch_def_for("_").manual(parts[0])&.version(parts[1])

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

  manual_yaml_path = $root / "arch" / "manual" / manual_name / "#{manual_name}.yaml"
  contents_path = $root / "arch" / "manual" / manual_name / version_name / "contents.yaml"
  nav_template_path = $root / "backends" / "manual" / "templates" / "#{manual_name}_nav.adoc.erb"

  raise "Cannot find #{manual_yaml_path}" unless manual_yaml_path.exist?
  raise "Cannot find #{contents_path}" unless contents_path.exist?

  FileList[
    __FILE__,
    manual_yaml_path.to_s,
    contents_path.to_s,
    nav_template_path.to_s
  ]
} do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_version = arch_def_for("_").manual(parts[0])&.version(parts[1])

  raise "Can't find any manual version for '#{parts[0]}' '#{parts[1]}'" if manual_version.nil?

  nav_template_path = $root / "backends" / "manual" / "templates" / "#{parts[0]}_nav.adoc.erb"
  unless nav_template_path.exist?
    raise "There is no navigation file for manual '#{parts[0]}' at '#{nav_template_path}'"
  end

  erb = ERB.new(nav_template_path.read, trim_mode: "-")
  erb.filename = nav_template_path.to_s
  puts erb.encoding

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, erb.result(binding)
end

# Rule to create start page for a manual version
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/modules/ROOT/pages/index.adoc} => proc { |tname|
  parts = tname.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]
  version_name = parts[1]

  manual_yaml_path = $root / "arch" / "manual" / manual_name / "#{manual_name}.yaml"
  contents_path = $root / "arch" / "manual" / manual_name / version_name / "contents.yaml"
  version_index_template_path = $root / "backends" / "manual" / "templates" / "#{manual_name}_version_index.adoc.erb"

  raise "Cannot find #{manual_yaml_path}" unless manual_yaml_path.exist?
  raise "Cannot find #{contents_path}" unless contents_path.exist?
  raise "Cannot find #{version_index_template_path}" unless version_index_template_path.exist?

  FileList[
    __FILE__,
    manual_yaml_path.to_s,
    contents_path.to_s,
    version_index_template_path.to_s
  ]
} do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_version = arch_def_for("_").manual(parts[0])&.version(parts[1])

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
  "gen:arch",
  ($root / "backends" / "manual" / "templates" / "instruction.adoc.erb").to_s
] do |t|
  inst_name = File.basename(t.name, ".adoc")

  arch_def = arch_def_for("_")
  inst = arch_def.instruction(inst_name)
  raise "Can't find instruction '#{inst_name}'" if inst.nil?

  inst_template_path = $root / "backends" / "manual" / "templates" / "instruction.adoc.erb"
  erb = ERB.new(inst_template_path.read, trim_mode: "-")
  erb.filename = inst_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AntoraUtils.resolve_links(erb.result(binding))
end

# rule to create csr appendix page
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/modules/csrs/pages/.*.adoc} => [
  __FILE__,
  "gen:arch",
  ($root / "backends" / "manual" / "templates" / "csr.adoc.erb").to_s
] do |t|
  csr_name = File.basename(t.name, ".adoc")

  arch_def = arch_def_for("_")
  csr = arch_def.csr(csr_name)
  raise "Can't find csr '#{csr_name}'" if csr.nil?

  csr_template_path = $root / "backends" / "manual" / "templates" / "csr.adoc.erb"
  erb = ERB.new(csr_template_path.read, trim_mode: "-")
  erb.filename = csr_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AntoraUtils.resolve_links(erb.result(binding))
end

# rule to create IDL function appendix page
rule %r{#{MANUAL_GEN_DIR}/.*/.*/antora/modules/funcs/pages/funcs.adoc} => [
  __FILE__,
  "gen:arch",
  ($root / "backends" / "manual" / "templates" / "func.adoc.erb").to_s
] do |t|
  arch_def = arch_def_for("_")

  funcs_template_path = $root / "backends" / "manual" / "templates" / "func.adoc.erb"
  erb = ERB.new(funcs_template_path.read, trim_mode: "-")
  erb.filename = funcs_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AntoraUtils.resolve_links(erb.result(binding))
end

rule %r{#{MANUAL_GEN_DIR}/.*/top/.*/antora/landing/antora.yml} => [
  __FILE__
] do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]

  arch_def = arch_def_for("_")
  manual = arch_def.manual(manual_name)
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
  FileList[
    __FILE__,
    ($root / "arch" / "manual" / manual_name / "#{manual_name}.yaml").to_s,
    ($root / "backends" / "manual" / "templates" / "index.adoc.erb").to_s,
    ($root / "arch" / "manual" / manual_name / "**" / "contents.yaml").to_s
  ]
} do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]

  arch_def = arch_def_for("_")
  manual = arch_def.manual(manual_name)
  raise "Can't find any manual version for '#{manual_name}'" if manual.nil?

  versions, output_hash = versions_from_env(manual)
  raise "unexpected mismatch" unless output_hash == parts[2]

  landing_template_path = $root / "backends" / "manual" / "templates" / "index.adoc.erb"
  erb = ERB.new(landing_template_path.read, trim_mode: "-")
  erb.filename = landing_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, erb.result(binding)
end

rule %r{#{MANUAL_GEN_DIR}/.*/top/.*/antora/playbook/playbook.yml} => proc { |tname|
  parts = tname.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]
  FileList[
    __FILE__,
    ($root / "arch" / "manual" / manual_name / "#{manual_name}.yaml").to_s,
    ($root / "backends" / "manual" / "templates" / "playbook.yml.erb").to_s,
    ($root / "arch" / "manual" / manual_name / "**" / "contents.yaml").to_s
  ]
} do |t|
  parts = t.name.sub("#{MANUAL_GEN_DIR}/", "").split("/")
  manual_name = parts[0]

  arch_def = arch_def_for("_")
  manual = arch_def.manual(manual_name)
  raise "Can't find any manual version for '#{manual_name}'" if manual.nil?

  versions, output_hash = versions_from_env(manual)
  raise "unexpected mismatch" unless output_hash == parts[2]

  playbook_template_path = $root / "backends" / "manual" / "templates" / "playbook.yml.erb"
  erb = ERB.new(playbook_template_path.read, trim_mode: "-")
  erb.filename = playbook_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, erb.result(binding)
end

file $root / "ext" / "riscv-isa-manual" / "README.md" do
  sh "git submodule update --init ext/riscv-isa-manual 2>&1"
end

Dir.glob($root / "arch" / "manual" / "**" / "contents.yaml") do |content_fn|
  file "#{File.dirname(content_fn)}/riscv-isa-manual/README.md" => ($root / "ext" / "riscv-isa-manual" / "README.md").to_s do |t|
    content_obj = YAML.load_file(content_fn)
    git_dir = `git rev-parse --git-dir`.strip
    cmd = [
      "git",
      "--git-dir=#{git_dir}/modules/ext/riscv-isa-manual",
      "worktree add",
      File.dirname(t.name),
      content_obj["isa_manual_tree"],
      "2>&1"
    ].join(" ")
    sh cmd
  end
end

namespace :gen do
  html_manual_desc = <<~DESC
    Generate an HTML site for one or more versions of the manual (./do --desc for options)

    Options:

     * MANUAL_NAME: The database name (key) of the manual to generate.
     * VERSIONS: A comma-separated list of versions to generate, or "all".

    Examples:

     ./do gen:html_manual MANUAL_NAME=isa VERSIONS=20191008,20240411
     ./do gen:html_manual MANUAL_NAME=isa VERSIONS=all

    Result:

      A static HTML website will be written into gen/manual/MANUAL_NAME/<hash of versions>/html
  DESC
  desc html_manual_desc
  task :html_manual => "gen:arch" do
    raise ArgumentError, "Missing required environment variable MANUAL_NAME\n\n#{html_manual_desc}" if ENV["MANUAL_NAME"].nil?
    raise ArgumentError, "Missing required environment variable VERSIONS\n\n#{html_manual_desc}" if ENV["VERSIONS"].nil?

    arch_def = arch_def_for("_")
    manual = arch_def.manuals.find { |m| m.name == ENV["MANUAL_NAME"] }
    raise "No manual '#{ENV['MANUAL_NAME']}'" if manual.nil?

    versions, output_hash = versions_from_env(manual)

    # check out the correct version of riscv-isa-manual, if needed
    versions.each do |version|
      next unless version.uses_isa_manual?

      unless ($root / "arch" / "manual" / ENV["MANUAL_NAME"] / version.name / "riscv-isa-manual").exist?
        Rake::Task[$root / "arch" / "manual" / ENV["MANUAL_NAME"] / version.name / "riscv-isa-manual" / "README.md"].invoke
      end
    end

    # create chapter pages in antora
    versions.each do |version|
      antora_path = MANUAL_GEN_DIR / ENV["MANUAL_NAME"] / version.name / "antora"
      version.volumes.each do |volume|
        volume.chapters.each do |chapter|
          Rake::Task[antora_path / "modules" / "chapters" / "pages" / "#{chapter.name}.adoc"].invoke
        end
      end
      Rake::Task[antora_path / "modules" / "funcs" / "pages" / "funcs.adoc"].invoke
      Rake::Task[antora_path / "modules" / "ROOT" / "pages" / "index.adoc"].invoke
      Rake::Task[antora_path / "antora.yml"].invoke
      Rake::Task[antora_path / "nav.adoc"].invoke
      version.instructions.each do |inst|
        Rake::Task[antora_path / "modules" / "insts" / "pages" / "#{inst.name}.adoc"].invoke
      end
      version.csrs.each do |csr|
        Rake::Task[antora_path / "modules" / "csrs" / "pages" / "#{csr.name}.adoc"].invoke
      end
    end

    landing_page_path = MANUAL_GEN_DIR / ENV["MANUAL_NAME"] / "top" / output_hash / "antora" / "landing" / "modules" / "ROOT" / "pages" / "index.adoc"
    Rake::Task[landing_page_path].invoke

    landing_antora_path = MANUAL_GEN_DIR / ENV["MANUAL_NAME"] / "top" / output_hash / "antora" / "landing" / "antora.yml"
    Rake::Task[landing_antora_path].invoke

    playbook_path = MANUAL_GEN_DIR / ENV["MANUAL_NAME"] / "top" / output_hash / "antora" / "playbook" / "playbook.yml"
    Rake::Task[playbook_path].invoke

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

    puts "SUCCESS: HTML site written to '#{MANUAL_GEN_DIR / ENV['MANUAL_NAME'] / output_hash / 'html'}'"
  end
end

namespace :serve do
  task :html_manual do |t|
    Rake::Task["gen:html_manual"].invoke

    port = ENV.key?("PORT") ? ENV["PORT"] : 8000

    arch_def = arch_def_for("_")
    manual = arch_def.manuals.find { |m| m.name == ENV["MANUAL_NAME"] }
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

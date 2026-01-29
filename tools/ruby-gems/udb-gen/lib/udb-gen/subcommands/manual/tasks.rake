# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

require "digest"

def versions_from_env(versions)
  manual_name = "isa"
  output_hash = nil
  if versions.include?("all")
    raise ArgumentError, "'all' was given as a version, so nothing else should be" unless versions.length == 1

    versions = []
    version_fns = Dir.glob("#{Rake.application.resolver.std_path}/manual_version/**/*.yaml")
    raise "Cannot find version files" if version_fns.empty?

    version_fns.each do |manual_version_fn|
      manual_version_obj = YAML.load_file(manual_version_fn, permitted_classes: [Date])
      versions << manual_version_obj["name"] if manual_version_obj["manual"]["$ref"] == "manual/#{manual_name}.yaml#"
    end
    output_hash = "all"
  else
    versions.each do |version|
      Udb.logger.warn "No manual version #{version} in the standard spec" if Dir.glob("#{Rake.application.resolver.std_path}/manual_version/**/#{version}.yaml").empty?
    end
    output_hash = versions.size == 1 ? versions[0] : Digest::SHA2.hexdigest(versions.join(""))
  end

  [versions, output_hash]
end

directory Rake.application.gen_dir / "adoc"
directory Rake.application.gen_dir / "antora"
directory Rake.application.gen_dir / "html"

file Rake.application.gen_dir / "antora" / "antora.yml" => (Rake.application.gen_dir / "antora").to_s do |t|
  File.write t.name, <<~ANTORA
    name: riscv_manual
    version: #{cfg_arch.manual_version?}
    nav:
    - modules/nav.adoc
    title: RISC-V ISA Manual
  ANTORA
end

# Rule to create a chapter page in antora hierarchy
rule %r{#{Rake.application.gen_dir}/.*/.*/antora/modules/chapters/pages/.*\.adoc} do |t|
  parts = t.name.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_name = parts[0]
  version_name = parts[1]
  manual = Rake.application.cfg_arch.manual(parts[0])
  manual_version = manual.version(parts[1])
  chapter_name = File.basename(t.name, ".adoc")

  volume = manual_version.volumes.find { |v| !v.chapter(chapter_name).nil? }
  raise "Can't find any volume with chapter '#{chapter_name}'" if volume.nil?

  chapter = volume.chapter(chapter_name)

  FileUtils.mkdir_p File.dirname(t.name)
  FileUtils.ln_s chapter.fullpath, t.name
end

# Rule to create antora.yml for a manual version
rule %r{#{Rake.application.gen_dir}/.*/.*/antora/antora.yml} => proc { |tname|
  parts = tname.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_name = parts[0]
  version_name = parts[1]

  cfg_arch = Rake.application.cfg_arch
  manual = cfg_arch.manual(manual_name)
  version = cfg_arch.manual_version(version_name)

  raise "Cannot find manual" if manual.nil?
  raise "Cannot find version" if version.nil?

  [
    __FILE__,
    manual.__source,
    version.__source
  ]
} do |t|
  parts = t.name.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_version = Rake.application.cfg_arch.manual(parts[0])&.version(parts[1])

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
rule %r{#{Rake.application.gen_dir}/.*/.*/antora/nav.adoc} => proc { |tname|
  parts = tname.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_name = parts[0]
  version_name = parts[1]

  cfg_arch = Rake.application.cfg_arch
  manual = cfg_arch.manual(manual_name)
  version = cfg_arch.manual_version(version_name)

  raise "Cannot find manual" if manual.nil?
  raise "Cannot find version" if version.nil?

  nav_template_path = UdbGen.root / "templates" / "manual" / "#{manual_name}_nav.adoc.erb"

  FileList[
    __FILE__,
    manual.__source,
    version.__source,
    nav_template_path.to_s
  ]
} do |t|
  parts = t.name.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_version = Rake.application.cfg_arch.manual(parts[0])&.version(parts[1])

  raise "Can't find any manual version for '#{parts[0]}' '#{parts[1]}'" if manual_version.nil?

  nav_template_path = UdbGen.root / "templates" / "manual" / "#{parts[0]}_nav.adoc.erb"
  unless nav_template_path.exist?
    raise "There is no navigation file for manual '#{parts[0]}' at '#{nav_template_path}'"
  end

  raise "no cfg_arch" if manual_version.cfg_arch.nil?

  erb = ERB.new(nav_template_path.read, trim_mode: "-")
  erb.filename = nav_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, Udb::Helpers::AntoraUtils.resolve_links(erb.result(binding))
end

# Rule to create start page for a manual version
rule %r{#{Rake.application.gen_dir}/.*/.*/antora/modules/ROOT/pages/index.adoc} => proc { |tname|
  parts = tname.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_name = parts[0]
  version_name = parts[1]

  cfg_arch = Rake.application.cfg_arch
  manual = cfg_arch.manual(manual_name)
  version = cfg_arch.manual_version(version_name)

  raise "Cannot find manual" if manual.nil?
  raise "Cannot find version" if version.nil?

  version_index_template_path = UdbGen.root / "templates" / "manual" / "#{manual_name}_version_index.adoc.erb"

  raise "Cannot find #{version_index_template_path}" unless version_index_template_path.exist?

  FileList[
    __FILE__,
    manual.__source,
    version.__source,
    version_index_template_path.to_s
  ]
} do |t|
  parts = t.name.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_version = Rake.application.cfg_arch.manual(parts[0])&.version(parts[1])

  raise "Can't find any manual version for '#{parts[0]}' '#{parts[1]}'" if manual_version.nil?

  version_index_template_path = UdbGen.root / "templates" / "manual" / "#{parts[0]}_version_index.adoc.erb"
  unless version_index_template_path.exist?
    raise "There is no navigation file for manual '#{parts[0]}' at '#{version_index_template_path}'"
  end

  erb = ERB.new(version_index_template_path.read, trim_mode: "-")
  erb.filename = version_index_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, erb.result(binding)
end

# rule to create instruction appendix page
rule %r{#{Rake.application.gen_dir}/.*/.*/antora/modules/insts/pages/.*.adoc} => [
  __FILE__,
  (UdbGen.root / "templates" / "manual" / "instruction.adoc.erb").to_s
] do |t|
  inst_name = File.basename(t.name, ".adoc")

  cfg_arch = Rake.application.cfg_arch
  inst = cfg_arch.instruction(inst_name)
  raise "Can't find instruction '#{inst_name}'" if inst.nil?

  inst_template_path = UdbGen.root / "templates" / "manual" / "instruction.adoc.erb"
  erb = ERB.new(inst_template_path.read, trim_mode: "-")
  erb.filename = inst_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, Udb::Helpers::AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
end

# rule to create csr appendix page
rule %r{#{Rake.application.gen_dir}/.*/.*/antora/modules/csrs/pages/.*\.adoc} => [
  __FILE__,
  (UdbGen.root / "templates" / "common" / "csr.adoc.erb").to_s
] do |t|
  csr_name = File.basename(t.name, ".adoc")

  cfg_arch = Rake.application.cfg_arch

  csr = cfg_arch.csr(csr_name)
  raise "Can't find csr '#{csr_name}'" if csr.nil?

  csr_template_path = UdbGen.root / "templates" / "common" / "csr.adoc.erb"
  erb = ERB.new(csr_template_path.read, trim_mode: "-")
  erb.filename = csr_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, Udb::Helpers::AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
end

# rule to create ext appendix page
rule %r{#{Rake.application.gen_dir}/.*/.*/antora/modules/exts/pages/.*.adoc} => [
  __FILE__,
  (UdbGen.root / "templates" / "manual" / "ext.adoc.erb").to_s
] do |t|
  ext_name = File.basename(t.name, ".adoc")

  cfg_arch = Rake.application.cfg_arch
  ext = cfg_arch.extension(ext_name)
  raise "Can't find extension '#{ext_name}'" if ext.nil?

  ext_template_path = UdbGen.root / "templates" / "manual" / "ext.adoc.erb"
  erb = ERB.new(ext_template_path.read, trim_mode: "-")
  erb.filename = ext_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, Udb::Helpers::AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
end

# rule to create IDL function appendix page
rule %r{#{Rake.application.gen_dir}/.*/.*/antora/modules/funcs/pages/funcs.adoc} => [
  __FILE__,
  (UdbGen.root / "templates" / "manual" / "func.adoc.erb").to_s
] do |t|
  cfg_arch = Rake.application.cfg_arch

  funcs_template_path = UdbGen.root / "templates" / "manual" / "func.adoc.erb"
  erb = ERB.new(funcs_template_path.read, trim_mode: "-")
  erb.filename = funcs_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, Udb::Helpers::AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
end

# rule to create IDL function appendix page
rule %r{#{Rake.application.gen_dir}/.*/.*/antora/modules/params/pages/param_list.adoc} => [
  __FILE__,
  (UdbGen.root / "templates" / "manual" / "param_list.adoc.erb").to_s
] do |t|
  cfg_arch = Rake.application.cfg_arch
  parts = t.name.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_version = cfg_arch.manual(parts[0])&.version(parts[1])

  param_list_template_path = UdbGen.root / "templates" / "manual" / "param_list.adoc.erb"
  erb = ERB.new(param_list_template_path.read, trim_mode: "-")
  erb.filename = param_list_template_path.to_s

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, Udb::Helpers::AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
end

rule %r{#{Rake.application.gen_dir}/.*/top/.*/antora/landing/antora.yml} => [
  __FILE__
] do |t|
  parts = t.name.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_name = parts[0]

  cfg_arch = Rake.application.cfg_arch
  manual = cfg_arch.manual(manual_name)
  raise "Can't find any manual version for '#{manual_name}'" if manual.nil?

  FileUtils.mkdir_p File.basename(t.name)
  File.write t.name, <<~ANTORA
    name: landing
    version: ~
    title: Home
  ANTORA
end

rule %r{#{Rake.application.gen_dir}/.*/top/.*/antora/landing/modules/ROOT/pages/index.adoc} => proc { |tname|
  parts = tname.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_name = parts[0]
  versions, _ = versions_from_env(Rake.application.versions)
  cfg_arch = Rake.application.cfg_arch
  version_files = versions.map { |v| cfg_arch.manual_version(v).__source }
  manual = cfg_arch.manual(manual_name)
  FileList[
    __FILE__,
    manual.__source,
    (UdbGen.root / "templates" / "manual" / "index.adoc.erb").to_s,
  ] + version_files
} do |t|
  parts = t.name.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_name = parts[0]

  versions, output_hash = versions_from_env(Rake.application.versions)
  raise "unexpected mismatch" unless output_hash == parts[2]

  landing_template_path = UdbGen.root / "templates" / "manual" / "index.adoc.erb"
  erb = ERB.new(landing_template_path.read, trim_mode: "-")
  erb.filename = landing_template_path.to_s

  manual = Rake.application.cfg_arch.manual(manual_name)

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, erb.result(binding)
end

rule %r{#{Rake.application.gen_dir}/.*/top/.*/antora/playbook/playbook.yml} => proc { |tname|
  parts = tname.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_name = parts[0]
  versions, _ = versions_from_env(Rake.application.versions)
  cfg_arch = Rake.application.cfg_arch
  version_files = versions.map { |v| cfg_arch.manual_version(v).__source }
  manual = cfg_arch.manual(manual_name)
  FileList[
    __FILE__,
    manual.__source,
    (UdbGen.root / "templates" / "manual" / "playbook.yml.erb").to_s,
  ] + version_files
} do |t|
  parts = t.name.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_name = parts[0]

  versions, output_hash = versions_from_env(Rake.application.versions)
  raise "unexpected mismatch" unless output_hash == parts[2]

  playbook_template_path = UdbGen.root / "templates" / "manual" / "playbook.yml.erb"
  erb = ERB.new(playbook_template_path.read, trim_mode: "-")
  erb.filename = playbook_template_path.to_s

  manual = Rake.application.cfg_arch.manual(manual_name)

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, erb.result(binding)
end

file Udb.repo_root / "ext" / "riscv-isa-manual" / "README.md" do
  sh "git submodule update --init ext/riscv-isa-manual 2>&1"
end

rule %r{#{Rake.application.gen_dir}/[^/]+/[^/]+/riscv-isa-manual/README.md} => ["#{Udb.repo_root}/ext/riscv-isa-manual/README.md"] do |t|
  parts = t.name.sub("#{Rake.application.gen_dir}/", "").split("/")
  manual_version_name = parts[1]

  cfg_arch = Rake.application.cfg_arch
  version = cfg_arch.manual_version(manual_version_name)

  raise "No manual version named '#{manual_version_name}' found" if version.nil?

  FileUtils.mkdir_p File.dirname(t.name)
  tree = version.isa_manual_tree
  Dir.chdir(Udb.repo_root / "ext" / "riscv-isa-manual") do
    Tempfile.create("isa-manual") do |tmpfile|
      sh "git archive --format=tar -o #{tmpfile.path} #{tree}"
      sh "tar xf #{tmpfile.path} -C #{File.dirname(t.name)}"
    end
  end
end

namespace :gen do
  task :html_manual do
    versions, output_hash = versions_from_env(Rake.application.versions)
    cfg_arch = Rake.application.cfg_arch

    manual = cfg_arch.manual("isa")

    # check out the correct version of riscv-isa-manual, if needed
    versions.each do |version|
      version_obj = cfg_arch.manual_version(version)

      manual.repo_path = Rake.application.gen_dir / "isa" / version / "riscv-isa-manual"

      if version_obj.uses_isa_manual? == true \
         && !(Rake.application.gen_dir / "isa" / version_obj.name / "riscv-isa-manual").exist?
        Rake::Task[Rake.application.gen_dir / "isa" / version_obj.name / "riscv-isa-manual" / "README.md"].invoke
      end

      # create chapter pages in antora

      antora_path = Rake.application.gen_dir / "isa" / version_obj.name / "antora"
      version_obj.volumes.each do |volume|
        volume.chapters.each do |chapter|
          Rake::Task[antora_path / "modules" / "chapters" / "pages" / "#{chapter.name}.adoc"].invoke
        end
      end
      Rake::Task[antora_path / "modules" / "funcs" / "pages" / "funcs.adoc"].invoke
      Rake::Task[antora_path / "modules" / "ROOT" / "pages" / "index.adoc"].invoke
      Rake::Task[antora_path / "antora.yml"].invoke
      Rake::Task[antora_path / "nav.adoc"].invoke

      Udb.logger.info "Generating CSRs"
      version_obj.csrs.each do |csr|
        Rake::Task[antora_path / "modules" / "csrs" / "pages" / "#{csr.name}.adoc"].invoke
      end

      Udb.logger.info "Generating Instructions"
      version_obj.instructions.each do |inst|
        Rake::Task[antora_path / "modules" / "insts" / "pages" / "#{inst.name}.adoc"].invoke
      end

      Udb.logger.info "Generating Extensions"
      version_obj.extensions.each do |ext|
        Rake::Task[antora_path / "modules" / "exts" / "pages" / "#{ext.name}.adoc"].invoke
      end
      Rake::Task[antora_path / "modules" / "params" / "pages" / "param_list.adoc"].invoke
    end

    landing_page_path = Rake.application.gen_dir / "isa" / "top" / output_hash / "antora" / "landing" / "modules" / "ROOT" / "pages" / "index.adoc"
    Rake::Task[landing_page_path].invoke

    landing_antora_path = Rake.application.gen_dir / "isa" / "top" / output_hash / "antora" / "landing" / "antora.yml"
    Rake::Task[landing_antora_path].invoke

    playbook_path = Rake.application.gen_dir / "isa" / "top" / output_hash / "antora" / "playbook" / "playbook.yml"
    Rake::Task[playbook_path].invoke

    Udb.logger.info "Running Antora for HTML site to create '#{Rake.application.gen_dir / "isa" / output_hash / 'html'}'"

    # antora requires that the source directories be git repositories
    versions.each do |version_name|
      dir = Rake.application.gen_dir / manual.name / version_name / "antora"
      gitfile = dir / ".git"
      unless gitfile.exist?
        Dir.chdir dir do
          sh "git init"
          sh "git add *"
          sh "git config --local user.email 'me@you.com'" # doesn't matter
          sh "git config --local user.name 'Me You'" # doesn't matter
          sh "git config --local init.defaultBranch main"
          sh "git commit --no-verify -m 'initial'"
        end
      end
    end

    landing_dir = Rake.application.gen_dir / manual.name / "top" / output_hash / "antora" / "landing"
    gitfile = landing_dir / ".git"
    unless gitfile.exist?
      Dir.chdir landing_dir do
        sh "git init"
        sh "git add *"
        sh "git config --local user.email 'me@you.com'" # doesn't matter
        sh "git config --local user.name 'Me You'" # doesn't matter
        sh "git config --local init.defaultBranch main"
        sh "git commit --no-verify -m 'initial'"
      end
    end

    sh [
      "/opt/node/node_modules/.bin/antora",
      "--stacktrace",
      "generate",
      "--cache-dir=#{Udb.repo_root}/.home/.antora",
      "--to-dir=#{Rake.application.gen_dir}/isa/top/#{output_hash}/html",
      "--log-level=all",
      "--fetch",
      playbook_path.to_s
    ].join(" ")

    Udb.logger.info "Done running Antora for HTML site to create '#{Rake.application.gen_dir / "isa" / output_hash / 'html'}'"
  end
end

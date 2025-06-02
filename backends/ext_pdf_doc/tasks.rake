# frozen_string_literal: true

require "pathname"

require "idlc/passes/gen_adoc"

EXT_PDF_DOC_DIR = Pathname.new "#{$root}/backends/ext_pdf_doc"

file "#{$root}/ext/docs-resources/themes/riscv-pdf.yml" => "#{$root}/.gitmodules" do |t|
  system "git submodule update --init ext/docs-resources"
end

rule %r{#{$root}/gen/ext_pdf_doc/.*/pdf/.*_extension\.pdf} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/ext_pdf_doc").to_s.split("/")[0]
  ext_name = Pathname.new(tname).basename(".pdf").to_s.split("_")[0..-2].join("_")
  [
    ENV["THEME"],
    "#{$root}/ext/docs-resources/themes/riscv-pdf.yml",
    "#{$root}/gen/ext_pdf_doc/#{config_name}/adoc/#{ext_name}_extension.adoc"
  ]
} do |t|
  ext_name = Pathname.new(t.name).basename(".pdf").to_s.split("_")[0..-2].join("_")
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/ext_pdf_doc").to_s.split("/")[0]
  adoc_file = "#{$root}/gen/ext_pdf_doc/#{config_name}/adoc/#{ext_name}_extension.adoc"

  FileUtils.mkdir_p File.dirname(t.name)
  sh [
    "asciidoctor-pdf",
    "-w",
    "-v",
    "-a toc",
    "-a compress",
    "-a pdf-theme=#{ENV['THEME']}",
    "-a pdf-fontsdir=#{$root}/ext/docs-resources/fonts",
    "-a imagesdir=#{$root}/ext/docs-resources/images",
    "-r asciidoctor-diagram",
    "-r #{$root}/backends/ext_pdf_doc/idl_lexer",
    "-o #{t.name}",
    adoc_file
  ].join(" ")

  puts
  puts "Success!! File written to #{t.name}"
end

rule %r{#{$root}/gen/ext_pdf_doc/.*/html/.*_extension\.html} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/ext_pdf_doc").to_s.split("/")[0]
  ext_name = Pathname.new(tname).basename(".html").to_s.split("_")[0..-2].join("_")
  [
    "#{$root}/gen/ext_pdf_doc/#{config_name}/adoc/#{ext_name}_extension.adoc"
  ]
} do |t|
  ext_name = Pathname.new(t.name).basename(".html").to_s.split("_")[0..-2].join("_")
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/ext_pdf_doc").to_s.split("/")[0]
  adoc_file = "#{$root}/gen/ext_pdf_doc/#{config_name}/adoc/#{ext_name}_extension.adoc"

  FileUtils.mkdir_p File.dirname(t.name)
  sh [
    "asciidoctor",
    "-w",
    "-v",
    "-a toc",
    "-r asciidoctor-diagram",
    "-o #{t.name}",
    adoc_file
  ].join(" ")

  puts
  puts "Success!! File written to #{t.name}"
end

rule %r{#{$root}/gen/ext_pdf_doc/.*/adoc/.*_extension\.adoc} => proc { |tname|
  config_name = Pathname.new(tname).relative_path_from("#{$root}/gen/ext_pdf_doc").to_s.split("/")[0]
  arch_yaml_paths = Dir.glob("#{$root}/arch/**/*.yaml")
  cfg_path = $root / "gen" / "ext_pdf_doc" / "#{config_name}.yaml"
  cfg = FileConfig.create(cfg_path)
  arch_yaml_paths += Dir.glob("#{cfg.arch_overlay_abs}/**/*.yaml") unless cfg.arch_overlay.nil?
  [
    (EXT_PDF_DOC_DIR / "templates" / "ext_pdf.adoc.erb").to_s,
    arch_yaml_paths,
    (cfg_path).to_s,
    __FILE__
  ].flatten
} do |t|
  config_name = Pathname.new(t.name).relative_path_from("#{$root}/gen/ext_pdf_doc").to_s.split("/")[0]
  config_path = $root / "gen" / "ext_pdf_doc" / "#{config_name}.yaml"

  cfg_arch = cfg_arch_for(config_path)

  ext_name = Pathname.new(t.name).basename(".adoc").to_s.split("_")[0..-2].join("_")

  template_path = EXT_PDF_DOC_DIR / "templates" / "ext_pdf.adoc.erb"
  erb = ERB.new(template_path.read, trim_mode: "-")
  erb.filename = template_path.to_s

  ext = cfg_arch.extension(ext_name)
  version_strs = ENV["VERSION"].split(",")
  versions =
    if version_strs.include?("all")
      ext.versions
    else
      vs = ext.versions.select do |ext_ver|
        version_strs.any? { |v| v != "latest" && ext_ver.version_spec == VersionSpec.new(v) }
      end
      vs << ext.max_version if version_strs.include?("latest")
      vs.uniq
    end
  raise "No version matches #{ENV['VERSION']}" if versions.empty?

  max_version = versions.max { |a, b| a.version <=> b.version }
  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AsciidocUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
end

namespace :gen do
  desc <<~DESC
    Generate PDF documentation for :extension

    If the extension is custom (from an arch_overlay), also give the config name

    Options:

     * EXT     - The extension name
     * CFG     - Path to cfg with arch overlay, if needed. Can be either the name of a .yaml file in cfgs,
                 a relative path from CWD, or an absolute path.
     * VERSION - A list of versions to include. May also be "all" or "latest".
     * THEME   - path to an AsciidocPDF theme file. If not set, will use default RVI theme.

    Examples:

     ./do gen:ext_pdf EXT=Xqci CFG=qc_iu VERSION=latest THEME=my_theme.yaml
     ./do gen:ext_pdf EXT=B VERSION=all
     ./do gen:ext_pdf EXT=B VERSION=1.0.0
     ./do gen:ext_pdf EXT=B VERSION=1.0.0,1.1.0

  DESC
  task :ext_pdf do
    raise ArgumentError, "Missing required argument EXT" if ENV["EXT"].nil?

    extension = ENV["EXT"]
    cfg = ENV["CFG"]
    version = ENV["VERSION"]
    ENV["THEME"] =
      if ENV["THEME"].nil?
        "#{$root}/ext/docs-resources/themes/riscv-pdf.yml"
      else
        Pathname.new(ENV["THEME"]).realpath.to_s
      end

    cfg =
      if cfg.nil?
        "#{$root}/cfgs/_.yaml"
      elsif File.exist?("#{$root}/cfgs/#{cfg}.yaml")
        "#{$root}/cfgs/#{cfg}.yaml"
      elsif File.exist?("#{$root}/cfgs/#{cfg}")
        "#{$root}/cfgs/#{cfg}"
      elsif File.exist?(cfg)
        File.realpath(cfg)
      else
        raise "Cannot find config '#{config}'"
      end

    config_name = File.basename(cfg, ".yaml")

    versions = version.split(",")
    raise ArgumentError, "Nothing else should be specified with 'all'" if versions.include?("all") && versions.size > 1

    unless File.exist?($root / "gen" / "ext_pdf_doc" / File.basename(cfg))
      FileUtils.mkdir_p($root / "gen" / "ext_pdf_doc")
      FileUtils.ln_s(cfg, $root / "gen" / "ext_pdf_doc" / File.basename(cfg))
    end
    Rake::Task[$root / "gen" / "ext_pdf_doc" / config_name / "pdf" / "#{extension}_extension.pdf"].invoke
  end

  desc <<~DESC
    Generate HTML documentation for :extension that is defined or overlaid in :cfg

    The latest version will be used, but can be overloaded by setting the EXT_VERSION environment variable.
  DESC
  task :cfg_ext_html, [:extension, :cfg] do |_t, args|
    raise ArgumentError, "Missing required argument :extension" if args[:extension].nil?
    raise ArgumentError, "Missing required argument :cfg" if args[:cfg].nil?

    extension = args[:extension]

    Rake::Task[$root / "gen" / "ext_pdf_doc" / args[:cfg] / "html" / "#{extension}_extension.html"].invoke(args)
  end
end

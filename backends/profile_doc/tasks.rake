# frozen_string_literal: true

rule %r{#{$root}/gen/profile_doc/adoc/.*\.adoc} => proc { |tname|
  profile_family_name = Pathname.new(tname).basename(".adoc")

  [
    "#{$root}/.stamps/arch-gen.stamp",
    __FILE__,
    "#{$root}/lib/arch_obj_models/profile.rb",
    "#{$root}/backends/profile_doc/templates/profile_pdf.adoc.erb"
  ] + Dir.glob("#{$root}/arch/profile/**/*.yaml")
} do |t|
  profile_family_name = Pathname.new(t.name).basename(".adoc").to_s

  profile_family = arch_def_for("_64").profile_family(profile_family_name)
  raise ArgumentError, "No profile family named '#{profile_family_name}'" if profile_family.nil?

  template_path = Pathname.new "#{$root}/backends/profile_doc/templates/profile_pdf.adoc.erb"
  erb = ERB.new(template_path.read, trim_mode: "-")
  erb.filename = template_path.to_s

  arch_def = arch_def_for("_64")

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AsciidocUtils.resolve_links(arch_def.find_replace_links(erb.result(binding)))
  puts "Generated adoc source at #{t.name}"
end

rule %r{#{$root}/gen/profile_doc/pdf/.*\.pdf} => proc { |tname|
  profile_family_name = Pathname.new(tname).basename(".pdf")
  [__FILE__, "#{$root}/gen/profile_doc/adoc/#{profile_family_name}.adoc"]
} do |t|
  profile_family_name = Pathname.new(t.name).basename(".pdf")

  adoc_filename = "#{$root}/gen/profile_doc/adoc/#{profile_family_name}.adoc"

  FileUtils.mkdir_p File.dirname(t.name)
  sh [
    "asciidoctor-pdf",
    "-w",
    "-v",
    "-a toc",
    "-a compress",
    "-a pdf-theme=#{$root}/ext/docs-resources/themes/riscv-pdf.yml",
    "-a pdf-fontsdir=#{$root}/ext/docs-resources/fonts",
    "-a imagesdir=#{$root}/ext/docs-resources/images",
    "-r asciidoctor-diagram",
    "-r #{$root}/backends/ext_pdf_doc/idl_lexer",
    "-o #{t.name}",
    adoc_filename
  ].join(" ")

  puts
  puts "SUCCESS! File written to #{t.name}"
end

rule %r{#{$root}/gen/profile_doc/html/.*\.html} => proc { |tname|
  profile_family_name = Pathname.new(tname).basename(".html")
  [__FILE__, "#{$root}/gen/profile_doc/adoc/#{profile_family_name}.adoc"]
} do |t|
  profile_family_name = Pathname.new(t.name).basename(".html")

  adoc_filename = "#{$root}/gen/profile_doc/adoc/#{profile_family_name}.adoc"

  FileUtils.mkdir_p File.dirname(t.name)
  sh [
    "asciidoctor",
    "-w",
    "-v",
    "-a toc",
    "-a imagesdir=#{$root}/ext/docs-resources/images",
    "-r asciidoctor-diagram",
    "-r #{$root}/backends/ext_pdf_doc/idl_lexer",
    "-o #{t.name}",
    adoc_filename
  ].join(" ")

  puts
  puts "SUCCESS! File written to #{t.name}"
end

namespace :gen do
  desc "Create a specification PDF for +profile_family+"
  task :profile_pdf, [:profile_family] => ["gen:arch"] do |_t, args|
    family_name = args[:profile_family]
    raise ArgumentError, "Missing required option +profile_family+" if family_name.nil?

    family = arch_def_for("_64").profile_family(family_name)
    raise ArgumentError, "No profile family named '#{family_name}" if family.nil?

    Rake::Task["#{$root}/gen/profile_doc/pdf/#{family_name}.pdf"].invoke
  end

  desc "Create a specification HTML for +profile_family+"
  task :profile_html, [:profile_family] => ["gen:arch"] do |_t, args|
    family_name = args[:profile_family]
    raise ArgumentError, "Missing required option +profile_family+" if family_name.nil?

    family = arch_def_for("_64").profile_family(family_name)
    raise ArgumentError, "No profile family named '#{family_name}" if family.nil?

    Rake::Task["#{$root}/gen/profile_doc/html/#{family_name}.html"].invoke
  end
end

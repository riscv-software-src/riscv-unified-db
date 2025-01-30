# frozen_string_literal: true

rule %r{#{$root}/gen/profile_doc/adoc/.*\.adoc} => [
  __FILE__,
  "#{$root}/lib/arch_obj_models/profile.rb",
  "#{$root}/backends/profile_doc/templates/profile.adoc.erb",
  Dir.glob("#{$root}/arch/profile_release/**/*.yaml")
].flatten do |t|
  profile_release_name = Pathname.new(t.name).basename(".adoc").to_s
  profile_release = cfg_arch_for("_").profile_release(profile_release_name)
  raise ArgumentError, "No profile release named '#{profile_release_name}'" if profile_release.nil?

  template_path = Pathname.new "#{$root}/backends/profile_doc/templates/profile.adoc.erb"
  erb = ERB.new(template_path.read, trim_mode: "-")
  erb.filename = template_path.to_s

  # Switch to the generated profile certificate cfg arch and set some variables available to ERB template.
  cfg_arch = cfg_arch_for("_")

  # Create empty binding and then specify explicitly which variables the ERB template can access.
  def create_empty_binding
    binding
  end
  erb_binding = create_empty_binding
  erb_binding.local_variable_set(:cfg_arch, cfg_arch)
  erb_binding.local_variable_set(:profile_class, profile_release.profile_class)
  erb_binding.local_variable_set(:profile_release, profile_release)
  erb_binding.local_variable_set(:portfolio_class, profile_release.profile_class)

  FileUtils.mkdir_p File.dirname(t.name)
  File.write t.name, AsciidocUtils.resolve_links(cfg_arch.find_replace_links(erb.result(erb_binding)))
  puts "Generated adoc source at #{t.name}"
end

rule %r{#{$root}/gen/profile_doc/pdf/.*\.pdf} => proc { |tname|
  profile_release_name = Pathname.new(tname).basename(".pdf")
  [__FILE__, "#{$root}/gen/profile_doc/adoc/#{profile_release_name}.adoc"]
} do |t|
  profile_release_name = Pathname.new(t.name).basename(".pdf")

  adoc_filename = "#{$root}/gen/profile_doc/adoc/#{profile_release_name}.adoc"

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
  profile_release_name = Pathname.new(tname).basename(".html")
  [__FILE__, "#{$root}/gen/profile_doc/adoc/#{profile_release_name}.adoc"]
} do |t|
  profile_release_name = Pathname.new(t.name).basename(".html")

  adoc_filename = "#{$root}/gen/profile_doc/adoc/#{profile_release_name}.adoc"

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
  desc "Create a specification PDF for +profile_release+"
  task :profile, [:profile_release] do |_t, args|
    profile_release_name = args[:profile_release]
    raise ArgumentError, "Missing required option +profile_release+" if profile_release_name.nil?

    profile_release = cfg_arch_for("_").profile_release(profile_release_name)
    raise ArgumentError, "No profile release named '#{profile_release_name}'" if profile_release.nil?

    Rake::Task["#{$root}/gen/profile_doc/pdf/#{profile_release_name}.pdf"].invoke
  end

  desc "Create a specification HTML for +profile_release+"
  task :profile_html, [:profile_release] do |_t, args|
    profile_release_name = args[:profile_release]
    raise ArgumentError, "Missing required option +profile_release+" if profile_release_name.nil?

    profile_release = cfg_arch_for("_").profile_release(profile_release_name)
    raise ArgumentError, "No profile release named '#{profile_release_name}" if profile_release.nil?

    Rake::Task["#{$root}/gen/profile_doc/html/#{profile_release_name}.html"].invoke
  end
end

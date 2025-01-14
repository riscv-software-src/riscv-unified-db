# frozen_string_literal: true

require "pathname"

require "asciidoctor-pdf"
require "asciidoctor-diagram"

require_relative "#{$lib}/idl/passes/gen_adoc"

puts "UPDATE: Inside profile_doc tasks.rake"

PROFILE_DOC_DIR = Pathname.new "#{$root}/backends/profile_doc"

Dir.glob("#{$root}/arch/profile_release/*.yaml") do |f|
  profile_release_name = File.basename(f, ".yaml")
  profile_release_obj = YAML.load_file(f, permitted_classes: [Date])
  raise "Can't parse #{f}" if profile_release_obj.nil?

  raise "Ill-formed profile release file #{f}: missing 'class' field" if profile_release_obj['class'].nil?
  profile_class_name = File.basename(profile_release_obj['class']['$ref'].split("#")[0], ".yaml")
  raise "Ill-formed profile release file #{f}: can't parse class name" if profile_class_name.nil?

  raise "Ill-formed profile release file #{f}: missing 'profiles' field" if profile_release_obj['profiles'].nil?
  profile_names = profile_release_obj['profiles'].map {|p| File.basename(p['$ref'].split("#")[0], ".yaml") }
  raise "Ill-formed profile release file #{f}: can't parse profile names" if profile_names.nil?

  profile_pathnames = profile_names.map {|profile_name| "#{$root}/arch/profile/#{profile_name}.yaml" }

  file "#{$root}/gen/profile_doc/adoc/#{profile_release_name}.adoc" => [
    __FILE__,
    "#{$root}/arch/profile_class/#{profile_class_name}.yaml",
    "#{$root}/arch/profile_release/#{profile_release_name}.yaml",
    "#{$root}/lib/arch_obj_models/profile.rb",
    "#{$root}/lib/arch_obj_models/portfolio.rb",
    "#{$root}/lib/portfolio_design.rb",
    "#{$root}/lib/design.rb",
    "#{PROFILE_DOC_DIR}/templates/profile.adoc.erb"
  ].concat(profile_pathnames) do |t|
    # Ensure that unconfigured resolved architecture called "_" exists.
    Rake::Task["#{$root}/.stamps/resolve-_.stamp"].invoke

    # Create architecture object so we can have it create the ProcCertModel.
    # Use the unconfigured resolved architecture called "_".
    arch = Architecture.new("RISC-V Architecture", $root / "gen" / "resolved_arch" / "_")

    # Create PortfolioRelease for specific portfolio release as specified in its arch YAML file.
    # The Architecture object also creates all other portfolio-related class instances from their arch YAML files.
    # None of these objects are provided with a Design object when created.
    puts "UPDATE: Creating Profile Release for #{profile_release_name}"
    profile_release = arch.profile_release(profile_release_name)

    # Create the one PortfolioDesign object required for the ERB evaluation.
    # Provide it with all the profiles in this ProfileRelease.
    puts "UPDATE: Creating PortfolioDesign using profile release #{profile_release_name}"
    portfolio_design = PortfolioDesign.new(profile_release_name, arch, profile_release.profiles)

    # Create empty binding and then specify explicitly which variables the ERB template can access.
    # Seems to use this method name in stack backtraces (hence its name).
    def evaluate_erb
      binding
    end
    erb_binding = evaluate_erb
    erb_binding.local_variable_set(:arch, arch)
    erb_binding.local_variable_set(:design, portfolio_design)
    erb_binding.local_variable_set(:profile_class, profile_release.profile_class)
    erb_binding.local_variable_set(:portfolio_class, profile_release.profile_class)
    erb_binding.local_variable_set(:profile_release, profile_release)

    template_path = Pathname.new("#{PROFILE_DOC_DIR}/templates/profile.adoc.erb")
    erb = ERB.new(File.read(template_path), trim_mode: "-")
    erb.filename = template_path.to_s

    FileUtils.mkdir_p File.dirname(t.name)

    # Convert ERB to final ASCIIDOC. Note that this code is broken up into separate function calls
    # each with a variable name to aid in running a command-line debugger on this code.
    puts "UPDATE: Converting ERB template to adoc for #{profile_release_name}"
    erb_result = erb.result(erb_binding)
    erb_result_monospace_converted_to_links = portfolio_design.find_replace_links(erb_result)
    erb_result_with_links_added = portfolio_design.find_replace_links(erb_result_monospace_converted_to_links)
    erb_result_with_links_resolved = AsciidocUtils.resolve_links(erb_result_with_links_added)

    File.write(t.name, erb_result_with_links_resolved)
    puts "UPDATE: Generated adoc source at #{t.name}"
  end

  file "#{$root}/gen/profile_doc/pdf/#{profile_release_name}.pdf" => [
    __FILE__,
    "#{$root}/gen/profile_doc/adoc/#{profile_release_name}.adoc"
  ] do |t|
    adoc_file = "#{$root}/gen/profile_doc/adoc/#{profile_release_name}.adoc"
    FileUtils.mkdir_p File.dirname(t.name)

    puts "UPDATE: Generating PDF at #{t.name}"
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
      adoc_file
    ].join(" ")
    puts "UPDATE: Generated PDF at #{t.name}"
  end

  file "#{$root}/gen/profile_doc/html/#{profile_release_name}.html" => [
    __FILE__,
    "#{$root}/gen/profile_doc/adoc/#{profile_release_name}.adoc"
  ] do |t|
    adoc_file = "#{$root}/gen/profile_doc/adoc/#{profile_release_name}.adoc"
    FileUtils.mkdir_p File.dirname(t.name)

    puts "UPDATE: Generating PDF at #{t.name}"
    sh [
      "asciidoctor",
      "-w",
      "-v",
      "-a toc",
      "-a imagesdir=#{$root}/ext/docs-resources/images",
      "-r asciidoctor-diagram",
      "-r #{$root}/backends/ext_pdf_doc/idl_lexer",
      "-o #{t.name}",
      adoc_file
    ].join(" ")
    puts "UPDATE: Generated PDF at #{t.name}"
  end
end

namespace :gen do
  desc <<~DESC
    Generate profile documentation for a specific release as a PDF.

    Required options:
      profile_release_name - The key of the profile release under arch/portfolio_release
  DESC
  task :profile_release_pdf, [:profile_release_name] do |_t, args|
    profile_release_name = args[:profile_release_name]
    if profile_release_name.nil?
      warn "Missing required option: 'profile_release_name'"
      exit 1
    end

    unless File.exist?("#{$root}/arch/profile_release/#{profile_release_name}.yaml")
      warn "No profile release named '#{profile_release_name}' found in arch/profile_release"
      exit 1
    end

    Rake::Task["#{$root}/gen/profile_doc/pdf/#{profile_release_name}.pdf"].invoke
  end

  task :profile_release_html, [:profile_release_name] do |_t, args|
    profile_release_name = args[:profile_release_name]
    if profile_release_name.nil?
      warn "Missing required option: 'profile_release_name'"
      exit 1
    end

    unless File.exist?("#{$root}/arch/profile_release/#{profile_release_name}.yaml")
      warn "No profile release named '#{profile_release_name}' found in arch/profile_release"
      exit 1
    end

    Rake::Task["#{$root}/gen/profile_doc/html/#{profile_release_name}.html"].invoke
  end
end

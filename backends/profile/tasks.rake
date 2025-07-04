# frozen_string_literal: true
#
# Contains Rake rules to generate adoc, PDF, and HTML for a profile release.

require "pathname"

require "udb_helpers/paths"
require "udb/portfolio_design"

PROFILE_DOC_DIR = Pathname.new "#{$root}/backends/profile"
PROFILE_GEN_DIR = $resolver.gen_path / "profile"

Dir.glob("#{$resolver.std_path}/profile_release/*.yaml") do |f|
  release_name = File.basename(f, ".yaml")
  release_obj = YAML.load_file(f, permitted_classes: [Date])
  raise "Can't parse #{f}" if release_obj.nil?

  raise "Ill-formed profile release file #{f}: missing 'family' field" if release_obj['family'].nil?
  family_name = File.basename(release_obj['family']['$ref'].split("#")[0], ".yaml")
  raise "Ill-formed profile release file #{f}: can't parse family name" if family_name.nil?

  raise "Ill-formed profile release file #{f}: missing 'profiles' field" if release_obj['profiles'].nil?
  profile_names = release_obj['profiles'].map {|p| File.basename(p['$ref'].split("#")[0], ".yaml") }
  raise "Ill-formed profile release file #{f}: can't parse profile names" if profile_names.nil?

  profile_pathnames = profile_names.map {|profile_name| "#{$resolver.std_path}/profile/#{profile_name}.yaml" }

  file "#{PROFILE_GEN_DIR}/adoc/#{release_name}ProfileRelease.adoc" => [
    __FILE__,
    "#{$resolver.std_path}/profile_family/#{family_name}.yaml",
    "#{$resolver.std_path}/profile_release/#{release_name}.yaml",
    "#{Udb.gem_path}/lib/udb/obj/profile.rb",
    "#{Udb.gem_path}/lib/udb/obj/portfolio.rb",
    "#{Udb.gem_path}/lib/udb/portfolio_design.rb",
    "#{Udb::Helpers.gem_path}/lib/udb_helpers/backend_helpers.rb",
    "#{$root}/backends/portfolio/templates/ext_appendix.adoc.erb",
    "#{$root}/backends/portfolio/templates/inst_appendix.adoc.erb",
    "#{$root}/backends/portfolio/templates/csr_appendix.adoc.erb",
    "#{$root}/backends/portfolio/templates/beginning.adoc.erb",
    "#{PROFILE_DOC_DIR}/templates/profile.adoc.erb"
  ].concat(profile_pathnames) do |t|
    # Create architecture object without any knowledge of the profile release.
    # Just used to get the PortfolioGroup object.
    arch = pf_create_arch

    # Create ProfileRelease for specific profile release as specified in its arch YAML file.
    # The Architecture object also creates all other portfolio-related object instances from their arch YAML files.
    # None of these objects are provided with a AbstractConfig or Design object when created.
    $logger.info "Creating ProfileRelease with only an Architecture object for #{release_name}"
    profile_release_with_arch = arch.profile_release(release_name)

    # Now create a ConfiguredArchitecture object for the PortfolioDesign.
    cfg_arch = pf_create_cfg_arch(profile_release_with_arch.portfolio_grp)

    $logger.info "Creating ProfileRelease with a ConfiguredArchitecture object for #{release_name}"
    profile_release_with_cfg_arch = cfg_arch.profile_release(release_name)

    # Create the one PortfolioDesign object required for the ERB evaluation.
    # Provide it with all the profiles in this ProfileRelease.
    $logger.info "Creating PortfolioDesign object using profile release #{release_name}"
    portfolio_design = Udb::PortfolioDesign.new(
      release_name,
      cfg_arch,
      Udb::PortfolioDesign.profile_release_type,
      profile_release_with_cfg_arch.profiles,
      profile_release_with_cfg_arch.profile_family
    )

    # Create empty binding and then specify explicitly which variables the ERB template can access.
    # Seems to use this method name in stack backtraces (hence its name).
    def evaluate_erb
      binding
    end
    erb_binding = evaluate_erb
    portfolio_design.init_erb_binding(erb_binding)
    erb_binding.local_variable_set(:profile_release, profile_release_with_cfg_arch)
    erb_binding.local_variable_set(:profile_family, profile_release_with_cfg_arch.profile_family)

    pf_create_adoc("#{PROFILE_DOC_DIR}/templates/profile.adoc.erb", erb_binding, t.name, portfolio_design)
  end

  file "#{PROFILE_GEN_DIR}/pdf/#{release_name}ProfileRelease.pdf" => [
    __FILE__,
    "#{PROFILE_GEN_DIR}/adoc/#{release_name}ProfileRelease.adoc"
  ] do |t|
    pf_adoc2pdf("#{PROFILE_GEN_DIR}/adoc/#{release_name}ProfileRelease.adoc", t.name)
  end

  file "#{PROFILE_GEN_DIR}/html/#{release_name}ProfileRelease.html" => [
    __FILE__,
    "#{PROFILE_GEN_DIR}/adoc/#{release_name}ProfileRelease.adoc"
  ] do |t|
    pf_adoc2html("#{PROFILE_GEN_DIR}/adoc/#{release_name}ProfileRelease.adoc", t.name)
  end
end

namespace :gen do
  desc <<~DESC
    Generate profile documentation for a profile release as a PDF.

    Required options:
      release_name - The name of the profile release under arch/profile_release
  DESC
  task :profile_release_pdf, [:release_name] do |_t, args|
    release_name = args[:release_name]
    if release_name.nil?
      warn "Missing required option: 'release_name'"
      exit 1
    end

    unless File.exist?("#{$resolver.std_path}/profile_release/#{release_name}.yaml")
      warn "No profile release named '#{release_name}' found in arch/profile_release"
      exit 1
    end

    Rake::Task["#{PROFILE_GEN_DIR}/pdf/#{release_name}ProfileRelease.pdf"].invoke
  end

  desc <<~DESC
    Generate profile documentation for a profile release as an HTML.

    Required options:
      release_name - The name of the profile release under arch/profile_release
  DESC
  task :profile_release_html, [:release_name] do |_t, args|
    release_name = args[:release_name]
    if release_name.nil?
      warn "Missing required option: 'release_name'"
      exit 1
    end

    unless File.exist?("#{$resolver.std_path}/profile_release/#{release_name}.yaml")
      warn "No profile release named '#{release_name}' found in arch/profile_release"
      exit 1
    end

    Rake::Task["#{PROFILE_GEN_DIR}/html/#{release_name}ProfileRelease.html"].invoke
  end
end

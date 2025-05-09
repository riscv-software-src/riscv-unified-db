# frozen_string_literal: true
#
# Contains Rake rules to generate adoc, PDF, and HTML for a profile release.

require "pathname"

PROFILE_DOC_DIR = Pathname.new "#{$root}/backends/profile"
PROFILE_GEN_DIR = $root / "gen" / "profile"

rule %r{#{PROFILE_GEN_DIR}/adoc/[^/]+ProfileRelease.adoc} => [
  __FILE__,
  "#{$root}/lib/arch_obj_models/profile.rb",
  "#{$root}/lib/arch_obj_models/portfolio.rb",
  "#{$root}/lib/portfolio_design.rb",
  "#{$root}/lib/backend_helpers.rb",
  "#{$root}/backends/portfolio/templates/ext_appendix.adoc.erb",
  "#{$root}/backends/portfolio/templates/inst_appendix.adoc.erb",
  "#{$root}/backends/portfolio/templates/csr_appendix.adoc.erb",
  "#{$root}/backends/portfolio/templates/beginning.adoc.erb",
  "#{PROFILE_DOC_DIR}/templates/profile.adoc.erb"
] do |t|
  # Create architecture object without any knowledge of the profile release.
  # Just used to get the PortfolioGroup object.
  bootstrap_cfg_arch = cfg_arch_for(ENV["CONFIG"])
  release_name = File.basename(t.name, ".adoc")[0...-14]

  # Create ProfileRelease for specific profile release as specified in its arch YAML file.
  # The Architecture object also creates all other portfolio-related class instances from their arch YAML files.
  # None of these objects are provided with a AbstractConfig or Design object when created.
  $logger.info "Creating ProfileRelease with only an Architecture object for #{release_name}"
  profile_release_with_arch = bootstrap_cfg_arch.profile_release(release_name)

  # Now create a ConfiguredArchitecture object for the PortfolioDesign.
  cfg_arch = pf_create_cfg_arch(profile_release_with_arch.portfolio_grp, bootstrap_cfg_arch.name)

  $logger.info "Creating ProfileRelease with a ConfiguredArchitecture object for #{release_name}"
  profile_release_with_cfg_arch = cfg_arch.profile_release(release_name)

  # Create the one PortfolioDesign object required for the ERB evaluation.
  # Provide it with all the profiles in this ProfileRelease.
  $logger.info "Creating PortfolioDesign object using profile release #{release_name}"
  portfolio_design = PortfolioDesign.new(
    release_name,
    cfg_arch,
    PortfolioDesign.profile_release_type,
    profile_release_with_cfg_arch.profiles,
    profile_release_with_cfg_arch.profile_class
  )

  # Create empty binding and then specify explicitly which variables the ERB template can access.
  # Seems to use this method name in stack backtraces (hence its name).
  def evaluate_erb
    binding
  end
  erb_binding = evaluate_erb
  portfolio_design.init_erb_binding(erb_binding)
  erb_binding.local_variable_set(:profile_release, profile_release_with_cfg_arch)
  erb_binding.local_variable_set(:profile_class, profile_release_with_cfg_arch.profile_class)

  pf_create_adoc("#{PROFILE_DOC_DIR}/templates/profile.adoc.erb", erb_binding, t.name, portfolio_design)
end

rule %r{#{PROFILE_GEN_DIR}/pdf/[^/]+ProfileRelease.pdf} => proc { |tname|
  release_name = File.basename(tname, ".pdf")[0...-14]
  [
    __FILE__,
    "#{PROFILE_GEN_DIR}/adoc/#{release_name}ProfileRelease.adoc"
  ]
} do |t|
  release_name = File.basename(t.name, ".pdf")[0...-14]
  pf_adoc2pdf("#{PROFILE_GEN_DIR}/adoc/#{release_name}ProfileRelease.adoc", t.name)
end

rule %r{#{PROFILE_GEN_DIR}/html/[^/]+ProfileRelease.html} => proc { |tname|
  release_name = File.basename(tname, ".html")[0...-14]
  [
    __FILE__,
    "#{PROFILE_GEN_DIR}/adoc/#{release_name}ProfileRelease.adoc"
  ]
} do |t|
  release_name = File.basename(t.name, ".html")[0...-14]
  pf_adoc2html("#{PROFILE_GEN_DIR}/adoc/#{release_name}ProfileRelease.adoc", t.name)
end

namespace :gen do
  desc <<~DESC
    Generate profile documentation for a profile release as a PDF.

    Required options:
      CONFIG       - Configuration to use for base architecture
      RELEASE      - The name of the profile release under arch/profile_release
  DESC
  task :profile_release_pdf do |_t, args|
    raise "Missing required argument 'CONFIG'" unless ENV.key?("CONFIG")
    raise "Missing required argument 'RELEASE'" unless ENV.key?("RELEASE")

    release_name = ENV["RELEASE"]

    if release_name.nil?
      warn "Missing required option: 'release_name'"
      exit 1
    end

    cfg_arch = cfg_arch_for(ENV["CONFIG"])

    unless cfg_arch.profile_releases.any? { |release| release.name == release_name }
      warn "No profile release named '#{release_name}' found in arch/profile_release"
      exit 1
    end

    Rake::Task["#{PROFILE_GEN_DIR}/pdf/#{release_name}ProfileRelease.pdf"].invoke
  end

  desc <<~DESC
    Generate profile documentation for a profile release as an HTML.

    Required options:
      CONFIG       - Configuration to use for base architecture
      RELEASE      - The name of the profile release under arch/profile_release
  DESC
  task :profile_release_html, [:release_name] do |_t, args|
    raise "Missing required argument 'CONFIG'" unless ENV.key?("CONFIG")
    raise "Missing required argument 'RELEASE'" unless ENV.key?("RELEASE")

    release_name = ENV["RELEASE"]
    if release_name.nil?
      warn "Missing required option: 'release_name'"
      exit 1
    end

    cfg_arch = cfg_arch_for(ENV["CONFIG"])

    unless cfg_arch.profile_releases.any? { |release| release.name == release_name }
      warn "No profile release named '#{release_name}' found in arch/profile_release"
      exit 1
    end

    Rake::Task["#{PROFILE_GEN_DIR}/html/#{release_name}ProfileRelease.html"].invoke
  end
end

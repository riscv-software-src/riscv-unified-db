# tasks.rake

# Define the manual generation directory constant
ISA_INDEX_GEN_DIR = $root / "gen" / "instr_isa_manual/index"

# Rule to create the instructions index page (all instructions with details)
rule %r{#{ISA_INDEX_GEN_DIR}/.*/antora/modules/insts/pages/instructions_index\.adoc} => [
  __FILE__,
  ($root / "backends" / "instr_isa_manual" / "templates" / "instr_index.adoc.erb").to_s
] do |t|
  cfg_arch = cfg_arch_for("_")
  # Collect all instructions sorted by name
  instructions = cfg_arch.instructions.sort_by(&:name)
  template_path = $root / "backends" / "instr_isa_manual" / "templates" / "instr_index.adoc.erb"
  erb = ERB.new(template_path.read, trim_mode: "-")
  erb.filename = template_path.to_s

  FileUtils.mkdir_p(File.dirname(t.name))
  File.write(t.name, AsciidocUtils.resolve_links(cfg_arch.find_replace_links(erb.result(binding))))
end

# Rake task to generate the instructions index page.
namespace :gen do
  desc "Generate the instructions index page (with index and full instruction details)"
  task :instructions_index do
    # Use provided version or default to "latest"
    version = ENV["VERSION"] || "latest"
    target = ISA_INDEX_GEN_DIR / version / "antora/modules/insts/pages/instructions_index.adoc"

    # Invoke the rule to generate the file
    Rake::Task[target.to_s].invoke

    puts "SUCCESS: Instructions index generated at '#{target}'"
  end
end

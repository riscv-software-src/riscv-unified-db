# frozen_string_literal: true

require_relative "../../lib/arch_obj_models/instr_isa_manual.rb"

# Define the instructions manual generation directory constant.
INST_MANUAL_GEN_DIR = $root / "gen" / "instructions_isa_manual"

# Define the path to the merged instructions output.
MERGED_INSTRUCTIONS_FILE = INST_MANUAL_GEN_DIR / "all_instructions.adoc"

# Define the path to the ERB template that renders the merged instructions.
TEMPLATE_FILE = $root / "backends" / "instructions_isa_manual" / "templates" / "instructions.adoc.erb"

# Declare a file task for the template so Rake knows it exists.
file TEMPLATE_FILE.to_s do
  # Nothing to do—this file is assumed to be up-to-date.
end

# File task that generates the merged instructions adoc.
file MERGED_INSTRUCTIONS_FILE.to_s => [ __FILE__, TEMPLATE_FILE.to_s ] do |t|
  cfg_arch = cfg_arch_for("_")
  # Use the InstructionIndex helper to aggregate instructions from the entire architecture.
  instruction_index = InstructionIndex.new(cfg_arch)
  instructions = instruction_index.instructions

  # Load and process the template (which renders both an index and details).
  erb = ERB.new(File.read(TEMPLATE_FILE), trim_mode: "-")
  erb.filename = TEMPLATE_FILE.to_s

  FileUtils.mkdir_p(File.dirname(t.name))
  File.write(
    t.name,
    AntoraUtils.resolve_links(cfg_arch.find_replace_links(erb.result(binding)))
  )
end

namespace :gen do
  desc "Generate a merged instructions adoc with all instructions"
  task :merged_instructions do
    # Invoke the file task that creates the merged instructions file.
    Rake::Task[MERGED_INSTRUCTIONS_FILE.to_s].invoke
    puts "SUCCESS: Merged instructions file generated at '#{MERGED_INSTRUCTIONS_FILE}'"
  end
end

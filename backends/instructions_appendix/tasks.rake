# typed: false
# frozen_string_literal: true

# Define the instructions manual generation directory constant.
INST_MANUAL_GEN_DIR = $root / "gen" / "instructions_appendix"

# Define the path to the merged instructions output.
MERGED_INSTRUCTIONS_FILE = INST_MANUAL_GEN_DIR / "all_instructions.adoc"

# Define the path to the ERB template that renders the merged instructions.
TEMPLATE_FILE = $root / "backends" / "instructions_appendix" / "templates" / "instructions.adoc.erb"

# The four split appendix files produced by split_instructions.rb.
SPLIT_APPENDIX_NAMES = %w[unpriv_rv32 unpriv_rv64 priv_rv32 priv_rv64].freeze
SPLIT_APPENDIX_FILES = SPLIT_APPENDIX_NAMES.map { |n| INST_MANUAL_GEN_DIR / "#{n}.adoc" }.freeze

# Stamp file used to track whether all four split files are up to date.
SPLIT_APPENDIX_STAMP = INST_MANUAL_GEN_DIR / "split.stamp"

# Path to split_instructions.rb, used to invalidate outputs when the script changes.
SPLIT_SCRIPT = $root / "backends" / "instructions_appendix" / "split_instructions.rb"

# Root of the riscv-isa-manual checkout. Override with ISA_MANUAL_DIR env var.
ISA_MANUAL_DIR = Pathname.new(ENV.fetch("ISA_MANUAL_DIR", $root / ".." / "riscv-isa-manual"))

# Destination paths for each split file inside riscv-isa-manual.
ISA_MANUAL_DESTINATIONS = {
  "unpriv_rv32" => ISA_MANUAL_DIR / "src" / "unpriv" / "unpriv_rv32.adoc",
  "unpriv_rv64" => ISA_MANUAL_DIR / "src" / "unpriv" / "unpriv_rv64.adoc",
  "priv_rv32"   => ISA_MANUAL_DIR / "src" / "priv"   / "priv_rv32.adoc",
  "priv_rv64"   => ISA_MANUAL_DIR / "src" / "priv"   / "priv_rv64.adoc"
}.freeze

# Declare a file task for the template so Rake knows it exists.
file TEMPLATE_FILE.to_s do
  # Nothing to do—this file is assumed to be up-to-date.
end

# File task that generates the merged instructions adoc.
file MERGED_INSTRUCTIONS_FILE.to_s => [__FILE__, TEMPLATE_FILE.to_s] do |t|
  cfg_arch = $resolver.cfg_arch_for("_")
  instructions = cfg_arch.possible_instructions

  # Load and process the template (which renders both an index and details).
  erb = ERB.new(File.read(TEMPLATE_FILE), trim_mode: "-")
  erb.filename = TEMPLATE_FILE.to_s

  Udb.logger.info "Generating asciidoc for instruction appendix"
  FileUtils.mkdir_p(File.dirname(t.name))
  File.write(
    t.name,
    Udb::Helpers::AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
  )
end

# Stamp file task: runs split_instructions.rb to produce all four split files in
# one pass, then touches the stamp so Rake knows the outputs are current.
file SPLIT_APPENDIX_STAMP.to_s => [MERGED_INSTRUCTIONS_FILE.to_s, SPLIT_SCRIPT.to_s] do |t|
  Udb.logger.info "Splitting instruction appendix into four base/privilege files"
  sh "#{RbConfig.ruby} #{SPLIT_SCRIPT} #{MERGED_INSTRUCTIONS_FILE} #{INST_MANUAL_GEN_DIR}"
  touch t.name
end

# Each split file depends on the stamp (i.e., on the splitter having run).
SPLIT_APPENDIX_FILES.each do |f|
  file f.to_s => SPLIT_APPENDIX_STAMP.to_s
end

# Define the path to the output PDF file.
MERGED_INSTRUCTIONS_PDF = INST_MANUAL_GEN_DIR / "instructions_appendix.pdf"

# File task to generate the PDF from the merged adoc.
file MERGED_INSTRUCTIONS_PDF.to_s => [
  MERGED_INSTRUCTIONS_FILE.to_s,
  "#{$root}/ext/docs-resources/themes/riscv-pdf.yml"
] do |t|
  sh [
    "asciidoctor-pdf",
    "-a toc",
    "-a pdf-theme=#{ENV['THEME'] || "#{$root}/ext/docs-resources/themes/riscv-pdf.yml"}",
    "-a pdf-fontsdir=#{$root}/ext/docs-resources/fonts",
    "-a imagesdir=#{$root}/ext/docs-resources/images",
    "-r asciidoctor-diagram",
    "-o #{t.name}",
    MERGED_INSTRUCTIONS_FILE.to_s
  ].join(" ")

  puts "SUCCESS: PDF generated at #{t.name}"
end

namespace :gen do
  desc <<~DESC
    Generate the instruction appendix (merged .adoc)
  DESC
  task instruction_appendix_adoc: MERGED_INSTRUCTIONS_FILE.to_s

  desc <<~DESC
    Generate the four split instruction appendix adoc files.

    Produces:
      gen/instructions_appendix/unpriv_rv32.adoc
      gen/instructions_appendix/unpriv_rv64.adoc
      gen/instructions_appendix/priv_rv32.adoc
      gen/instructions_appendix/priv_rv64.adoc

    Each file contains only the instructions applicable to that base ISA and
    privilege level.  Anchors are qualified with the base (e.g.
    [#udb:doc:inst:rv32:add]) so that instructions present in both RV32 and
    RV64 appendixes have unique IDs.
  DESC
  task split_instruction_appendixes: SPLIT_APPENDIX_FILES.map(&:to_s)

  desc <<~DESC
    Copy the four split instruction appendix files into a riscv-isa-manual checkout.

    The destination checkout is determined by the ISA_MANUAL_DIR environment
    variable (default: ../riscv-isa-manual relative to the repo root).

    Prerequisites: gen:split_instruction_appendixes must have been run first, or
    this task will run it automatically.

    Environment flags:

     * ISA_MANUAL_DIR - path to the riscv-isa-manual checkout
                        (default: #{ISA_MANUAL_DIR})

    Examples:

     # Sync using the default sibling checkout:
     $ do gen:sync_isa_manual_appendixes

     # Sync to an explicit path:
     $ do gen:sync_isa_manual_appendixes ISA_MANUAL_DIR=/path/to/riscv-isa-manual

  DESC
  task sync_isa_manual_appendixes: :split_instruction_appendixes do
    abort "riscv-isa-manual not found at #{ISA_MANUAL_DIR}" unless ISA_MANUAL_DIR.directory?

    ISA_MANUAL_DESTINATIONS.each do |name, dest|
      src = INST_MANUAL_GEN_DIR / "#{name}.adoc"
      FileUtils.cp(src, dest)
      puts "  #{src.basename} -> #{dest}"
    end

    puts "SUCCESS: Instruction appendixes synced to #{ISA_MANUAL_DIR}"
  end

  desc <<~DESC
    Generate the instruction appendix (merged .adoc and PDF)

    By default this will produce the "merged instructions" AsciiDoc file and
    then render it to PDF.

    Environment flags:

     * ASSEMBLY - set to `1` to include an "Assembly" line (instruction mnemonic + operands)
                  before the Encoding section for each instruction.

    Examples:

     # Just regenerate AsciiDoc + PDF:
     $ do gen:instruction_appendix

     # Include assembly templates in the docs:
     $ do gen:instruction_appendix ASSEMBLY=1

  DESC
  task :instruction_appendix do
    # Generate the merged instructions adoc.
    Rake::Task[MERGED_INSTRUCTIONS_FILE.to_s].invoke
    # Then generate the PDF.
    Rake::Task[MERGED_INSTRUCTIONS_PDF.to_s].invoke
    puts "SUCCESS: Instruction appendix generated at '#{MERGED_INSTRUCTIONS_FILE}' and PDF at '#{MERGED_INSTRUCTIONS_PDF}'"
  end
end

namespace :test do
  desc "Check the instruction appendix output vs. stored golden output"
  task instruction_appendix: "gen:instruction_appendix_adoc" do
    golden = "#{$root}/tests/golden/all_instructions.golden.adoc"
    output = "gen/instructions_appendix/all_instructions.adoc"

    sh "diff -u #{golden} #{output}"
    if $? == 0
      puts "PASSED"
    else
      warn <<~MSG
              The golden output for the instruction appendix has changed. If this is expected, run

              cp gen/instructions_appendix/all_instructions.adoc tests/golden/all_instructions.golden.adoc
              git add tests/golden/all_instructions.golden.adoc

              And commit
            MSG
      exit 1
    end
  end
end

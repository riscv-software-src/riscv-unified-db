# typed: false
# frozen_string_literal: true

# Define the instructions manual generation directory constant.
INST_MANUAL_GEN_DIR = $root / "gen" / "instructions_appendix"

# Define the path to the merged instructions output.
MERGED_INSTRUCTIONS_FILE = INST_MANUAL_GEN_DIR / "all_instructions.adoc"

# Define the path to the ERB template that renders the merged instructions.
TEMPLATE_FILE = $root / "backends" / "instructions_appendix" / "templates" / "instructions.adoc.erb"

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
    Generate the instruction appendix (merged .adoc and PDF)

    By default this will produce the “merged instructions” AsciiDoc file and
    then render it to PDF.

    Environment flags:

     * ASSEMBLY - set to `1` to include an “Assembly” line (instruction mnemonic + operands)
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

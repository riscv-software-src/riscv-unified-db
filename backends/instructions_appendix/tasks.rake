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
  cfg_arch = cfg_arch_for("_")
  instructions = cfg_arch.possible_instructions

  # Load and process the template (which renders both an index and details).
  erb = ERB.new(File.read(TEMPLATE_FILE), trim_mode: "-")
  erb.filename = TEMPLATE_FILE.to_s

  FileUtils.mkdir_p(File.dirname(t.name))
  File.write(
    t.name,
    AntoraUtils.resolve_links(cfg_arch.convert_monospace_to_links(erb.result(binding)))
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
  task instruction_appendix_adoc: MERGED_INSTRUCTIONS_FILE.to_s

  desc "Generate instruction appendix (merged instructions adoc and PDF)"
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
    files = {
      golden: {
        file: Tempfile.new("golden"),
        path: "#{File.dirname(__FILE__)}/all_instructions.golden.adoc"
      },
      output: {
        file: Tempfile.new("output"),
        path: "gen/instructions_appendix/all_instructions.adoc"
      }
    }

    # filter out lines that have file paths
    [:golden, :output].each do |which|
      file = files[which][:file]
      path = files[which][:path]
      orig = File.read(path)
      filtered = orig.lines.reject { |l| l =~ /^:wavedrom:/ }.join("\n")
      file.write(filtered)
      file.flush
    end

    sh "diff -u #{files[:golden][:file].path} #{files[:output][:file].path}"
    if $? == 0
      puts "PASSED"
    else
      warn <<~MSG
        The golden output for the instruction appendix has changed. If this is expected, run

        cp gen/instructions_appendix/all_instructions.adoc backends/instructions_appendix/all_instructions.golden.adoc
        git add backends/instructions_appendix/all_instructions.golden.adoc

        And commit
      MSG
      exit 1
    end
  end
end

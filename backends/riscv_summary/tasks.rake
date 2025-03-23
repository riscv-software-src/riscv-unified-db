# frozen_string_literal: true
#
# Contains Rake rules to generate xslx and html table summarizing entire RISC-V architecture.

require "pathname"
require_relative "gen_summary"

BACKEND_NAME = "riscv_summary"
TAB_MASTER_NAME = "tabulator-master"

# Source directories/files
BACKEND_DIR = "#{$root}/backends/#{BACKEND_NAME}"
HTML_FNAME = "#{BACKEND_NAME}.html"
HTML_SRC_PNAME = "#{BACKEND_DIR}/#{HTML_FNAME}"
TAB_MASTER_SRC_PNAME = "#{BACKEND_DIR}/#{TAB_MASTER_NAME}"

# Generated directories/files
GEN_ROOT = $root / "gen" / BACKEND_NAME
XLSX_GEN_DIR = GEN_ROOT / "xlsx"
HTML_GEN_DIR = GEN_ROOT / "html"
XLSX_GEN_PNAME = XLSX_GEN_DIR / "#{BACKEND_NAME}.xlsx"
HTML_GEN_PNAME = HTML_GEN_DIR / HTML_FNAME
JS_GEN_PNAME = HTML_GEN_DIR / "#{BACKEND_NAME}.js"

directory(XLSX_GEN_DIR)
directory(HTML_GEN_DIR)

namespace :gen do
  desc("Generate RISC-V architecture summary as an Excel spreadsheet")
  task :riscv_summary_xlsx do
    Rake::Task["#{XLSX_GEN_PNAME}"].invoke
  end

  desc("Generate RISC-V architecture summary as dynamic HTML table using JavaScript")
  task :riscv_summary_html do
    Rake::Task["#{HTML_GEN_PNAME}"].invoke
    Rake::Task["#{JS_GEN_PNAME}"].invoke
  end
end

src_pnames = [
  "#{BACKEND_DIR}/gen_summary.rb",
  "#{$root}/lib/architecture.rb",
  "#{$root}/lib/arch_obj_models/database_obj.rb",
  "#{$root}/lib/arch_obj_models/extension.rb",
  "#{$root}/lib/backend_helpers.rb"
]

file "#{XLSX_GEN_PNAME}" => [
    __FILE__,
    src_pnames
].flatten do |t|
    arch = create_arch

    # Ensure directory holding target file is present.
    FileUtils.mkdir_p File.dirname(t.name)

    gen_xlsx(arch, t.name)

    puts "Success: Generated #{t.name}"
end

file "#{HTML_GEN_PNAME}" => [
    __FILE__,
  HTML_SRC_PNAME
].flatten do |t|
    # Ensure directory holding target file is present.
    FileUtils.mkdir_p File.dirname(t.name)

    # Delete target file if already present.
    if File.exist?(t.name)
      begin
        File.delete(t.name)
      rescue StandardError => e
        raise "Can't delete '#{t.name}': #{e.message}"
      end
    end

    # Just copy static HTML file.
    FileUtils.copy_file(HTML_SRC_PNAME, t.name)

    # Also copy tabulator-master library in case it isn't already there.
    FileUtils.cp_r(TAB_MASTER_SRC_PNAME, HTML_GEN_DIR)

    puts "Success: Copied #{HTML_SRC_PNAME} to #{t.name}"
end

file "#{JS_GEN_PNAME}" => [
    __FILE__,
    src_pnames,
    HTML_SRC_PNAME
].flatten do |t|
    arch = create_arch

    # Ensure directory holding target file is present.
    FileUtils.mkdir_p File.dirname(t.name)

    gen_js(arch, t.name)

    puts "Success: Generated #{t.name}"
end

# @return [Architecture]
def create_arch
  # Ensure that unconfigured resolved architecture called "_" exists.
  Rake::Task["#{$root}/.stamps/resolve-_.stamp"].invoke

  # Create architecture object using the unconfigured resolved architecture called "_" to get the entire RISC-V arch.
  Architecture.new("RISC-V Architecture", $root / "gen" / "resolved_arch" / "_")
end

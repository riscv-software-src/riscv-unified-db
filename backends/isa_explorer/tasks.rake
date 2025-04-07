# frozen_string_literal: true
#
# Contains Rake rules to generate ISA explorer.

require "pathname"
require_relative "isa_explorer"

# Backend generator directory
BACKEND_NAME = "isa_explorer"
BACKEND_DIR = "#{$root}/backends/#{BACKEND_NAME}"

# Library used to generate dynamic JavaScript tables
# Currently located under backend but would be better to be under ext directory - TBD.
TAB_MASTER_NAME = "tabulator-master"
SRC_TAB_MASTER_DIR = "#{BACKEND_DIR}/#{TAB_MASTER_NAME}"

# Static source files
SRC_EXT_HTML_PNAME = "#{BACKEND_DIR}/ext_table.html"
SRC_INST_HTML_PNAME = "#{BACKEND_DIR}/inst_table.html"

# Generated directories/files
GEN_ROOT = $root / "gen" / BACKEND_NAME
GEN_SPREADSHEET_DIR = GEN_ROOT / "spreadsheet"
GEN_BROWSER_DIR = GEN_ROOT / "browser"
GEN_XLSX = GEN_SPREADSHEET_DIR / "isa_explorer.xlsx"
GEN_HTML_EXT_TABLE = GEN_BROWSER_DIR / "ext_table.html"
GEN_JS_EXT_TABLE = GEN_BROWSER_DIR / "ext_table.js"
GEN_HTML_INST_TABLE = GEN_BROWSER_DIR / "inst_table.html"
GEN_JS_INST_TABLE = GEN_BROWSER_DIR / "inst_table.js"

directory(GEN_SPREADSHEET_DIR)
directory(GEN_BROWSER_DIR)

namespace :gen do
  desc("Generate RISC-V ISA Explorer for Excel spreadsheet")
  task :isa_explorer_spreadsheet do
    Rake::Task["#{GEN_XLSX}"].invoke
  end

  desc("Generate RISC-V ISA Explorer Extensions for browser")
  task :isa_explorer_browser_ext do
    Rake::Task["#{GEN_HTML_EXT_TABLE}"].invoke
    Rake::Task["#{GEN_JS_EXT_TABLE}"].invoke
  end

  desc("Generate RISC-V ISA Explorer Instructions for browser")
  task :isa_explorer_browser_inst do
    Rake::Task["#{GEN_HTML_INST_TABLE}"].invoke
    Rake::Task["#{GEN_JS_INST_TABLE}"].invoke
  end
end

src_pnames = [
  "#{BACKEND_DIR}/isa_explorer.rb",
  "#{$root}/lib/architecture.rb",
  "#{$root}/lib/version.rb",
  "#{$root}/lib/presence.rb",
  "#{$root}/lib/backend_helpers.rb",
  "#{$root}/lib/arch_obj_models/database_obj.rb",
  "#{$root}/lib/arch_obj_models/extension.rb",
  "#{$root}/lib/arch_obj_models/instruction.rb"
]

file "#{GEN_XLSX}" => [
    __FILE__,
    src_pnames
].flatten do |t|
    arch = create_arch

    # Ensure directory holding target file is present.
    FileUtils.mkdir_p File.dirname(t.name)

    gen_xlsx(arch, t.name)

    puts "Success: Generated #{t.name}"
end

file "#{GEN_HTML_EXT_TABLE}" => [
    __FILE__,
  SRC_EXT_HTML_PNAME
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
    FileUtils.copy_file(SRC_EXT_HTML_PNAME, t.name)

    # Also copy tabulator-master library in case it isn't already there.
    FileUtils.cp_r(SRC_TAB_MASTER_DIR, GEN_BROWSER_DIR)
end

file "#{GEN_HTML_INST_TABLE}" => [
    __FILE__,
  SRC_INST_HTML_PNAME
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
    FileUtils.copy_file(SRC_INST_HTML_PNAME, t.name)

    # Also copy tabulator-master library in case it isn't already there.
    FileUtils.cp_r(SRC_TAB_MASTER_DIR, GEN_BROWSER_DIR)
end

file "#{GEN_JS_EXT_TABLE}" => [
    __FILE__,
    src_pnames,
    SRC_EXT_HTML_PNAME
].flatten do |t|
    arch = create_arch

    # Ensure directory holding target file is present.
    FileUtils.mkdir_p File.dirname(t.name)

    gen_js_ext_table(arch, t.name)

    puts "Success: Generated #{t.name}"
end

file "#{GEN_JS_INST_TABLE}" => [
    __FILE__,
    src_pnames,
    SRC_INST_HTML_PNAME
].flatten do |t|
    arch = create_arch

    # Ensure directory holding target file is present.
    FileUtils.mkdir_p File.dirname(t.name)

    gen_js_inst_table(arch, t.name)

    puts "Success: Generated #{t.name}"
end

# @return [ConfiguredArchitecture]
def create_arch
  # Ensure that unconfigured resolved architecture called "_" exists.
  Rake::Task["#{$root}/.stamps/resolve-_.stamp"].invoke

  # Create architecture object using the unconfigured resolved architecture called "_" to get the entire RISC-V arch.
  cfg_arch_for("_")
end

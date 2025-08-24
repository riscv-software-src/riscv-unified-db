# frozen_string_literal: true
#
# Contains Rake rules to generate ISA explorer.

require "udb/cfg_arch"

require "pathname"
require_relative "isa_explorer"

# Backend generator directory
BACKEND_NAME = "isa_explorer"
BACKEND_DIR = "#{$root}/backends/#{BACKEND_NAME}"

# Static source files
SRC_EXT_HTML_PNAME = "#{BACKEND_DIR}/ext_table.html"
SRC_INST_HTML_PNAME = "#{BACKEND_DIR}/inst_table.html"
SRC_CSR_HTML_PNAME = "#{BACKEND_DIR}/csr_table.html"
SRC_LOAD_TABLE_JS_PNAME = "#{BACKEND_DIR}/load_table.js"

# Generated directories/files
GEN_ROOT = $root / "gen" / BACKEND_NAME
GEN_SPREADSHEET_DIR = GEN_ROOT / "spreadsheet"
GEN_BROWSER_DIR = GEN_ROOT / "browser"
GEN_XLSX = GEN_SPREADSHEET_DIR / "isa_explorer.xlsx"
GEN_HTML_EXT_TABLE = GEN_BROWSER_DIR / "ext_table.html"
GEN_JS_EXT_TABLE = GEN_BROWSER_DIR / "ext_table.js"
GEN_HTML_INST_TABLE = GEN_BROWSER_DIR / "inst_table.html"
GEN_JS_INST_TABLE = GEN_BROWSER_DIR / "inst_table.js"
GEN_HTML_CSR_TABLE = GEN_BROWSER_DIR / "csr_table.html"
GEN_JS_CSR_TABLE = GEN_BROWSER_DIR / "csr_table.js"

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

  desc("Generate RISC-V ISA Explorer CSR for browser")
  task :isa_explorer_browser_csr do
    Rake::Task["#{GEN_HTML_CSR_TABLE}"].invoke
    Rake::Task["#{GEN_JS_CSR_TABLE}"].invoke
  end

  desc("Generate RISC-V ISA Explorer for browser")
  task :isa_explorer_browser do
    Rake::Task["#{GEN_HTML_EXT_TABLE}"].invoke
    Rake::Task["#{GEN_JS_EXT_TABLE}"].invoke
    Rake::Task["#{GEN_HTML_INST_TABLE}"].invoke
    Rake::Task["#{GEN_JS_INST_TABLE}"].invoke
    Rake::Task["#{GEN_HTML_CSR_TABLE}"].invoke
    Rake::Task["#{GEN_JS_CSR_TABLE}"].invoke
  end
end

src_pnames = [
  "#{BACKEND_DIR}/isa_explorer.rb",
  "#{$root}/tools/ruby-gems/udb/lib/udb/architecture.rb",
  "#{$root}/tools/ruby-gems/udb/lib/udb/version_spec.rb",
  "#{$root}/tools/ruby-gems/udb/lib/udb/presence.rb",
  "#{$root}/tools/ruby-gems/udb_helpers/lib/udb_helpers/backend_helpers.rb",
  "#{$root}/tools/ruby-gems/udb/lib/udb/obj/database_obj.rb",
  "#{$root}/tools/ruby-gems/udb/lib/udb/obj/extension.rb",
  "#{$root}/tools/ruby-gems/udb/lib/udb/obj/instruction.rb"
]

file "#{GEN_XLSX}" => [
    __FILE__,
    src_pnames
].flatten do |t|
    arch = $resolver.cfg_arch_for("_")

    # Ensure directory holding target file is present.
    FileUtils.mkdir_p File.dirname(t.name)

    gen_xlsx(arch, t.name)

    puts "Success: Generated #{t.name}"
end

file "#{GEN_HTML_EXT_TABLE}" => [
    __FILE__,
  SRC_EXT_HTML_PNAME,
  SRC_LOAD_TABLE_JS_PNAME
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

    # Copy static JS file for table loading
    js_target = File.join(File.dirname(t.name), File.basename(SRC_LOAD_TABLE_JS_PNAME))
    FileUtils.copy_file(SRC_LOAD_TABLE_JS_PNAME, js_target)
end

file "#{GEN_HTML_INST_TABLE}" => [
    __FILE__,
  SRC_INST_HTML_PNAME,
  SRC_LOAD_TABLE_JS_PNAME
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

    # Copy static JS file for table loading
    js_target = File.join(File.dirname(t.name), File.basename(SRC_LOAD_TABLE_JS_PNAME))
    FileUtils.copy_file(SRC_LOAD_TABLE_JS_PNAME, js_target)
end

file "#{GEN_HTML_CSR_TABLE}" => [
    __FILE__,
  SRC_CSR_HTML_PNAME,
  SRC_LOAD_TABLE_JS_PNAME
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
    FileUtils.copy_file(SRC_CSR_HTML_PNAME, t.name)

    # Copy static JS file for table loading
    js_target = File.join(File.dirname(t.name), File.basename(SRC_LOAD_TABLE_JS_PNAME))
    FileUtils.copy_file(SRC_LOAD_TABLE_JS_PNAME, js_target)
end

file "#{GEN_JS_EXT_TABLE}" => [
    __FILE__,
    src_pnames,
    SRC_EXT_HTML_PNAME
].flatten do |t|
    arch = $resolver.cfg_arch_for("_")

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
    arch = $resolver.cfg_arch_for("_")

    # Ensure directory holding target file is present.
    FileUtils.mkdir_p File.dirname(t.name)

    gen_js_inst_table(arch, t.name)

    puts "Success: Generated #{t.name}"
end

file "#{GEN_JS_CSR_TABLE}" => [
    __FILE__,
    src_pnames,
    SRC_CSR_HTML_PNAME
].flatten do |t|
    arch = $resolver.cfg_arch_for("_")

    # Ensure directory holding target file is present.
    FileUtils.mkdir_p File.dirname(t.name)

    gen_js_csr_table(arch, t.name)

    puts "Success: Generated #{t.name}"
end

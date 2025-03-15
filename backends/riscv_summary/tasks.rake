# frozen_string_literal: true
#
# Contains Rake rules to generate xslx and html table summarizing entire RISC-V architecture.

require "pathname"
require_relative "gen_summary"

GEN_ROOT = $root / "gen" / "riscv_summary"
XLSX_GEN_DIR = GEN_ROOT / "xlsx"
XLSX_GEN_PNAME = XLSX_GEN_DIR / "riscv_summary.xlsx"

directory(XLSX_GEN_DIR)

namespace :gen do
  desc("Generate RISC-V architecture summary as an Excel spreadsheet.")
  task :riscv_summary_xlsx do
    Rake::Task["#{XLSX_GEN_PNAME}"].invoke
  end
end

file "#{XLSX_GEN_PNAME}" => [
    __FILE__,
    "#{$root}/backends/riscv_summary/gen_summary.rb",
    "#{$root}/lib/architecture.rb",
    "#{$root}/lib/arch_obj_models/database_obj.rb",
    "#{$root}/lib/arch_obj_models/extension.rb",
    "#{$root}/lib/backend_helpers.rb"
  ] do |t|
    arch = create_arch

    # Ensure directory holding target file is present.
    FileUtils.mkdir_p File.dirname(t.name)

    gen_xlsx(arch, t.name)

    puts "Success: Generated #{t.name}"
  end

# @return [Architecture]
def create_arch
  # Ensure that unconfigured resolved architecture called "_" exists.
  Rake::Task["#{$root}/.stamps/resolve-_.stamp"].invoke

  # Create architecture object using the unconfigured resolved architecture called "_" to get the entire RISC-V arch.
  Architecture.new("RISC-V Architecture", $root / "gen" / "resolved_arch" / "_")
end

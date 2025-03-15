# frozen_string_literal: true
#
# Generate

require_relative $root / "lib" / "architecture"

# @param arch [Architecture] The entire RISC-V architecture
# @param output_pname [String] Full absolute pathname to output file
def gen_xlsx(arch, output_pname)
  arch.extensions.sort_by!(&:name).each do |ext|
    puts "XXX #{ext.name}"
  end
end

# frozen_string_literal: true
#
# Generate

require "write_xlsx"
require_relative $root / "lib" / "architecture"

# @param arch [Architecture] The entire RISC-V architecture
# @param output_pname [String] Full absolute pathname to output file
def gen_xlsx(arch, output_pname)
  # Create a new Excel workbook
  workbook = WriteXLSX.new(output_pname)

  # Add a worksheet
  worksheet = workbook.add_worksheet

  # Add and define a header format
  header_format = workbook.add_format
  header_format.set_bold
  header_format.set_align('center')

  # Write a formatted and unformatted string, row and column notation.
  col = 0
  worksheet.write(0, 0, "Extension Name", header_format)

  # Add a row for each extension
  row = 1
  arch.extensions.sort_by!(&:name).each do |ext|
    worksheet.write(row, col, ext.name)
    row = row + 1
  end

  workbook.close

  # Example from https://github.com/cxn03651/write_xlsx#readme
  #
  # Write a formatted and unformatted string, row and column notation.
  #  col = row = 0
  #  worksheet.write(row, col, "Hi Excel!", header_format)
  #  worksheet.write(1,   col, "Hi Excel!")
  #
  #  header_format.set_color('red')
  #
  #  # Write a number and a formula using A1 notation
  #  worksheet.write('A3', 1.2345)
  #  worksheet.write('A4', '=SIN(PI()/4)')
end

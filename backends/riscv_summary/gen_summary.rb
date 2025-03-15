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

  # Get array of profile releases and sort by name
  sorted_profile_releases = arch.profile_releases.sort_by(&:name)

  # Remove Mock profile release if present.
  sorted_profile_releases.delete_if {|pr| pr.name == "Mock" }

  # Move RVI20 to the beginning of the array if it exists.
  if sorted_profile_releases.any? {|pr| pr.name == "RVI20" }
    sorted_profile_releases.delete_if {|pr| pr.name == "RVI20" }
    sorted_profile_releases.unshift(arch.profile_release("RVI20"))
  end

  # Write a formatted and unformatted string, row and column notation.
  col = 0
  worksheet.write(0, col, "Extension Name", header_format); col += 1
  worksheet.write(0, col, "Ratification\nPackage\nName", header_format); col += 1
  worksheet.write(0, col, "Description", header_format); col += 1
  worksheet.write(0, col, "IC", header_format); col += 1
  worksheet.write(0, col, "Extensions\nIncluded\n(subsets)", header_format); col += 1
  worksheet.write(0, col, "Implies\n(and\ntransitives)", header_format); col += 1
  worksheet.write(0, col, "Incompatible\n(and\ntransitives)", header_format); col += 1
  worksheet.write(0, col, "Ratified\n(Y/N)", header_format); col += 1
  worksheet.write(0, col, "Ratification\nDate", header_format); col += 1
  sorted_profile_releases.each do |pr|
    worksheet.write(0, col, pr.name, header_format); col += 1
  end

  # Add a row for each extension
  row = 1
  arch.extensions.sort_by!(&:name).each do |ext|
    col = 0
    worksheet.write(row, col, ext.name); col += 1
    worksheet.write(row, col, "UDB Missing"); col += 1
    worksheet.write(row, col, ext.long_name); col += 1
    worksheet.write(row, col, ext.compact_priv_type); col += 1
    worksheet.write(row, col, "UDB Missing"); col += 1
    worksheet.write(row, col, ext.max_version.transitive_implications.map(&:name).join("\n")); col += 1
    worksheet.write(row, col, ext.max_version.transitive_conflicts.map(&:name).join("\n")); col += 1
    worksheet.write(row, col, ext.ratified ? "Y" : "N"); col += 1
    worksheet.write(row, col,
      if ext.ratified
        if ext.min_ratified_version.ratification_date.nil? || ext.min_ratified_version.ratification_date.empty?
          "UDB MISSING"
        else
          ext.min_ratified_version.ratification_date
        end
      else
        ""
      end
    ); col += 1
    sorted_profile_releases.each do |pr|
      ep = pr.extension_presence(ext.name)
      worksheet.write(row, col,
        if ep == ExtensionPresence.mandatory
          "m"
        elsif ep == ExtensionPresence.optional
          "o"
        elsif ep == "-"
          "n"
        else
          raise "Unknown presence of '#{ep}' for extension #{ext.name}"
        end
      ); col += 1
    end

    row += 1
  end

  # Set column widths to hold data width.
  worksheet.autofit

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

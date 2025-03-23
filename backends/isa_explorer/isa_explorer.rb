# frozen_string_literal: true
#
# Generate

require "write_xlsx"
require_relative $root / "lib" / "architecture"

# @param arch [Architecture] The entire RISC-V architecture
# @return [Hash<String,Array<String>] Summary data with array of column names and array of row data.
def arch2summary(arch)
  # Get array of profile releases and sort by name
  sorted_profile_releases = arch.profile_releases.sort_by(&:name)

  # Remove Mock profile release if present.
  sorted_profile_releases.delete_if {|pr| pr.name == "Mock" }

  # Move RVI20 to the beginning of the array if it exists.
  if sorted_profile_releases.any? {|pr| pr.name == "RVI20" }
    sorted_profile_releases.delete_if {|pr| pr.name == "RVI20" }
    sorted_profile_releases.unshift(arch.profile_release("RVI20"))
  end

  summary = {
    "column_names" => [
      "Extension Name",
      "Ratification\nPackage\nName",
      "Description",
      "IC",
      "Extensions\nIncluded\n(subsets)",
      "Implies\n(and\ntransitives)",
      "Incompatible\n(and\ntransitives)",
      "Ratified\n(Y/N)",
      "Ratification\nDate",
      sorted_profile_releases.map(&:name)
    ].flatten,

    # Will eventually be an array containing arrays.
    "rows" => []
  }

  arch.extensions.sort_by!(&:name).each do |ext|
    row = [
      ext.name,
      "UDB Missing",
      ext.long_name,
      ext.compact_priv_type,
      "UDB Missing",
      ext.max_version.transitive_implications.map(&:name).join("\n"),
      ext.max_version.transitive_conflicts.map(&:name).join("\n"),
      ext.ratified ? "Y" : "N",
      if ext.ratified
        if ext.min_ratified_version.ratification_date.nil? || ext.min_ratified_version.ratification_date.empty?
          "UDB MISSING"
        else
          ext.min_ratified_version.ratification_date
        end
      else
        ""
      end,
      sorted_profile_releases.map do |pr|
        ep = pr.extension_presence(ext.name)
        if ep == ExtensionPresence.mandatory
          "m"
        elsif ep == ExtensionPresence.optional
          "o"
        elsif ep == "-"
          "n"
        else
          raise "Unknown presence of '#{ep}' for extension #{ext.name}"
        end
      end
    ].flatten

    summary["rows"].append(row)
  end

  return summary
end

# Create ISA Explorer extension table as XLSX file.
#
# @param arch [Architecture] The entire RISC-V architecture
# @param output_pname [String] Full absolute pathname to output file
def gen_xlsx_ext_table(arch, output_pname)
  # Convert arch to summary data structure
  summary = arch2summary(arch)

  # Create a new Excel workbook
  workbook = WriteXLSX.new(output_pname)

  # Add a worksheet
  worksheet = workbook.add_worksheet

  # Add and define a header format
  header_format = workbook.add_format
  header_format.set_bold
  header_format.set_align('center')

  # Add column names in 1st row (row 0).
  col = 0
  summary["column_names"].each do |column_name|
    worksheet.write(0, col, column_name, header_format)
    col += 1
  end

  # Add extension information in rows
  row = 1
  summary["rows"].each do |row_cells|
    col = 0
    row_cells.each do |cell|
      worksheet.write(row, col, cell)
      col += 1
    end
    row += 1
  end

  # Set column widths to hold data width.
  worksheet.autofit

  workbook.close
end

# Create ISA Explorer extension table as JavaScript file.
#
# @param arch [Architecture] The entire RISC-V architecture
# @param output_pname [String] Full absolute pathname to output file
def gen_js_ext_table(arch, output_pname)
  # Convert arch to summary data structure
  summary = arch2summary(arch)

  column_names = summary["column_names"]
  rows = summary["rows"]

  File.open(output_pname, "w") do |fp|
    fp.write "// Define data array\n"
    fp.write "\n"
    fp.write "var tabledata = [\n"

    rows.each do |row|
      items = []
      column_names.each_index do |i|
          column_name = column_names[i].gsub("\n", " ")
          cell = row[i].gsub("\n", " ")
          items.append('"' + column_name + '":"' + cell + '"')
      end
      fp.write "  {" + items.join(", ") + "},\n"
    end

    fp.write "];\n"
    fp.write "\n"
    fp.write "// Initialize table\n"
    fp.write "var table = new Tabulator(\"#ext_table\", {\n"
    fp.write "  data: tabledata, // Assign data to table\n"
    fp.write "  autoColumns: true // Create columns from data field names\n"
    fp.write "});\n"
    fp.write "\n"
  end
end

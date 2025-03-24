# frozen_string_literal: true
#
# Generate

require "write_xlsx"
require_relative $root / "lib" / "architecture"

# @param arch [Architecture] The entire RISC-V architecture
# @return [Hash<String,Array<String>] Extension table data with array of column names and array of row data.
def arch2ext_table(arch)
  # Get array of profile releases and sort by name
  sorted_profile_releases = arch.profile_releases.sort_by(&:name)

  # Remove Mock profile release if present.
  sorted_profile_releases.delete_if {|pr| pr.name == "Mock" }

  # Move RVI20 to the beginning of the array if it exists.
  if sorted_profile_releases.any? {|pr| pr.name == "RVI20" }
    sorted_profile_releases.delete_if {|pr| pr.name == "RVI20" }
    sorted_profile_releases.unshift(arch.profile_release("RVI20"))
  end

  ext_table = {
    # Array of hashes
    "columns" => [
      {name: "Extension Name", formatter: "link", sorter: "alphanum", formatterParams:
        {
        labelField:"Extension Name",
        urlPrefix: "https://risc-v-certification-steering-committee.github.io/riscv-unified-db/manual/html/isa/isa_20240411/exts/"
        }
      },
      {name: "Ratification\nPackage\nName",  formatter: "textarea", sorter: "alphanum"},
      {name: "Description", formatter: "textarea", sorter: "alphanum"},
      {name: "IC", formatter: "textarea", sorter: "alphanum"},
      {name: "Extensions\nIncluded\n(subsets)", formatter: "textarea", sorter: "alphanum"},
      {name: "Implies\n(and\ntransitives)", formatter: "textarea", sorter: "alphanum"},
      {name: "Incompatible\n(and\ntransitives)", formatter: "textarea", sorter: "alphanum"},
      {name: "Ratified\n(Y/N)", formatter: "textarea", sorter: "alphanum"},
      {name: "Ratification\nDate", formatter: "textarea", sorter: "alphanum"},
      sorted_profile_releases.map do |pr|
        {name: "#{pr.name}", formatter: "textarea", sorter: "alphanum"}
      end
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

    ext_table["rows"].append(row)
  end

  return ext_table
end

# Create ISA Explorer extension table as XLSX file.
#
# @param arch [Architecture] The entire RISC-V architecture
# @param output_pname [String] Full absolute pathname to output file
def gen_xlsx_ext_table(arch, output_pname)
  # Convert arch to ext_table data structure
  ext_table = arch2ext_table(arch)

  # Create a new Excel workbook
  workbook = WriteXLSX.new(output_pname)

  # Add a worksheet
  worksheet = workbook.add_worksheet

  # Add and define a header format
  header_format = workbook.add_format
  header_format.set_bold
  header_format.set_align('center')

  # Add column names in 1st row (row 0).
  col_num = 0
  ext_table["columns"].each do |column|
    worksheet.write(0, col_num, column[:name], header_format)
    col_num += 1
  end

  # Add extension information in rows
  row_num = 1
  ext_table["rows"].each do |row_cells|
    col_num = 0
    row_cells.each do |cell|
      worksheet.write(row_num, col_num, cell)
      col_num += 1
    end
    row_num += 1
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
  # Convert arch to ext_table data structure
  ext_table = arch2ext_table(arch)

  columns = ext_table["columns"]
  rows = ext_table["rows"]

  File.open(output_pname, "w") do |fp|
    fp.write "// Define data array\n"
    fp.write "\n"
    fp.write "var tabledata = [\n"

    rows.each do |row|
      items = []
      columns.each_index do |i|
          column = columns[i]
          column_name = column[:name].gsub("\n", " ")
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
    fp.write "  columns:[\n"
    columns.each do |column|
      column_name = column[:name].gsub("\n", " ")
      sorter = column[:sorter]
      formatter = column[:formatter]
      fp.write "    {title: \"#{column_name}\", field: \"#{column_name}\", sorter: \"#{sorter}\", formatter: \"#{formatter}\""
      if formatter == "link"
        formatterParams = column[:formatterParams]
        urlPrefix = formatterParams[:urlPrefix]
        fp.write ", formatterParams:{\n"
        fp.write "      labelField:\"#{column_name}\",\n"
        fp.write "      urlPrefix:\"#{urlPrefix}\"\n"
        fp.write "      }\n"
      end
      fp.write "    },\n"
    end
    fp.write "  ]\n"
    fp.write "});\n"
    fp.write "\n"
  end
end

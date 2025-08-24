
# typed: true
# frozen_string_literal: true

# Generate

require "sorbet-runtime"
require "write_xlsx"

require "udb/architecture"

# @param presence [String] Can be nil
# @return [String] m=mandatory, o=optional, n=not present
def presence2char(presence)
  raise ArgumentError, "Expecting String but got class #{presence}" unless presence.is_a?(String)

  if presence == Udb::Presence.mandatory
    "m"
  elsif presence == Udb::Presence.optional
    "o"
  elsif presence == '-'
    "n"
  else
    raise ArgumentError, "Unknown presence of #{presence}"
  end
end

# @param arch [Udb::Architecture] The entire RISC-V architecture
# @return [Hash<String,Array<String>] Extension table data
def arch2ext_table(arch)
  raise ArgumentError, "arch is a #{arch.class} class but needs to be Architecture" unless arch.is_a?(Udb::Architecture)

  sorted_profile_releases = get_sorted_profile_releases(arch)

  ext_table = {
    # Array of hashes
    "columns" => [
      {name: "Extension Name", formatter: "link", sorter: "alphanum", headerFilter: true, frozen: true, formatterParams:
        {
        labelField:"Extension Name",
        urlPrefix: "https://riscv-software-src.github.io/riscv-unified-db/manual/html/isa/isa_20240411/exts/"
        }
      },
      {name: "Description", formatter: "textarea", sorter: "alphanum", headerFilter: true},
      {name: "IC", formatter: "textarea", sorter: "alphanum", headerFilter: true},
      {name: "Implies\n(Exts)", formatter: "textarea", sorter: "alphanum"},
      {name: "Requires\n(Ext Reqs)", formatter: "textarea", sorter: "alphanum"},
      {name: "Incompatible\n(Ext Reqs)", formatter: "textarea", sorter: "alphanum"},
      {name: "Ratified", formatter: "textarea", sorter: "boolean", headerFilter: true},
      {name: "Ratification\nDate", formatter: "textarea", sorter: "alphanum", headerFilter: true},
      sorted_profile_releases.map do |pr|
        {name: "#{pr.name}", formatter: "textarea", sorter: "alphanum", headerFilter: true}
      end
    ].flatten,

    # Will eventually be an array containing arrays.
    "rows" => []
    }

  arch.extensions.sort_by!(&:name).each do |ext|
    row = [
      ext.name,           # Name
      ext.long_name,      # Description
      ext.compact_priv_type,  # IC
      ext.max_version.implications.map{|cond_ext_ver| cond_ext_ver.ext_ver.name}.uniq,  # Implies
      ext.max_version.requirement_condition.empty? ? "" : ext.max_version.requirement_condition.to_logic_tree.to_s, # Requires
      ext.conflicts_condition.empty? ? "" : ext.conflicts_condition.to_logic_tree.to_s, # Incompatible
      ext.ratified,
      if ext.ratified
        if ext.min_ratified_version.ratification_date.nil? || ext.min_ratified_version.ratification_date.empty?
          "UDB MISSING"
        else
          ext.min_ratified_version.ratification_date
        end
      else
        ""
      end
    ]

    sorted_profile_releases.each do |pr|
      row.append(presence2char(pr.extension_presence(ext.name)))
    end

    ext_table["rows"].append(row)
  end

  return ext_table
end

# @param arch [Udb::Architecture] The entire RISC-V architecture
# @return [Hash<String,Array<String>] Instruction table data
sig { params(arch: Udb::Architecture).returns(T::Hash[String, T::Array[String]]) }
def arch2inst_table(arch)
  sorted_profile_releases = get_sorted_profile_releases(arch)

  inst_table = {
    # Array of hashes
    "columns" => [
      {name: "Instruction Name", formatter: "link", sorter: "alphanum", headerFilter: true, frozen: true, formatterParams:
        {
        labelField:"Instruction Name",
        urlPrefix: "https://riscv-software-src.github.io/riscv-unified-db/manual/html/isa/isa_20240411/insts/"
        }
      },
      {name: "Description", formatter: "textarea", sorter: "alphanum", headerFilter: true},
      {name: "Assembly", formatter: "textarea", sorter: "alphanum", headerFilter: true},
      sorted_profile_releases.map do |pr|
        {name: "#{pr.name}", formatter: "textarea", sorter: "alphanum", headerFilter: true}
      end
    ].flatten,

    # Will eventually be an array containing arrays.
    "rows" => []
    }

  insts = arch.instructions.sort_by!(&:name)
  progressbar = ProgressBar.create(title: "Instruction Table", total: insts.size)

  insts.each do |inst|
    progressbar.increment

    row = [
      inst.name,
      inst.long_name,
      inst.name + " " + inst.assembly.gsub('x', 'r')
    ]

    sorted_profile_releases.each do |pr|
      row.append(presence2char(pr.instruction_presence(inst.name)))
    end

    inst_table["rows"].append(row)
  end

  return inst_table
end

# @param arch [Udb::Architecture] The entire RISC-V architecture
# @return [Hash<String,Array<String>] CSR table data
sig { params(arch: Udb::Architecture).returns(T::Hash[String, T::Array[String]]) }
def arch2csr_table(arch)
  sorted_profile_releases = get_sorted_profile_releases(arch)

  csr_table = {
    # Array of hashes
    "columns" => [
      {name: "CSR Name", formatter: "link", sorter: "alphanum", headerFilter: true, frozen: true, formatterParams:
        {
        labelField:"CSR Name",
        urlPrefix: "https://riscv-software-src.github.io/riscv-unified-db/manual/html/isa/isa_20240411/csrs/"
        }
      },
      {name: "Address", formatter: "textarea", sorter: "number", headerFilter: true},
      {name: "Description", formatter: "textarea", sorter: "alphanum", headerFilter: true},
      sorted_profile_releases.map do |pr|
        {name: "#{pr.name}", formatter: "textarea", sorter: "alphanum", headerFilter: true}
      end
    ].flatten,

    # Will eventually be an array containing arrays.
    "rows" => []
    }

  csrs = arch.csrs.sort_by!(&:name)
  progressbar = ProgressBar.create(title: "CSR Table", total: csrs.size)

  csrs.each do |csr|
    progressbar.increment

    raise "Indirect CSRs not yet supported for CSR #{csr.name}" if csr.address.nil?

    row = [
      csr.name,
      csr.address,
      csr.long_name,
    ]

    sorted_profile_releases.each do |pr|
      row.append(presence2char(pr.csr_presence(csr.name)))
    end

    csr_table["rows"].append(row)
  end

  return csr_table
end

# Create ISA Explorer table as XLSX worksheet.
#
# @param table [Hash<String,Array<String>] Table data
# @param workbook
# @param worksheet
def gen_xlsx_table(table, workbook, worksheet)
  # Add and define a header format
  header_format = workbook.add_format
  header_format.set_bold
  header_format.set_align('center')

  # Add column names in 1st row (row 0).
  col_num = 0
  table["columns"].each do |column|
    worksheet.write(0, col_num, column[:name], header_format)
    col_num += 1
  end

  # Add table information in rows
  row_num = 1
  table["rows"].each do |row_cells|
    col_num = 0
    row_cells.each do |cell|
      if cell.is_a?(String) || cell.is_a?(Integer)
        cell_fmt = cell.to_s
      elsif cell.is_a?(TrueClass) || cell.is_a?(FalseClass)
        cell_fmt = cell ? "Y" : "N"
      elsif cell.is_a?(Array)
        cell_fmt = cell.join(", ")
      else
        raise ArgumentError, "Unknown cell class of #{cell.class} for '#{cell}'"
      end

      worksheet.write(row_num, col_num, cell_fmt)
      col_num += 1
    end
    row_num += 1
  end

  # Set column widths to hold data width.
  worksheet.autofit
end

# Create ISA Explorer tables as XLSX file.
#
# @param arch [Udb::Architecture] The entire RISC-V architecture
# @param output_pname [String] Full absolute pathname to output file
sig { params(arch: Udb::Architecture, output_pname: String).void }
def gen_xlsx(arch, output_pname)

  # Create a new Excel workbook
  $logger.info "Creating Excel workboook #{output_pname}"
  workbook = WriteXLSX.new(output_pname)

  # Convert arch to ext_table data structure
  $logger.info "Creating extension table data structure"
  ext_table = arch2ext_table(arch)

  # Add a worksheet
  ext_worksheet = workbook.add_worksheet("Extensions")

  # Populate worksheet with ext_table
  $logger.info "Adding extension table to worksheet #{ext_worksheet.name}"
  gen_xlsx_table(ext_table, workbook, ext_worksheet)

  # Convert arch to inst_table data structure
  $logger.info "Creating instruction table data structure"
  inst_table = arch2inst_table(arch)

  # Add a worksheet
  inst_worksheet = workbook.add_worksheet("Instructions")

  # Populate worksheet with inst_table
  $logger.info "Adding instruction table to worksheet #{inst_worksheet.name}"
  gen_xlsx_table(inst_table, workbook, inst_worksheet)

  # Convert arch to csr_table data structure
  $logger.info "Creating CSR table data structure"
  csr_table = arch2csr_table(arch)

  # Add a worksheet
  csr_worksheet = workbook.add_worksheet("CSRs")

  # Populate worksheet with csr
  $logger.info "Adding CSR table to worksheet #{csr_worksheet.name}"
  gen_xlsx_table(csr_table, workbook, csr_worksheet)

  workbook.close
end

# Create ISA Explorer table as JavaScript file.
#
# @param table [Hash<String,Array<String>] Table data
# @param div_name [String] Name of div element in HTML
# @param output_pname [String] Full absolute pathname to output file
def gen_js_table(table, div_name, output_pname)
  columns = table["columns"]
  rows = table["rows"]

  File.open(output_pname, "w") do |fp|
    fp.write "// Define data array\n"
    fp.write "\n"
    fp.write "var tabledata = [\n"

    rows.each do |row|
      items = []
      columns.each_index do |i|
          column = columns[i]
          column_name = column[:name].gsub("\n", " ")
          cell = row[i]
          if cell.is_a?(String)
            cell_fmt = '"' + row[i].gsub("\n", "\\n") + '"'
          elsif cell.is_a?(TrueClass) || cell.is_a?(FalseClass) || cell.is_a?(Integer)
            cell_fmt = "#{cell}"
          elsif cell.is_a?(Array)
            cell_fmt = '"'+ cell.join("\\n") + '"'
          else
            raise ArgumentError, "Unknown cell class of #{cell.class} for '#{cell}'"
          end
          items.append('"' + column_name + '":' + cell_fmt)
      end
      fp.write "  {" + items.join(", ") + "},\n"
    end

    fp.write "];\n"
    fp.write "\n"
    fp.write "// Initialize table\n"
    fp.write "var table = new Tabulator(\"##{div_name}\", {\n"
    fp.write "  height: window.innerHeight-25, // Set height to window less 25 pixels for horz scrollbar\n"
    fp.write "  data: tabledata, // Assign data to table\n"
    fp.write "  columns:[\n"
    columns.each do |column|
      column_name = column[:name].gsub("\n", " ")
      sorter = column[:sorter]
      formatter = column[:formatter]
      fp.write "    {title: \"#{column_name}\", field: \"#{column_name}\", sorter: \"#{sorter}\", formatter: \"#{formatter}\""

      if column[:headerFilter] == true
        fp.write ", headerFilter: true"
      end
      if column[:headerVertical] == true
        fp.write ", headerVertical: true"
      end
      if column[:frozen] == true
        fp.write ", frozen: true"
      end

      if formatter == "link"
        formatterParams = column[:formatterParams]
        urlPrefix = formatterParams[:urlPrefix]
        fp.write ", formatterParams:{\n"
        fp.write "      labelField:\"#{column_name}\",\n"
        fp.write "      urlPrefix:\"#{urlPrefix}\"\n"
        fp.write "      }\n"
      # elsif formatter == "array"
      end
      fp.write "    },\n"
    end
    fp.write "  ]\n"
    fp.write "});\n"
    fp.write "\n"

    fp.write "// Load data in chunks after table is built\n"
    fp.write "table.on(\"tableBuilt\", function() {\n"
    fp.write "    loadDataInChunks(tabledata);\n"
    fp.write "});\n"
    fp.write "\n"
  end
end

# Create ISA Explorer extension table as JavaScript file.
#
# @param arch [Udb::Architecture] The entire RISC-V architecture
# @param output_pname [String] Full absolute pathname to output file
def gen_js_ext_table(arch, output_pname)
  raise ArgumentError, "arch is a #{arch.class} class but needs to be Architecture" unless arch.is_a?(Udb::Architecture)
  raise ArgumentError, "output_pname is a #{output_pname.class} class but needs to be String" unless output_pname.is_a?(String)

  # Convert arch to ext_table data structure
  $logger.info "Creating extension table data structure"
  ext_table = arch2ext_table(arch)

  $logger.info "Converting extension table to #{output_pname}"
  gen_js_table(ext_table, "ext_table", output_pname)
end

# Create ISA Explorer instruction table as JavaScript file.
#
# @param arch [Udb::Architecture] The entire RISC-V architecture
# @param output_pname [String] Full absolute pathname to output file
def gen_js_inst_table(arch, output_pname)
  raise ArgumentError, "arch is a #{arch.class} class but needs to be Architecture" unless arch.is_a?(Udb::Architecture)
  raise ArgumentError, "output_pname is a #{output_pname.class} class but needs to be String" unless output_pname.is_a?(String)

  # Convert arch to inst_table data structure
  $logger.info "Creating instruction table data structure"
  inst_table = arch2inst_table(arch)

  $logger.info "Converting instruction table to #{output_pname}"
  gen_js_table(inst_table, "inst_table", output_pname)
end

# Create ISA Explorer CSR table as JavaScript file.
#
# @param arch [Udb::Architecture] The entire RISC-V architecture
# @param output_pname [String] Full absolute pathname to output file
def gen_js_csr_table(arch, output_pname)
  raise ArgumentError, "arch is a #{arch.class} class but needs to be Architecture" unless arch.is_a?(Udb::Architecture)
  raise ArgumentError, "output_pname is a #{output_pname.class} class but needs to be String" unless output_pname.is_a?(String)

  # Convert arch to csr_table data structure
  $logger.info "Creating CSR table data structure"
  csr_table = arch2csr_table(arch)

  $logger.info "Converting CSR table to #{output_pname}"
  gen_js_table(csr_table, "csr_table", output_pname)
end

# param [Udb::Architecture] arch
# return [Array<ProfileRelease>] Nice list of profile release to use in a nice order
def get_sorted_profile_releases(arch)
  raise ArgumentError, "arch is a #{arch.class} class but needs to be Udb::Architecture" unless arch.is_a?(Udb::Architecture)

  # Get array of profile releases and sort by name
  sorted_profile_releases = arch.profile_releases.sort_by(&:name)

  # Remove Mock profile release if present.
  sorted_profile_releases.delete_if {|pr| pr.name == "Mock" }

  # Move RVI20 to the beginning of the array if it exists.
  if sorted_profile_releases.any? {|pr| pr.name == "RVI20" }
    sorted_profile_releases.delete_if {|pr| pr.name == "RVI20" }
    sorted_profile_releases.unshift(arch.profile_release("RVI20"))
  end

  return sorted_profile_releases
end

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"
require "tty-exit"
require "tty-progressbar"
require "write_xlsx"

require_relative "../common-opts"
require_relative "../defines"
require_relative "../template_helpers"

require "udb/obj/extension"

module UdbGen
  module IsaExplorerGen
    extend T::Sig

    # @param presence [String] Can be nil
    # @return [String] m=mandatory, o=optional, n=not present
    def self.presence2char(presence)
      raise ArgumentError, "Expecting String but got class #{presence}" unless presence.is_a?(String)

      if presence == "mandatory"
        "m"
      elsif presence == "optional"
        "o"
      elsif presence == "-"
        "n"
      else
        raise ArgumentError, "Unknown presence of #{presence}"
      end
    end

    # @param arch The entire RISC-V architecture
    # @return Extension table data
    sig { params(arch: Udb::ConfiguredArchitecture, skip: Integer).returns(T::Hash[String, T::Array[String]]) }
    def self.arch2ext_table(arch, skip)

      sorted_profile_releases = get_sorted_profile_releases(arch)

      ext_table = {
        # Array of hashes
        "columns" => [
          { name: "Extension Name", formatter: "link", sorter: "alphanum", headerFilter: true, frozen: true, formatterParams:
            {
            labelField: "Extension Name",
            urlPrefix: "https://riscv-software-src.github.io/riscv-unified-db/manual/html/isa/isa_20240411/exts/"
            }
          },
          { name: "Description", formatter: "textarea", sorter: "alphanum", headerFilter: true },
          { name: "IC", formatter: "textarea", sorter: "alphanum", headerFilter: true },
          { name: "Requires\n(Exts)", formatter: "textarea", sorter: "alphanum" },
          { name: "Transitive Requires\n(Ext)", formatter: "textarea", sorter: "alphanum" },
          { name: "Incompatible\n(Ext Reqs)", formatter: "textarea", sorter: "alphanum" },
          { name: "Ratified", formatter: "textarea", sorter: "boolean", headerFilter: true },
          { name: "Ratification\nDate", formatter: "textarea", sorter: "alphanum", headerFilter: true },
          sorted_profile_releases.map do |pr|
            { name: "#{pr.name}", formatter: "textarea", sorter: "alphanum", headerFilter: true }
          end
        ].flatten,

        # Will eventually be an array containing arrays.
        "rows" => []
        }

      pb = Udb.create_progressbar(
        "Analyzing extensions [:bar] :current/:total",
        total: arch.extensions.size,
        clear: true
      )

      arch.extensions.sort_by!(&:name).each_with_index do |ext, idx|
        pb.advance

        if skip != 0
          next unless (idx % skip) == 0
        end

        row = [
          ext.name,           # Name
          ext.long_name,      # Description
          ext.compact_priv_type,  # IC
          ext.max_version.ext_requirements(expand: false).map do |cond_ext_req|
            if cond_ext_req.cond.empty?
              cond_ext_req.ext_req.name
            else
              "#{cond_ext_req.ext_req.name} if #{cond_ext_req.cond}"
            end
          end.uniq,  # Requires
          ext.max_version.ext_requirements(expand: true).map do |cond_ext_req|
            if cond_ext_req.cond.empty?
              cond_ext_req.ext_req.name
            else
              "#{cond_ext_req.ext_req.name} if #{cond_ext_req.cond}"
            end
          end.uniq,  # Transitive Requires
          ext.conflicting_extensions.map(&:name),
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

    # Create ISA Explorer table as JavaScript file.
    #
    # @param table Table data
    # @param div_name Name of div element in HTML
    sig { params(table: T::Hash[String, T::Array[String]], div_name: String).returns(String) }
    def self.gen_js_table(table, div_name)
      columns = table["columns"]
      rows = table["rows"]

      fp = StringIO.new
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
            cell_fmt = '"' + cell.join("\\n") + '"'
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
      fp.rewind
      fp.read
    end

    # Create ISA Explorer extension table as JavaScript file.
    #
    # @param arch [Udb::Architecture] The entire RISC-V architecture
    sig { params(arch: Udb::ConfiguredArchitecture, skip: Integer).returns(String) }
    def self.gen_js_ext_table(arch, skip)

      # Convert arch to ext_table data structure
      Udb.logger.info "Creating extension table data structure"
      ext_table = arch2ext_table(arch, skip)

      gen_js_table(ext_table, "ext_table")
    end

    # return Nice list of profile release to use in a nice order
    sig { params(arch: Udb::ConfiguredArchitecture).returns(T::Array[Udb::ProfileRelease]) }
    def self.get_sorted_profile_releases(arch)
      raise ArgumentError, "arch is a #{arch.class} class but needs to be Udb::Architecture" unless arch.is_a?(Udb::Architecture)

      # Get array of profile releases and sort by name
      sorted_profile_releases = arch.profile_releases.sort_by(&:name)

      # Remove Mock profile release if present.
      sorted_profile_releases.delete_if { |pr| pr.name == "Mock" }

      # Move RVI20 to the beginning of the array if it exists.
      if sorted_profile_releases.any? { |pr| pr.name == "RVI20" }
        sorted_profile_releases.delete_if { |pr| pr.name == "RVI20" }
        sorted_profile_releases.unshift(T.must(arch.profile_release("RVI20")))
      end

      return sorted_profile_releases
    end
  end

  class GenIsaExplorerOptions < SubcommandWithCommonOptions
    include TTY::Exit
    include TemplateHelpers

    sig { void }
    def initialize
      super(name: "isa-explorer", desc: "Create ISA explorer tables / sites")
    end

    usage \
      command: name,
      desc:   "Create static websites and/or spreadsheets populated with helpful ISA information",
      example: <<~EXAMPLE
        Generate a static HTML page with extension information
          $ #{$PROGRAM_NAME} #{name} -t ext-browser -o gen/isa_explorer
      EXAMPLE

    option :type do
      T.bind(self, TTY::Option::Parameter::Option)
      short "-t"
      long "--type=type"
      desc "The type of artifact to build"
      permit ["ext-browser"]
      required
    end

    option :skip do
      T.bind(self, TTY::Option::Parameter::Option)
      long "--skip=N"
      desc "Only consider every Nth ext/inst/etc. (for testing)"
      convert :integer
      default 0
    end

    option :output_dir do
      T.bind(self, TTY::Option::Parameter::Option)
      required
      short "-o"
      long "--out=directory"
      desc "Output directory"
      convert :path
    end

    option :debug do
      T.bind(self, TTY::Option::Parameter::Option)
      desc "Set debug level"
      long "--debug=level"
      short "-d"
      default "info"
      permit ["debug", "info", "warn", "error", "fatal"]
    end

    sig { void }
    def gen_ext_browser
      FileUtils.mkdir_p params[:output_dir].dirname

      target_html_fn = params[:output_dir] / "ext-explorer.html"

      # Delete target file if already present.
      if target_html_fn.exist?
        begin
          File.delete(target_html_fn)
        rescue StandardError => e
          raise "Can't delete '#{target_html_fn}': #{e.message}"
        end
      end

      js_table = IsaExplorerGen.gen_js_ext_table(cfg_arch, params[:skip])

      template_path = Pathname.new(Gem.loaded_specs["udb-gen"].full_gem_path) / "templates" / "ext-browser.html.erb"

      erb = ERB.new(template_path.read, trim_mode: "-")
      erb.filename = template_path.to_s

      template_path.write erb.result(binding)
    end

    sig { override.params(argv: T::Array[String]).returns(T.noreturn) }
    def run(argv)
      parse(argv)

      if params[:help]
        print help
        exit_with(:success)
      end

      if params.errors.any?
        exit_with(:usage_error, "#{params.errors.summary}\n\n#{help}")
      end

      unless params.remaining.empty?
        exit_with(:usage_error, "Unknown arguments: #{params.remaining}\n")
      end

      case params[:type]
      when "ext-browser"
        gen_ext_browser
      else
        Udb.logger.error "Unknown target type: #{params[:type]}"
      end

      exit_with(:success)
    end

  end
end

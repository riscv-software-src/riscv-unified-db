#!/usr/bin/env ruby

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen-string-literal: true

require "tty-box"
require "tty-markdown"
require "tty-prompt"

require "numbers_and_words"
require "udb/cli/sub_command_base"

module Udb
  module CreationActions
    extend T::Sig

    class CreatedFile < T::Struct
      const :path, Pathname
      const :contents, String
      const :next_steps, T::Array[String]
    end

    class OpcodeOrVariable < T::Struct
      const :name, String
      const :location, String
    end

    sig { returns(T::Hash[String, T.untyped]) }
    def self.schema_defs
      @schema_defs ||= JSON.load_file(Udb.repo_root / "spec" / "schemas" / "schema_defs.json")
    end

    sig { params(prompt: TTY::Prompt).returns(String) }
    def self.get_copyright(prompt)
      prompt.say \
        "First, let's get the legal necessities out of the way."

      copyright = prompt.ask \
      "What copyright do you want to assign to newly created files?",
      default: "Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.",
      required: true,
      modify: [:trim]

      license_info = <<~INFO
        Great. The copyright will read:
           #{copyright}

        The license defaults to BSD-3-Clear.
        Other licenses will likely not be accepted upstream.

        Press any key to continue
      INFO
      TtyTools.display_box(prompt, "LICENSE", license_info)

      copyright
    end

    sig { params(prompt: TTY::Prompt, copyright: String, outdir: Pathname).returns(CreatedFile) }
    def self.create_extension(prompt, copyright, outdir)
      schema_defs = CreationActions.schema_defs
      spec_states = schema_defs["$defs"]["spec_state"]["enum"]

      type = prompt.select \
        "Is this a RISC-V standard extension or a custom extension?",
        ["standard", "custom"], default: "standard"

      name_regex =
        if type == "standard"
          /#{schema_defs["$defs"]["standard_extension_name"]["pattern"]}/
        else
          /#{schema_defs["$defs"]["custom_extension_name"]["pattern"]}/
        end
      name = prompt.ask \
        "What is the extension name (e.g., Zibi)?",
        validate: name_regex

      state = prompt.select \
        "What is the state of the extension?",
        spec_states,
        default: "development"

      priv_type = prompt.select \
        "Is this an unprivileged or privileged extension?",
        ["unprivileged", "privileged"],
        default: "unprivileged"

      long_name = prompt.ask \
        "What is a short description of the extension? (e.g., \"Bitmanipulation instructions\", \"Vector cryptography\", ...)",
        required: true,
        modify: [:trim]

      version = prompt.ask \
        "What is the initial version?",
        validate: /#{schema_defs["$defs"]["rvi_version"]["pattern"]}/,
        default: "0.1"

      contributors = prompt.collect do
        loop do
          prompt.say "Who is the first contributor?"
          me = T.cast(self, TTY::Prompt::AnswersCollector)
          me.key(:people).values do
            me.key(:name).ask("Full name?", required: true, modify: [:trim])

            me.key(:email).ask("Email?", validate: :email, modify: [:trim])

            me.key(:company).ask("Company?", modify: [:trim])
          end
          break unless prompt.yes?("Add another contributor?")
        end
      end

      template_path = Udb.gem_path / "lib" / "udb" / "templates" / "extension.yaml.erb"
      dest_path = outdir / "ext" / "#{name}.yaml"

      erb = ERB.new(template_path.read, trim_mode: "-")
      erb.filename = template_path.to_s

      CreatedFile.new(path: dest_path, contents: erb.result(binding), next_steps: [])
    end

    sig { params(prompt: TTY::Prompt, copyright: String, outdir: Pathname, location: String).returns(CreatedFile) }
    def self.create_inst_opcode(prompt, copyright, outdir, location)
      size = location.index("-").nil? ? 1 : location.split("-")[0].to_i - location.split("-")[1].to_i + 1
      name = prompt.ask \
        "What is the name of the opcode (e.g., OP-32)?"

      value = prompt.ask \
        "What is the value of the opcode, as a binary number (e.g., 0111011)?",
        validate: (proc do |v|
          v =~ /^[01]+$/ && \
            v.to_i(2).bit_length <= size
        end)

      display = prompt.ask \
        "How should the opcode be displayed in documentation?",
        default: name

      template_path = Udb.gem_path / "lib" / "udb" / "templates" / "instruction_opcode.yaml.erb"
      dest_path = outdir / "inst_opcode" / "#{name}.yaml"

      erb = ERB.new(template_path.read, trim_mode: "-")
      erb.filename = template_path.to_s

      CreatedFile.new(path: dest_path, contents: erb.result(binding), next_steps: [])
    end


    sig { params(prompt: TTY::Prompt, copyright: String, outdir: Pathname).returns(CreatedFile) }
    def self.create_inst_type(prompt, copyright, outdir)
      name = prompt.ask \
        "What is the instruction type name? It should be a single letter (e.g., 'R')",
        modify: [:trim],
        required: true

      desc = prompt.ask \
        "What is a short description (e.g., 'R-type instructions have three 5-bit operands')\n",
        modify: [:trim],
        required: true

      length = prompt.select \
        "What is the instruction encoding length for #{name}-type instructions?",
        [16, 32]

      opcodes = []

      opcode_info = <<~INFO
        Next, we will specify opcode fields.

        An opcode field is a single _contiguous_ set of bits that hold fixed opcode bits.
        For example, R-type instructions have three opcodes: `funct7`, 'funct3' and 'opcode'.

        Press any key to continue.
      INFO
      TtyTools.display_box(prompt, "Opcodes", opcode_info)

      loop do
        opcode_name = prompt.ask \
          "What is the name of the #{(opcodes.size + 1).to_words(ordinal: true, remove_hyphen: true)} opcode field (e.g., `funct7`)?",
          modify: [:trim]

        opcode_location = prompt.ask \
          "What is the location of the '#{opcode_name}' field (e.g., '5', '14-12')?",
          validate: (proc do |loc|
            # must be a valid location, and if it is a range, msb must come first
            loc =~ /^[0-9]+(-[0-9]+)?$/ && \
              (loc.index("-").nil? || (loc.split("-")[0].to_i >= loc.split("-")[1].to_i))
          end)

        opcodes << OpcodeOrVariable.new(name: opcode_name, location: opcode_location)

        break unless prompt.yes? "Is there another opcode field?"
      end

      variables = []
      prompt.say "\nFinally, we will specify opcode variables (a.k.a. operands)."
      prompt.say "A variable field is a single _potentionally non-contiguous_ set of bits that change value from encoding to encoding (e.g., `rs1` in R-type)"

      loop do
        break unless prompt.yes? (variables.empty?) ? "Do you want to add a variable?" : "Is there another variable to add?"

        variable_name = prompt.ask \
          "What is the name of the #{(variables.size + 1).to_words(ordinal: true, remove_hyphen: true)} variable field (e.g., `rs1`)?",
          modify: [:trim]

        variable_location = T.let(nil, T.nilable(String))
        loop do
          variable_location = prompt.ask \
            "What is the location of the '#{variable_name}' variable (e.g., '5', '14-12', '31|7|30-25|11-8'. Type 'help' for more)"

          if variable_location == "help"
            location_help = <<~HELP
              Locations can be specified as:
                * A single digit, when the field is one bit wide
                  ex: 5
                  ex: 31
                * A range of digits separated by a dash ('-'), with the MSB first
                  ex: 14-12
                  ex: 24-20
                * A concatenated list of digits and/or ranges joined by a pipe ('|')
                  Used when the field is split in the encoding.
                  The bits of the field must be listed in order from MSB to LSB _of the field_ (not of the encoding)
                    ex: 31|7|30-25|11-8  # location of 12-bit imm in B-Type instructions;
                                         # imm[11] is at $encoding[31]
                                         # imm[10] is at $encoding[7]
                                         # imm[9:4] is at $encoding[30:25]
                                         # imm[3:0] is at $encoding[11:8]

                Press any key to continue
            HELP

            TtyTools.display_box(prompt, "Variable location", location_help)
          else
            break
          end
        end

        variables << OpcodeOrVariable.new(name: variable_name, location: T.must(variable_location))
      end

      template_path = Udb.gem_path / "lib" / "udb" / "templates" / "instruction_type.yaml.erb"
      dest_path = outdir / "inst_type" / "#{name}.yaml"

      erb = ERB.new(template_path.read, trim_mode: "-")
      erb.filename = template_path.to_s

      CreatedFile.new(path: dest_path, contents: erb.result(binding), next_steps: [])
    end

    sig { params(prompt: TTY::Prompt, copyright: String, outdir: Pathname, inst_type: T.nilable(String)).returns(CreatedFile) }
    def self.create_inst_var(prompt, copyright, outdir, inst_type)
      name = prompt.ask \
        "What is the instruction var name (e.g., 'xs1')?",
        modify: [:trim]

      inst_types =
        Dir[Udb.repo_root / "spec" / "std" / "isa" / "inst_type" / "*.yaml"].map do |f|
          next if !inst_type.nil? && inst_type != File.basename(f, ".yaml")
          { name: File.basename(f, ".yaml"), contents: YAML.load_file(f) }
        end.compact
      raise if inst_types.empty?

      opcode_fields = {}
      inst_types.each do |itype|
        itype[:contents]["variables"].each_key do |itype_var_name|
          opcode_fields["#{itype[:name]}:#{itype_var_name}"] =
            { type: itype, var: itype_var_name }
        end
      end

      opcode_field = prompt.select \
        "What opcode field does this variable correspond with?",
        opcode_fields.keys

      inst_type, inst_type_var = opcode_field.split(":")

      var_types =
        Dir[Udb.repo_root / "spec" / "std" / "isa" / "inst_var_type" / "*.yaml"].map do |f|
          { name: File.basename(f, ".yaml"), contents: YAML.load_file(f) }
        end
      var_type = prompt.select \
        "What is the variable type?",
        var_types.map { |t| t[:name] }

      display = prompt.ask \
        "How should this variable type be displayed in documentation such as instruction encoding diagrams?",
        default: name

      template_path = Udb.gem_path / "lib" / "udb" / "templates" / "instruction_var_type.yaml.erb"
      dest_path = outdir / "inst_var_type" / "#{name}.yaml"

      erb = ERB.new(template_path.read, trim_mode: "-")
      erb.filename = template_path.to_s

      CreatedFile.new(path: dest_path, contents: erb.result(binding), next_steps: [])
    end

    sig { params(prompt: TTY::Prompt, copyright: String, outdir: Pathname).returns(T::Array[CreatedFile]) }
    def self.create_inst_subtype(prompt, copyright, outdir)
      files = T.let([], T::Array[CreatedFile])

      types = Dir[Udb.repo_root / "spec" / "std" / "isa" / "inst_type" / "*.yaml"].map { |f| File.basename(f, ".yaml") }
      types << "Create new"
      type = prompt.select \
        "What instruction type does the new instruction subtype inherit from?",
        types,
        filter: true

      type_data =
        if type == "Create new"
          prompt.say "Ok. Let's get some information on the new instruction type"
          files << CreationActions.create_inst_type(prompt, copyright, outdir)
          type = T.must(files.last).path.basename(".yaml")
          prompt.say "That's all I need for the instruction type. Back to the subtype:\n\n"
          YAML.load(T.must(files.last).contents)
        else
          YAML.load_file(Udb.repo_root / "spec" / "std" / "isa" / "inst_type" / "#{type}.yaml")
        end

      name = T.let(nil, T.nilable(String))
      loop do
        name = prompt.ask \
          "What is the subtype name? It should begin with the type name and then a dash (e.g., #{type_data["name"]}-new): ",
          required: true,
          modify: [:trim],
          validate: /^#{type_data["name"]}-.*$/
        if File.exist?(outdir / "inst_subtype" / "#{type_data["name"]}" / "#{name}.yaml")
          prompt.say "Instruction subtype '#{name}' already exists. Please select another name."
        else
          break
        end
      end

      inst_vars = Dir[Udb.repo_root / "spec" / "std" / "isa" / "inst_var" / "*.yaml"].map do |f|
        var_name = File.basename(f, ".yaml")
        var_data = YAML.load_file(f)
        ["#{var_name.ljust(10)} (#{var_data["long_name"]})", var_name]
      end.to_h
      inst_vars["Create new kind of variable"] = "Create new"
      var_type_map = {}
      type_data["variables"].each do |var_name, var_data|
        var_type = prompt.select \
          "What kind of variable is the '#{var_name}' slot for subtype #{name}?",
          inst_vars,
          filter: true

        if var_type == "Create new"
          prompt.say "Ok. Let's get some information on the new instruction variable type"
          files << CreationActions.create_inst_var(prompt, copyright, outdir, type_data["name"])
          var_type = T.must(files.last).path.basename(".yaml")
          prompt.say "That's all I need for the instruction variable type. Back to the subtype variable.\n\n"
        end

        var_type_map[var_name] = var_type
      end

      template_path = Udb.gem_path / "lib" / "udb" / "templates" / "instruction_subtype.yaml.erb"
      dest_path = outdir / "inst_subtype" / "#{type}" / "#{name}.yaml"

      FileUtils.mkdir_p dest_path.dirname

      erb = ERB.new(template_path.read, trim_mode: "-")
      erb.filename = template_path.to_s

      files << CreatedFile.new(path: dest_path, contents: erb.result(binding), next_steps: [])
    end
  end

  module TtyTools
    extend T::Sig

    sig { params(prompt: TTY::Prompt, title: String, text: String).void }
    def self.display_box(prompt, title, text)
      unless ENV["SKIP_INFO"]
        print TTY::Box.frame(text, padding: 1, title: { top_left: title }, style: { fg: :white, bg: :blue })
        prompt.keypress
        lines = text.lines.size
        print prompt.clear_lines(lines + 6)
      end
    end
  end

  module CliCommands
    class Create < SubCommandBase
      extend T::Sig

      desc "extension", "Create a new extension YAML file"
      long_desc <<~DESC
        Creates a new extension file and populates fields based on interactive questions.
      DESC
      method_option :dry_run, aliases: "-n", type: :string, lazy_default: "/dev/null", desc: "Write files to directory dry_run instead of the UDB databse"
      sig { void }
      def extension
        prompt = TTY::Prompt.new

        copyright = CreationActions.get_copyright(prompt)

        outdir = options[:dry_run].nil? ? Udb.repo_root / "spec" / "std" / "isa" : Pathname.new(options[:dry_run])

        file = CreationActions.create_extension(prompt, copyright, outdir)

        File.write file.path, file.contents

        puts
        puts "New file written to #{file.path}"
      end

      desc "instruction_type", "Create a new instruction type (e.g., R-type)"
      long_desc <<~DESC
        Creates a new instruction type and populates fields based on interactive questions.
      DESC
      method_option :dry_run, aliases: "-n", type: :string, lazy_default: "/dev/null", desc: "Write files to directory dry_run instead of the UDB databse"
      sig { void }
      def instruction_type
        outdir = options[:dry_run].nil? ? Udb.repo_root / "spec" / "std" / "isa" : Pathname.new(options[:dry_run])
        input = self.options.key?("input") ? self.options.fetch("input") : $stdin
        output = self.options.key?("output") ? self.options.fetch("output") : $stdout
        prompt = TTY::Prompt.new(input:, output:, env: { "TTY_TEST" => true })

        intro_text = <<~INTRO
          Instruction types are generic formats that instructions follow.
          They are described in the RISC-V ISA Manual as R-type, I-type, etc.

          In UDB, an instruction type identifies where fixed opcodes and variable operands are located.

          An instruction _sub type_ further refines encoding fields by adding semantic information
          to operands. For example, that type field 'rd' is an X destination register.

          Press any key to continue
        INTRO
        print prompt.cursor.clear_screen
        print prompt.cursor.move_to
        TtyTools.display_box(prompt, "Intro", intro_text)

        copyright = CreationActions.get_copyright(prompt)

        file = CreationActions.create_inst_type(prompt, copyright, outdir)

        File.write file.path, file.contents

        prompt.say "\nBased on your answers, I've created the following file:"
        prompt.say "   #{file.path}"

        unless file.next_steps.empty?
          prompt.say
          prompt.say "Next steps include:"
          file.next_steps.each do |step|
            prompt.say "  - #{step}"
          end
        end
      end

      desc "instruction", "Create a new instruction template"
      long_desc <<~DESC
        Creates a new instruction file and populates fields based on interactive questions.
      DESC
      method_option :dry_run, aliases: "-n", type: :string, lazy_default: "/dev/null", desc: "Write files to directory dry_run instead of the UDB databse"
      sig { void }
      def instruction
        outdir = options[:dry_run].nil? ? Udb.repo_root / "spec" / "std" / "isa" : Pathname.new(options[:dry_run])
        input = self.options.key?("input") ? self.options.fetch("input") : $stdin
        output = self.options.key?("output") ? self.options.fetch("output") : $stdout
        prompt = TTY::Prompt.new(input:, output:, env: { "TTY_TEST" => true })
        next_steps = T.let([], T::Array[String])

        intro_text = <<~INTRO
          To create an instruction, you will provide attributes such as the defining extension,
          encoding format, access rights, etc.

          Some of the attributes, like extensions, are top-level UDB objects themselves.
          If you need to create any of them along the way, the prompts will guide you.

          Press any key to continue
        INTRO
        print prompt.cursor.clear_screen
        print prompt.cursor.move_to
        TtyTools.display_box(prompt, "Intro", intro_text)

        files = T.let([], T::Array[CreationActions::CreatedFile])
        schema_defs = CreationActions.schema_defs

        copyright = CreationActions.get_copyright(prompt)


        mnemonic = prompt.ask \
          "What is the instruction mnemonic?",
          required: true,
          validate: /#{schema_defs.fetch("$defs").fetch("inst_mnemonic").fetch("pattern")}/

        prompt.clear_lines 2

        extension_list = ["Create new"]
        Dir.glob((Udb.repo_root / "spec" / "std" / "isa" / "ext" / "*.yaml").to_s) do |f|
          extension_list << File.basename(f, ".yaml")
        end

        ext_name = prompt.select \
          "What extension defines this instruction? If more than one, or if it is dependent on a parameter, you can edit the template later.",
          extension_list,
          filter: true

        if ext_name == "Create new"
          files.append CreationActions.create_extension(prompt, copyright, outdir)
          ext_name = T.must(files.last).path.basename(".yaml")
        end

        long_name = prompt.ask \
          "What is a short description of the instruction? (e.g., \"Unsigned add\", \"Shift logical left immediate\", ...)",
          required: true

        access_options = ["always", "sometimes", "never"]
        u_access = prompt.select("When is this instruction accessible in U mode?", access_options, filter: true)
        s_access = prompt.select("When is this instruction accessible in (H)S mode?", access_options, filter: true)
        vs_access = prompt.select("When is this instruction accessible in VS mode?", access_options, filter: true)
        vu_access = prompt.select("When is this instruction accessible in VU mode?", access_options, filter: true)

        data_independent_timing = prompt.yes?("Is this instruction required to have data-independent timing when extension Zkt and/or Zvkt is used?")

        subtypes = { "Create new" => "Create new" }
        Dir.glob((Udb.repo_root / "spec" / "**" / "isa" / "inst_subtype" / "**" / "*.yaml").to_s) do |f|
          subtype_contents = YAML.load_file(f)
          subtype_name = subtype_contents["name"]
          subtypes["#{subtype_name.ljust(10)} (#{subtype_contents["long_name"]})"] = subtype_name
        end

        type_subtype_info = <<~INFO
          Next, you will identify the instruction _subtype_, which points to an instruction _type_.

          An instruction _type_ represents the general structure of an instruction encoding:
            - where fixed _opcode_ fields occur (e.g., OP-32 in bits 6:0)
            - where variable _operand_ fields occur (e.g., rd in bits 11:7).

          An instruction _sub type_ is a child of an instruction _type_ that attaches semantic
          information to the variable operands (e.g., rd is an X destination register).

          There are few instruction types (e.g., I, R, U, B, S)
          but many instruction sub types (e.g., R-x, R-f, R-x-i)

          Press any key to continue
        INFO

        TtyTools.display_box(prompt, "Subtypes", type_subtype_info)

        subtype = prompt.select \
          "What is the subtype of the instruction format?",
          subtypes,
          filter: true

        type_contents = nil
        subtype_contents = nil
        if subtype == "Create new"
          files.concat CreationActions.create_inst_subtype(prompt, copyright, outdir)
          subtype_file = T.must(files.find { |f| f.path.to_s =~ /inst_subtype/ })
          subtype_contents = YAML.load(subtype_file.contents)
          type_ref = subtype_contents.fetch("data").fetch("type").fetch("$ref")
          $stderr.puts type_ref
          type_paths = Dir[Udb.repo_root / "spec" / "**" / type_ref.gsub("#", "")]
          if type_paths.empty?
            type_file = T.must(files.find { |f| f.path.to_s =~ /inst_type/ })
            type_contents = YAML.load(type_file.contents)
          else
            type_contents = YAML.load_file(type_paths.fetch(0))
          end
        else
          subtype_paths = Dir[Udb.repo_root / "spec" / "std" / "isa" / "inst_subtype" / "*" / "#{subtype}.yaml"]
          raise "can't find subtype" unless subtype_paths.size == 1
          subtype_contents = YAML.load_file(subtype_paths.fetch(0))
          type_ref = subtype_contents.fetch("data").fetch("type").fetch("$ref")
          type_paths = Dir[Udb.repo_root / "spec" / "std" / "isa" / type_ref.gsub("#", "")]
          if type_paths.empty?
            raise "Can't find type path"
          else
            type_contents = YAML.load_file(type_paths.fetch(0))
          end
        end
        type_name = type_contents["name"]
        subtype_name = subtype_contents["name"]

        opcode_info = <<~INFO
          The #{subtype_name} subtype has #{type_contents.fetch("opcodes").size} opcodes and #{subtype_contents.fetch("data").fetch("variables").size} variables.

          Everything needed for variables is provided by the subtype.

          For opcodes, you will provide a _display name_ for documentation (such as encoding diagrams)
          and a specific _value_ for the instruction.

          We distinguish between two classes of opcodes:
            - Those that are shared by multiple instructions (e.g., OP, OP-32 in encoding[6:0])
            - Those that are specific to an instruction (e.g., ADDI in encoding[14:12])

          Common opcodes become their own object in the database and referenced by instructions.
          The specific opcodes are defined directly in the instruction, and do not elevate to a
          top-level database object.

          Press any key to continue
        INFO

        TtyTools.display_box(prompt, "Opcodes", opcode_info)

        opcodes = {}
        type_contents.fetch("opcodes").each do |opcode_name, opcode_data|
          opcode_type = prompt.select \
            "Is opcode '#{opcode_name}' a common/shared value among instructions (e.g., OP-32), or is it unique to this instrction (e.g., ADDI)?",
            ["common/shared", "unique"],
            filter: true

          if opcode_type == "common/shared"
            matching_opcodes = ["Create a new common opcode"]
            Dir.glob((Udb.repo_root / "spec" / "std" / "isa" / "inst_opcode" / "*.yaml").to_s) do |opcode_file|
              common_opcode_data = YAML.load_file(opcode_file)

              if opcode_data["location"] == common_opcode_data["data"]["location"]
                matching_opcodes << common_opcode_data["name"]
              end
            end
            op = prompt.select \
              "What is the opcode?",
              matching_opcodes,
              filter: true
            if op == "Create a new common opcode"
              files.append CreationActions.create_inst_opcode(prompt, copyright, outdir, opcode_data["location"])
              op = T.must(files.last).path.basename(".yaml")
            end
            opcodes[opcode_name] = { ref: op }
          else
            display_name = prompt.ask \
              "How should opcode '#{opcode_name}' be displayed in documentation (e.g., #{mnemonic.upcase})?",
              required: true

            value = prompt.ask \
              "What is the value of '#{opcode_name}' for '#{mnemonic}', as a binary value (e.g., 001101)? If you don't know, just hit enter.",
              validate: /^[01]*$/

            if value.nil?
              value = "0 # TODO: Replace with actual value"
              next_steps << "Fill in the actual value of opcode '#{opcode_name}'"
            end

            opcodes[opcode_name] = { display_name:, value: }
          end
        end

        template_path = Udb.gem_path / "lib" / "udb" / "templates" / "instruction.yaml.erb"
        dest_path =
          outdir / "inst" / ext_name / "#{mnemonic}.yaml"

        erb = ERB.new(template_path.read, trim_mode: "-")
        erb.filename = template_path.to_s

        files << CreationActions::CreatedFile.new(path: dest_path, contents: erb.result(binding), next_steps:)

        files.each do |f|
          FileUtils.mkdir_p f.path.dirname
          File.write f.path, f.contents
        end

        prompt.ok "\nBased on your answers, I've created the following file(s):"
        files.each do |f|
          prompt.say "   - #{f.path}"
        end

        unless files.all? { |f| f.next_steps.empty? }
          prompt.say "\n\n"
          prompt.warn "NEXT STEPS"
          files.each do |f|
            next if f.next_steps.empty?
            prompt.say "  In #{f.path}:"
            f.next_steps.each do |step|
              prompt.say "    - #{step}"
            end
          end
        end
      end
    end
  end
end

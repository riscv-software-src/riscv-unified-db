#!/usr/bin/env ruby

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen-string-literal: true

require "udb/cli/sub_command_base"

module Udb
  module CreationActions
    extend T::Sig

    class CreatedFile < T::Struct
      const :path, Pathname
      const :contents, String
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
      copyright = prompt.ask \
        "Lets get this out of the way: what copyright do you want to assign to newly created files?",
        default: "Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.",
        required: true,
        modify: [:trim]

      prompt.say "Great. The license defaults to BSD-3-Clear. Other licenses will likely not be accepted upstream.\n\n"

      copyright
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

      CreatedFile.new(path: dest_path, contents: erb.result(binding))
    end


    sig { params(prompt: TTY::Prompt, copyright: String).returns(CreatedFile) }
    def self.create_inst_type(prompt, copyright)
      name = prompt.ask \
        "What is the instruction type name (e.g., 'R')?",
        modify: [:trim]

      desc = prompt.ask \
        "What is a short description (e.g., 'R-type instructions have three 5-bit operands')\n",
        modify: [:trim]

      length = prompt.select \
        "What is the instruction encoding length for #{name}-type instructions?",
        [16, 32]

      opcodes = []
      prompt.say "\nNext, we will specify opcode fields."
      prompt.say "An opcode field is a single _contiguous_ set of bits that hold fixed opcode bits (e.g., `funct7` in R-type)"
      loop do
        opcode_name = prompt.ask \
          "What is the name of the #{(opcodes.size + 1).to_words(ordinal: true, remove_hyphen: true)} opcode field (e.g., `funct7`)?",
          modify: [:trim]

        opcode_location = prompt.ask \
          "What is the location of the '#{opcode_name}' field (e.g., '5', '14-12')?",
          validate: proc do |loc|
            # must be a valid location, and if it is a range, msb must come first
            loc =~ /#{schema_defs["$defs"]["field_location"]}/ && \
              (loc.index("-").nil? || (loc.split("-")[0].to_i >= loc.split("-")[1].to_i))
          end

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

        variable_location = prompt.ask \
          "What is the location of the '#{variable_name}' variable (e.g., '5', '14-12', '31|7|30-25|11-8')"

        variables << OpcodeOrVariable.new(name: variable_name, location: variable_location)
      end

      template_path = Udb.gem_path / "lib" / "udb" / "templates" / "instruction_type.yaml.erb"
      dest_path =
        if type == "standard"
          Udb.repo_root / "spec" / "std" / "isa" / "inst_type" / "#{name}.yaml"
        else
          raise "TODO: custom extension"
        end

      erb = ERB.new(template_path.read, trim_mode: "-")
      erb.filename = template_path.to_s

      CreatedFile.new(path: dest_path, contents: erb.result(binding))
    end

    sig { params(prompt: TTY::Prompt, copyright: String, outdir: Pathname).returns(CreatedFile) }
    def self.create_inst_var(prompt, copyright, outdir)
      name = prompt.ask \
        "What is the instruction var name (e.g., 'xs1')?",
        modify: [:trim]

      inst_types =
        Dir[Udb.repo_root / "spec" / "std" / "isa" / "inst_type" / "*.yaml"].map do |f|
          { name: File.basename(f, ".yaml"), content: YAML.load_file(f) }
        end

      opcode_fields = {}
      inst_types.each do |itype|
        itype[:content]["variables"].each_key do |itype_var_name|
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
          { name: File.basename(f, ".yaml"), content: YAML.load_file(f) }
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

      CreatedFile.new(path: dest_path, contents: erb.result(binding))
    end

    sig { params(prompt: TTY::Prompt, copyright: String, outdir: Pathname).returns(T::Array[CreatedFile]) }
    def self.create_inst_subtype(prompt, copyright, outdir)
      files = T.let([], T::Array[CreatedFile])

      prompt.say <<~INFO
        [INFO]
          An instruction _type_ represents the general structure of an instruction encoding.
          The type identifies where fixed _opcode_ fields occur (e.g., OP-32 in bits 6:0)
          and where variable _operand_ fields occur (e.g., rd in bits 11:7).

          Instruction _sub types_ refine instruction types by attaching semantic information to the
          variable operand fields (e.g., field rd is an X destination register).

          There are few instruction types (e.g., I, R, U, B, S)
          but many instruction sub types (e.g., R-x, R-f, R-x-i)

      INFO

      prompt.say "With that in mind, let's get started.\n"

      types = Dir[Udb.repo_root / "spec" / "std" / "isa" / "inst_type" / "*.yaml"].map { |f| File.basename(f, ".yaml") }
      types << "Create new"
      type = prompt.select \
        "What instruction type does the new instruction subtype inherit from?",
        types,
        filter: true

      type_data =
        if type == "Create new"
          prompt.say "Ok. Let's get some information on the new instruction type"
          files << CreationActions.create_inst_type(prompt, copyright)
          type = files.last.path.basename(".yaml")
          prompt.say "That's all I need for the instruction type. Back to the subtype:\n\n"
          YAML.load(files.last.content)
        else
          YAML.load_file(Udb.repo_root / "spec" / "std" / "isa" / "inst_type" / "#{type}.yaml")
        end

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

      prompt.say "[INFO] Instruction subtypes use the instruction type for opcode fields, so we only need information on the variables.\n"

      inst_vars = Dir[Udb.repo_root / "spec" / "std" / "isa" / "inst_var" / "*.yaml"].map do |f|
        var_name = File.basename(f, ".yaml")
        var_data = YAML.load_file(f)
        [var_data["long_name"], var_name]
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
          files << CreationActions.create_inst_var(prompt, copyright, outdir)
          var_type = files.last.path.basename(".yaml")
          prompt.say "That's all I need for the instruction variable type. Back to the subtype variable.\n\n"
        end

        var_type_map[var_name] = var_type
      end

      template_path = Udb.gem_path / "lib" / "udb" / "templates" / "instruction_subtype.yaml.erb"
      dest_path = outdir / "inst_subtype" / "#{type}" / "#{name}.yaml"

      FileUtils.mkdir_p dest_path.dirname

      erb = ERB.new(template_path.read, trim_mode: "-")
      erb.filename = template_path.to_s

      files << CreatedFile.new(path: dest_path, contents: erb.result(binding))
    end
  end

  module CliCommands
    class Create < SubCommandBase
      extend T::Sig

      desc "extension", "Create a new extension YAML file"
      long_desc <<~DESC
        Creates a new extension file and populates fields based on interactive questions.
      DESC
      sig { void }
      def extension
        prompt = TTY::Prompt.new

        copyright = CreationActions.get_copyright(prompt)

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
            key(:people).values do
              key(:name).ask("Full name?", required: true, modify: [:trim])

              key(:email).ask("Email?", validate: :email, modify: [:trim])

              key(:company).ask("Company?", modify: [:trim])
            end
            break unless prompt.yes?("Add another contributor?")
          end
        end

        template_path = Udb.gem_path / "lib" / "udb" / "templates" / "extension.yaml.erb"
        dest_path =
          if type == "standard"
            Udb.repo_root / "spec" / "std" / "isa" / "ext" / "#{name}.yaml"
          else
            raise "TODO: custom extension"
          end

        erb = ERB.new(template_path.read, trim_mode: "-")
        erb.filename = template_path.to_s

        File.write dest_path, erb.result(binding)

        puts
        puts "New file written to #{dest_path}"
      end

      desc "instruction", "Create a new instruction template"
      long_desc <<~DESC
        Creates a new instruction file and populates fields based on interactive questions.
      DESC
      method_option :dry_run, aliases: "-n", type: :string, lazy_default: "/dev/null", desc: "Write files to directory dry_run instead of the UDB databse"
      sig { void }
      def instruction
        outdir = options[:dry_run].nil? ? Udb.repo_root / "spec" / "std" / "isa" : Pathname.new(options[:dry_run])
        $stderr.puts "outdir = #{outdir}"
        input = self.options.key?("input") ? self.options.fetch("input") : $stdin
        output = self.options.key?("output") ? self.options.fetch("output") : $stdout
        prompt = TTY::Prompt.new(input:, output:, env: { "TTY_TEST" => true })

        files = T.let([], T::Array[CreationActions::CreatedFile])
        schema_defs = CreationActions.schema_defs

        copyright = CreationActions.get_copyright(prompt)

        $stderr.puts copyright

        mnemonic = prompt.ask \
          "What is the instruction mnemonic?",
          required: true,
          validate: /#{schema_defs.fetch("$defs").fetch("inst_mnemonic").fetch("pattern")}/

        ext_name = prompt.ask \
          "What extension defines this instruction? If more than one, or if it is dependent on a parameter, you can edit the template later." do |q|
            q.validate do |name|
              (name =~ %r{#{schema_defs["$defs"]["standard_extension_name"]["pattern"]}} || name =~ %r{#{schema_defs["$defs"]["custom_extension_name"]["pattern"]}}) && \
                (Dir[Udb.repo_root / "spec" / "**" / "ext" / "#{name}.yaml"].size == 1)
            end
            q.messages[:valid?] = "Invalid extension '%{value}'. The extension must be a valid extension name and exist in the database"
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

        subtypes = Dir[Udb.repo_root / "spec" / "**" / "isa" / "inst_subtype" / "**" / "*.yaml"].map { |f| File.basename(f, ".yaml") }
        subtypes << "Create new"

        subtype = prompt.select \
          "What is the subtype of the instruction format?",
          subtypes,
          filter: true

        type_contents = nil
        subtype_contents = nil
        if subtype == "Create new"
          files.concat CreationActions.create_inst_subtype(prompt, copyright, outdir)
          subtype_file = files.find { |f| f.path.to_s =~ /inst_subtype/ }
          subtype_contents = YAML.load(subtype_file.contents)
          type_ref = subtype_contents.fetch("data").fetch("type").fetch("$ref")
          $stderr.puts type_ref
          type_paths = Dir[Udb.repo_root / "spec" / "**" / type_ref.gsub("#", "")]
          if type_paths.empty?
            type_file = files.find { |f| f.path.to_s =~ /inst_type/ }
            type_contents = YAML.load(type_file.contents)
          else
            type_contents = YAML.load_file(type_paths[0])
          end
        else
          subtype_paths = Dir[Udb.repo_root / "spec" / "std" / "isa" / "inst_subtype" / "*" / "#{subtype}.yaml"]
          raise "can't find subtype" unless subtype_paths.size == 1
          subtype_contents = YAML.load_file(subtype_paths[0])
          type_ref = subtype_contents.fetch("data").fetch("type").fetch("$ref")
          type_paths = Dir[Udb.repo_root / "spec" / "std" / "isa" / type_ref.gsub("#", "")]
          if type_paths.empty?
            raise "Can't find type path"
          else
            type_contents = YAML.load_file(type_paths[0])
          end
        end
        type_name = type_contents["name"]
        subtype_name = type_contents["name"]

        opcodes = {}
        $stderr.puts type_name
        $stderr.puts type_contents.fetch("opcodes")
        type_contents.fetch("opcodes").each do |opcode_name, opcode_data|
          opcode_type = prompt.select \
            "Is opcode '#{opcode_name}' a common/shared value among instructions (e.g., OP-32), or is it unique to this instrction (e.g., ADDI)?",
            ["common/shared", "unique"],
            filter: true

          if opcode_type == "common/shared"
            matching_opcodes = ["Create a new common opcode"]
            Dir.glob(Udb.repo_root / "spec" / "std" / "isa" / "inst_opcode" / "*.yaml") do |opcode_file|
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
              op = files.last.path.basename(".yaml")
            end
            opcodes[opcode_name] = { ref: op }
          else
            display_name = prompt.ask \
              "How should opcode '#{opcode_name}' be displayed in documentation (e.g., #{mnemonic.upcase})?",
              required: true

            value = prompt.ask \
              "What is the value of '#{opcode_name}' for '#{mnemonic}', as a binary value (e.g., 001101)? If you don't know, just hit enter.",
              validate: /^[01]*$/

            opcodes[opcode_name] = { display_name:, value: }
          end
        end

        template_path = Udb.gem_path / "lib" / "udb" / "templates" / "instruction.yaml.erb"
        dest_path =
          outdir / "inst" / ext_name / "#{mnemonic}.yaml"

        erb = ERB.new(template_path.read, trim_mode: "-")
        erb.filename = template_path.to_s

        files << CreationActions::CreatedFile.new(path: dest_path, contents: erb.result(binding))

        files.each do |f|
          FileUtils.mkdir_p f.path.dirname
          File.write f.path, f.contents
        end

        prompt.say "\nBased on your answers, I've created the following file(s):"
        files.each do |f|
          prompt.say "   #{f.path}"
        end
      end
    end
  end
end

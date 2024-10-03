# frozen_string_literal: true

require_relative "obj"


# model of a specific instruction in a specific base (RV32/RV64)
class Instruction < ArchDefObject
  def ==(other)
    if other.is_a?(Instruction)
      name == other.name
    else
      raise ArgumentError, "Instruction is comparable to a #{other.class.name}"
    end
  end

  # @return [Hash<String, String>] Hash of access permissions for each mode. The key is the lowercase name of a privilege mode, and the value is one of ['never', 'sometimes', 'always']
  def access
    @data["access"]
  end

  # @return [String] Details of the access restrictions
  # @return [nil] if no details are available
  def access_detail
    @data["access_detail"]
  end

  # @return [Integer] XLEN that must be effective for instruction to exist
  # @return [nil] if instruction exists in all XLENs
  def base
    @data["base"]
  end

  # @return [Boolean] Whether or not the instruction must have data-independent timing when Zkt is enabled.
  def data_independent_timing? = @data["data_independent_timing"]

  # @param xlen [Integer] 32 or 64, the target xlen
  # @return [Boolean] whethen or not instruction is defined in base +xlen+
  def defined_in_base?(xlen)
    base == xlen
  end

  # @return [String] Assembly format
  def assembly
    @data["assembly"]
  end

  # @return [Array<ExtensionRequirement>] List of extensions requirements (in addition to one returned by {#defined_by}) that must be met for the instruction to exist
  def extension_requirements
    return [] unless @data.key?("requires")

    @extension_requirements = []
    if @data["requires"].is_a?(Array)
      # could be either a single extension with requirement, or a list of requirements
      if extension_requirement?(@data["requires"][0])
        @extension_requirements << to_extension_requirement(@data["requires"][0])
      else
        # this is a list
        @data["requires"].each do |r|
          @extension_requirements << to_extension_requirement(r)
        end
      end
    else
      @extension_requirements << to_extension_requirement(@data["requires"])
    end

    @extension_requirements
  end

  def fill_symtab(global_symtab, effective_xlen)
    symtab = global_symtab.deep_clone
    symtab.push
    symtab.add(
      "__instruction_encoding_size",
      Idl::Var.new("__instruction_encoding_size", Idl::Type.new(:bits, width: encoding_width.bit_length), encoding_width)
    )
    symtab.add(
      "__effective_xlen",
      Idl::Var.new("__effective_xlen", Idl::Type.new(:bits, width: 7), effective_xlen)
    )
    @encodings[effective_xlen].decode_variables.each do |d|
      qualifiers = []
      qualifiers << :signed if d.sext?
      width = d.size

      var = Idl::Var.new(d.name, Idl::Type.new(:bits, qualifiers:, width:), decode_var: true)
      symtab.add(d.name, var)
    end

    symtab
  end
  private :fill_symtab

  # @param global_symtab [Idl::SymbolTable] Symbol table with global scope populated and a configuration loaded
  # @return [Idl::FunctionBodyAst] A pruned abstract syntax tree
  def pruned_operation_ast(global_symtab, effective_xlen)
    @pruned_asts ||= {}

    arch_def = global_symtab.archdef

    pruned_ast = @pruned_asts[arch_def.name]
    return pruned_ast unless pruned_ast.nil?

    return nil unless @data.key?("operation()")

    type_checked_ast = type_checked_operation_ast(arch_def.idl_compiler, global_symtab, effective_xlen)
    pruned_ast = type_checked_ast.prune(fill_symtab(global_symtab, effective_xlen))
    arch_def.idl_compiler.type_check(
      pruned_ast,
      fill_symtab(global_symtab, effective_xlen),
      "#{name}.operation() (pruned)"
    )

    @pruned_asts[arch_def.name] = pruned_ast
  end

  # @param symtab [Idl::SymbolTable] Symbol table with global scope populated
  # @param effective_xlen [Integer] The effective XLEN to evaluate against
  # @return [Array<Idl::FunctionBodyAst>] List of all functions that can be reached from operation()
  def reachable_functions(symtab, effective_xlen)
    if @data["operation()"].nil?
      []
    else
      # RubyProf.start
      pruned_operation_ast(symtab, effective_xlen).reachable_functions(fill_symtab(symtab, effective_xlen))
      # result = RubyProf.stop
      # RubyProf::FlatPrinter.new(result).print($stdout)
      # exit
    end
  end

  # @param symtab [Idl::SymbolTable] Symbol table with global scope populated
  # @param effective_xlen [Integer] Effective XLEN to evaluate against
  # @return [Array<Integer>] List of all exceptions that can be reached from operation()
  def reachable_exceptions(symtab, effective_xlen)
    if @data["operation()"].nil?
      []
    else
      pruned_operation_ast(symtab).reachable_exceptions(fill_symtab(symtab, effective_xlen)).uniq
    end
  end

  # @param symtab [Idl::SymbolTable] Symbol table with global scope populated
  # @param effective_xlen [Integer] Effective XLEN to evaluate against. If nil, evaluate against all valid XLENs
  # @return [Array<Integer>] List of all exceptions that can be reached from operation()
  def reachable_exceptions_str(symtab, effective_xlen=nil)
    if @data["operation()"].nil?
      []
    else
      # RubyProf.start
      etype = symtab.get("ExceptionCode")
      if effective_xlen.nil?
        if symtab.archdef.multi_xlen?
          if base.nil?
            (
              pruned_operation_ast(symtab, 32).reachable_exceptions(fill_symtab(symtab, 32)).uniq.map { |code|
                etype.element_name(code)
              } +
              pruned_operation_ast(symtab, 64).reachable_exceptions(fill_symtab(symtab, 64)).uniq.map { |code|
                etype.element_name(code)
              }
            ).uniq
          else
            pruned_operation_ast(symtab, base).reachable_exceptions(fill_symtab(symtab, base)).uniq.map { |code|
              etype.element_name(code)
            }
          end
        else
          effective_xlen = symtab.archdef.mxlen
          pruned_operation_ast(symtab, effective_xlen).reachable_exceptions(fill_symtab(symtab, effective_xlen)).uniq.map { |code|
            etype.element_name(code)
          }
        end
      else
        pruned_operation_ast(symtab, effective_xlen).reachable_exceptions(fill_symtab(symtab, effective_xlen)).uniq.map { |code|
          etype.element_name(code)
        }
      end
      # result = RubyProf.stop
      # RubyProf::FlatPrinter.new(result).print(STDOUT)
    end
  end

  # @return [ArchDef] The architecture definition
  attr_reader :arch_def

  def initialize(data, arch_def)
    super(data)
    @arch_def = arch_def
  end

  # represents a single contiguous instruction encoding field
  # Multiple EncodingFields may make up a single DecodeField, e.g., when an immediate
  # is split across multiple locations
  class EncodingField
    # name, which corresponds to a name used in riscv_opcodes
    attr_reader :name

    # range in the encoding
    attr_reader :range

    def initialize(name, range, pretty = nil)
      @name = name
      @range = range
      @pretty = pretty
    end

    # is this encoding field a fixed opcode?
    def opcode?
      name.match?(/^[01]+$/)
    end


    def eql?(other)
      @name == other.name && @range == other.range
    end

    def hash
      [@name, @range].hash
    end

    def pretty_to_s
      return @pretty unless @pretty.nil?

      @name
    end

    def size
      @range.size
    end
  end
  
  # decode field constructions from YAML file, rather than riscv-opcodes
  # eventually, we will move so that all instructions use the YAML file,
  class DecodeVariable
    # the name of the field
    attr_reader :name

    # alias of this field, or nil if none
    #
    # used, e.g., when a field reprsents more than one variable (like rs1/rd for destructive instructions)
    attr_reader :alias

    # amount the field is left shifted before use, or nil is there is no left shift
    #
    # For example, if the field is offset[5:3], left_shift is 3
    attr_reader :left_shift

    # @return [Array<Integer>] Specific values that are prohibited for this variable
    attr_reader :excludes

    # @return [String] Name, along with any != constraints,
    # @example
    #   pretty_name #=> "rd != 0"
    #   pretty_name #=> "rd != {0,2}"
    def pretty_name
      if excludes.empty?
        name
      elsif excludes.size == 1
        "#{name} != #{excludes[0]}"
      else
        "#{name} != {#{excludes[0].join(',')}}"
      end
    end

    def extract_location(location)
      @encoding_fields = []

      if location.is_a?(Integer)
        @encoding_fields << EncodingField.new("", location..location)
        return
      end

      location_string = location
      parts = location_string.split("|")
      parts.each do |part|
        if part =~ /^([0-9]+)$/
          bit = ::Regexp.last_match(1)
          @encoding_fields << EncodingField.new("", bit.to_i..bit.to_i)
        elsif part =~ /^([0-9]+)-([0-9]+)$/
          msb = ::Regexp.last_match(1)
          lsb = ::Regexp.last_match(2)
          raise "range must be specified 'msb-lsb'" unless msb.to_i >= lsb.to_i

          @encoding_fields << EncodingField.new("", lsb.to_i..msb.to_i)
        else
          raise "location format error"
        end
      end
    end

    def inst_pos_to_var_pos
      s = size
      map = Array.new(32, nil)
      @encoding_fields.each do |ef|
        ef.range.to_a.reverse.each do |ef_i|
          raise "unexpected" if s <= 0

          map[ef_i] = s - 1
          s -= 1
        end
      end
      map
    end

    # given a range of the instruction, return a string representing the bits of the field the range
    # represents
    def inst_range_to_var_range(r)
      var_bits = inst_pos_to_var_pos

      raise "?" if var_bits[r.last].nil?
      parts = [var_bits[r.last]..var_bits[r.last]]
      r.to_a.reverse[1..].each do |i|
        if var_bits[i] == (parts.last.min - 1)
          raise "??" if parts.last.max.nil?
          parts[-1] = var_bits[i]..parts.last.max
        else
          parts << Range.new(var_bits[i], var_bits[i])
        end
      end

      parts.map { |p| p.size == 1 ? p.first.to_s : "#{p.last}:#{p.first}"}.join("|")
    end
    private :inst_range_to_var_range

    # array of constituent encoding fields
    def grouped_encoding_fields
      sorted_encoding_fields = @encoding_fields.sort { |a, b| b.range.last <=> a.range.last }
      # need to group encoding_fields if they are consecutive
      grouped_fields = [sorted_encoding_fields[0].range]
      sorted_encoding_fields[1..].each do |ef|
        if (ef.range.last + 1) == grouped_fields.last.first
          grouped_fields[-1] = (ef.range.first..grouped_fields.last.last)
        else
          grouped_fields << ef.range
        end
      end
      if grouped_fields.size == 1
        if grouped_fields.last.size == size
          [EncodingField.new(pretty_name, grouped_fields[0])]
        else
          [EncodingField.new("#{pretty_name}[#{inst_range_to_var_range(grouped_fields[0])}]", grouped_fields[0])]
        end
      else
        grouped_fields.map do |f|
          EncodingField.new("#{pretty_name}[#{inst_range_to_var_range(f)}]", f)
        end
      end
    end

    def initialize(inst, field_data)
      @inst = inst
      @name = field_data["name"]
      @left_shift = field_data["left_shift"].nil? ? 0 : field_data["left_shift"]
      @sext = field_data["sign_extend"].nil? ? false : field_data["sign_extend"]
      @alias = field_data["alias"].nil? ? nil : field_data["alias"]
      extract_location(field_data["location"])
      @excludes =
        if field_data.key?("not")
          if field_data["not"].is_a?(Array)
            field_data["not"]
          else
            [field_data["not"]]
          end
        else
          []
        end
      @decode_variable =
        if @alias.nil?
          name
        else
          @decode_variable = [name, @alias]
        end
    end

    def eql?(other)
      @name.eql?(other.name)
    end

    def hash
      @name.hash
    end

    # returns true if the field is encoded across more than one groups of bits
    def split?
      @encoding_fields.size > 1
    end

    # returns bits of the encoding that make up the field, as an array
    #   Each item of the array is either:
    #     - A number, to represent a single bit
    #     - A range, to represent a continugous range of bits
    #
    #  The array is ordered from encoding MSB (at index 0) to LSB (at index n-1)
    def bits
      @encoding_fields.map do |ef|
        ef.range.size == 1 ? ef.range.first : ef.range
      end
    end

    # @return [Integer] the number of bits in the field, _including any implicit bits_
    def size
      size_in_encoding + @left_shift
    end

    # the number of bits in the field, _not including any implicit ones_
    def size_in_encoding
      bits.reduce(0) { |sum, f| sum + (f.is_a?(Integer) ? 1 : f.size) }
    end

    # true if the field should be sign extended
    def sext?
      @sext
    end

    # return code to extract the field
    def extract
      ops = []
      so_far = 0
      bits.each do |b|
        if b.is_a?(Integer)
          op = "$encoding[#{b}]"
          ops << op
          so_far += 1
        elsif b.is_a?(Range)
          op = "$encoding[#{b.end}:#{b.begin}]"
          ops << op
          so_far += b.size
        end
      end
      ops << "#{@left_shift}'d0" unless @left_shift.zero?
      ops =
        if ops.size > 1
          "{#{ops.join(', ')}}"
        else
          ops[0]
        end
      ops = "sext(#{ops})" if sext?
      ops
    end
  end

  # represents an instruction encoding
  class Encoding
    # @return [String] format, as a string of 0,1 and -,
    # @example Format of `sd`
    #      sd.format #=> '-----------------011-----0100011'
    attr_reader :format

    # @return [Array<Field>] List of fields containing opcodes
    # @example opcode_fields of `sd`
    #      sd.opcode_fields #=> [Field('011', ...), Field('0100011', ...)]
    attr_reader :opcode_fields

    # @return [Array<DecodeVariable>] List of decode variables
    attr_reader :decode_variables

    # represents an encoding field (contiguous set of bits that form an opcode or decode variable slot)
    class Field
      # @return [String] Either string of 0's ans 1's or a bunch of dashses
      # @example Field of a decode variable
      #   encoding.opcode_fields[0] #=> '-----' (for imm5)
      # @example Field of an opcode
      #   encoding.opcode_fields[1] #=> '0010011' (for funct7)
      attr_reader :name

      # @return [Range] Range of bits in the parent corresponding to this field
      attr_reader :range

      # @param name [#to_s] Either string of 0's ans 1's or a bunch of dashses
      # @param range [Range] Range of the field in the parent CSR
      def initialize(name, range)
        @name = name.to_s
        @range = range
      end

      # @return [Boolean] whether or not the field represents part of the opcode (i.e., not a decode variable)
      def opcode?
        name.match?(/^[01]+$/)
      end

      def to_s
        "#{name}[#{range}]"
      end
    end

    # @param format [String] Format of the encoding, as 0's, 1's and -'s (for decode variables)
    # @param decode_vars [Array<Hash<String,Object>>] List of decode variable defintions from the arch spec
    def initialize(format, decode_vars)
      @format = format

      @opcode_fields = []
      field_chars = []
      @format.chars.each_with_index do |c, idx|
        if c == "-"
          next if field_chars.empty?
          
          field_text = field_chars.join("")
          field_lsb = @format.size - idx
          field_msb = @format.size - idx - 1 + field_text.size
          @opcode_fields << Field.new(field_text, field_lsb..field_msb)

          field_chars.clear
          next
        else
          field_chars << c
        end
      end

      # add the least significant field
      unless field_chars.empty?
        field_text = field_chars.join("")
        @opcode_fields << Field.new(field_text, 0...field_text.size)
      end

      @decode_variables = []
      decode_vars&.each do |var|
        @decode_variables << DecodeVariable.new(self, var)
      end
    end

    # @return [Integer] Size, in bits, of the encoding
    def size
      @format.size
    end
  end

  def load_encoding
    @encodings = {}
    if @data["encoding"].key?("RV32")
      # there are different encodings for RV32/RV64
      @encodings[32] = Encoding.new(@data["encoding"]["RV32"]["match"], @data["encoding"]["RV32"]["variables"])
      @encodings[64] = Encoding.new(@data["encoding"]["RV64"]["match"], @data["encoding"]["RV64"]["variables"])
    elsif @data.key("base")
      @encodings[@data["base"]] = Encoding.new(@data["encoding"]["match"], @data["encoding"]["variables"])
    else
      @encodings[32] = Encoding.new(@data["encoding"]["match"], @data["encoding"]["variables"])
      @encodings[64] = Encoding.new(@data["encoding"]["match"], @data["encoding"]["variables"])
    end
  end
  private :load_encoding

  # @return [Boolean] whether or not this instruction has different encodings depending on XLEN
  def multi_encoding?
    @data.key?("encoding") && @data["encoding"].key?("RV32")
  end

  # @return [FunctionBodyAst] A type-checked abstract syntax tree of the operation
  # @param idl_compiler [Idl::Compiler] Compiler
  # @param symtab [Idl::SymbolTable] Symbol table with globals
  # @param effective_xlen [Integer] 32 or 64, the effective xlen to type check against
  def type_checked_operation_ast(idl_compiler, symtab, effective_xlen)
    @type_checked_operation_ast ||= {}
    ast = @type_checked_operation_ast[symtab.hash]
    return ast unless ast.nil?

    return nil unless @data.key?("operation()")

    ast = operation_ast(idl_compiler)

    idl_compiler.type_check(ast, fill_symtab(symtab, effective_xlen), "#{name}.operation()")

    @type_checked_operation_ast[symtab.hash] = ast
  end

  # @return [FunctionBodyAst] The abstract syntax tree of the instruction operation
  def operation_ast(idl_compiler)
    return @operation_ast unless @operation_ast.nil?
    return nil if @data["operation()"].nil?

    # now, parse the operation
    @operation_ast = idl_compiler.compile_inst_operation(
      self,
      input_file: @data["__source"],
      input_line: source_line("operation()")
    )

    raise "unexpected #{@operation_ast.class}" unless @operation_ast.is_a?(Idl::FunctionBodyAst)

    @operation_ast
  end

  # @param base [Integer] 32 or 64
  # @return [Encoding] the encoding
  def encoding(base)
    load_encoding if @encodings.nil?

    @encodings[base]
  end

  # @return [Integer] the width of the encoding
  def encoding_width
    raise "unexpected: encodings are different sizes" unless encoding(32).size == encoding(64).size

    encoding(64).size
  end

  # @return [Array<DecodeVariable>] The decode variables
  def decode_variables(base)
    encoding(base).decode_variables
  end

  # @return [Boolean] true if the instruction has an 'access_detail' field
  def access_detail?
    @data.key?("access_detail")
  end

  # Generates a wavedrom description of the instruction encoding
  #
  # @param base [Integer] The XLEN (32 or 64), needed if the instruction is {#multi_encoding?}
  # @return [String] The wavedrom JSON description
  def wavedrom_desc(base)
    desc = {
      "reg" => []
    }
    display_fields = encoding(base).opcode_fields
    display_fields += encoding(base).decode_variables.map(&:grouped_encoding_fields).flatten

    display_fields.sort { |a, b| b.range.last <=> a.range.last }.reverse.each do |e|
      desc["reg"] << { "bits" => e.range.size, "name" => e.name, "type" => (e.opcode? ? 2 : 4) }
    end

    desc
  end

  # @return [Boolean] whether or not this instruction is defined for RV32
  def rv32?
    !@data.key?("base") || base == 32
  end

  # @return [Boolean] whether or not this instruction is defined for RV64
  def rv64?
    !@data.key?("base") || base == 64
  end

  # @return [Array<ExtensionRequirement>] Extension exclusions for the instruction. If *any* exclusion is met, the instruction is not defined
  def extension_exclusions
    return @extension_exclusions unless @extension_excludions.nil?

    @extension_exclusions = []
    if @data.key?("excludedBy")
      if @data["exludedBy"].is_a?(Array)
        # could be either a single extension with exclusion, or a list of exclusions
        if extension_exclusion?(@data["excludedBy"][0])
          @extension_exclusions << to_extension_requirement(@data["excludedBy"][0])
        else
          # this is a list
          @data["excludeddBy"].each do |r|
            @extension_exclusions << to_extension_exclusion(r)
          end
        end
      else
        @extension_exclusions << to_extension_requirement(@data["excludedBy"])
      end
    end

    @extension_exclusions
  end

  # @overload excluded_by?(ext_name, ext_version)
  #   @param ext_name [#to_s] An extension name
  #   @param ext_version [#to_s] A specific extension version
  #   @return [Boolean] Whether or not the instruction is excluded by extesion `ext`, version `version`
  # @overload excluded_by?(ext_version)
  #   @param ext_version [ExtensionVersion] An extension version
  #   @return [Boolean] Whether or not the instruction is excluded by ext_version
  def excluded_by?(*args)
    if args.size == 1
      raise ArgumentError, "Parameter must be an ExtensionVersion" unless args[0].is_a?(ExtensionVersion)

      extension_exclusions.any? do |r|
        r.satisfied_by?(args[0])
      end
    elsif args.size == 2
      raise ArgumentError, "First parameter must be an extension name" unless args[0].respond_to?(:to_s)
      raise ArgumentError, "Second parameter must be an extension version" unless args[0].respond_to?(:to_s)

      extension_exclusions.any? do |r|
        r.satisfied_by?(args[0].to_s, args[1].to_s)
      end
    end
  end

  # @param possible_xlens [Array<Integer>] List of xlens that be used in any implemented mode
  # @param extensions [Array<ExtensionVersion>] List of extensions implemented
  # @return [Boolean] whether or not the instruction is implemented given the supplies config options
  def exists_in_cfg?(possible_xlens, extensions)
    (@data["base"].nil? || (possible_xlens.include? @data["base"])) &&
      extensions.any? { |e| defined_by?(e) } &&
      extensions.none? { |e| excluded_by?(e) }
  end
end

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

  def extract_location(location_string)
    parts = location_string.split("|")
    @encoding_fields = []
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
    @encoding_fields.sort { |a, b| b.range.last <=> a.range.last }.each do |ef|
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
      if var_bits[i] == (parts.last.first - 1)
        raise "??" if parts.last.last.nil?
        parts[-1] = var_bits[i]..parts.last.last
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
        [EncodingField.new(name, grouped_fields[0])]
      else
        [EncodingField.new("#{name}[#{inst_range_to_var_range(grouped_fields[0])}]", grouped_fields[0])]
      end
    else
      grouped_fields.map do |f|
        EncodingField.new("#{name}[#{inst_range_to_var_range(f)}]", f)
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

  # the number of bits in the field, _including any implicit ones_
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
        op = "encoding[#{b}]"
        ops << op
        so_far += 1
      elsif b.is_a?(Range)
        op = "encoding[#{b.end}:#{b.begin}]"
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

class DecodeField
  # the name of the field
  attr_reader :name


  # aliases of this field.
  #  if there is one alias, a String
  #  if there is more than one alias, an Array
  #  if there are no aliases, nil
  attr_reader :decode_variable

  def initialize(inst, name, decode_ring_key, field_data)
    raise "No field '#{name}', needed by #{inst.name}, in Opcodes module" unless Opcodes::DECODER_RING.key?(decode_ring_key)

    @encoding_fields = []
    if decode_ring_key.is_a?(Array)
      raise "Split fields '#{decode_ring_key}' must have an alias" unless field_data.key?(:decode_variable)

      raise "Split fields '#{decode_ring_key}' must have a group_by field" unless field_data.key?(:group_by)

      decode_ring_key.each_index do |i|
        range = field_data[:group_by][i].is_a?(Integer) ? (field_data[:group_by][i]..field_data[:group_by][i]) : field_data[:group_by][i]
        raise "expecting a range" unless range.is_a?(Range)

        display =
          if field_data[:display].nil?
            nil
          elsif field_data[:display].is_a?(Array)
            field_data[:display][i]
          else
            field_data[:display]
          end
        @encoding_fields << EncodingField.new(decode_ring_key[i], range, display)
      end
    else
      raise 'decode_ring_key must be an Array or a String' unless decode_ring_key.is_a?(String)

      range = field_data[:bits].is_a?(Range) ? field_data[:bits] : field_data[:group_by]
      raise 'expecting a range' unless range.is_a?(Range)

      @encoding_fields << EncodingField.new(decode_ring_key, range, field_data[:display])
    end

    @name = name
    if field_data.key?(:decode_variable) && field_data[:decode_variable] != name
      if field_data[:decode_variable].is_a?(String)
        @alias = field_data[:decode_variable]
      else
        raise "unexpected" unless field_data[:decode_variable].is_a?(Array)

        other_aliases = field_data[:decode_variable].reject { |a| a == @name }
        if other_aliases.size == 1
          @alias = other_aliases[0]
        else
          @alias = other_aliases
        end
      end
    end
    @decode_variable = @alias
    raise "unexpected: #{name}" unless @name.is_a?(String)

    @field_data = field_data

  end

  def eql?(other)
    @name.eql?(other.name)
  end

  def hash
    @name.hash
  end

  # returns true if the field is encoded across more than one groups of bits
  def split?
    encoding_fields.size > 1
  end

  # returns bits of the encoding that make up the field, as an array
  #   Each item of the array is either:
  #     - A number, to represent a single bit
  #     - A range, to represent a continugous range of bits
  #
  #  The array is ordered from encoding MSB (at index 0) to LSB (at index n-1)
  def bits
    @field_data[:bits].is_a?(Range) ? [@field_data[:bits]] : @field_data[:bits]
  end

  def grouped_encoding_fields
    @encoding_fields
  end

  # the number of bits in the field, _including any implicit ones_
  def size
    size_in_encoding + (@field_data.key?(:lshift) ? @field_data[:lshift] : 0)
  end

  # the number of bits in the field, _not including any implicit ones_
  def size_in_encoding
    bits.reduce(0) { |sum, f| sum + (f.is_a?(Integer) ? 1 : f.size) }
  end

  # true if the field should be sign extended
  def sext?
    @field_data[:sext] == true
  end

  # return code to extract the field
  def extract
    ops = []
    so_far = 0
    bits.each do |b|
      if b.is_a?(Integer)
        op = "encoding[#{b}]"
        # shamt = size - so_far - 1
        # op = "(#{op} << #{shamt})" if shamt != 0
        ops << op
        so_far += 1
      elsif b.is_a?(Range)
        op = "encoding[#{b.end}:#{b.begin}]"
        # shamt = size - so_far - b.size
        # op = "(#{op} << #{shamt})" if shamt != 0
        ops << op
        so_far += b.size
      end
    end
    ops << "#{@field_data[:lshift]}'d0" unless @field_data[:lshift].nil?
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

module Opcodes
  DECODER_RING = {
    'rd' => {
      bits: (7..11)
    },
    'rd_p' => {
      bits: (2..4),
      lshift: 2,
      display: "rd'",
      decode_variable: 'rd'
    },
    'rd_n0' => {
      bits: (7..11),
      display: "rd != 0",
      decode_variable: 'rd'
    },
    'rd_n2' => {
      bits: (7..11),
      display: 'rd != {0,2}',
      decode_variable: 'rd'
    },
    'rs1' => {
      bits: (15..19)
    },
    'rs1_p' => {
      bits: (7..9),
      lshift: 2,
      display: "rs1'",
      decode_variable: 'rs1'
    },
    'c_rs1_n0' => {
      bits: (7..11),
      display: "rs1 != 0",
      decode_variable: 'rs1'
    },

    'rs2' => {
      bits: (20..24)
    },
    'c_rs2' => {
      bits: (2..6),
      display: 'rs2'
    },
    'rs2_p' => {
      bits: (2..4),
      lshift: 2,
      display: "rs2'",
      decode_variable: 'rs2'
    },
    'c_rs2_n0' => {
      bits: (2..6),
      display: "rs2 != 0",
      decode_variable: 'rs2'
    },
    'rd_rs1' => {
      bits: (7..11),
      display: 'rs1/rd != 0',
      decode_variable: ['rd', 'rs1']
    },
    'rd_rs1_p' => {
      bits: (7..9),
      lshift: 2,
      display: "rd'/rs1'",
      decode_variable: ['rd', 'rs1']
    },
    'rd_rs1_n0' => {
      bits: (7..11),
      display: 'rd/rs1 != 0',
      decode_variable: ['rd', 'rs1']
    },
    'rs1_n0' => {
      bits: (7..11),
      display: 'rs1 != 0',
      decode_variable: 'rs1'
    },
    'shamtd' => {
      bits: 20..25,
      display: 'shamt',
      decode_variable: 'shamt'
    },
    'shamtw' => {
      bits: 20..24,
      display: 'shamt',
      decode_variable: 'shamt'
    },
    'csr' => {
      bits: 20..31
    },
    'zimm' => {
      bits: 15..19
    },
    'imm12' => {
      bits: (20..31),
      sext: true,
      display: 'imm[11:0]',
      decode_variable: 'imm'
    },
    'imm20' => {
      bits: (12..31),
      lshift: 12,
      sext: true,
      display: 'imm[31:20]',
      decode_variable: 'imm'
    },
    'jimm20' => {
      bits: [31, (12..19), 20, (21..30)],
      group_by: 12..31,
      lshift: 1,
      sext: true,
      display: 'imm[20|10:1|11|19:12]',
      decode_variable: 'imm'
    },
    ['bimm12hi', 'bimm12lo'] => {
      bits: [31, 7, (25..30), (8..11)],
      group_by: [(25..31), (7..11)],
      sext: true,
      lshift: 1,
      display: ['imm[12|10:5]', 'imm[4:1|11]'],
      decode_variable: 'offset'
    },
    ['imm12hi', 'imm12lo'] => {
      bits: [(25..31), (7..11)],
      group_by: [(25..31), (7..11)],
      sext: true,
      display: ['imm[11:5]', 'imm[4:0]'],
      decode_variable: 'imm'
    },
    'pred' => {
      bits: (24..27)
    },
    'succ' => {
      bits: (20..23)
    },
    'fm' => {
      bits: (28..31)
    },

    'c_nzuimm10' => {
      bits: [(7..10), (11..12), 5, 6],
      group_by: 5..12,
      lshift: 2,
      display: 'nzuimm[5:4|9:6|2|3]',
      decode_variable: 'imm'
    },
    ['c_uimm8lo', 'c_uimm8hi'] => {
      bits: [(5..6), (10..12)],
      group_by: [(5..6), (10..12)],
      lshift: 3,
      display: ['uimm[7:6]', 'uimm[5:3]'],
      decode_variable: 'imm'
    },
    ['c_uimm7lo', 'c_uimm7hi'] => {
      bits: [5, (10..12), 6],
      group_by: [(10..12), (5..6)],
      lshift: 2,
      display: ['uimm[5:3]', 'uimm[2|6]'],
      decode_variable: 'imm'
    },
    ['c_nzimm6hi', 'c_nzimm6lo'] => {
      bits: [12, (2..6)],
      group_by: [12, (2..6)],
      sext: true,
      display: ['nzimm[5]', 'nzimm[4:0]'],
      decode_variable: 'imm'
    },
    ['c_nzuimm6hi', 'c_nzuimm6lo'] => {
      bits: [12, (2..6)],
      group_by: [12, (2..6)],
      display: ['nzuimm[5]', 'nzuimm[4:0]'],
      decode_variable: 'imm'
    },
    ['c_imm6hi', 'c_imm6lo'] => {
      bits: [12, (2..6)],
      group_by: [12, (2..6)],
      sext: true,
      display: ['nzimm[5]', 'nzimm[4:0]'],
      decode_variable: 'imm'
    },
    ['c_nzimm10hi', 'c_nzimm10lo'] => {
      bits: [12, (3..4), 5, 2, 6],
      group_by: [12, (2..6)],
      lshift: 4,
      sext: true,
      display: ['nzimm[9]', 'nzimm[4|6|8:7|5]'],
      decode_variable: 'imm'
    },
    ['c_nzimm18hi', 'c_nzimm18lo'] => {
      bits: [12, (2..6)],
      group_by: [12, (2..6)],
      lshift: 12,
      sext: true,
      display: ['nzimm[17]', 'nzimm[16:12]'],
      decode_variable: 'imm'
    },
    'c_imm12' => {
      bits: [12, 8, (9..10), 6, 7, 2, 11, (3..5)],
      group_by: 2..12,
      lshift: 1,
      sext: true,
      display: 'imm[11|4|9:8|10|6|7|3:1|5]',
      decode_variable: 'imm'
    },
    ['c_bimm9hi', 'c_bimm9lo'] => {
      bits: [12, (5..6), 2, (10..11), (3..4)],
      group_by: [(10..12), (2..6)],
      lshift: 1,
      sext: true,
      display: ['imm[8|4:3]', 'imm[7:6|2:1|5]'],
      decode_variable: 'imm'
    },
    ['c_uimm8sphi', 'c_uimm8splo'] => {
      bits: [(2..3), 12, (4..6)],
      group_by: [12, (2..6)],
      lshift: 2,
      display: ['uimm5', 'uimm[4:2|7:6]'],
      decode_variable: 'imm'
    },
    'cuimm8sp_s' => {
      bits: [(7..8), (9..12)],
      group_by: (7..12),
      lshift: 2,
      display: 'uimm[5:2|7:6]',
      decode_variable: 'imm'
    },
    ['c_uimm9sphi', 'c_uimm9splo'] => {
      bits: [(2..3), 12, (4..6)],
      group_by: [12, (2..6)],
      lshift: 3,
      display: ['uimm[5]', 'uimm[4:3|8:6]'],
      decode_variable: 'imm'
    },
    'c_uimm8sp_s' => {
      bits: [(7..8), (9..12)],
      group_by: 7..12,
      lshift: 2,
      display: 'uimm[5:2|7:6]',
      decode_variable: 'imm'
    },
    'c_uimm9sp_s' => {
      bits: [(7..9), (10..12)],
      group_by: 7..12,
      lshift: 3,
      display: 'uimm[5:3|8:6]',
      decode_variable: 'imm'
    },
    'rm' => {
      bits: (12..14)
    }

  }

  def self.insn_table
    return @insn_table unless @insn_table.nil?

    @insn_table = YAML.safe_load(
      File.read(File.join(File.dirname(__FILE__), '..', '..', 'ext', 'riscv-opcodes', 'instr_dict.yaml'))
    )
  end
end

# frozen_string_literal: true

class DecodeGen
  class DecodeTreeNode
    # insts are a group of instructions that share opcode bit positions
    # up to the most significant bit considered along this path
    #
    # range: the encoding range considered at this point
    # value: the value of the encoding at this range that will match insts
    # type: either endpoint (instructions are fully decoded) or in_progress
    attr_accessor :parent, :children, :insts, :range, :value, :type

    # types
    ENDPOINT_TYPE = 1  # holding instructions that are fully defined at this point
    SELECT_TYPE = 2    # holding instructions that need to be selected on the range

    def initialize(parent, insts, range, value, type)
      @parent = parent
      @insts = insts
      @range = range
      @value = value
      @type = type
      @children = []
    end

    def print(indent = 0)
      $stdout.print (' ' * indent)
      $stdout.print @type == ENDPOINT_TYPE ? 'ENDPOINT' : 'SELECT'
      @children.each do |child|
        child.print(indent + 2)
      end
    end

    def range_overlap?(a, b)
      (b.begin <= a.end) && (a.begin <= b.end)
    end
    private :range_overlap?

    def mask_overlap?(test_range, extra_range = nil)
      return true if !@range.nil? && range_overlap?(@range, test_range)
      return true if !extra_range.nil? && range_overlap?(extra_range, test_range)
      return true if !@parent.nil? && @parent.mask_overlap?(test_range)

      false
    end

    # return mask of opcode positions at this node
    def mask(extra_range = nil)
      this_mask =
        if @range.nil?
          0
        else
          ((1 << @range.size) - 1) << @range.first
        end
      extra_mask =
        if extra_range.nil?
          0
        else
          ((1 << extra_range.size) - 1) << extra_range.first
        end
      parent_mask =
        if @parent.nil?
          0
        else
          parent.mask
        end
      this_mask | parent_mask | extra_mask
    end

    # returns lowest non opcode bit either:
    #   gte == nil : overall
    #   gte is_a? Integer : greater than or equal to gte
    def lowest_non_opcode_bit(gte=nil)
      if gte.nil?
        "0#{mask.to_s(2)}".reverse.index('0')
      else
        if gte >= mask.to_s(2).size
          gte
        else
          "0#{mask.to_s(2)}".reverse[gte..].index('0') + gte
        end
      end
    end

    def opcode_bit?(index)
      if index >= mask.to_s(2).size
        false
      else
        mask.to_s(2).reverse[index] == '1'
      end
    end

    def <<(child)
      @children << child
    end
  end


  def initialize(cfg_arch)
    @cfg_arch = cfg_arch
  end

  def construct_decode_tree(tree, xlen, cur_range, test: false)
    # list of instructions that are completely decoded with this (and all previous) range
    done_insts = {}

    # hash of instructions that still being decoded, grouped by value over the current range
    in_progress_groups = {}

    # list of instructions that have a variable bit in cur_range
    variable_insts = []

    tree.insts.each do |inst|
      inst_format = inst.encoding(xlen).format
      if inst_format.reverse[cur_range].match?(/^[01]+$/)
        puts "#{inst.name} has opcode bit(s) in #{cur_range} (#{inst_format.reverse[cur_range].reverse})"
        # whole range is opcode bits
        if inst_format.gsub('0', '1') == tree.mask(cur_range).to_s(2).gsub('0', '-').rjust(inst.encoding(xlen).size, '-')
          done_insts[inst_format.reverse[cur_range]] = inst
        else
          in_progress_groups[inst_format.reverse[cur_range]] ||= []
          in_progress_groups[inst_format.reverse[cur_range]] << inst
        end
      else
        puts "#{inst.name} has variable bit(s) in #{cur_range} (#{inst_format.reverse[cur_range].reverse} #{inst_format.reverse})"
        variable_insts << inst
      end
    end
    if test
      puts "test result for #{cur_range}: #{variable_insts.empty?} (#{tree.insts.map(&:name)})"
      return variable_insts.empty?
    end
    if !variable_insts.empty? && (!done_insts.empty? || !in_progress_groups.empty?)
      raise 'Problem: variable/opcode mix when range size > 1' unless cur_range.size == 1

      # some instructions have an opcode, while some have hit a variable
      # that means that the next test needs to come from a higher bit position
      # we'll have to search for that next position, and then circle back to the current spot
      next_range = nil
      loop do
        next_range = (cur_range.last+1..cur_range.last+1)
        break unless tree.mask_overlap?(next_range)
      end
      puts "testing range #{next_range} on #{tree.insts.map(&:name)}"
      while construct_decode_tree(tree, xlen, next_range, test: true) == false
        loop do
          next_range = (next_range.last+1..next_range.last+1)
          break unless tree.mask_overlap?(next_range)
        end
      end
      puts "found range that works (#{next_range}) on #{tree.insts.map(&:name)}...constructing"
      construct_decode_tree(tree, xlen, next_range)
      return
    end

    if done_insts.empty? && !in_progress_groups.empty?
      # everything is still in an opcode, so grow the range and try again
      next_range = (cur_range.first..cur_range.last+1)
      puts "All insts have opcode at #{cur_range}, trying #{next_range}..."
      if tree.opcode_bit?(cur_range.last+1) || (construct_decode_tree(tree, xlen, next_range, test: true) == false)
        # next bit goes too far, so this is the endpoint
        in_progress_groups.each do |val, insts|
          child = DecodeTreeNode.new(tree, insts, cur_range, val, DecodeTreeNode::SELECT_TYPE)
          tree << child
          puts "starting child for selector #{cur_range}, starting search again at bit #{child.lowest_non_opcode_bit} for #{insts.map{ |i| i.name}}"
          construct_decode_tree(child, xlen, (child.lowest_non_opcode_bit..child.lowest_non_opcode_bit))
        end
        done_insts.each do |val, inst|
          puts "Found endpoint for #{inst.name}: #{tree.mask}"
          child = DecodeTreeNode.new(tree, [inst], cur_range, val, DecodeTreeNode::ENDPOINT_TYPE)
          tree << child
        end
      else
        # go to the next range
        puts "going to next range #{next_range}"
        construct_decode_tree(tree, xlen, next_range)
      end
    elsif !done_insts.empty?
      # must end
      done_insts.each do |val, inst|
        puts "Completed #{inst.name} at #{cur_range} -- #{tree.mask(cur_range).to_s(2).ljust(32, '0')}"
        child = DecodeTreeNode.new(tree, [inst], cur_range, val, DecodeTreeNode::ENDPOINT_TYPE)
        tree << child
      end
      in_progress_groups.each do |val, insts|
        child = DecodeTreeNode.new(tree, insts, cur_range, val, DecodeTreeNode::SELECT_TYPE)
        tree << child
        puts "Starting child at #{child.lowest_non_opcode_bit} for #{insts.map{|i| i.name}}"
        construct_decode_tree(child, xlen, (child.lowest_non_opcode_bit..child.lowest_non_opcode_bit))
      end
    else
      raise 'unexpected' if variable_insts.empty?

      raise "unexpected: variable when range size > 1 #{cur_range} #{cur_range.size} #{variable_insts.map{ |i| i.name}}" unless cur_range.size == 1

      puts "Moving to next variable at #{tree.lowest_non_opcode_bit(cur_range.last+1)}"
      construct_decode_tree(tree, xlen, (tree.lowest_non_opcode_bit(cur_range.last+1)..tree.lowest_non_opcode_bit(cur_range.last+1)))
    end
  end
  private :construct_decode_tree

  def comment_tree(tree, indent)
    str = tree.parent.nil? ? "" : comment_tree(tree.parent, indent)
    if !tree.value.nil?
      str + "#{' ' * indent}// encoding[#{tree.range}] == #{tree.value.reverse}\n"
    else
      str
    end
  end

  def extract_dv(dv, encoding_var_name)
    idx = 0
    efs = []
    dv.encoding_fields.each do |ef|
      bits = "extract<#{ef.range.first}, #{ef.range.size}>(#{encoding_var_name}.get())"
      efs <<
        if idx == 0
          bits
        else
          "(#{bits} << #{idx})"
        end
      idx += ef.size
    end

    efs.join(" && ")
  end

  def needs_long_form?(node, inst_list)
    node.children.any? do |child|
      child.type == DecodeTreeNode::ENDPOINT_TYPE \
        && child.insts[0].encoding(xlen).decode_variables.any? { |dv| !dv.excludes.empty?  }
    end \
      || node.children.any? do |child|
        child.type == DecodeTreeNode::ENDPOINT_TYPE \
          && inst_list.any? do |other_inst|
            (other_inst != chlid.insts[0]) \
              && child.insts[0].encoding(xlen).conflicts?(other_inst.encoding(xlen))
          end
      end
  end
  # @return [String] C++ decoder switch
  def decode_c(encoding_var_name, xlen, inst_list, node = nil, indent = 0)
    # frst, sanity check that all the children have the same range
    raise "Bad tree" unless (node.children.empty? || node.children.all? { |child| child.range == node.children.first.range })

    tenv = CppHartGen::TemplateEnv.new(@cfg_arch)

    code = ''
    if node.type == DecodeTreeNode::SELECT_TYPE
      if needs_long_form?(node, inst_list)
        # there is at least one child with a not statement or a conflict, can't use a simple switch
        els = ""
        node.children.each do |child|
          code += comment_tree(child, indent + 2)
          has_not = child.type == DecodeTreeNode::ENDPOINT_TYPE \
            && child.insts[0].encoding(xlen).decode_variables.any? { |dv| !dv.excludes.empty? }
          has_conflict = child.type == DecodeTreeNode::ENDPOINT_TYPE \
            && inst_list.any? { |other_inst| child.insts[0].encoding(xlen).conflicts?(other_inst.encoding(xlen)) }
          if has_not
            not_conds = []
            child.insts[0].encoding(xlen).decode_variables.each do |dv|
              next if dv.excludes.empty?

              dv_val = extract_dv(dv, encoding_var_name)
              not_conds.concat(dv.excludes.map { |val| "(#{dv_val} != #{val})" })
            end
            code += "#{' '*indent}#{els}if ((extract<#{child.range.first}, #{child.range.size}>(#{encoding_var_name}).get() == 0b#{child.value.reverse}) && #{not_conds.join(' && ')}) {\n"
          else
            code += "#{' '*indent}#{els}if (extract<#{child.range.first}, #{child.range.size}>(#{encoding_var_name}).get() == 0b#{child.value.reverse}) {\n"
          end
          code += decode_c(encoding_var_name, xlen, inst_list, child, indent + 2)
          code += "#{' '*indent}}\n"
          els = "else "
        end
      else
        code += "#{' ' * indent}switch(extract<#{node.children.first.range.first}, #{node.children.first.range.size}>(#{encoding_var_name}).get()) {\n"
        node.children.each do |child|
          code += comment_tree(child, indent + 2)
          code += "#{' ' * (indent + 2)}case 0b#{child.value.reverse}:\n"
          code += decode_c(encoding_var_name, xlen, inst_list, child, indent + 2)
          code += "#{' ' * (indent + 4)}break;\n"
        end
        code += "#{' ' * indent}}\n"
      end
    else
      raise 'unexpected' unless node.type == DecodeTreeNode::ENDPOINT_TYPE

      code += "#{' ' * (indent + 2)}return new #{tenv.name_of(:inst, @cfg_arch, node.insts[0].name)}<#{xlen}>(this, pc, #{encoding_var_name});\n"
    end
    code
  end
  private :decode_c

  def annotate_identical(tree, xlen)
    tree.children.each do |child|
      if child.type == DecodeTreeNode::ENDPOINT_TYPE
        matches = tree.children.select do |other_child|
          other_child.type == DecodeTreeNode::ENDPOINT_TYPE \
          && child != other_child \
          && child.insts[0].encoding(xlen).format == other_child.insts[0].encoding(xlen).format
        end
        unless matches.empty?
          puts "#{child.insts[0].name} identical to #{ matches.map { |n| n.insts[0].name }.join(', ')}"
        end
      end
      annotate_identical(child, xlen) if child.type == DecodeTreeNode::SELECT_TYPE
    end
  end

  # @param instructions [Array<Instruction>] Set of instructions to generate a decode for
  # @param xlen [Integer] Effective xlen
  # @return [String] Decoder function for the given set of instructions and the effective xlen
  def generate(instructions, xlen, indent: 2)
    root = DecodeTreeNode.new(nil, instructions, nil, nil, DecodeTreeNode::SELECT_TYPE)
    construct_decode_tree(root, xlen, 0..0)
    annotate_identical(root, xlen)
    decode_c('m_encoding', xlen, instructions, root, indent)
  end
end
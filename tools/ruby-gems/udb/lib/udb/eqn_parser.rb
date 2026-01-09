# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# grammar for the EQNTOTT format

module Eqn
  include Treetop::Runtime

  def root
    @root ||= :eqn
  end

  module Eqn0
    def expression
      elements[0]
    end

  end

  def _nt_eqn
    start_index = index
    if node_cache[:eqn].has_key?(index)
      cached = node_cache[:eqn][index]
      if cached
        node_cache[:eqn][index] = cached = SyntaxNode.new(input, index...(index + 1)) if cached == true
        @index = cached.interval.end
      end
      return cached
    end

    i0, s0 = index, []
    r1 = _nt_expression
    s0 << r1
    if r1
      s2, i2 = [], index
      loop do
        r3 = _nt_space
        if r3
          s2 << r3
        else
          break
        end
      end
      r2 = instantiate_node(SyntaxNode,input, i2...index, s2)
      s0 << r2
      if r2
        if (match_len = has_terminal?(';', false, index))
          r4 = true
          @index += match_len
        else
          terminal_parse_failure('\';\'')
          r4 = nil
        end
        s0 << r4
        if r4
          s5, i5 = [], index
          loop do
            r6 = _nt_space
            if r6
              s5 << r6
            else
              break
            end
          end
          r5 = instantiate_node(SyntaxNode,input, i5...index, s5)
          s0 << r5
        end
      end
    end
    if s0.last
      r0 = instantiate_node(Udb::Eqn::EqnTop,input, i0...index, s0)
      r0.extend(Eqn0)
    else
      @index = i0
      r0 = nil
    end

    node_cache[:eqn][start_index] = r0

    r0
  end

  module Name0
  end

  def _nt_name
    start_index = index
    if node_cache[:name].has_key?(index)
      cached = node_cache[:name][index]
      if cached
        node_cache[:name][index] = cached = SyntaxNode.new(input, index...(index + 1)) if cached == true
        @index = cached.interval.end
      end
      return cached
    end

    i0, s0 = index, []
    if has_terminal?(@regexps[gr = '\A[a-zA-Z_]'] ||= Regexp.new(gr), :regexp, index)
      r1 = true
      @index += 1
    else
      terminal_parse_failure('[a-zA-Z_]')
      r1 = nil
    end
    s0 << r1
    if r1
      s2, i2 = [], index
      loop do
        if has_terminal?(@regexps[gr = '\A[a-zA-Z0-9.]'] ||= Regexp.new(gr), :regexp, index)
          r3 = true
          @index += 1
        else
          terminal_parse_failure('[a-zA-Z0-9.]')
          r3 = nil
        end
        if r3
          s2 << r3
        else
          break
        end
      end
      r2 = instantiate_node(SyntaxNode,input, i2...index, s2)
      s0 << r2
    end
    if s0.last
      r0 = instantiate_node(Udb::Eqn::EqnName,input, i0...index, s0)
      r0.extend(Name0)
    else
      @index = i0
      r0 = nil
    end

    node_cache[:name][start_index] = r0

    r0
  end

  def _nt_zero
    start_index = index
    if node_cache[:zero].has_key?(index)
      cached = node_cache[:zero][index]
      if cached
        node_cache[:zero][index] = cached = SyntaxNode.new(input, index...(index + 1)) if cached == true
        @index = cached.interval.end
      end
      return cached
    end

    i0 = index
    if (match_len = has_terminal?('ZERO', false, index))
      r1 = instantiate_node(SyntaxNode,input, index...(index + match_len))
      @index += match_len
    else
      terminal_parse_failure('\'ZERO\'')
      r1 = nil
    end
    if r1
      r1 = SyntaxNode.new(input, (index-1)...index) if r1 == true
      r0 = r1
    else
      if (match_len = has_terminal?('0', false, index))
        r2 = instantiate_node(Udb::Eqn::EqnZero,input, index...(index + match_len))
        @index += match_len
      else
        terminal_parse_failure('\'0\'')
        r2 = nil
      end
      if r2
        r2 = SyntaxNode.new(input, (index-1)...index) if r2 == true
        r0 = r2
      else
        @index = i0
        r0 = nil
      end
    end

    node_cache[:zero][start_index] = r0

    r0
  end

  def _nt_one
    start_index = index
    if node_cache[:one].has_key?(index)
      cached = node_cache[:one][index]
      if cached
        node_cache[:one][index] = cached = SyntaxNode.new(input, index...(index + 1)) if cached == true
        @index = cached.interval.end
      end
      return cached
    end

    i0 = index
    if (match_len = has_terminal?('ONE', false, index))
      r1 = instantiate_node(SyntaxNode,input, index...(index + match_len))
      @index += match_len
    else
      terminal_parse_failure('\'ONE\'')
      r1 = nil
    end
    if r1
      r1 = SyntaxNode.new(input, (index-1)...index) if r1 == true
      r0 = r1
    else
      if (match_len = has_terminal?('1', false, index))
        r2 = instantiate_node(Udb::Eqn::EqnOne,input, index...(index + match_len))
        @index += match_len
      else
        terminal_parse_failure('\'1\'')
        r2 = nil
      end
      if r2
        r2 = SyntaxNode.new(input, (index-1)...index) if r2 == true
        r0 = r2
      else
        @index = i0
        r0 = nil
      end
    end

    node_cache[:one][start_index] = r0

    r0
  end

  module Paren0
  end

  module Paren1
    def conjunction
      elements[2]
    end

  end

  def _nt_paren
    start_index = index
    if node_cache[:paren].has_key?(index)
      cached = node_cache[:paren][index]
      if cached
        node_cache[:paren][index] = cached = SyntaxNode.new(input, index...(index + 1)) if cached == true
        @index = cached.interval.end
      end
      return cached
    end

    i0 = index
    i1, s1 = index, []
    if (match_len = has_terminal?('(', false, index))
      r2 = true
      @index += match_len
    else
      terminal_parse_failure('\'(\'')
      r2 = nil
    end
    s1 << r2
    if r2
      s3, i3 = [], index
      loop do
        r4 = _nt_space
        if r4
          s3 << r4
        else
          break
        end
      end
      r3 = instantiate_node(SyntaxNode,input, i3...index, s3)
      s1 << r3
      if r3
        if (match_len = has_terminal?(')', false, index))
          r5 = true
          @index += match_len
        else
          terminal_parse_failure('\')\'')
          r5 = nil
        end
        s1 << r5
      end
    end
    if s1.last
      r1 = instantiate_node(Udb::Eqn::EmptyEqnParen,input, i1...index, s1)
      r1.extend(Paren0)
    else
      @index = i1
      r1 = nil
    end
    if r1
      r1 = SyntaxNode.new(input, (index-1)...index) if r1 == true
      r0 = r1
    else
      i6, s6 = index, []
      if (match_len = has_terminal?('(', false, index))
        r7 = true
        @index += match_len
      else
        terminal_parse_failure('\'(\'')
        r7 = nil
      end
      s6 << r7
      if r7
        s8, i8 = [], index
        loop do
          r9 = _nt_space
          if r9
            s8 << r9
          else
            break
          end
        end
        r8 = instantiate_node(SyntaxNode,input, i8...index, s8)
        s6 << r8
        if r8
          r10 = _nt_conjunction
          s6 << r10
          if r10
            s11, i11 = [], index
            loop do
              r12 = _nt_space
              if r12
                s11 << r12
              else
                break
              end
            end
            r11 = instantiate_node(SyntaxNode,input, i11...index, s11)
            s6 << r11
            if r11
              if (match_len = has_terminal?(')', false, index))
                r13 = true
                @index += match_len
              else
                terminal_parse_failure('\')\'')
                r13 = nil
              end
              s6 << r13
            end
          end
        end
      end
      if s6.last
        r6 = instantiate_node(Udb::Eqn::EqnParen,input, i6...index, s6)
        r6.extend(Paren1)
      else
        @index = i6
        r6 = nil
      end
      if r6
        r6 = SyntaxNode.new(input, (index-1)...index) if r6 == true
        r0 = r6
      else
        @index = i0
        r0 = nil
      end
    end

    node_cache[:paren][start_index] = r0

    r0
  end

  module Not0
    def name
      elements[2]
    end
  end

  def _nt_not
    start_index = index
    if node_cache[:not].has_key?(index)
      cached = node_cache[:not][index]
      if cached
        node_cache[:not][index] = cached = SyntaxNode.new(input, index...(index + 1)) if cached == true
        @index = cached.interval.end
      end
      return cached
    end

    i0, s0 = index, []
    if (match_len = has_terminal?('!', false, index))
      r1 = true
      @index += match_len
    else
      terminal_parse_failure('\'!\'')
      r1 = nil
    end
    s0 << r1
    if r1
      s2, i2 = [], index
      loop do
        r3 = _nt_space
        if r3
          s2 << r3
        else
          break
        end
      end
      r2 = instantiate_node(SyntaxNode,input, i2...index, s2)
      s0 << r2
      if r2
        r4 = _nt_name
        s0 << r4
      end
    end
    if s0.last
      r0 = instantiate_node(Udb::Eqn::EqnNot,input, i0...index, s0)
      r0.extend(Not0)
    else
      @index = i0
      r0 = nil
    end

    node_cache[:not][start_index] = r0

    r0
  end

  def _nt_unary_expression
    start_index = index
    if node_cache[:unary_expression].has_key?(index)
      cached = node_cache[:unary_expression][index]
      if cached
        node_cache[:unary_expression][index] = cached = SyntaxNode.new(input, index...(index + 1)) if cached == true
        @index = cached.interval.end
      end
      return cached
    end

    i0 = index
    r1 = _nt_paren
    if r1
      r1 = SyntaxNode.new(input, (index-1)...index) if r1 == true
      r0 = r1
    else
      r2 = _nt_not
      if r2
        r2 = SyntaxNode.new(input, (index-1)...index) if r2 == true
        r0 = r2
      else
        r3 = _nt_zero
        if r3
          r3 = SyntaxNode.new(input, (index-1)...index) if r3 == true
          r0 = r3
        else
          r4 = _nt_one
          if r4
            r4 = SyntaxNode.new(input, (index-1)...index) if r4 == true
            r0 = r4
          else
            r5 = _nt_name
            if r5
              r5 = SyntaxNode.new(input, (index-1)...index) if r5 == true
              r0 = r5
            else
              @index = i0
              r0 = nil
            end
          end
        end
      end
    end

    node_cache[:unary_expression][start_index] = r0

    r0
  end

  module Conjunction0
    def unary_expression
      elements[3]
    end
  end

  module Conjunction1
    def first
      elements[0]
    end

    def r
      elements[1]
    end
  end

  def _nt_conjunction
    start_index = index
    if node_cache[:conjunction].has_key?(index)
      cached = node_cache[:conjunction][index]
      if cached
        node_cache[:conjunction][index] = cached = SyntaxNode.new(input, index...(index + 1)) if cached == true
        @index = cached.interval.end
      end
      return cached
    end

    i0 = index
    i1, s1 = index, []
    r2 = _nt_unary_expression
    s1 << r2
    if r2
      s3, i3 = [], index
      loop do
        i4, s4 = index, []
        s5, i5 = [], index
        loop do
          r6 = _nt_space
          if r6
            s5 << r6
          else
            break
          end
        end
        r5 = instantiate_node(SyntaxNode,input, i5...index, s5)
        s4 << r5
        if r5
          if (match_len = has_terminal?('&', false, index))
            r7 = true
            @index += match_len
          else
            terminal_parse_failure('\'&\'')
            r7 = nil
          end
          s4 << r7
          if r7
            s8, i8 = [], index
            loop do
              r9 = _nt_space
              if r9
                s8 << r9
              else
                break
              end
            end
            r8 = instantiate_node(SyntaxNode,input, i8...index, s8)
            s4 << r8
            if r8
              r10 = _nt_unary_expression
              s4 << r10
            end
          end
        end
        if s4.last
          r4 = instantiate_node(SyntaxNode,input, i4...index, s4)
          r4.extend(Conjunction0)
        else
          @index = i4
          r4 = nil
        end
        if r4
          s3 << r4
        else
          break
        end
      end
      if s3.empty?
        @index = i3
        r3 = nil
      else
        r3 = instantiate_node(SyntaxNode,input, i3...index, s3)
      end
      s1 << r3
    end
    if s1.last
      r1 = instantiate_node(Udb::Eqn::EqnAnd,input, i1...index, s1)
      r1.extend(Conjunction1)
    else
      @index = i1
      r1 = nil
    end
    if r1
      r1 = SyntaxNode.new(input, (index-1)...index) if r1 == true
      r0 = r1
    else
      r11 = _nt_unary_expression
      if r11
        r11 = SyntaxNode.new(input, (index-1)...index) if r11 == true
        r0 = r11
      else
        @index = i0
        r0 = nil
      end
    end

    node_cache[:conjunction][start_index] = r0

    r0
  end

  module Disjunction0
    def conjunction
      elements[3]
    end
  end

  module Disjunction1
    def first
      elements[0]
    end

    def r
      elements[1]
    end
  end

  def _nt_disjunction
    start_index = index
    if node_cache[:disjunction].has_key?(index)
      cached = node_cache[:disjunction][index]
      if cached
        node_cache[:disjunction][index] = cached = SyntaxNode.new(input, index...(index + 1)) if cached == true
        @index = cached.interval.end
      end
      return cached
    end

    i0 = index
    i1, s1 = index, []
    r2 = _nt_conjunction
    s1 << r2
    if r2
      s3, i3 = [], index
      loop do
        i4, s4 = index, []
        s5, i5 = [], index
        loop do
          r6 = _nt_space
          if r6
            s5 << r6
          else
            break
          end
        end
        r5 = instantiate_node(SyntaxNode,input, i5...index, s5)
        s4 << r5
        if r5
          if (match_len = has_terminal?('|', false, index))
            r7 = true
            @index += match_len
          else
            terminal_parse_failure('\'|\'')
            r7 = nil
          end
          s4 << r7
          if r7
            s8, i8 = [], index
            loop do
              r9 = _nt_space
              if r9
                s8 << r9
              else
                break
              end
            end
            r8 = instantiate_node(SyntaxNode,input, i8...index, s8)
            s4 << r8
            if r8
              r10 = _nt_conjunction
              s4 << r10
            end
          end
        end
        if s4.last
          r4 = instantiate_node(SyntaxNode,input, i4...index, s4)
          r4.extend(Disjunction0)
        else
          @index = i4
          r4 = nil
        end
        if r4
          s3 << r4
        else
          break
        end
      end
      if s3.empty?
        @index = i3
        r3 = nil
      else
        r3 = instantiate_node(SyntaxNode,input, i3...index, s3)
      end
      s1 << r3
    end
    if s1.last
      r1 = instantiate_node(Udb::Eqn::EqnOr,input, i1...index, s1)
      r1.extend(Disjunction1)
    else
      @index = i1
      r1 = nil
    end
    if r1
      r1 = SyntaxNode.new(input, (index-1)...index) if r1 == true
      r0 = r1
    else
      r11 = _nt_conjunction
      if r11
        r11 = SyntaxNode.new(input, (index-1)...index) if r11 == true
        r0 = r11
      else
        @index = i0
        r0 = nil
      end
    end

    node_cache[:disjunction][start_index] = r0

    r0
  end

  module Expression0
    def disjunction
      elements[1]
    end

  end

  module Expression1
    def to_logic_tree(term_map)
      disjunction.to_logic_tree(term_map)
    end
  end

  def _nt_expression
    start_index = index
    if node_cache[:expression].has_key?(index)
      cached = node_cache[:expression][index]
      if cached
        node_cache[:expression][index] = cached = SyntaxNode.new(input, index...(index + 1)) if cached == true
        @index = cached.interval.end
      end
      return cached
    end

    i0, s0 = index, []
    s1, i1 = [], index
    loop do
      r2 = _nt_space
      if r2
        s1 << r2
      else
        break
      end
    end
    r1 = instantiate_node(SyntaxNode,input, i1...index, s1)
    s0 << r1
    if r1
      r3 = _nt_disjunction
      s0 << r3
      if r3
        s4, i4 = [], index
        loop do
          r5 = _nt_space
          if r5
            s4 << r5
          else
            break
          end
        end
        r4 = instantiate_node(SyntaxNode,input, i4...index, s4)
        s0 << r4
      end
    end
    if s0.last
      r0 = instantiate_node(SyntaxNode,input, i0...index, s0)
      r0.extend(Expression0)
      r0.extend(Expression1)
    else
      @index = i0
      r0 = nil
    end

    node_cache[:expression][start_index] = r0

    r0
  end

  def _nt_space
    start_index = index
    if node_cache[:space].has_key?(index)
      cached = node_cache[:space][index]
      if cached
        node_cache[:space][index] = cached = SyntaxNode.new(input, index...(index + 1)) if cached == true
        @index = cached.interval.end
      end
      return cached
    end

    if has_terminal?(@regexps[gr = '\A[
    ]'] ||= Regexp.new(gr), :regexp, index)
      r0 = instantiate_node(SyntaxNode,input, index...(index + 1))
      @index += 1
    else
      terminal_parse_failure('[
      ]')
      r0 = nil
    end

    node_cache[:space][start_index] = r0

    r0
  end

end

class EqnParser < Treetop::Runtime::CompiledParser
  include Eqn
end

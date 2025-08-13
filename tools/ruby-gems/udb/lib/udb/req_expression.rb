# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "sorbet-runtime"
require_relative "obj/extension"

module Udb

  # sorbet needs a forward declration
  class ExtensionVersion; end

  # return type for satisfied_by functions
  class SatisfiedResult < T::Enum
    enums do
      Yes = new
      No = new
      Maybe = new
    end
  end

module AbstractRequirement
  extend T::Sig
  extend T::Helpers
  interface!

  sig { abstract.returns(String) }
  def to_rb; end

  sig { abstract.returns(T::Boolean) }
  def satisfied_by?; end

  sig { abstract.returns(T::Boolean) }
  def empty?; end

  sig { abstract.params(_other: T.untyped).returns(T::Boolean) }
  def compatible?(_other); end

  sig { abstract.returns(T.any(String, T::Hash[String, T.untyped])) }
  def to_h; end

  sig { abstract.params(_hsh: T.any(String, T::Hash[String, T.untyped])).returns(T.any(String, T::Hash[String, T.untyped])) }
  def minimize(_hsh); end

  sig { abstract.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
  def satisfied_by_cfg_arch?(_cfg_arch); end

  sig { abstract.params(_cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
  def could_be_true?(_cfg_arch); end
end

# represents a JSON Schema composition of extension requirements, e.g.:
#
# anyOf:
#   - oneOf:
#     - A
#     - B
#   - C
#
class ExtensionRequirementExpression
  extend T::Sig
  include AbstractRequirement

  # @param composition_hash [Hash] A possibly recursive hash of "allOf", "anyOf", "oneOf", "not", "if"
  sig { params(composition_hash: T.any(String, T::Hash[String, T.untyped]), cfg_arch: ConfiguredArchitecture).void }
  def initialize(composition_hash, cfg_arch)
    unless is_a_condition?(composition_hash)
      raise ArgumentError, "Expecting a JSON schema comdition (got #{composition_hash})"
    end

    @hsh = composition_hash
    @arch = cfg_arch
    @satisfied_by_cfg_arch = T.let({}, T::Hash[String, SatisfiedResult])
  end

  sig { override.returns(T.any(String, T::Hash[String, T.untyped])) }
  def to_h = @hsh

  sig { override.returns(T::Boolean) }
  def empty? = false

  sig { params(ver: T.untyped).returns(T::Boolean) }
  def is_a_version_requirement(ver)
    case ver
    when String
      !(ver =~ RequirementSpec::REQUIREMENT_REGEX).nil?
    when Array
      ver.all? { |v| v =~ RequirementSpec::REQUIREMENT_REGEX }
    else
      false
    end
  end
  private :is_a_version_requirement

  # @return [Boolean] True if the condition is a join of N terms over the same operator
  #
  #  A or B or C   #=> true
  #  A and B       #=> true
  #  A or B and C  #=> false
  sig { returns(T::Boolean) }
  def flat?
    case @hsh
    when String
      true
    when Hash
      @hsh.key?("name") || @hsh[T.must(@hsh.keys.first)].all? { |child| child.is_a?(String) || (child.is_a?(Hash) && child.key?("name")) }
    end
  end

  # @return [TYPES::Or, TYPES::And] The operator for a flat condition
  #                     Only valid if #flat? is true
  sig { returns(Symbol) }
  def flat_op
    case @hsh
    when String
      TYPES::Or
    when Hash
      @hsh.key?("name") ? TYPES::Or : { "allOf" => TYPES::And, "anyOf" => TYPES::Or }[T.must(@hsh.keys.first)]
    end
  end

  # @return [Array<ExtensionRequirement>] The elements of the flat join
  #                                       Only valid if #flat? is true
  sig { returns(T::Array[ExtensionRequirement]) }
  def flat_versions
    case @hsh
    when String
      [ExtensionRequirement.new(@hsh, [], arch: @arch)]
    when Hash
      if @hsh.key?("name")
        if @hsh.key?("version").nil?
          [ExtensionRequirement.new(@hsh["name"], [], arch: @arch)]
        else
          [ExtensionRequirement.new(@hsh["name"], @hsh["version"], arch: @arch)]
        end
      else
        @hsh[T.must(@hsh.keys.first)].map do |r|
          if r.is_a?(String)
            ExtensionRequirement.new(r, [], arch: @arch)
          else
            if r.key?("version").nil?
              ExtensionRequirement.new(r["name"], [], arch: @arch)
            else
              ExtensionRequirement.new(r["name"], r["version"], arch: @arch)
            end
          end
        end
      end
    end
  end

  sig { params(cond: T.any(String, T::Hash[String, T.untyped], T::Array[T.untyped])).returns(T::Boolean) }
  def is_simple_single_extension?(cond)
    case cond
    when String
      true
    when Hash
      # Single extension with name and optional version
      cond.key?("name") && cond.size <= 2 && (cond.size == 1 || cond.key?("version"))
    else
      false
    end
  end

  sig { params(cond: T.any(String, T::Hash[String, T.untyped], T::Array[T.untyped])).returns(T::Boolean) }
  def is_complex_condition_header?(cond)
    # Check if this is a complex condition header (allOf, anyOf, oneOf, etc.)
    cond.is_a?(Hash) && !cond.key?("name")
  end

  sig { params(cond: T.any(String, T::Hash[String, T.untyped], T::Array[T.untyped]), indent: Integer, join: String).returns(String) }
  def to_asciidoc(cond = @hsh, indent = 0, join: "\n")
    # For simple single extension OR complex condition headers at root level (indent = 0), don't show bullets
    use_bullets = !(indent == 0 && (is_simple_single_extension?(cond) || is_complex_condition_header?(cond)))
    bullet_prefix = use_bullets ? "#{'*' * indent} " : ""

    case cond
    when String
      "#{bullet_prefix}#{cond}, version >= #{T.must(@arch.extension(cond)).min_version}"
    when Hash
      if cond.key?("name")
        if cond.key?("version")
          "#{bullet_prefix}#{cond['name']}, version #{cond['version']}#{join}"
        else
          "#{bullet_prefix}#{cond['name']}, version >= #{T.must(@arch.extension(cond['name'])).min_version}#{join}"
        end
      else
        "#{bullet_prefix}#{cond.keys[0]}:#{join}" + to_asciidoc(cond[T.must(cond.keys[0])], indent + 1)
      end
    when Array
      # Arrays represent multiple items, so they need bullets for clarity
      # Use indent=1 at root level to ensure bullets are shown
      array_indent = indent == 0 ? 1 : indent
      cond.map { |e| to_asciidoc(e, array_indent) }.join(join)
    else
      T.absurd(cond)
    end
  end

  sig { params(hsh: T.any(String, T::Hash[String, T.untyped])).returns(T::Boolean) }
  def is_a_condition?(hsh)
    case hsh
    when String
      true
    when Hash
      if hsh.key?("name")
        return false if hsh.size > 2

        if hsh.size > 1
          return false unless hsh.key?("version")

          return false unless is_a_version_requirement(hsh["version"])
        end

      elsif hsh.key?("not")
        return false unless hsh.size == 1

        return is_a_condition?(hsh["not"])

      else
        return false unless hsh.size == 1

        return false unless ["allOf", "anyOf", "oneOf", "if"].include?(hsh.keys[0])

        hsh[T.must(hsh.keys[0])].each do |element|
          return false unless is_a_condition?(element)
        end
      end
    else
      T.absurd(hsh)
    end

    true
  end
  private :is_a_condition?

  # @return [ExtensionRequirement] First requirement found, without considering any boolean operators
  sig { params(req: T.any(String, T::Hash[String, T.untyped], T::Array[T.untyped])).returns(ExtensionRequirement) }
  def first_requirement(req = @hsh)
    case req
    when String
      ExtensionRequirement.new(req, [], arch: @arch)
    when Hash
      if req.key?("name")
        if req["version"].nil?
          ExtensionRequirement.new(req["name"], [], arch: @arch)
        else
          ExtensionRequirement.new(req["name"], req["version"], arch: @arch)
        end
      else
        first_requirement(req[T.must(req.keys[0])])
      end
    when Array
      first_requirement(req[0])
    else
      T.absurd(req)
    end
  end

  # combine all conds into one using AND
  sig { params(conds: T::Array[T.untyped], cfg_arch: ConfiguredArchitecture).void }
  def self.all_of(*conds, cfg_arch:)
    cond = ExtensionRequirementExpression.new({
      "allOf" => conds
    }, cfg_arch)

    ExtensionRequirementExpression.new(cond.minimize, cfg_arch)
  end

  # @return [Object] Schema for this expression, with basic logic minimization
  sig { override.params(hsh: T.any(String, T::Hash[String, T.untyped])).returns(T.any(String, T::Hash[String, T.untyped])) }
  def minimize(hsh = @hsh)
    case hsh
    when Hash
      if hsh.key?("name")
        hsh
      else
        min_ary = key = nil
        if hsh.key?("allOf")
          min_ary = hsh["allOf"].map { |element| minimize(element) }
          key = "allOf"
        elsif hsh.key?("anyOf")
          min_ary = hsh["anyOf"].map { |element| minimize(element) }
          key = "anyOf"
        elsif hsh.key?("oneOf")
          min_ary = hsh["oneOf"].map { |element| minimize(element) }
          key = "oneOf"
        elsif hsh.key?("not")
          min_ary = hsh.dup
          key = "not"
        elsif hsh.key?("if")
          return hsh
        end
        min_ary = min_ary.uniq
        if min_ary.size == 1
          min_ary.first
        else
          { key => min_ary }
        end
      end
    else
      hsh
    end
  end

  sig { params(hsh: T.any(String, T::Hash[String, T.untyped])).returns(String) }
  def to_rb_helper(hsh)
    if hsh.is_a?(Hash)
      if hsh.key?("name")
        if hsh.key?("version")
          if hsh["version"].is_a?(String)
            "(yield ExtensionRequirement.new('#{hsh["name"]}', '#{hsh["version"]}', arch: @arch))"
          elsif hsh["version"].is_a?(Array)
            "(yield ExtensionRequirement.new('#{hsh["name"]}', #{hsh["version"].map { |v| "'#{v}'" }.join(', ')}, arch: @arch))"
          else
            raise "unexpected"
          end
        else
          "(yield ExtensionRequirement.new('#{hsh["name"]}', [], arch: @arch))"
        end
      else
        key = hsh.keys[0]

        case key
        when "allOf"
          rb_str = hsh["allOf"].map { |element| to_rb_helper(element) }.join(' && ')
          "(#{rb_str})"
        when "anyOf"
          rb_str = hsh["anyOf"].map { |element| to_rb_helper(element) }.join(' || ')
          "(#{rb_str})"
        when "oneOf"
          rb_str = hsh["oneOf"].map { |element| to_rb_helper(element) }.join(', ')
          "([#{rb_str}].count(true) == 1)"
        when "not"
          rb_str = to_rb_helper(hsh["not"])
          "(!#{rb_str})"
        when "if"
          cond_rb_str = to_rb_helper(hsh["if"])
          body_rb_str = to_rb_helper(hsh["body"])
          "(#{body_rb_str}) if (#{cond_rb_str})"
        else
          raise "Unexpected"
          # "(yield #{hsh})"
        end
      end
    else
      "(yield ExtensionRequirement.new('#{hsh}', [], arch: @arch))"
    end
  end

  # Given the name of a ruby array +ary_name+ containing the available objects to test,
  # return a string that can be eval'd to determine if the objects in +ary_name+
  # meet the Condition
  #
  # @param ary_name [String] Name of a ruby string in the eval binding
  # @return [Boolean] If the condition is met
  sig { override.returns(String) }
  def to_rb
    to_rb_helper(@hsh)
  end

  class TYPES < T::Enum
    enums do
      Term = new
      Not = new
      And = new
      Or = new
      If = new
    end
  end

  # Abstract syntax tree of the logic
  class LogicNode
    extend T::Sig

    sig { returns(TYPES) }
    attr_accessor :type

    sig { params(type: TYPES, children: T::Array[T.any(LogicNode, ExtensionRequirement)], term_idx: T.nilable(Integer)).void }
    def initialize(type, children, term_idx: nil)
      raise ArgumentError, "Children must be singular" if [TYPES::Term, TYPES::Not].include?(type) && children.size != 1
      raise ArgumentError, "Children must have two elements" if [TYPES::And, TYPES::Or, TYPES::If].include?(type) && children.size != 2

      if type == TYPES::Term
        raise ArgumentError, "Term must be an ExtensionRequirement (found #{children[0]})" unless children[0].is_a?(ExtensionRequirement)
      else
        raise ArgumentError, "All Children must be LogicNodes" unless children.all? { |child| child.is_a?(LogicNode) }
      end

      @type = type
      @children = children

      raise ArgumentError, "Need term_idx" if term_idx.nil? && type == TYPES::Term
      raise ArgumentError, "term_idx isn't an int" if !term_idx.is_a?(Integer) && type == TYPES::Term

      @term_idx = term_idx
    end

    # @return [Array<ExtensionRequirements>] The terms (leafs) of this tree
    sig { returns(T::Array[ExtensionRequirement]) }
    def terms
      @terms ||=
        if @type == TYPES::Term
          [@children[0]]
        else
          @children.map { |child| T.cast(child, LogicNode).terms }.flatten.uniq
        end
    end

    sig { params(term_values: T::Array[ExtensionVersion]).returns(T::Boolean) }
    def eval(term_values)
      if @type == TYPES::Term
        ext_req = T.cast(@children[0], ExtensionRequirement)
        term_value = term_values.find { |tv| tv.name == ext_req.name }
        return false if term_value.nil?

        ext_req.satisfied_by?(term_value)
      elsif @type == TYPES::If
        cond_ext_ret = T.cast(@children[0], LogicNode)
        if cond_ext_ret.eval(term_values)
          T.cast(@children[1], LogicNode).eval(term_values)
        else
          false
        end
      elsif @type == TYPES::Not
        !T.cast(@children[0], LogicNode).eval(term_values)
      elsif @type == TYPES::And
        @children.all? { |child| T.cast(child, LogicNode).eval(term_values) }
      elsif @type == TYPES::Or
        @children.any? { |child| T.cast(child, LogicNode).eval(term_values) }
      end
    end

    sig { returns(String) }
    def to_s
      if @type == TYPES::Term
        "(#{@children[0].to_s})"
      elsif @type == TYPES::Not
        "!#{@children[0]}"
      elsif @type == TYPES::And
        "(#{@children[0]} ^ #{@children[1]})"
      elsif @type == TYPES::Or
        "(#{@children[0]} v #{@children[1]})"
      elsif @type == TYPES::If
        "(#{@children[0]} -> #{@children[1]})"
      else
        T.absurd(@type)
      end
    end
  end

  # given an extension requirement, convert it to a LogicNode term, and optionally expand it to
  # exclude any conflicts and include any implications
  #
  # @param ext_req [ExtensionRequirement] An extension requirement
  # @param expand [Boolean] Whether or not to expand the node to include conflicts / implications
  # @return [LogicNode] Logic tree for ext_req
  sig { params(ext_req: ExtensionRequirement, term_idx: T::Array[Integer], expand: T::Boolean).returns(LogicNode) }
  def ext_req_to_logic_node(ext_req, term_idx, expand: true)
    n = LogicNode.new(TYPES::Term, [ext_req], term_idx: term_idx[0])
    term_idx[0] = T.must(term_idx[0]) + 1
    if expand
      c = ext_req.extension.conflicts_condition
      unless c.empty?
        c = LogicNode.new(TYPES::Not, [to_logic_tree(ext_req.extension.data["conflicts"], term_idx:)])
        n = LogicNode.new(TYPES::And, [c, n])
      end

      ext_req.satisfying_versions.each do |ext_ver|
        ext_ver.implied_by_with_condition.each do |implied_by|
          implying_ext_ver = implied_by[:ext_ver]
          implying_cond = implied_by[:cond]
          implying_ext_req = ExtensionRequirement.new(implying_ext_ver.name, "= #{implying_ext_ver.version_str}", arch: @arch)
          if implying_cond.empty?
            # convert to an ext_req
            n = LogicNode.new(TYPES::Or, [n, ext_req_to_logic_node(implying_ext_req, term_idx)])
          else
            # conditional
            # convert to an ext_req
            cond_node = implying_cond.to_logic_tree(term_idx:, expand:)
            cond = LogicNode.new(TYPES::If, [cond_node, ext_req_to_logic_node(implying_ext_req, term_idx)])
            n = LogicNode.new(TYPES::Or, [n, cond])
          end
        end
      end
    end

    n
  end

  # convert the YAML representation of an Extension Requirement Expression into
  # a tree of LogicNodes.
  # Also expands any Extension Requirement to include its conflicts / implications
  sig { params(hsh: T.any(String, T::Hash[String, T.untyped]), term_idx: T::Array[Integer], expand: T::Boolean).returns(LogicNode) }
  def to_logic_tree(hsh = @hsh, term_idx: [0], expand: true)
    root = T.let(nil, T.nilable(LogicNode))

    if hsh.is_a?(Hash)
      if hsh.key?("name")
        if hsh.key?("version")
          if hsh["version"].is_a?(String)
            ext_req_to_logic_node(ExtensionRequirement.new(hsh["name"], hsh["version"], arch: @arch), term_idx, expand:)
          elsif hsh["version"].is_a?(Array)
            ext_req_to_logic_node(ExtensionRequirement.new(hsh["name"], hsh["version"].map { |v| "'#{v}'" }.join(', '), arch: @arch), term_idx, expand:)
          else
            raise "unexpected"
          end
        else
          ext_req_to_logic_node(ExtensionRequirement.new(hsh["name"], [], arch: @arch), term_idx, expand:)
        end
      else
        key = hsh.keys[0]

        case key
        when "allOf"
          raise "unexpected" unless hsh["allOf"].is_a?(Array) && hsh["allOf"].size > 1

          root = LogicNode.new(TYPES::And, [to_logic_tree(hsh["allOf"][0], term_idx:, expand:), to_logic_tree(hsh["allOf"][1], term_idx:, expand:)])
          (2...hsh["allOf"].size).each do |i|
            root = LogicNode.new(TYPES::And, [root, to_logic_tree(hsh["allOf"][i], term_idx:, expand:)])
          end
          root
        when "anyOf"
          raise "unexpected: #{hsh}" unless hsh["anyOf"].is_a?(Array) && hsh["anyOf"].size > 1

          root = LogicNode.new(TYPES::Or, [to_logic_tree(hsh["anyOf"][0], term_idx:, expand:), to_logic_tree(hsh["anyOf"][1], term_idx:, expand:)])
          (2...hsh["anyOf"].size).each do |i|
            root = LogicNode.new(TYPES::Or, [root, to_logic_tree(hsh["anyOf"][i], term_idx:, expand:)])
          end
          root
        when "if"
          raise "unexpected" unless hsh.keys.size == 2 && hsh.keys[1] == "then"

          cond = to_logic_tree(hsh["if"], term_idx:, expand:)
          body = to_logic_tree(hsh["then"], term_idx:, expand:)
          LogicNode.new(TYPES::If, [cond, body])
        when "oneOf"
          # expand oneOf into AND
          roots = T.let([], T::Array[LogicNode])

          if hsh["oneOf"].size < 2
            to_logic_tree(hsh["oneOf"][0], term_idx:, expand:)
          else
            hsh["oneOf"].size.times do |k|
              root =
                if k.zero?
                  LogicNode.new(TYPES::And, [to_logic_tree(hsh["oneOf"][0], term_idx:, expand:), LogicNode.new(TYPES::Not, [to_logic_tree(hsh["oneOf"][1], term_idx:, expand:)])])
                elsif k == 1
                  LogicNode.new(TYPES::And, [LogicNode.new(TYPES::Not, [to_logic_tree(hsh["oneOf"][0], term_idx:, expand:)]), to_logic_tree(hsh["oneOf"][1], term_idx:, expand:)])
                else
                  LogicNode.new(TYPES::And, [LogicNode.new(TYPES::Not, [to_logic_tree(hsh["oneOf"][0], term_idx:, expand:)]), LogicNode.new(TYPES::Not, [to_logic_tree(hsh["oneOf"][1], term_idx:, expand:)])])
                end
              (2...hsh["oneOf"].size).each do |i|
                root =
                  if k == i
                    LogicNode.new(TYPES::And, [root, to_logic_tree(hsh["oneOf"][i], term_idx:, expand:)])
                  else
                    LogicNode.new(TYPES::And, [root, LogicNode.new(TYPES::Not, [to_logic_tree(hsh["oneOf"][i], term_idx:, expand:)])])
                  end
               end
              roots << root
            end

            root = LogicNode.new(TYPES::Or, [T.must(roots[0]), T.must(roots[1])])
            (2...roots.size).each do |i|
              root = LogicNode.new(TYPES::Or, [root, T.must(roots[i])])
            end
            root
          end
        when "not"
          LogicNode.new(TYPES::Not, [to_logic_tree(hsh["not"], term_idx:, expand:)])
        else
          raise "Unexpected"
        end
      end
    else
      ext_req_to_logic_node(ExtensionRequirement.new(hsh, [], arch: @arch), term_idx, expand:)
    end
  end

  sig { params(extension_versions: T::Array[T::Array[ExtensionVersion]]).returns(T::Array[T::Array[ExtensionVersion]])}
  def combos_for(extension_versions)
    ncombos = extension_versions.reduce(1) { |prod, vers| prod * (vers.size + 1) }
    combos = T.let([], T::Array[T::Array[ExtensionVersion]])
    ncombos.times do |i|
      combos << []
      extension_versions.size.times do |j|
        m = (T.must(extension_versions[j]).size + 1)
        d = j.zero? ? 1 : T.must(extension_versions[j..0]).reduce(1) { |prod, vers| prod * (vers.size + 1) }

        if (i / d) % m < T.must(extension_versions[j]).size
          T.must(combos.last) << T.must(T.must(extension_versions[j])[(i / d) % m])
        end
      end
    end
    # get rid of any combos that can't happen because of extension conflicts
    combos.reject do |combo|
      combo.any? { |ext_ver1| (combo - [ext_ver1]).any? { |ext_ver2| ext_ver1.conflicts_condition.satisfied_by? { |ext_req| ext_req.satisfied_by?(ext_ver2) } } }
    end
  end

  # @param other [ExtensionRequirementExpression] Another condition
  # @return [Boolean] if it's possible for both to be simultaneously true
  sig { override.params(other: ExtensionRequirementExpression).returns(T::Boolean) }
  def compatible?(other)
    tree1 = to_logic_tree(@hsh)
    tree2 = to_logic_tree(other.to_h)

    extensions = (tree1.terms + tree2.terms).map(&:extension).uniq

    extension_versions = extensions.map(&:versions)

    combos = combos_for(extension_versions)
    combos.each do |combo|
      return true if tree1.eval(combo) && tree2.eval(combo)
    end

    # there is no combination in which both self and other can be true
    false
  end

  # @example See if a string satisfies
  #   cond = { "anyOf" => ["A", "B", "C"] }
  #   string = "A"
  #   cond.satisfied_by? { |endpoint| endpoint == string } #=> true
  #   string = "D"
  #   cond.satisfied_by? { |endpoint| endpoint == string } #=> false
  #
  # @example See if an array satisfies
  #   cond = { "allOf" => ["A", "B", "C"] }
  #   ary = ["A", "B", "C", "D"]
  #   cond.satisfied_by? { |endpoint| ary.include?(endpoint) } #=> true
  #   ary = ["A", "B"]
  #   cond.satisfied_by? { |endpoint| ary.include?(endpoint) } #=> false
  #
  # @yieldparam obj [Object] An endpoint in the condition
  # @yieldreturn [Boolean] Whether or not +obj+ is what you are looking for
  # @return [Boolean] Whether or not the entire condition is satisfied
  sig { override.params(block: T.proc.params(arg0: ExtensionRequirement).returns(T::Boolean)).returns(T::Boolean) }
  def satisfied_by?(&block)
    raise ArgumentError, "Expecting one argument to block" unless block.arity == 1

    eval to_rb
  end

  sig { override.params(cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
  def could_be_true?(cfg_arch)
    r = satisfied_by_cfg_arch?(cfg_arch)
    r == SatisfiedResult::Yes || r == SatisfiedResult::Maybe
  end

  sig { override.params(cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
  def satisfied_by_cfg_arch?(cfg_arch)
    @satisfied_by_cfg_arch[cfg_arch.name] ||=
      if cfg_arch.fully_configured?
        if satisfied_by? { |ext_req| cfg_arch.transitive_implemented_extension_versions.any? { |ev| ext_req.satisfied_by?(ev) } }
          SatisfiedResult::Yes
        else
          SatisfiedResult::No
        end
      elsif cfg_arch.partially_configured?
        if satisfied_by? { |cond_ext_req| cfg_arch.mandatory_extension_reqs.any? { |cfg_ext_req| cond_ext_req.satisfied_by?(cfg_ext_req) }  }
          SatisfiedResult::Yes
        elsif satisfied_by? { |cond_ext_req| cfg_arch.possible_extension_versions.any? { |cfg_ext_ver| cond_ext_req.satisfied_by?(cfg_ext_ver) }  }
          SatisfiedResult::Maybe
        else
          SatisfiedResult::No
        end
      else
        # unconfig. everything flies
        SatisfiedResult::Yes
      end
  end

  # returns true if the list of extension requirements *can* satisfy the condition.
  #
  # note that it is possible that the condition might not be satisfied for all possible
  # extension versions implied by ext_req_list. For example, this condition:
  #
  #  { "name": "A", "version": ">= 1.2" }
  #
  # Will be "satisfied by":
  #
  #  { "name": "A", "version": ">= 1.1" }
  #
  # because A version 1.2 fits both requirements
  #
  sig { params(ext_req_list: T::Array[ExtensionRequirement]).returns(T::Boolean) }
  def could_be_satisfied_by_ext_reqs?(ext_req_list)
    satisfied_by? do |cond_ext_req|
      ext_req_list.any? do |ext_req|
        ext_req.satisfying_versions.any? do |ext_ver|
          cond_ext_req.satisfied_by?(ext_ver)
        end
      end
    end
  end

  # yes if:
  #   - ext_ver affects this condition
  #   - it is is possible for this condition to be true is ext_ver is implemented
  sig { params(ext_ver: ExtensionVersion).returns(T::Boolean) }
  def possibly_satisfied_by?(ext_ver)
    logic_tree = to_logic_tree

    return false unless logic_tree.terms.any? { |ext_req| ext_req.satisfying_versions.include?(ext_ver) }

    # ok, so ext_ver affects this condition
    # is it possible to be true with ext_ver implemented?
    extensions = logic_tree.terms.map(&:extension).uniq

    extension_versions = extensions.map(&:versions)

    combos = combos_for(extension_versions)
    combos.any? do |combo|
      # replace ext_ver, since it doesn't change
      logic_tree.eval(combo.map { |ev| ev.name == ext_ver.name ? ext_ver : ev })
    end
  end
end

class AlwaysTrueExtensionRequirementExpression
  extend T::Sig
  include AbstractRequirement

  sig { override.returns(String) }
  def to_rb = "true"

  sig { override.returns(T::Boolean) }
  def satisfied_by? = true

  sig { override.returns(T::Boolean) }
  def empty? = true

  sig { override.params(_other: T.untyped).returns(T::Boolean) }
  def compatible?(_other) = true

  sig { override.returns(T.any(String, T::Hash[String, T.untyped])) }
  def to_h = {}

  sig { override.params(_hsh: T.any(String, T::Hash[String, T.untyped])).returns(T.any(String, T::Hash[String, T.untyped])) }
  def minimize(_hsh) = {}

  sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
  def satisfied_by_cfg_arch?(_cfg_arch) = SatisfiedResult::Yes

  sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
  def could_be_true?(_cfg_arch) = true
end

class AlwaysFalseExtensionRequirementExpression
  extend T::Sig
  include AbstractRequirement

  sig { override.returns(String) }
  def to_rb = "false"

  sig { override.returns(T::Boolean) }
  def satisfied_by? = false

  sig { override.returns(T::Boolean) }
  def empty? = true

  sig { override.params(_other: T.untyped).returns(T::Boolean) }
  def compatible?(_other) = false

  sig { override.returns(T.any(String, T::Hash[String, T.untyped])) }
  def to_h = {}

  sig { override.params(_hsh: T.any(String, T::Hash[String, T.untyped])).returns(T.any(String, T::Hash[String, T.untyped])) }
  def minimize(_hsh) = {}

  sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(SatisfiedResult) }
  def satisfied_by_cfg_arch?(_cfg_arch) = SatisfiedResult::No

  sig { override.params(_cfg_arch: ConfiguredArchitecture).returns(T::Boolean) }
  def could_be_true?(_cfg_arch) = false
end

# represents an `implies:` entry for an extension
# which is a list of extension versions, zero or more of which
# may be conditional (via an ExtensionRequirementExpression)
class ConditionalExtensionVersionList
  extend T::Sig

  class ConditionalExtensionVersion < T::Struct
    prop :ext_ver, ExtensionVersion
    prop :cond, AbstractRequirement
  end

  YamlExtensionWithVersion = T.type_alias { T::Hash[String, String] }
  sig { params(data: T.any(NilClass, T::Array[YamlExtensionWithVersion], T::Hash[String, T.any(String, T::Hash[String, String])]), cfg_arch: ConfiguredArchitecture).void }
  def initialize(data, cfg_arch)
    @data = data
    @cfg_arch = cfg_arch
  end

  sig { returns(T::Boolean) }
  def empty? = @data.nil? || @data.empty?

  sig { returns(Integer) }
  def size = empty? ? 0 : eval.size

  sig { params(block: T.proc.params(arg0: ConditionalExtensionVersion).void).void }
  def each(&block)
    eval.each(&block)
  end

  sig { params(block: T.proc.params(arg0: ConditionalExtensionVersion).returns(T.untyped)).returns(T::Array[T.untyped]) }
  def map(&block)
    eval.map(&block)
  end

  # Returns array of ExtensionVersions, along with a condition under which it is in the list
  #
  # @example
  #   list.eval #=> [{ :ext_ver => ExtensionVersion.new(:A, "2.1.0"), :cond => ExtensionRequirementExpression.new(...) }]
  #
  # @return [Array<Hash{Symbol => ExtensionVersion, ExtensionRequirementExpression}>]
  #           The extension versions in the list after evaluation, and the condition under which it applies
  sig { returns(T::Array[ConditionalExtensionVersion]) }
  def eval
    result = []
    data = T.let({}, T::Hash[String, String])
    if @data.is_a?(Hash)
      data = T.cast(@data, T::Hash[String, String])
      result << ConditionalExtensionVersion.new(ext_ver: entry_to_ext_ver(data), cond: AlwaysTrueExtensionRequirementExpression.new)
    else
      T.must(@data).each do |elem|
        if elem.keys[0] == "if"
          cond_expr = ExtensionRequirementExpression.new(T.must(elem["if"]), @cfg_arch)
          data = T.cast(elem["then"], T::Hash[String, String])
          result << ConditionalExtensionVersion.new(ext_ver: entry_to_ext_ver(data), cond: cond_expr)
        else
          result << ConditionalExtensionVersion.new(ext_ver: entry_to_ext_ver(elem), cond: AlwaysTrueExtensionRequirementExpression.new)
        end
      end
    end
    result
  end
  alias to_a eval

  sig { params(entry: T::Hash[String, String]).returns(ExtensionVersion) }
  def entry_to_ext_ver(entry)
    ExtensionVersion.new(T.must(entry["name"]), T.must(entry["version"]), @cfg_arch, fail_if_version_does_not_exist: true)
  end
  private :entry_to_ext_ver
end

end

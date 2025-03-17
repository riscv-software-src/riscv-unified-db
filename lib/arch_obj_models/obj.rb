# frozen_string_literal: true

# base for any object representation of the Architecture Definition
# does two things:
#
#  1. Makes the raw data for the object accessible via []
#     For example, given:
#        data = {
#          'name' => 'mstatus',
#          'address' => 0x320,
#          ...
#        }
#
#     obj = DatabaseObject.new(data)
#     obj['name']    # 'mstatus'
#     obj['address'] # 0x320
#
#  2. Provides accessor methods for the data properties
#     Given the same example above, the following works:
#
#     obj.name       # 'mstatus'
#     obj.address    # 0x320
#
# Subclasses may override the accessors when a more complex data structure
# is warranted, e.g., the CSR Field 'alias' returns a CsrFieldAlias object
# instead of a simple string
class DatabaseObject
  # Exception raised when there is a problem with a schema file
  class SchemaError < ::StandardError
    # result from JsonSchemer.validate
    attr_reader :result

    def initialize(result)
      if result.is_a?(Enumerator)
        super(result.to_a.map { |e| "At #{e['schema_pointer']}: #{e['type']}" })
      else
        super(result["error"])
      end
      @result = result
    end
  end

  # exception raised when an object does not validate against its schema
  class SchemaValidationError < ::StandardError

    # result from JsonSchemer.validate
    attr_reader :result

    # create a new SchemaValidationError
    #
    # @param result [JsonSchemer::Result] JsonSchemer result
    def initialize(path, result)
      msg = "While validating #{path}:\n\n"
      nerrors = result.count
      msg << "#{nerrors} error(s) during validations\n\n"
      result.to_a.each do |r|
        msg <<
          if r["type"] == "required" && !r.dig("details", "missing_keys").nil?
            "    At '#{r['data_pointer']}': Missing required parameter(s) '#{r['details']['missing_keys']}'\n"
          elsif r["type"] == "schema"
            if r["schema_pointer"] == "/additionalProperties"
              "    At #{r['data_pointer']}, there is an unallowed additional key\n"
            else
              "    At #{r['data_pointer']}, endpoint is an invalid key\n"
            end
          elsif r["type"] == "enum"
            "    At #{r['data_pointer']}, '#{r['data']}' is not a valid enum value (#{r['schema']['enum']})\n"
          elsif r["type"] == "maxProperties"
            "    Maximum number of properties exceeded\n"
          elsif r["type"] == "object"
            "    At #{r['data_pointer']}, Expecting object, got #{r['data']}\n"
          elsif r["type"] == "pattern"
            "    At #{r['data_pointer']}, RegEx validation failed; '#{r['data']}' does not match '#{r['schema']['pattern']}'\n"
          elsif r["type"] == "integer"
            "    At #{r['data_pointer']}, '#{r['data']}' is not a integer\n"
          elsif r["type"] == "array"
            "    At #{r['data_pointer']}, '#{r['data']}' is not a array\n"
          elsif r["type"] == "oneOf"
            "    At #{r['data_pointer']}, '#{r['data']}' matches more than one of #{r['schema']['oneOf']}\n"
          elsif r["type"] == "const"
            "    At #{r['data_pointer']}, '#{r['data']}' does not match required value '#{r['schema']['const']}'\n"
          else
            "    #{r}\n\n"
          end
      end
      msg << "\n"
      # msg << result.to_a.to_s
      super(msg)
      @result = result
    end
  end

  attr_reader :data, :data_path, :name, :long_name, :description

  # @return [Architecture] If only a specification (no config) is known
  # @return [ConfiguredArchitecture] If a specification and config is known
  # @return [nil] If neither is known
  attr_reader :arch       # Use when Architecture class is sufficient

  # @return [ConfiguredArchitecture] If a specification and config is known
  # @return [nil] Otherwise
  attr_reader :cfg_arch   # Use when extra stuff provided by ConfiguredArchitecture is required

  def kind = @data["kind"]

  @@schemas ||= {}
  @@schema_ref_resolver ||= proc do |pattern|
    if pattern.to_s =~ /^http/
      JSON.parse(Net::HTTP.get(pattern))
    else
      JSON.load_file($root / "schemas" / pattern.to_s)
    end
  end

  # validate the data against it's schema
  # @raise [SchemaError] if the data is invalid
  def validate
    schemas = @@schemas
    ref_resolver = @@schema_ref_resolver

    if @data.key?("$schema")
      schema_path = data["$schema"]
      schema_file, obj_path = schema_path.split("#")
      schema =
        if schemas.key?(schema_file)
          schemas[schema_file]
        else
          schemas[schema_file] = JSONSchemer.schema(
            File.read("#{$root}/schemas/#{schema_file}"),
            regexp_resolver: "ecma",
            ref_resolver:,
            insert_property_defaults: true
          )
          raise SchemaError, schemas[schema_file].validate_schema unless schemas[schema_file].valid_schema?

          schemas[schema_file]
        end

      unless obj_path.nil?
        obj_path_parts = obj_path.split("/")[1..]

        obj_path_parts.each do |k|
          schema = schema.fetch(k)
        end
      end

      # convert through JSON to handle anything supported in YAML but not JSON
      # (e.g., integer object keys will be converted to strings)
      jsonified_obj = JSON.parse(JSON.generate(@data))

      raise "Nothing there?" if jsonified_obj.nil?

      raise SchemaValidationError.new(@data_path, schema.validate(jsonified_obj)) unless schema.valid?(jsonified_obj)
    else
      warn "No $schema for #{@data_path}"
    end
  end

  # clone this, and set the arch at the same time
  # @return [ExtensionRequirement] The new object
  def clone(arch: nil)
    obj = super()
    obj.instance_variable_set(:@arch, arch)
    obj
  end

  def <=>(other)
    name <=> other.name
  end

  # @return [String] Source file that data for this object can be attributed to
  # @return [nil] if the source isn't known
  def __source
    @data["$source"]
  end

  # The raw content of definedBy in the data.
  # @note Generally, you should prefer to use {#defined_by_condition}, etc. from Ruby
  #
  # @return [String] An extension name
  # @return [Array(String, Number)] An extension name and versions
  # @return [Array<*>] A list of extension names or extension names and versions
  def definedBy
    @data["definedBy"]
  end

  # @param data [Hash<String,Object>] Hash with fields to be added
  # @param data_path [Pathname] Path to the data file
  def initialize(data, data_path, arch: nil)
    raise ArgumentError, "Bad data" unless data.is_a?(Hash)

    @data = data
    @data_path = data_path
    if arch.is_a?(ConfiguredArchitecture)
      @cfg_arch = arch
    end
    @arch = arch
    @name = data["name"]
    @long_name = data["long_name"]
    @description = data["description"]

    @sem = Concurrent::Semaphore.new(1)
    @cache = Concurrent::Hash.new
  end

  def inspect
    self.class.name
  end

  # make the underlying YAML description available with []
  extend Forwardable
  def_delegator :@data, :[]

  # @return [Array<String>] List of keys added by this DatabaseObject
  def keys = @data.keys

  # @param k (see Hash#key?)
  # @return (see Hash#key?)
  def key?(k) = @data.key?(k)

  def defer(fn_name, &block)
    cache_value = @cache[fn_name]
    return cache_value unless cache_value.nil?

    raise "Missing block" unless block_given?

    @cache[fn_name] ||= yield
  end

  # @return [ExtensionRequirementExpression] Extension(s) that define the instruction. If *any* requirement is met, the instruction is defined.
  def defined_by_condition
    @defined_by_condition ||=
      begin
        raise "ERROR: definedBy is nul for #{name}" if @data["definedBy"].nil?

        ExtensionRequirementExpression.new(@data["definedBy"], @cfg_arch)
      end
  end

  # @return [String] Name of an extension that "primarily" defines the object (i.e., is the first in a list)
  def primary_defined_by
    defined_by_condition.first_requirement
  end

  # @return [Integer] THe source line number of +path+ in the YAML file
  # @param path [Array<String>] Path to the scalar you want.
  # @example
  #   yaml = <<~YAML
  #     misa:
  #       sw_read(): ...
  #       fields:
  #         A:
  #           type(): ...
  #   YAML
  #   misa_csr.source_line("sw_read()")  #=> 2
  #   mis_csr.source_line("fields", "A", "type()") #=> 5
  def source_line(*path)

    # find the line number of this operation() in the *original* file
    yaml_filename = @data["$source"]
    raise "No $source for #{name}" if yaml_filename.nil?
    line = nil
    path_idx = 0
    Psych.parse_stream(File.read(yaml_filename), filename: yaml_filename) do |doc|
      mapping = doc.children[0]
      data =
        if mapping.children.size == 2
          mapping.children[1]
        else
          mapping
        end
      while path_idx < path.size
        idx = 0
        while idx < data.children.size
          if data.children[idx].value == path[path_idx]
            if path_idx == path.size - 1
              line = data.children[idx + 1].start_line
              if data.children[idx + 1].style == Psych::Nodes::Scalar::LITERAL
                line += 1 # the string actually begins on the next line
              end
              return line
            else
              data = data.children[idx + 1]
              path_idx += 1
              break
            end
          end
          idx += 2
        end
      end
    end
    raise "Didn't find key '#{path}' in #{@data['$source']}"
  end
end

# A company description
class Company
  def initialize(data)
    @data = data
  end

  # @return [String] Company name
  def name = @data["name"]

  # @return [String] Company website
  def url = @data["url"]
end

# License information
class License
  def initialize(data)
    @data = data
  end

  # @return [String] License name
  def name = @data["name"]

  # @return [String] License website
  # @return [nil] if there is no website for the license
  def url = @data["url"]

  # @return [String] Text of the license
  def text
    if !@data["text_url"].nil?
      Net::HTTP.get(URI(@data["text_url"]))
    else
      @data["text"]
    end
  end
end

# Personal information about a contributor
class Person
  include Comparable

  # @return [String] Person's name
  def name = @data["name"]

  # @return [String] Email address
  # @return [nil] if email address is not known
  def email = @data["email"]

  # @return [String] Company the person works for
  # @return [nil] if the company is not known, or if the person is an individual contributor
  def company = @data["company"]

  def initialize(data)
    @data = data
  end

  def <=>(other)
    raise ArgumentError, "Person is only comparable to Person (not #{other.class.name})" unless other.is_a?(Person)

    name <=> other.name
  end
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
  # @param composition_hash [Hash] A possibly recursive hash of "allOf", "anyOf", "oneOf", "not"
  def initialize(composition_hash, cfg_arch)
    raise ArgumentError, "composition_hash is nil" if composition_hash.nil?

    unless is_a_condition?(composition_hash)
      raise ArgumentError, "Expecting a JSON schema comdition (got #{composition_hash})"
    end

    @hsh = composition_hash
    @arch = cfg_arch
  end

  def to_h = @hsh

  def empty? = false

  def is_a_version_requirement(ver)
    case ver
    when String
      ver =~ RequirementSpec::REQUIREMENT_REGEX
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
  def flat?
    case @hsh
    when String
      true
    when Hash
      @hsh.key?("name") || @hsh[@hsh.keys.first].all? { |child| child.is_a?(String) || (child.is_a?(Hash) && child.key?("name")) }
    else
      raise "unexpected"
    end
  end

  # @return [:or, :and] The operator for a flat condition
  #                     Only valid if #flat? is true
  def flat_op
    case @hsh
    when String
      :or
    when Hash
      @hsh.key?("name") ? :or : { "allOf" => :and, "anyOf" => :or }[@hsh.keys.first]
    else
      raise "unexpected"
    end
  end

  # @return [Array<ExtensionRequirement>] The elements of the flat join
  #                                       Only valid if #flat? is true
  def flat_versions
    case @hsh
    when String
      [ExtensionRequirement.new(@hsh, arch: @arch)]
    when Hash
      if @hsh.key?("name")
        if @hsh.key?("version").nil?
          [ExtensionRequirement.new(@hsh["name"], arch: @arch)]
        else
          [ExtensionRequirement.new(@hsh["name"], @hsh["version"], arch: @arch)]
        end
      else
        @hsh[@hsh.keys.first].map do |r|
          if r.is_a?(String)
            ExtensionRequirement.new(r, arch: @arch)
          else
            if r.key?("version").nil?
              ExtensionRequirement.new(r["name"], arch: @arch)
            else
              ExtensionRequirement.new(r["name"], r["version"], arch: @arch)
            end
          end
        end
      end
    else
      raise "unexpected"
    end
  end

  def to_asciidoc(cond = @hsh, indent = 0)
    case cond
    when String
      "#{'*' * indent}* #{cond}, version >= #{@arch.extension(cond).min_version}"
    when Hash
      if cond.key?("name")
        if cond.key?("version")
          "#{'*' * indent}* #{cond['name']}, version #{cond['version']}\n"
        else
          "#{'*' * indent}* #{cond['name']}, version >= #{@arch.extension(cond['name']).min_version}\n"
        end
      else
        "#{'*' * indent}* #{cond.keys[0]}:\n" + to_asciidoc(cond[cond.keys[0]], indent + 2)
      end
    when Array
      cond.map { |e| to_asciidoc(e, indent) }.join("\n")
    else
      raise "Unknown condition type: #{cond}"
    end
  end

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

        return false unless ["allOf", "anyOf", "oneOf"].include?(hsh.keys[0])

        hsh[hsh.keys[0]].each do |element|
          return false unless is_a_condition?(element)
        end
      end
    else
      raise "unexpected #{hsh.class.name} #{hsh} #{@hsh}"
    end

    true
  end
  private :is_a_condition?

  # @return [ExtensionRequirement] First requirement found, without considering any boolean operators
  def first_requirement(req = @hsh)
    case req
    when String
      ExtensionRequirement.new(req, arch: @arch)
    when Hash
      if req.key?("name")
        if req["version"].nil?
          ExtensionRequirement.new(req["name"], arch: @arch)
        else
          ExtensionRequirement.new(req["name"], req["version"], arch: @arch)
        end
      else
        first_requirement(req[req.keys[0]])
      end
    when Array
      first_requirement(req[0])
    else
      raise "unexpected"
    end
  end

  # combine all conds into one using AND
  def self.all_of(*conds, cfg_arch:)
    cond = ExtensionRequirementExpression.new({
      "allOf" => conds
    }, cfg_arch)

    ExtensionRequirementExpression.new(cond.minimize, cfg_arch)
  end

  # @return [Object] Schema for this expression, with basic logic minimization
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
          "(yield ExtensionRequirement.new('#{hsh["name"]}', arch: @arch))"
        end
      else
        key = hsh.keys[0]

        case key
        when "allOf"
          rb_str = hsh[key].map { |element| to_rb_helper(element) }.join(' && ')
          "(#{rb_str})"
        when "anyOf"
          rb_str = hsh[key].map { |element| to_rb_helper(element) }.join(' || ')
          "(#{rb_str})"
        when "oneOf"
          rb_str = hsh[key].map { |element| to_rb_helper(element) }.join(', ')
          "([#{rb_str}].count(true) == 1)"
        when "not"
          rb_str = to_rb_helper(hsh[key])
          "(!#{rb_str})"
        else
          raise "Unexpected"
          "(yield #{hsh})"
        end
      end
    else
      "(yield ExtensionRequirement.new('#{hsh}', arch: @arch))"
    end
  end

  # Given the name of a ruby array +ary_name+ containing the available objects to test,
  # return a string that can be eval'd to determine if the objects in +ary_name+
  # meet the Condition
  #
  # @param ary_name [String] Name of a ruby string in the eval binding
  # @return [Boolean] If the condition is met
  def to_rb
    to_rb_helper(@hsh)
  end

  class LogicNode
    attr_accessor :type

    TYPES = [ :term, :not, :and, :or ]

    def initialize(type, children, term_idx: nil)
      raise ArgumentError, "Bad type" unless TYPES.include?(type)
      raise ArgumentError, "Children must be an array" unless children.is_a?(Array)

      raise ArgumentError, "Children must be singular" if [:term, :not].include?(type) && children.size != 1

      if type == :term
        raise ArgumentError, "Term must be an ExtensionRequirement" unless children[0].is_a?(ExtensionRequirement)
      else
        raise ArgumentError, "All Children must be LogicNodes" unless children.all? { |child| child.is_a?(LogicNode) }
      end

      @type = type
      @children = children

      raise ArgumentError, "Need term_idx" if term_idx.nil? && type == :term
      raise ArgumentError, "term_idx isn't an int" if !term_idx.is_a?(Integer) && type == :term

      @term_idx = term_idx
    end

    # @return [Array<ExtensionRequirements>] The terms (leafs) of this tree
    def terms
      @terms ||=
        if @type == :term
          [@children[0]]
        else
          @children.map(&:terms).flatten.uniq
        end
    end

    def eval(term_values)
      if @type == :term
        ext_ret = @children[0]
        term_value = term_values.find { |term_value| term_value.name == ext_ret.name }
        @children[0].satisfied_by?(term_value)
      elsif @type == :not
        !@children[0].eval(term_values)
      elsif @type == :and
        @children.all? { |child| child.eval(term_values) }
      elsif @type == :or
        @children.any? { |child| child.eval(term_values) }
      end
    end
  end

  def ext_req_to_logic_node(ext_req, term_idx)
    n = LogicNode.new(:term, [ext_req], term_idx: term_idx[0])
    term_idx[0] += 1
    c = ext_req.extension.conflicts_condition
    unless c.empty?
      c = LogicNode.new(:not, [to_logic_tree(ext_req.extension.data["conflicts"], term_idx:)])
      n = LogicNode.new(:and, [c, n])
    end

    ext_req.satisfying_versions.each do |ext_ver|
      ext_ver.implications.each do |implied_ext_ver|
        # convert to an ext_req
        implied_ext_req = ExtensionRequirement.new(implied_ext_ver.name, "= #{implied_ext_ver.version_str}", arch: @arch)
        n = LogicNode.new(:or, [n, ext_req_to_logic_node(implied_ext_req, term_idx)])
      end
    end

    n
  end

  # convert the YAML representation of an Extension Requirement Expression into
  # a tree of LogicNodes.
  # Also expands any Extension Requirement to include its conflicts / implications
  def to_logic_tree(hsh = @hsh, term_idx: [0])
    if hsh.is_a?(Hash)
      if hsh.key?("name")
        if hsh.key?("version")
          if hsh["version"].is_a?(String)
            ext_req_to_logic_node(ExtensionRequirement.new(hsh["name"], hsh["version"], arch: @arch), term_idx)
          elsif hsh["version"].is_a?(Array)
            ext_req_to_logic_node(ExtensionRequirement.new(hsh["name"], hsh["version"].map { |v| "'#{v}'" }.join(', '), arch: @arch), term_idx)
          else
            raise "unexpected"
          end
        else
          ext_req_to_logic_node(ExtensionRequirement.new(hsh["name"], arch: @arch), term_idx)
        end
      else
        key = hsh.keys[0]

        case key
        when "allOf"
          raise "unexpected" unless hsh[key].is_a?(Array) && hsh[key].size > 1

          root = LogicNode.new(:and, [to_logic_tree(hsh[key][0], term_idx:), to_logic_tree(hsh[key][1], term_idx:)])
          (2...hsh[key].size).each do |i|
            root = LogicNode.new(:and, [root, to_logic_tree(hsh[key][i], term_idx:)])
          end
          root
        when "anyOf"
          raise "unexpected" unless hsh[key].is_a?(Array) && hsh[key].size > 1

          root = LogicNode.new(:or, [to_logic_tree(hsh[key][0], term_idx:), to_logic_tree(hsh[key][1], term_idx:)])
          (2...hsh[key].size).each do |i|
            root = LogicNode.new(:or, [root, to_logic_tree(hsh[key][i], term_idx:)])
          end
          root
        when "oneOf"
          # expand oneOf into AND
          roots = []
          hsh[key].size.times do |k|
            root =
              if k.zero?
                LogicNode.new(:and, [to_logic_tree(hsh[key][0], term_idx:), LogicNode.new(:not, [to_logic_tree(hsh[key][1], term_idx:)])])
              elsif k == 1
                LogicNode.new(:and, [LogicNode.new(:not, [to_logic_tree(hsh[key][0], term_idx:)]), to_logic_tree(hsh[key][1], term_idx:)])
              else
                LogicNode.new(:and, [LogicNode.new(:not, [to_logic_tree(hsh[key][0], term_idx:)]), LogicNode.new(:not, [to_logic_tree(hsh[key][1], term_idx:)])])
              end
            (2...hsh[key].size).each do |i|
              root =
                if k == i
                  LogicNode.new(:and, [root, to_logic_tree(hsh[key][i], term_idx:)])
                else
                  LogicNode.new(:and, [root, LogicNode.new(:not, [to_logic_tree(hsh[key][i], term_idx:)])])
                end
             end
            roots << root
          end
          root = LogicNode.new(:or, [roots[0], roots[1]])
          (2...roots.size).each do |i|
            root = LogicNode.new(:or, [root, roots[i]])
          end
          root
        when "not"
          LogicNode.new(:not, [to_logic_tree(hsh[key], term_idx:)])
        else
          raise "Unexpected"
        end
      end
    else
      ext_req_to_logic_node(ExtensionRequirement.new(hsh, arch: @arch), term_idx)
    end
  end

  # convert to Negation Normal Form
  def nnf(logic_tree)
    if logic_tree.type == :not
      # distribute
      if logic_tree.children.size == 1 && logic_tree.children[0].type == :term
        logic_tree
      else
        # distribute NOT
        child = logic_tree.children[0]

        if child.type == :and
          LogicNode.new(:or, child.children.map { |child2| LogicNode.new(:not, [child2]) })
        elsif child.type == :or
          LogicNode.new(:and, child.children.map { |child2| LogicNode.new(:not, [child2]) })
        elsif child.type == :xor
          raise "TODO"
        elsif child.type == :not
          child
        else
          raise "?"
        end
      end
    else
      LogicNode.new(logic_tree.type, logic_tree.children.map { |child| nnf(child) })
    end
  end

  # convert to Disjunctive Normal Form
  def dnf(logic_tree)
    logic_tree = nnf(logic_tree)
    if logic_tree.type == :and
      # distribute
      if logic_tree.children.all? { |child| child.type == :term }
        logic_tree
      else
        LogicTree.new(:or, logic_tree.children.map { |child| LogicTree.new(:and, dnf(child)) })
      end
    else
      logic_tree
    end
  end

  def combos_for(extension_versions)
    ncombos = extension_versions.reduce(1) { |prod, vers| prod * vers.size }
    combos = []
    ncombos.times do |i|
      combos << []
      extension_versions.size.times do |j|
        m = extension_versions[j].size
        d = j.zero? ? 1 : extension_versions[j..0].reduce(1) { |prod, vers| prod * vers.size }

        combos.last << extension_versions[j][(i / d) % m]
      end
    end
    combos
  end

  # @param other [ExtensionRequirementExpression] Another condition
  # @return [Boolean] if it's possible for both to be simultaneously true
  def compatible?(other)
    raise ArgumentError, "Expecting a ExtensionRequirementExpression" unless other.is_a?(ExtensionRequirementExpression)

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
  def satisfied_by?(&block)
    raise ArgumentError, "Missing required block" unless block_given?

    raise ArgumentError, "Expecting one argument to block" unless block.arity == 1

    eval to_rb
  end

  def possibly_satisfied_by?(ext_ver)
    # yes if:
    #   - ext_ver affects this condition
    #   - it is is possible for this condition to be true is ext_ver is implemented
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
  def to_rb = "true"

  def satisfied_by? = true

  def empty? = true

  def compatible?(_other) = true

  def to_h = {}
  def minimize = {}
end

class AlwaysFalseExtensionRequirementExpression
  def to_rb = "false"

  def satisfied_by? = false

  def empty? = true

  def compatible?(_other) = false

  def to_h = {}
  def minimize = {}
end

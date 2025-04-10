# frozen_string_literal: true

# Base class for any object representation of the Architecture.
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
  attr_reader :data, :data_path, :name, :long_name, :description

  # @return [Architecture] If only a specification (no config) is known
  # @return [ConfiguredArchitecture] If a specification and config is known
  # @return [nil] If neither is known
  attr_reader :arch       # Use when Architecture class is sufficient

  # @return [ConfiguredArchitecture] If a specification and config is known
  # @return [nil] Otherwise
  attr_reader :cfg_arch   # Use when extra stuff provided by ConfiguredArchitecture is required

  def kind = @data["kind"]

  # @param data [Hash<String,Object>] Hash with fields to be added
  # @param data_path [Pathname] Path to the data file
  # @param arch [Architecture or ConfiguredArchitecture] The RISC-V database with or without a specific configuration
  def initialize(data, data_path, arch)
    raise ArgumentError, "Need Architecture class but it's a #{arch.class}" unless arch.is_a?(Architecture)
    raise ArgumentError, "Bad data" unless data.is_a?(Hash)

    @data = data
    @data_path = data_path
    @arch = arch
    if arch.is_a?(ConfiguredArchitecture)
      @cfg_arch = arch
    else
      @cfg_arch = nil
    end
    @name = data["name"]
    @long_name = data["long_name"]
    @description = data["description"]

    @sem = Concurrent::Semaphore.new(1)
    @cache = Concurrent::Hash.new
  end

  # @return [Array<CertNormativeRule>]
  def cert_normative_rules
    return @cert_normative_rules unless @cert_normative_rules.nil?

    @cert_normative_rules = []
    @data["cert_normative_rules"]&.each do |cert_data|
      @cert_normative_rules << CertNormativeRule.new(cert_data, self)
    end
    @cert_normative_rules
  end

  # @return [Hash<String, CertNormativeRule>] Hash with ID as key of all normative rules defined by database object
  def cert_coverage_point_hash
    return @cert_coverage_point_hash unless @cert_coverage_point_hash.nil?

    @cert_coverage_point_hash = {}
    cert_normative_rules.each do |cp|
      @cert_coverage_point_hash[cp.id] = cp
    end
    @cert_coverage_point_hash
  end

  # @param id [String] Unique ID for the normative rule
  # @return [CertNormativeRule]
  # @return [nil] if there is no certification normative ruleed with ID of +id+
  def cert_coverage_point(id)
    cert_coverage_point_hash[id]
  end

  # @return [Array<CertTestProcedure>]
  def cert_test_procedures
    return @cert_test_procedures unless @cert_test_procedures.nil?

    @cert_test_procedures = []
    @data["cert_test_procedures"]&.each do |cert_data|
      @cert_test_procedures << CertTestProcedure.new(cert_data, self)
    end
    @cert_test_procedures
  end

  # @return [Hash<String, CertTestProcedure>] Hash of all normative rules defined by database object
  def cert_test_procedure_hash
    return @cert_test_procedure_hash unless @cert_test_procedure_hash.nil?

    @cert_test_procedure_hash = {}
    cert_test_procedures.each do |tp|
      @cert_test_procedure_hash[tp.id] = tp
    end
    @cert_test_procedure_hash
  end

  # @param id [String] Unique ID for test procedure
  # @return [CertTestProcedure]
  # @return [nil] if there is no certification test procedure with ID +id+
  def cert_test_procedure(id)
    cert_test_procedure_hash[id]
  end

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

  def inspect
    self.class.name + "##{name}"
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

# represents an `implies:` entry for an extension
# which is a list of extension versions, zero or more of which
# may be conditional (via an ExtensionRequirementExpression)
class ConditionalExtensionVersionList
  def initialize(ary, cfg_arch)
    @ary = ary
    @cfg_arch = cfg_arch
  end

  def empty? = @ary.nil? || @ary.empty?

  def size = empty? ? 0 : eval.size

  def each(&block)
    raise "Missing block" unless block_given?

    eval.each(&block)
  end

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
  def eval
    result = []
    if @ary.is_a?(Hash)
      result << { ext_ver: entry_to_ext_ver(@ary), cond: AlwaysTrueExtensionRequirementExpression.new }
    else
      @ary.each do |elem|
        if elem.is_a?(Hash) && elem.keys[0] == "if"
          cond_expr = ExtensionRequirementExpression.new(elem["if"], @cfg_arch)
          result << { ext_ver: entry_to_ext_ver(elem["then"]), cond: cond_expr }
        else
          result << { ext_ver: entry_to_ext_ver(elem), cond: AlwaysTrueExtensionRequirementExpression.new }
        end
      end
    end
    result
  end
  alias to_a eval

  def entry_to_ext_ver(entry)
    ExtensionVersion.new(entry["name"], entry["version"], @cfg_arch, fail_if_version_does_not_exist: true)
  end
  private :entry_to_ext_ver
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
  # @param composition_hash [Hash] A possibly recursive hash of "allOf", "anyOf", "oneOf", "not", "if"
  def initialize(composition_hash, cfg_arch)
    raise ArgumentError, "composition_hash is nil" if composition_hash.nil?

    unless is_a_condition?(composition_hash)
      raise ArgumentError, "Expecting a JSON schema comdition (got #{composition_hash})"
    end

    unless cfg_arch.is_a?(ConfiguredArchitecture)
      raise ArgumentError, "Must provide a cfg_arch"
    end

    @hsh = composition_hash
    @arch = cfg_arch
  end

  def to_h = @hsh

  def empty? = false

  VERSION_REQ_REGEX = /^((>=)|(>)|(~>)|(<)|(<=)|(=))?\s*[0-9]+(\.[0-9]+(\.[0-9]+(-[a-fA-F0-9]+)?)?)?$/
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

  def to_asciidoc(cond = @hsh, indent = 0, join: "\n")
    case cond
    when String
      "#{'*' * indent}* #{cond}, version >= #{@arch.extension(cond).min_version}"
    when Hash
      if cond.key?("name")
        if cond.key?("version")
          "#{'*' * indent}* #{cond['name']}, version #{cond['version']}#{join}"
        else
          "#{'*' * indent}* #{cond['name']}, version >= #{@arch.extension(cond['name']).min_version}#{join}"
        end
      else
        "#{'*' * indent}* #{cond.keys[0]}:#{join}" + to_asciidoc(cond[cond.keys[0]], indent + 2)
      end
    when Array
      cond.map { |e| to_asciidoc(e, indent) }.join(join)
    else
      raise "Unknown condition type: #{cond}"
    end
  end

  # @overload is_a_condition?(hsh)
  #   @param hsh [String] Extension name (case sensitive)
  #   @return [Boolean] True
  # @overload is_a_condition?(hsh)
  #   @param hsh [Hash<String, Object>] Extension name (case sensitive)
  #   @return [Boolean] True if hash is a JSON schema condition
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
        when "if"
          cond_rb_str = to_rb_helper(hsh["if"])
          body_rb_str = to_rb_helper(hsh["body"])
          "(#{body_rb_str}) if (#{cond_rb_str})"
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

  # Abstract syntax tree of the logic
  class LogicNode
    attr_accessor :type

    TYPES = [ :term, :not, :and, :or, :if ]

    def initialize(type, children, term_idx: nil)
      raise ArgumentError, "Bad type" unless TYPES.include?(type)
      raise ArgumentError, "Children must be an array" unless children.is_a?(Array)

      raise ArgumentError, "Children must be singular" if [:term, :not].include?(type) && children.size != 1
      raise ArgumentError, "Children must have two elements" if [:and, :or, :if].include?(type) && children.size != 2

      if type == :term
        raise ArgumentError, "Term must be an ExtensionRequirement (found #{children[0]})" unless children[0].is_a?(ExtensionRequirement)
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
        term_value = term_values.find { |tv| tv.name == ext_ret.name }
        unless term_value.nil?
          @children[0].satisfied_by?(term_value)
        end
      elsif @type == :if
        cond_ext_ret = @children[0]
        if cond_ext_ret.eval(term_values)
          @children[1].eval(term_values)
        else
          false
        end
      elsif @type == :not
        !@children[0].eval(term_values)
      elsif @type == :and
        @children.all? { |child| child.eval(term_values) }
      elsif @type == :or
        @children.any? { |child| child.eval(term_values) }
  end
end

    def to_s
      if @type == :term
        "(#{@children[0].to_s})"
      elsif @type == :not
        "!#{@children[0]}"
      elsif @type == :and
        "(#{@children[0]} ^ #{@children[1]})"
      elsif @type == :or
        "(#{@children[0]} v #{@children[1]})"
      elsif @type == :if
        "(#{@children[0]} -> #{@children[1]})"
      end
    end
  end

  # given an extension requirement, convert it to a LogicNode term, and optionally expand it to
  # exclude any conflicts and include any implications
  #
  # @param ext_req [ExtensionRequirement] An extension requirement
  # @param expand [Boolean] Whether or not to expand the node to include conflicts / implications
  # @return [LogicNode] Logic tree for ext_req
  def ext_req_to_logic_node(ext_req, term_idx, expand: true)
    n = LogicNode.new(:term, [ext_req], term_idx: term_idx[0])
    term_idx[0] += 1
    if expand
      c = ext_req.extension.conflicts_condition
      unless c.empty?
        c = LogicNode.new(:not, [to_logic_tree(ext_req.extension.data["conflicts"], term_idx:)])
        n = LogicNode.new(:and, [c, n])
      end

      ext_req.satisfying_versions.each do |ext_ver|
        ext_ver.implied_by_with_condition.each do |implied_by|
          implying_ext_ver = implied_by[:ext_ver]
          implying_cond = implied_by[:cond]
          implying_ext_req = ExtensionRequirement.new(implying_ext_ver.name, "= #{implying_ext_ver.version_str}", arch: @arch)
          if implying_cond.empty?
            # convert to an ext_req
            n = LogicNode.new(:or, [n, ext_req_to_logic_node(implying_ext_req, term_idx)])
          else
            # conditional
            # convert to an ext_req
            cond_node = implying_cond.to_logic_tree(term_idx:, expand:)
            cond = LogicNode.new(:if, [cond_node, ext_req_to_logic_node(implying_ext_req, term_idx)])
            n = LogicNode.new(:or, [n, cond])
          end
        end
      end
    end

    n
  end

  # convert the YAML representation of an Extension Requirement Expression into
  # a tree of LogicNodes.
  # Also expands any Extension Requirement to include its conflicts / implications
  def to_logic_tree(hsh = @hsh, term_idx: [0], expand: true)
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
          ext_req_to_logic_node(ExtensionRequirement.new(hsh["name"], arch: @arch), term_idx, expand:)
        end
      else
        key = hsh.keys[0]

        case key
        when "allOf"
          raise "unexpected" unless hsh[key].is_a?(Array) && hsh[key].size > 1

          root = LogicNode.new(:and, [to_logic_tree(hsh[key][0], term_idx:, expand:), to_logic_tree(hsh[key][1], term_idx:, expand:)])
          (2...hsh[key].size).each do |i|
            root = LogicNode.new(:and, [root, to_logic_tree(hsh[key][i], term_idx:, expand:)])
          end
          root
        when "anyOf"
          raise "unexpected: #{hsh}" unless hsh[key].is_a?(Array) && hsh[key].size > 1

          root = LogicNode.new(:or, [to_logic_tree(hsh[key][0], term_idx:, expand:), to_logic_tree(hsh[key][1], term_idx:, expand:)])
          (2...hsh[key].size).each do |i|
            root = LogicNode.new(:or, [root, to_logic_tree(hsh[key][i], term_idx:, expand:)])
          end
          root
        when "if"
          raise "unexpected" unless hsh.keys.size == 2 && hsh.keys[1] == "then"

          cond = to_logic_tree(hsh[key], term_idx:, expand:)
          body = to_logic_tree(hsh["then"], term_idx:, expand:)
          LogicNode.new(:if, [cond, body])
        when "oneOf"
          # expand oneOf into AND
          roots = []
          hsh[key].size.times do |k|
            root =
              if k.zero?
                LogicNode.new(:and, [to_logic_tree(hsh[key][0], term_idx:, expand:), LogicNode.new(:not, [to_logic_tree(hsh[key][1], term_idx:, expand:)])])
              elsif k == 1
                LogicNode.new(:and, [LogicNode.new(:not, [to_logic_tree(hsh[key][0], term_idx:, expand:)]), to_logic_tree(hsh[key][1], term_idx:, expand:)])
              else
                LogicNode.new(:and, [LogicNode.new(:not, [to_logic_tree(hsh[key][0], term_idx:, expand:)]), LogicNode.new(:not, [to_logic_tree(hsh[key][1], term_idx:, expand:)])])
              end
            (2...hsh[key].size).each do |i|
              root =
                if k == i
                  LogicNode.new(:and, [root, to_logic_tree(hsh[key][i], term_idx:, expand:)])
                else
                  LogicNode.new(:and, [root, LogicNode.new(:not, [to_logic_tree(hsh[key][i], term_idx:, expand:)])])
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
          LogicNode.new(:not, [to_logic_tree(hsh[key], term_idx:, expand:)])
        else
          raise "Unexpected"
        end
      end
    else
      ext_req_to_logic_node(ExtensionRequirement.new(hsh, arch: @arch), term_idx, expand:)
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
    ncombos = extension_versions.reduce(1) { |prod, vers| prod * (vers.size + 1) }
    combos = []
    ncombos.times do |i|
      combos << []
      extension_versions.size.times do |j|
        m = (extension_versions[j].size + 1)
        d = j.zero? ? 1 : extension_versions[j..0].reduce(1) { |prod, vers| prod * (vers.size + 1) }

        if (i / d) % m < extension_versions[j].size
          combos.last << extension_versions[j][(i / d) % m]
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

  # yes if:
  #   - ext_ver affects this condition
  #   - it is is possible for this condition to be true is ext_ver is implemented
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

class CertNormativeRule
  # @param data [Hash<String, Object>] Data from YAML file
  # @param db_obj [DatabaseObject] Database object that defines normative rule (Extension, Instruction, CSR, or CSR field)
  def initialize(data, db_obj)
    raise ArgumentError, "Need Hash but was passed a #{data.class}" unless data.is_a?(Hash)
    raise ArgumentError, "Need DatabaseObject but was passed a #{db_obj.class}" unless db_obj.is_a?(DatabaseObject)

    @data = data
    @db_obj = db_obj

    raise ArgumentError, "Missing certification normative rule description for #{db_obj.name} of kind #{db_obj.kind}" if description.nil?
    raise ArgumentError, "Missing certification normative rule ID for #{db_obj.name} of kind #{db_obj.kind}" if id.nil?
  end

  # @return [String] Description of normative rule (could be multiple lines)
  def description = @data["description"]

  # @return [String] Unique ID of the normative rule
  def id = @data["id"]

  # @return [Array<DocLink>] List of certification point documentation links
  def doc_links
    return @doc_links unless @doc_links.nil?

    @doc_links = []
    @data["doc_links"]&.each do |dst|
      @doc_links << DocLink.new(dst, @db_obj)
    end

    raise "Missing doc_links for certification normative rule ID '#{id}' of kind #{@db_obj.kind}" if @doc_links.empty?

    @doc_links
  end
end

# Creates links into RISC-V documentation with the following formats for the destination link:
#
#   Documenation  Format
#   ============  ===============================================================
#   ISA manuals   manual:ext:<ext_name>:<identifier>
#                 manual:inst:<inst_name>:<identifier>
#                 manual:insts:<inst_name>[-<inst_name>]+:<identifier>
#                 manual:inst_group:<group_name>:<identifier>
#                 manual:csr:<csr_name>:<identifier>
#                 manual:csr_field:<csr_name>:<field_name>:<identifier>
#                 manual:param:<ext_name>:<param_name>:<identifier>
#                   where <identifier> is a string that describes the tagged text
#   UDB doc       udb:doc:ext:<ext_name>
#                 udb:doc:ext_param:<ext_name>:<param_name>
#                 udb:doc:inst:<inst_name>
#                 udb:doc:csr:<csr_name>
#                 udb:doc:csr_field:<csr_name>:<field_name>
#                 udb:doc:func:<func_name>  (Documentation of common/built-in IDL functions)
#                 udb:doc:cov_pt:<org>:<id>
#                   where <org> is:
#                      sep for UDB documentation that "separates" normative rules from test plans
#                      combo for UDB documentation that "combines" normative rules with test plans
#                      appendix for UDB documentation that has normative rules and test plans in appendices
#                   where <id> is the ID of the normative rule
#   IDL code      idl:code:inst:<inst-name>:<location>
#                 TODO for CSR and CSR Fields
class DocLink
  # @param dst_link [String] The documentation link provided in the YAML
  # @param db_obj [String] Database object
  def initialize(dst_link, db_obj)
    raise ArgumentError, "Need String but was passed a #{data.class}" unless dst_link.is_a?(String)
    @dst_link = dst_link

    raise ArgumentError, "Missing documentation link for #{db_obj.name} of kind #{db_obj.kind}" if @dst_link.nil?
  end

  # @return [String] Unique ID of the linked to normative rule
  def dst_link = @dst_link

  # @return [String] Asciidoc to create desired link.
  def to_adoc
    "<<#{@dst_link},#{@dst_link}>>"
  end
end

class CertTestProcedure
  # @param data [Hash<String, Object>] Data from YAML file
  # @param db_obj [DatabaseObject] Database object that defines test procedure (Extension, Instruction, CSR, or CSR field)
  def initialize(data, db_obj)
    raise ArgumentError, "Need Hash but was passed a #{data.class}" unless data.is_a?(Hash)
    raise ArgumentError, "Need DatabaseObject but was passed a #{db_obj.class}" unless db_obj.is_a?(DatabaseObject)

    @data = data
    @db_obj = db_obj

    raise ArgumentError, "Missing certification test procedure ID for #{db_obj.name} of kind #{db_obj.kind}" if id.nil?
    warn "Warning: Missing test_file_name for certification test procedure description for #{db_obj.name} of kind #{db_obj.kind}" if test_file_name.nil?
    raise ArgumentError, "Missing certification test procedure description for #{db_obj.name} of kind #{db_obj.kind}" if description.nil?
  end

  # @return [String] Unique ID of the test procedure
  def id = @data["id"]

  # @return [String] Name of test file that implements this test procedure. Could be nil.
  def test_file_name = @data["test_file_name"]

  # @return [String] Description of test procedure (could be multiple lines)
  def description = @data["description"]

  # @return [Array<CertNormativeRule>]
  def cert_normative_rules
    return @cert_normative_rules unless @cert_normative_rules.nil?

    @cert_normative_rules = []
    @data["normative_rules"]&.each do |id|
      cp = @db_obj.cert_coverage_point(id)
      raise ArgumentError, "Can't find certification test procedure with ID '#{id}' for '#{@db_obj.name}' of kind #{@db_obj.kind}" if cp.nil?
      @cert_normative_rules << cp
    end
    @cert_normative_rules
  end

  # @return [String] String (likely multiline) of certification test procedure steps using Asciidoc lists
  def cert_steps = @data["steps"]
end

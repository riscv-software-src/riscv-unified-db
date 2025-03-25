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
  # @note Generally, you should prefer to use {#defined_by?}, etc. from Ruby
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

  # @overload defined_by?(ext_name, ext_version)
  #   @param ext_name [#to_s] An extension name
  #   @param ext_version [#to_s] A specific extension version
  #   @return [Boolean] Whether or not the instruction is defined by extension `ext`, version `version`
  # @overload defined_by?(ext_version)
  #   @param ext_version [ExtensionVersion] An extension version
  #   @return [Boolean] Whether or not the instruction is defined by ext_version
  def defined_by?(*args)
    ext_ver =
      if args.size == 1
        raise ArgumentError, "Parameter must be an ExtensionVersion" unless args[0].is_a?(ExtensionVersion)

        args[0]
      elsif args.size == 2
        raise ArgumentError, "First parameter must be an extension name" unless args[0].respond_to?(:to_s)
        raise ArgumentError, "First parameter must be an extension version" unless args[1].respond_to?(:to_s)

        ExtensionVersion.new(args[0], args[1], arch)
      else
        raise ArgumentError, "Unsupported number of arguments (#{args.size})"
      end

    defined_by_condition.satisfied_by? { |req| req.satisfied_by?(ext_ver) }
  end

  # because of multiple ("allOf") conditions, we generally can't return a list of extension versions here....
  # # @return [Array<ExtensionVersion>] Extension(s) that define the instruction. If *any* requirement is met, the instruction is defined.
  # def defined_by
  #   raise "ERROR: definedBy is nul for #{name}" if @data["definedBy"].nil?

  #   SchemaCondition.new(@data["definedBy"], @arch).satisfying_ext_versions
  # end

  # @return [SchemaCondition] Extension(s) that define the instruction. If *any* requirement is met, the instruction is defined.
  def defined_by_condition
    @defined_by_condition ||=
      begin
        raise "ERROR: definedBy is nul for #{name}" if @data["definedBy"].nil?

        SchemaCondition.new(@data["definedBy"], @arch)
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

# represents a JSON Schema compoisition, e.g.:
#
# anyOf:
#   - oneOf:
#     - A
#     - B
#   - C
#
class SchemaCondition
  # @param composition_hash [Hash] A possibly recursive hash of "allOf", "anyOf", "oneOf"
  def initialize(composition_hash, arch)
    raise ArgumentError, "composition_hash is nil" if composition_hash.nil?

    unless is_a_condition?(composition_hash)
      raise ArgumentError, "Expecting a JSON schema comdition (got #{composition_hash})"
    end

    @hsh = composition_hash
    @arch = arch
  end

  def to_h = @hsh

  def empty? = false

  VERSION_REQ_REGEX = /^((>=)|(>)|(~>)|(<)|(<=)|(=))?\s*[0-9]+(\.[0-9]+(\.[0-9]+(-[a-fA-F0-9]+)?)?)?$/
  def is_a_version_requirement(ver)
    case ver
    when String
      ver =~ VERSION_REQ_REGEX
    when Array
      ver.all? { |v| v =~ VERSION_REQ_REGEX }
    else
      false
    end
  end

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
      "#{'*' * indent}* #{cond}, version >= 0"
    when Hash
      if cond.key?("name")
        if cond.key?("version")
          "#{'*' * indent}* #{cond['name']}, version #{cond['version']}\n"
        else
          "#{'*' * indent}* #{cond['name']}, version >= 0\n"
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
  def self.all_of(*conds, arch:)
    cond = SchemaCondition.new({
      "allOf" => conds
    }, arch)

    SchemaCondition.new(cond.minimize, arch)
  end

  # @return [Object] Schema for this condition, with basic logic minimization
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
        end
        min_ary = min_ary.uniq!
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

  def satisfying_ext_versions
    list = []
    arch.extensions.each do |ext|
      ext.versions.each do |ext_ver|
        list << ext_ver if satisfied_by? { |ext_req| ext_req.satisfied_by?(ext_ver) }
      end
    end
    list
  end
end

class AlwaysTrueSchemaCondition
  def to_rb = "true"

  def satisfied_by? = true

  def empty? = true

  def flat? = false

  def to_h = {}
  def minimize = {}
end

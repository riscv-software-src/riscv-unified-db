# frozen_string_literal: true
# typed: true

require "sorbet-runtime"

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
  extend T::Sig

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

  # exception raised when an object does not validate, from a check other than JSON Schema
  class ValidationError < ::StandardError
  end

  sig { returns(T::Hash[String, T.untyped]) }
  attr_reader :data

  sig { returns(Pathname) }
  attr_reader :data_path

  sig { returns(String) }
  attr_reader :name

  sig { returns(String) }
  attr_reader :long_name

  sig { returns(String) }
  attr_reader :description

  # @return [Architecture] If only a specification (no config) is known
  # @return [ConfiguredArchitecture] If a specification and config is known
  # @return [nil] If neither is known
  sig { returns(Architecture) }
  attr_reader :arch       # Use when Architecture class is sufficient

  # @return [ConfiguredArchitecture] If a specification and config is known
  # @return [nil] Otherwise
  sig { returns(ConfiguredArchitecture) }
  attr_reader :cfg_arch   # Use when extra stuff provided by ConfiguredArchitecture is required

  sig { returns(String) }
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
  sig { void }
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
          raise SchemaError, T.must(schemas[schema_file]).validate_schema unless T.must(schemas[schema_file]).valid_schema?

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
  # @return [DatabaseObject] The new object
  sig { params(arch: T.nilable(Architecture)).returns(DatabaseObject) }
  def clone(arch: nil)
    obj = super()
    obj.instance_variable_set(:@arch, arch)
    obj
  end

  sig { params(other: DatabaseObject).returns(T.nilable(Integer)) }
  def <=>(other)
    return nil unless other.is_a?(DatabaseObject)

    name <=> other.name
  end

  # @return [String] Source file that data for this object can be attributed to
  # @return [nil] if the source isn't known
  sig { returns(T.nilable(String)) }
  def __source
    @data["$source"]
  end

  # The raw content of definedBy in the data.
  # @note Generally, you should prefer to use {#defined_by_condition}, etc. from Ruby
  #
  # @return [String] An extension name
  # @return [Hash<String, Object>] A requirements entry
  sig { returns(T.any(String, T::Hash[String, Object])) }
  def definedBy
    @data["definedBy"]
  end

  # @param data [Hash<String,Object>] Hash with fields to be added
  # @param data_path [Pathname] Path to the data file
  sig { params(data: T::Hash[String, T.untyped], data_path: T.any(String, Pathname), arch: T.nilable(Architecture)).void }
  def initialize(data, data_path, arch: nil)
    @data = data
    @data_path = Pathname.new(data_path)
    if arch.is_a?(ConfiguredArchitecture)
      @cfg_arch = arch
    end
    @arch = T.must(arch)
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
  sig { returns(T::Array[String]) }
  def keys = @data.keys

  # @param k (see Hash#key?)
  # @return (see Hash#key?)
  sig { params(k: String).returns(T::Boolean) }
  def key?(k) = @data.key?(k)

  # defer the calculation of 'blk' until later, then memoize the result
  sig { params(fn_name: Symbol, block: T.proc.void).returns(T.untyped) }
  def defer(fn_name, &block)
    cache_value = @cache[fn_name]
    return cache_value unless cache_value.nil?

    @cache[fn_name] ||= yield
  end

  # @return [ExtensionRequirementExpression] Extension(s) that define the instruction. If *any* requirement is met, the instruction is defined.
  sig { returns(ExtensionRequirementExpression) }
  def defined_by_condition
    @defined_by_condition ||=
      begin
        raise "ERROR: definedBy is nul for #{name}" if @data["definedBy"].nil?

        ExtensionRequirementExpression.new(@data["definedBy"], @cfg_arch)
      end
  end

  # @return [ExtensionRequirement] Name of an extension that "primarily" defines the object (i.e., is the first in a list)
  sig { returns(ExtensionRequirement) }
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
  sig { params(path: String).returns(Integer) }
  def source_line(*path)

    # find the line number of this operation() in the *original* file
    yaml_filename = @data["$source"]
    raise "No $source for #{name}" if yaml_filename.nil?
    line = T.let(nil, T.untyped)
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
  extend T::Sig

  sig { params(data: T::Hash[String, String]).void }
  def initialize(data)
    @data = data
  end

  # @return [String] Company name
  sig { returns(String) }
  def name = T.must(@data["name"])

  # @return [String] Company website
  sig { returns(String) }
  def url = T.must(@data["url"])
end

# License information
class License
  extend T::Sig

  sig { params(data: T::Hash[String, T.nilable(String)]).void }
  def initialize(data)
    @data = data
  end

  # @return [String] License name
  sig { returns(String) }
  def name = T.must(@data["name"])

  # @return [String] License website
  # @return [nil] if there is no website for the license
  sig { returns(String) }
  def url = T.must(@data["url"])

  # @return [String] Text of the license
  sig { returns(String) }
  def text
    if !@data["text_url"].nil?
      Net::HTTP.get(URI(T.must(@data["text_url"])))
    else
      @data["text"]
    end
  end
end

# Personal information about a contributor
class Person
  extend T::Sig
  include Comparable

  # @return [String] Person's name
  sig { returns(String) }
  def name = T.must(@data["name"])

  # @return [String] Email address
  # @return [nil] if email address is not known
  sig { returns(T.nilable(String)) }
  def email = @data["email"]

  # @return [String] Company the person works for
  # @return [nil] if the company is not known, or if the person is an individual contributor
  sig { returns(T.nilable(String)) }
  def company = @data["company"]

  sig { params(data: T::Hash[String, T.nilable(String)]).void }
  def initialize(data)
    @data = data
  end

  sig { params(other: Person).returns(T.nilable(Integer)) }
  def <=>(other)
    return nil unless other.is_a?(Person)

    name <=> other.name
  end
end

# frozen_string_literal: true

require "json"
require "json_schemer"
require "pathname"
require "singleton"
require "yaml"

$root = Pathname.new(__FILE__).dirname.dirname.realpath if $root.nil?

# class used to validate schmeas and objects
class Validator
  include Singleton

  # map of type to schema filesystem path
  SCHEMA_PATHS = {
    arch: $root / "schemas" / "arch_schema.json",
    inst: $root / "schemas" / "inst_schema.json",
    ext: $root / "schemas" / "ext_schema.json",
    csr: $root / "schemas" / "csr_schema.json",
    cfg_impl_ext: $root / "schemas" / "implemented_exts_schema.json"
  }.freeze

  # types of objects that can be validated
  TYPES = SCHEMA_PATHS.keys.freeze

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
  class ValidationError < ::StandardError

    # result from JsonSchemer.validate
    attr_reader :result

    # create a new ValidationError
    #
    # @param result [JsonSchemer::Result] JsonSchemer result
    def initialize(result)
      nerrors = result.count
      msg = +"#{nerrors} error(s) during validations\n\n"
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

  # iniailize a new Validator
  #
  # @raise [SchemaError] if a schema is ill-formed
  def initialize
    @schemas = {}
    SCHEMA_PATHS.each do |type, path|
      # resolve refs as a relative path from the schema file
      ref_resolver = proc do |pattern|
        if pattern.to_s =~ /^http/
          JSON.parse(Net::HTTP.get(pattern))
        else
          JSON.load_file($root / "schemas" / pattern.to_s)
        end
      end

      @schemas[type] =
        JSONSchemer.schema(
          path.read,
          regexp_resolver: "ecma",
          ref_resolver:,
          insert_property_defaults: true
        )
      raise SchemaError, @schemas[type].validate_schema unless @schemas[type].valid_schema?
    end
  end

  # validate a YAML string of a given type
  #
  # @return [Object] The object represented by str
  # @param str [String] A YAML document
  # @param type [Symbol] Type of the object (One of TYPES)
  # @raise [ValidationError] if the str is not valid against the type schema
  # @see TYPES
  def validate_str(str, type: nil, schema_path: nil)
    raise "Invalid type #{type}" unless TYPES.any?(type) || !schema_path.nil?

    begin
      obj = YAML.safe_load(str, permitted_classes: [Symbol])
    rescue Psych::SyntaxError => e
      warn "While parsing: #{str}\n\n"
      raise e
    end
    # convert through JSON to handle anything supported in YAML but not JSON
    # (e.g., integer object keys will be coverted to strings)
    jsonified_obj = JSON.parse(JSON.generate(obj))

    raise "Nothing there?" if jsonified_obj.nil?

    schema =
      if schema_path.nil?
        @schemas[type]
      else
        # resolve refs as a relative path from the schema file
        ref_resolver = proc do |pattern|
          JSON.load_file(schema_path.dirname / pattern.to_s)
        end
        JSONSchemer.schema(
          schema_path.read,
          regexp_resolver: "ecma",
          ref_resolver:,
          insert_property_defaults: true
        )
      end

    raise ValidationError, schema.validate(jsonified_obj) unless schema.valid?(jsonified_obj)

    jsonified_obj
  end

  # validate a YAML file
  #
  # The type of the file is infered from its path unless type is provided
  #
  # @param path [#to_s] Path to a YAML document
  # @param type [Symbol] Type of the object (One of TYPES). If nil, type will be inferred from path
  # @raise [ValidationError] if the str is not valid against the type schema
  # @see TYPES
  def validate(path, type: nil)
    schema_path = nil
    if type.nil?
      case path.to_s
      when %r{.*cfgs/([^/]+)/params\.yaml}
        cfg_name = $1.to_s
        type = :cfg_params
        schema_path = $root / "gen" / cfg_name / "schemas" / "params_schema.json"
      when %r{.*cfgs/[^/]+/implemented_exts\.yaml$}
        type = :cfg_impl_ext
      when %r{.*arch/arch_def\.yaml$}
        type = :arch
      when %r{.*arch/inst/.*/.*\.yaml$}
        type = :inst
      when %r{.*arch/ext/.*\.yaml$}
        type = :ext
      when %r{.*arch/csr/.*\.yaml$}
        type = :csr
      else
        warn "Cannot determine type from YAML path '#{path}'; skipping"
        return
      end
    end
    begin
      validate_str(File.read(path.to_s), type:, schema_path:)
    rescue Psych::SyntaxError => e
      warn "While parsing #{path}"
      raise e
    end
  end
end

# frozen_string_literal: true

require "pathname"
require "yaml"

# loads a YAML file and expands any $ref/$mref references
class YamlLoader
  @cache = {}

  def self.expand(filename, obj, yaml_opts = {})
    return obj unless obj.is_a?(Hash) || obj.is_a?(Array)

    return obj.map { |v| expand(filename, v, yaml_opts) } if obj.is_a?(Array)

    if obj.keys.include?("$ref")
      # according JSON Reference, all keys except $ref are ignored
      target_filename = File.dirname(obj["$ref"]) + value.split("#")[0]
      obj = YamlLoader.load(target_filename, yaml_opts).dig(*value.spilt("#")[1].split("/"))
    else
      obj_keys = obj.keys
      obj_keys.each do |key|
        value = obj[key]

        if key == "$mref"
          relative_path = value.split("#")[0]
          target_filename = File.realpath(File.join(filename.dirname, relative_path))

          unless File.exist?(target_filename)
            raise "While locating $mref in #{filename}, #{target_filename} does not exist"
          end

          target_obj = YamlLoader.load(target_filename, yaml_opts)
          target_obj = target_obj.dig(*value.split("#/")[1].split("/"))
          target_obj.each { |target_key, target_value|
            obj[target_key] = expand(filename, target_value, yaml_opts)
          }
          obj.delete("$mref")
        else
          obj[key] = expand(filename, value, yaml_opts)
        end
      end
    end
    obj
  end

  # load a YAML file and expand any $ref/$mref references
  # @param filename [String,Pathname] path to the YAML file
  # @param yaml_opts [Hash] options to pass to YAML.load_file
  # @return [Object] the loaded YAML file
  def self.load(filename, yaml_opts = {})
    filename = Pathname.new(filename)
    raise ArgumentError, "Cannot find file #{filename}" unless filename.exist?

    filename = filename.realpath
    return @cache[filename] if @cache.key?(filename)

    obj = YAML.load_file(filename, **yaml_opts)
    obj = expand(filename, obj, yaml_opts) if obj.is_a?(Hash)

    # @cache[filename] = obj
  end
end

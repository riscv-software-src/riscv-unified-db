# frozen_string_literal: true

require "pathname"
require "yaml"

# loads a YAML file and expands any $ref/$mref references
class YamlLoader
  @cache = {}

  class DereferenceError < StandardError; end

  def self.expand(filename, obj, yaml_opts = {})
    return obj unless obj.is_a?(Hash) || obj.is_a?(Array)

    return obj.map { |v| expand(filename, v, yaml_opts) } if obj.is_a?(Array)

    if obj.keys.include?("$ref")
      # according JSON Reference, all keys except $ref are ignored
      relative_path = obj["$ref"].split("#")[0]
      if relative_path.empty?
        # this is a reference in the same document
        obj_doc = YAML.load_file(filename, **yaml_opts)
        obj_path = obj["$ref"].split("#")[1].split("/")[1..]
        target_obj = obj_doc.dig(*obj_path)
        raise DereferenceError, "#{obj['$ref']} cannot be found" if target_obj.nil?

        ref = expand(filename, target_obj, yaml_opts)
        if ref.nil?
          raise DereferenceError, "JSON Path #{obj['$ref'].split('#')[1]} does not exist in #{filename}"
        end

        ref
      else
        target_filename = File.realpath(File.join(filename.dirname, relative_path))

        obj_doc = YamlLoader.load(target_filename, yaml_opts)
        obj_path = obj["$ref"].split("#")[1].split("/")[1..]
        target_obj = obj_doc.dig(*obj_path)
        raise "#{obj['$ref']} cannot be found" if target_obj.nil?

        ref = expand(target_filename, target_obj, yaml_opts)
        if ref.nil?
          raise DereferenceError, "JSON Path #{obj['$ref'].split('#')[1]} does not exist in #{target_filename}"
        end

        ref
      end
    elsif obj.keys.include?("$mref")
      # we handle the mref key first so that any override will take priority
      mref = obj["$mref"]
      mref_targets = mref.is_a?(String) ? [mref] : mref

      new_obj = {}

      mref_targets.each do |mref_target|
        relative_path = mref_target.split("#")[0]
        target_obj =
          if relative_path.empty?
            YAML.load_file(filename, **yaml_opts)
          else
            target_filename = File.realpath(File.join(filename.dirname, relative_path))

            unless File.exist?(target_filename)
              raise DereferenceError, "While locating $mref in #{filename}, #{target_filename} does not exist"
            end

            YamlLoader.load(target_filename, yaml_opts)
          end

        target_obj = target_obj.dig(*mref_target.split("#/")[1].split("/"))
        if target_obj.nil?
          raise DereferenceError, "JSON Path #{mref_target.split('#')[1]} does not exist in #{relative_path}"
        end

        target_obj = expand(filename, target_obj, yaml_opts)
        target_obj.each do |target_key, target_value|
          new_obj[target_key] = target_value
        end
      end

      obj.delete("$mref")
      obj_keys = obj.keys
      obj_keys.each do |key|
        value = obj[key]

        new_obj[key] = expand(filename, value, yaml_opts)
      end
      new_obj
    else
      obj_keys = obj.keys
      obj_keys.each do |key|
        value = obj[key]

        obj[key] = expand(filename, value, yaml_opts)
      end
      obj
    end
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

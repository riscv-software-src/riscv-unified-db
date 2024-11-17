# frozen_string_literal: true

require "pathname"
require "yaml"

# loads a YAML file and expands any $ref/$inherits references
class YamlLoader
  @cache = {}

  class DereferenceError < StandardError; end

  def self.expand(filename, obj, yaml_opts = {})
    return obj unless obj.is_a?(Hash) || obj.is_a?(Array)

    return obj.map { |v| expand(filename, v, yaml_opts) } if obj.is_a?(Array)

    new_obj =
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

        { "$ref" => obj["$ref"] } # ignore any other keys that might exist
      else
        target_filename =
          if File.exist?(File.join(filename.dirname, relative_path))
            File.realpath(File.join(filename.dirname, relative_path))
          elsif File.exist?(File.join($root, 'arch', relative_path))
            File.join($root, 'arch', relative_path)
          else
            raise DereferenceError, "#{relative_path} cannot be found"
          end

        obj_doc = YamlLoader.load(target_filename, yaml_opts)
        file_path, obj_path = obj["$ref"].split("#")
        target_obj =
          if obj_path.nil?
            obj_doc
          else
            obj_doc.dig(*(obj_path.split("/")[1..]))
            
          end
        raise "#{obj['$ref']} cannot be found" if target_obj.nil?

        ref = expand(target_filename, target_obj, yaml_opts)
        if ref.nil?
          raise DereferenceError, "JSON Path #{obj['$ref'].split('#')[1]} does not exist in #{target_filename}"
        end

        { "$ref" => obj["$ref"] } # ignore any other keys that might exist
      end
    elsif obj.keys.include?("$inherits")
      # we handle the inherits key first so that any override will take priority
      inherits = obj["$inherits"]
      raise ArgumentError, "Missing reference after $inherits (did you forget to put a relative reference in quotes?)" if inherits.nil?
      inherits_targets = inherits.is_a?(String) ? [inherits] : inherits

      new_obj = {}

      inherits_targets.each do |inherits_target|
        relative_path = inherits_target.split("#")[0]
        target_obj =
          if relative_path.empty?
            YAML.load_file(filename, **yaml_opts)
          else
            target_filename =
              if File.exist?(File.join(filename.dirname, relative_path))
                File.realpath(File.join(filename.dirname, relative_path))
              elsif File.exist?(File.join($root, 'arch', relative_path))
                File.join($root, 'arch', relative_path)
              else
                raise DereferenceError, "#{relative_path} cannot be found"
              end

            unless File.exist?(target_filename)
              raise DereferenceError, "While locating $inherits in #{filename}, #{target_filename} does not exist"
            end

            YamlLoader.load(target_filename, yaml_opts)
          end

        inherits_target_suffix = inherits_target.split("#/")[1]
        inherits_target_path = inherits_target_suffix.split("/")
        begin
          target_obj = target_obj.dig(*inherits_target_path) 
        rescue TypeError => e
          if e.message == "no implicit conversion of String into Integer"
            warn "$inherits: \"#{inherits_target}\" found in file #{filename} references an Array but needs to reference a Hash"
          end
          raise e
        end

        raise DereferenceError, "JSON Path #{inherits_target_suffix} in file #{filename} does not exist in #{relative_path}" if target_obj.nil?
        raise ArgumentError, "$inherits: \"#{inherits_target}\" in file #{filename} references a #{target_obj.class} but needs to reference a Hash" unless target_obj.is_a?(Hash)

        target_obj = expand(filename, target_obj, yaml_opts)
        target_obj.each do |target_key, target_value|
          if (new_obj[target_key].is_a?(Hash))
            raise "Should be a hash" unless target_value.is_a?(Hash)
            new_obj[target_key] = target_value.merge(new_obj[target_key])
          else
            new_obj[target_key] = target_value
          end
        end
      end

      obj.delete("$inherits")
      # now merge target_obj and obj
      keys = (obj.keys + new_obj.keys).uniq
      final_obj = {}
      keys.each do |key|
        if !obj.key?(key)
          final_obj[key] = new_obj[key]
        elsif !new_obj.key?(key)
          final_obj[key] = expand(filename, obj[key], yaml_opts)
        else
          value = obj[key]

          if new_obj[key].is_a?(Hash)
            raise "should be a hash" unless new_obj[key].is_a?(Hash)
            final_obj[key] = new_obj[key].merge(obj[key])
          else
            final_obj[key] = expand(filename, obj[key], yaml_opts)
          end
        end
      end

      final_obj
    else
      # Go through each hash entry.
      obj.each do |key, value|
        obj[key] =
        if value.is_a?(String) && value.start_with?("$copy:")
          copy_target = value.delete_prefix("$copy:").lstrip
          self.get_ref_target_obj(filename, copy_target, yaml_opts)
        else
          expand(filename, value, yaml_opts)
        end
      end
      obj
    end

    obj_keys = new_obj.keys
    if obj_keys.include? "$remove"
      remove_keys = obj["$remove"].is_a?(Array) ? obj["$remove"] : [obj["$remove"]]
      remove_keys.each do |key|
        new_obj.delete(key)
      end
    end
    new_obj.delete("$remove")
    new_obj
  end

  # @param filename [String,Pathname] path to the YAML file
  # @param ref_target [String]
  # @param yaml_opts [Hash] options to pass to YAML.load_file
  # @return [Object]
  def self.get_ref_target_obj(filename, ref_target, yaml_opts)
    relative_path = ref_target.split("#")[0]
    if relative_path.empty?
      # this is a reference in the same document
      obj_doc = YAML.load_file(filename, **yaml_opts)
      obj_path = ref_target.split("#")[1].split("/")[1..]
      target_obj = obj_doc.dig(*obj_path)
      raise DereferenceError, "$ref: #{obj_path} cannot be found in file #{filename}" if target_obj.nil?

      ref = expand(filename, target_obj, yaml_opts)
      if ref.nil?
        raise DereferenceError, "JSON Path #{obj_path} does not exist in file #{filename}"
      end

      ref
    else
      target_filename = File.realpath(File.join(filename.dirname, relative_path))

      obj_doc = YamlLoader.load(target_filename, yaml_opts)
      obj_path = ref_target.split("#")[1].split("/")[1..]
      target_obj = obj_doc.dig(*obj_path)
      raise "$ref: #{obj_path} cannot be found in file #{target_filename}" if target_obj.nil?

      ref = expand(target_filename, target_obj, yaml_opts)
      if ref.nil?
        raise DereferenceError, "JSON Path #{obj_path} does not exist in file #{target_filename}"
      end

      ref
    end
  end

  # load a YAML file and expand any $ref/$inherits references
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

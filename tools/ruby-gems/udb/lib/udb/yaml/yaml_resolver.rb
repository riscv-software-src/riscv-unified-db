# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require "psych"
require "pathname"
require "fileutils"
require "json"
require "json_schemer"
require "sorbet-runtime"

require "idlc"

require_relative "comment_parser"
require_relative "preserving_emitter"
require_relative "../log"
require_relative "../paths"

module Udb
  module Yaml
    # Ruby implementation of YAML resolver that preserves comments and order
    class Resolver
      extend T::Sig

      sig {
        params(
          quiet: T::Boolean,
          compile_idl: T::Boolean,
          schemas_path: T.nilable(T.any(String, Pathname))
        ).void
      }
      def initialize(quiet: false, compile_idl: false, schemas_path: nil)
        @quiet = T.let(quiet, T::Boolean)
        @compile_idl = T.let(compile_idl, T::Boolean)
        @compiler = T.let(nil, T.nilable(Idl::Compiler))
        if @compile_idl
          @compiler = Idl::Compiler.new
        end
        @resolved_objs = T.let({}, T::Hash[String, T::Hash[Symbol, T.untyped]])
        @current_comment_map = T.let(nil, T.nilable(CommentMap))
        @schemas_path = T.let(schemas_path.nil? ? nil : Pathname.new(schemas_path), T.nilable(Pathname))
        @schema_version_map = T.let(nil, T.nilable(T::Hash[String, String]))
      end

      # Returns the path to JSON schema files.
      # Defaults to Udb.default_schemas_path but can be overridden via the constructor.
      sig { returns(Pathname) }
      def schemas_path
        if @schemas_path.nil?
          @schemas_path = Udb.default_schemas_path
        end
        T.must(@schemas_path)
      end

      # Lazy map from schema filename -> version string, built by reading the $id
      # field from each schema file (e.g. 'csr_schema.json' -> 'v0.1').
      sig { returns(T::Hash[String, String]) }
      def schema_version_map
        if @schema_version_map.nil?
          version_map = T.let({}, T::Hash[String, String])
          if schemas_path.exist?
            schemas_path.glob("*.json").each do |schema_file|
              next if schema_file.basename.to_s == "json-schema-draft-07.json"

              begin
                schema_data = JSON.parse(schema_file.read)
                version = schema_data["$id"]
                version_map[schema_file.basename.to_s] = version if version.is_a?(String) && !version.start_with?("http")
              rescue StandardError
                # Silently skip files that can't be parsed
              end
            end
          end
          @schema_version_map = version_map
        end
        T.must(@schema_version_map)
      end

      # Rewrite a bare schema URI to include the version prefix recorded in $id.
      # For example, 'csr_schema.json#' becomes 'v0.1/csr_schema.json#'.
      # URIs that already contain a '/' in the base are returned unchanged.
      sig { params(uri: String).returns(String) }
      def versioned_schema_uri(uri)
        fragment_sep = uri.index("#")
        if fragment_sep
          base = T.must(uri[0...fragment_sep])
          fragment = T.must(uri[fragment_sep..])
        else
          base = uri
          fragment = ""
        end

        # Already has a version prefix
        return uri if base.include?("/")

        version = schema_version_map[base]
        version ? "#{version}/#{base}#{fragment}" : uri
      end

      sig {
        params(
          base_dir: T.any(String, Pathname),
          overlay_dir: T.nilable(T.any(String, Pathname)),
          output_dir: T.any(String, Pathname)
        ).void
      }
      def merge_files(base_dir, overlay_dir, output_dir)
        base_dir = Pathname.new(base_dir)
        overlay_dir = overlay_dir.nil? ? nil : Pathname.new(overlay_dir)
        output_dir = Pathname.new(output_dir)

        base_files = Dir.glob((base_dir / "**" / "*.yaml").to_s).map { |f| Pathname.new(f).relative_path_from(base_dir).to_s }
        overlay_files = overlay_dir.nil? ? [] : Dir.glob((overlay_dir / "**" / "*.yaml").to_s).map { |f| Pathname.new(f).relative_path_from(overlay_dir).to_s }

        # Include existing output files to detect stale entries
        existing_output_files = Dir.glob((output_dir / "**" / "*.yaml").to_s).map { |f| Pathname.new(f).relative_path_from(output_dir).to_s }

        all_files = (base_files + overlay_files + existing_output_files).uniq

        pb =
            Udb.create_progressbar(
              "Merging spec files [:bar] :current/:total",
              total: all_files.size,
              clear: true
            )
        all_files.each do |rel_path|
          pb.advance
          merge_file(rel_path, base_dir, overlay_dir, output_dir)
        end

        Udb.logger.info "Merged architecture files written to #{output_dir}" unless @quiet
      end

      sig {
        params(
          rel_path: String,
          base_dir: Pathname,
          overlay_dir: T.nilable(Pathname),
          output_dir: Pathname
        ).void
      }
      def merge_file(rel_path, base_dir, overlay_dir, output_dir)
        base_path = base_dir / rel_path
        overlay_path = overlay_dir.nil? ? nil : (overlay_dir / rel_path)
        output_path = output_dir / rel_path

        FileUtils.mkdir_p(output_path.dirname)

        if !base_path.exist? && (overlay_path.nil? || !overlay_path.exist?)
          FileUtils.rm_f(output_path) if output_path.exist?
        elsif overlay_path.nil? || !overlay_path.exist?
          if !output_path.exist? || base_path.mtime > output_path.mtime
            FileUtils.cp(base_path, output_path)
          end
        elsif !base_path.exist?
          if !output_path.exist? || overlay_path.mtime > output_path.mtime
            FileUtils.cp(overlay_path, output_path)
          end
        else
          if !output_path.exist? ||
             base_path.mtime > output_path.mtime ||
             overlay_path.mtime > output_path.mtime

            parser = CommentParser.new
            base_result = parser.parse_file(base_path)
            overlay_result = parser.parse_file(overlay_path)

            # Validate IDL scalar styles in both source files before merging so
            # that any error message points to the correct source file rather than
            # the generated merged output.
            [base_path, overlay_path].each do |src_path|
              yaml_string = File.read(src_path, encoding: "utf-8")
              ast = Psych.parse(yaml_string, filename: src_path.to_s)
              validate_idl_scalars(ast, [], src_path)
            end

            merged_data = json_merge_patch(base_result[:data], overlay_result[:data])

            # Fill in styles for keys that exist only in the base file so the
            # emitter uses the correct (base-file) style for those keys.
            overlay_result[:comments].merge_styles_from(base_result[:comments])

            emitter = PreservingEmitter.new(overlay_result[:comments])
            emitter.emit_file(merged_data, output_path)
          end
        end
      end

      sig {
        params(
          input_dir: T.any(String, Pathname),
          output_dir: T.any(String, Pathname),
          options: T::Hash[Symbol, T.untyped]
        ).void
      }
      def resolve_files(input_dir, output_dir, options = {})
        input_dir = Pathname.new(input_dir)
        output_dir = Pathname.new(output_dir)
        no_checks = options[:no_checks] || false

        yaml_files = Dir.glob((input_dir / "**" / "*.yaml").to_s).map do |f|
          Pathname.new(f).relative_path_from(input_dir).to_s
        end

        pb =
            Udb.create_progressbar(
              "Resolving spec files [:bar] :current/:total",
              total: yaml_files.size,
              clear: true
            )
        yaml_files.each do |rel_path|
          pb.advance
          resolve_file(rel_path, input_dir, output_dir, no_checks)
        end

        yaml_files.each do |rel_path|
          write_resolved_file(rel_path, input_dir, output_dir, no_checks)
        end

        # Remove stale resolved files that no longer have a corresponding input
        existing_output_files = Dir.glob((output_dir / "**" / "*.yaml").to_s).map do |f|
          Pathname.new(f).relative_path_from(output_dir).to_s
        end.reject { |rel| rel == "index.yaml" || rel == "index.json" }

        stale_files = existing_output_files - yaml_files
        stale_files.each do |rel_path|
          output_path = output_dir / rel_path
          FileUtils.rm_f(output_path) if output_path.exist?
        end

        FileUtils.mkdir_p(output_dir)
        File.write(output_dir / "index.yaml", Psych.dump(yaml_files))
        File.write(output_dir / "index.json", JSON.pretty_generate(yaml_files))

        Udb.logger.info "Resolved architecture files written to #{output_dir}" unless @quiet
      end

      sig {
        params(
          rel_path: String,
          input_dir: Pathname,
          output_dir: Pathname,
          no_checks: T::Boolean
        ).void
      }
      def resolve_file(rel_path, input_dir, output_dir, no_checks)
        input_path = input_dir / rel_path

        return unless input_path.exist?

        parser = CommentParser.new
        result = parser.parse_file(input_path)
        data = result[:data]

        # Validate that multiline IDL functions use literal block scalars
        # We need to check the raw YAML to detect multiline plain scalars
        yaml_string = File.read(input_path, encoding: "utf-8")
        ast = Psych.parse(yaml_string, filename: input_path.to_s)
        validate_idl_scalars(ast, [], input_path)

        track_source_locations(input_path, result[:comments])
        @current_comment_map = result[:comments]

        if !no_checks && data.key?("name")
          fn_name = Pathname.new(rel_path).basename(".yaml").to_s
          if fn_name != data["name"]
            raise "ERROR: 'name' key (#{data["name"]}) must match filename (#{fn_name}) in #{rel_path}"
          end
        end

        resolved_data = resolve_object(data, [], rel_path, data, input_dir, no_checks)

        # Second pass: set $parent_of on parent objects based on $child_of relationships.
        # This must be done after the full document is resolved because a child (e.g. "bottom")
        # may be processed after its parent (e.g. "middle") is already in resolved_data.
        set_parent_of_relationships(resolved_data, rel_path)

        @resolved_objs[rel_path] = { data: resolved_data, comments: result[:comments] }
      end

      sig {
        params(
          rel_path: String,
          input_dir: Pathname,
          output_dir: Pathname,
          no_checks: T::Boolean
        ).void
      }
      def write_resolved_file(rel_path, input_dir, output_dir, no_checks)
        output_path = output_dir / rel_path

        return unless @resolved_objs.key?(rel_path)

        resolved_obj = @resolved_objs.fetch(rel_path).fetch(:data)
        comments = @resolved_objs.fetch(rel_path).fetch(:comments)

        resolved_obj["$source"] = (input_dir / rel_path).realpath.to_s

        # Phase 1: Validate against bare (unversioned) $schema URI before rewriting.
        # Source files use bare names like 'csr_schema.json#', so the schema enum
        # only needs to list bare names.
        if !no_checks && resolved_obj.key?("$schema")
          validate_against_schema(resolved_obj, rel_path)
        end

        # Phase 2: Rewrite $schema to include the version prefix so the output
        # file records the exact schema version used (e.g. 'v0.1/csr_schema.json#').
        if resolved_obj.key?("$schema")
          resolved_obj["$schema"] = versioned_schema_uri(resolved_obj["$schema"])
        end

        FileUtils.mkdir_p(output_path.dirname)

        emitter = PreservingEmitter.new(comments)
        emitter.emit_file(resolved_obj, output_path)

        FileUtils.chmod(0o666, output_path)
      end

      sig {
        params(
          obj: T.untyped,
          obj_path: T::Array[T.untyped],
          obj_file_path: T.any(String, Pathname),
          doc_obj: T.untyped,
          arch_root: Pathname,
          no_checks: T::Boolean
        ).returns(T.untyped)
      }
      def resolve_object(obj, obj_path, obj_file_path, doc_obj, arch_root, no_checks)
        return obj unless obj.is_a?(Hash) || obj.is_a?(Array)

        if obj.is_a?(Array)
          return obj.map.with_index do |item, idx|
            resolve_object(item, obj_path + [idx], obj_file_path, doc_obj, arch_root, no_checks)
          end
        end

        if obj.key?("$inherits")
          return resolve_inherits(obj, obj_path, obj_file_path, doc_obj, arch_root, no_checks)
        end

        resolved = T.let({}, T::Hash[String, T.untyped])
        obj.each do |key, value|
          resolved[key] = resolve_object(value, obj_path + [key], obj_file_path, doc_obj, arch_root, no_checks)
        end

        if resolved.key?("$remove")
          remove_keys = resolved["$remove"]
          remove_keys = [remove_keys] unless remove_keys.is_a?(Array)
          remove_keys.each { |key| resolved.delete(key) }
          resolved.delete("$remove")
        end

        if @compile_idl
          idl_keys = obj.keys.select { |k| k.end_with?(")") }
          idl_keys.each do |key|
            idl_source = obj[key]

            # Skip compilation for nil or blank IDL blocks, matching previous resolver behavior.
            next if idl_source.nil?
            if idl_source.respond_to?(:strip) && idl_source.strip.empty?
              next
            end

            unless idl_source.is_a?(String)
              raise TypeError, "Expected IDL body for #{(obj_path + [key]).join('.')} to be a String, got #{idl_source.class}"
            end

            key_minus_args = key.split("(")[0] + "_ast"
            source_loc = @current_comment_map&.get_source_location(obj_path + [key])
            # :line is 1-based; set_input_file expects 0-based, so subtract 1
            starting_line = source_loc ? source_loc[:line] - 1 : 0
            starting_offset = source_loc ? (source_loc[:offset] || 0) : 0
            line_file_offsets = source_loc ? source_loc[:line_file_offsets] : nil
            parse_root =
              if key == "operation()"
                :instruction_operation
              elsif obj_path.include?("requirements")
                :constraint_body
              else
                :function_body
              end
            compiler = T.must(@compiler)
            compiler.parser.set_input_file(obj_file_path.to_s, starting_line, starting_offset, line_file_offsets)
            m = compiler.parser.parse(idl_source, root: parse_root)
            if m.nil?
              raise SyntaxError, <<~MSG
                While parsing #{obj_file_path}:#{compiler.parser.failure_line}

                #{compiler.parser.failure_reason}
              MSG
            end
            ast = m.to_ast
            if ast.nil?
              raise "IDL compiler could not convert to ast"
            end
            ast.set_input_file_unless_already_set(obj_file_path, starting_line, starting_offset, line_file_offsets)
            resolved[key_minus_args] = ast.to_h
          end
        end

        resolved
      end

      sig {
        params(
          obj: T::Hash[String, T.untyped],
          obj_path: T::Array[T.untyped],
          obj_file_path: T.any(String, Pathname),
          doc_obj: T.untyped,
          arch_root: Pathname,
          no_checks: T::Boolean
        ).returns(T::Hash[String, T.untyped])
      }
      def resolve_inherits(obj, obj_path, obj_file_path, doc_obj, arch_root, no_checks)
        inherits_value = obj["$inherits"]
        inherits_targets = inherits_value.is_a?(Array) ? inherits_value : [inherits_value]

        # Build a new hash instead of mutating obj in-place.
        # Mutating obj would corrupt doc_obj (the original parsed data), causing subsequent
        # resolutions of the same key to see the already-mutated version without $inherits.
        obj = obj.reject { |k, _| k == "$inherits" }.merge("$child_of" => inherits_value)

        parent_obj = T.let({}, T::Hash[String, T.untyped])

        inherits_targets.each do |inherits_target|
          if inherits_target.include?("#")
            ref_file_path, ref_obj_path_str = inherits_target.split("#", 2)
          else
            ref_file_path = ""
            ref_obj_path_str = inherits_target.start_with?("/") ? inherits_target : "/#{inherits_target}"
          end

          ref_obj_path = ref_obj_path_str.split("/").drop(1)

          ref_obj = T.let(nil, T.nilable(T::Hash[String, T.untyped]))
          if ref_file_path.empty?
            ref_obj = if ref_obj_path.empty?
                        doc_obj
            else
              T.unsafe(doc_obj).dig(*ref_obj_path)
            end
            raise "#{ref_obj_path.join("/")} cannot be found in #{obj_file_path}" if ref_obj.nil?
            ref_obj = resolve_object(ref_obj, ref_obj_path, obj_file_path, doc_obj, arch_root, no_checks)
          else
            ref_full_path = arch_root / ref_file_path
            raise "#{ref_file_path} does not exist in #{arch_root}/" unless ref_full_path.exist?

            ref_doc_obj = get_resolved_object(ref_file_path, arch_root, no_checks)
            ref_obj = if ref_obj_path.empty?
                        ref_doc_obj
            else
              T.unsafe(ref_doc_obj).dig(*ref_obj_path)
            end
            raise "#{ref_obj_path.join("/")} cannot be found in #{ref_file_path}" if ref_obj.nil?
          end

          ref_obj.each do |key, value|
            next if key == "$parent_of" || key == "$child_of"

            if parent_obj.key?(key) && parent_obj[key].is_a?(Hash) && value.is_a?(Hash)
              deep_merge!(parent_obj[key], value)
            else
              parent_obj[key] = deep_copy(value)
            end
          end

        end

        final_obj = T.let({}, T::Hash[String, T.untyped])
        all_keys = (parent_obj.keys + obj.keys).uniq

        all_keys.each do |key|
          if !obj.key?(key)
            final_obj[key] = parent_obj[key]
          elsif !parent_obj.key?(key)
            final_obj[key] = resolve_object(obj[key], obj_path + [key], obj_file_path, doc_obj, arch_root, no_checks)
          else
            if parent_obj[key].is_a?(Hash) && obj[key].is_a?(Hash)
              final_obj[key] = deep_merge(parent_obj[key], resolve_object(obj[key], obj_path + [key], obj_file_path, doc_obj, arch_root, no_checks))
            else
              final_obj[key] = resolve_object(obj[key], obj_path + [key], obj_file_path, doc_obj, arch_root, no_checks)
            end
          end
        end

        if final_obj.key?("$remove")
          remove_keys = final_obj["$remove"]
          remove_keys = [remove_keys] unless remove_keys.is_a?(Array)
          remove_keys.each { |key| final_obj.delete(key) }
          final_obj.delete("$remove")
        end

        final_obj
      end

      sig {
        params(
          resolved_data: T::Hash[String, T.untyped],
          rel_path: String
        ).void
      }
      def set_parent_of_relationships(resolved_data, rel_path)
        walk_for_parent_of(resolved_data, [], resolved_data, rel_path)
      end

      sig {
        params(
          obj: T.untyped,
          path: T::Array[String],
          doc_root: T::Hash[String, T.untyped],
          rel_path: String
        ).void
      }
      def walk_for_parent_of(obj, path, doc_root, rel_path)
        return unless obj.is_a?(Hash)

        if obj.key?("$child_of")
          child_of = obj["$child_of"]
          targets = child_of.is_a?(Array) ? child_of : [child_of]
          child_ref = path.empty? ? "#{rel_path}#/" : "#{rel_path}#/#{path.join("/")}"

          targets.each do |target|
            next unless target.is_a?(String)

            if target.start_with?("#")
              # Same-document reference
              ref_path_str = T.must(target.split("#", 2)).fetch(1)
              ref_path = ref_path_str.split("/").drop(1)
              parent_obj = T.unsafe(doc_root).dig(*ref_path)
              next if parent_obj.nil? || !parent_obj.is_a?(Hash)

              add_parent_of_reference(parent_obj, child_ref)
            elsif target.include?("#")
              # Cross-file reference
              ref_file_path, ref_obj_path_str = target.split("#", 2)
              ref_obj_path = T.must(ref_obj_path_str).split("/").drop(1)

              # Get the resolved object from the cache
              next unless @resolved_objs.key?(T.must(ref_file_path))

              ref_doc = @resolved_objs.fetch(T.must(ref_file_path)).fetch(:data)
              parent_obj = ref_obj_path.empty? ? ref_doc : T.unsafe(ref_doc).dig(*ref_obj_path)
              next if parent_obj.nil? || !parent_obj.is_a?(Hash)

              add_parent_of_reference(parent_obj, child_ref)
            end
          end
        end

        obj.each do |key, value|
          walk_for_parent_of(value, path + [key], doc_root, rel_path)
        end
      end

      sig {
        params(
          parent_obj: T::Hash[String, T.untyped],
          child_ref: String
        ).void
      }
      def add_parent_of_reference(parent_obj, child_ref)
        if parent_obj.key?("$parent_of")
          existing = parent_obj["$parent_of"]
          existing = [existing] unless existing.is_a?(Array)
          existing << child_ref unless existing.include?(child_ref)
          parent_obj["$parent_of"] = existing.length == 1 ? existing[0] : existing
        else
          parent_obj["$parent_of"] = child_ref
        end
      end

      # rel_path can come from a `$inherits` target in a spec file, so it is untrusted:
      # without the containment check a `../` sequence or an absolute path would read an
      # arbitrary file and inline it into the resolved (and published) output.
      sig {
        params(
          rel_path: String,
          arch_root: Pathname,
          no_checks: T::Boolean
        ).returns(T::Hash[String, T.untyped])
      }
      def get_resolved_object(rel_path, arch_root, no_checks)
        arch_root_abs = arch_root.realpath
        target = (arch_root_abs / rel_path).expand_path
        target = target.realpath if target.exist?
        unless target.to_s.start_with?("#{arch_root_abs}/")
          raise "#{rel_path} escapes the architecture root #{arch_root}/"
        end

        return @resolved_objs.fetch(rel_path).fetch(:data) if @resolved_objs.key?(rel_path)

        input_path = arch_root / rel_path
        parser = CommentParser.new
        result = parser.parse_file(input_path)
        data = result[:data]

        resolved_data = resolve_object(data, [], rel_path, data, arch_root, no_checks)
        @resolved_objs[rel_path] = { data: resolved_data, comments: result[:comments] }

        resolved_data
      end

      sig {
        params(
          base: T.untyped,
          patch: T.untyped
        ).returns(T.untyped)
      }
      def json_merge_patch(base, patch)
        return patch unless patch.is_a?(Hash)
        return patch unless base.is_a?(Hash)

        result = base.dup

        patch.each do |key, value|
          if value.nil?
            result.delete(key)
          elsif value.is_a?(Hash) && result[key].is_a?(Hash)
            result[key] = json_merge_patch(result[key], value)
          else
            result[key] = deep_copy(value)
          end
        end

        result
      end

      sig {
        params(
          base: T::Hash[T.untyped, T.untyped],
          other: T::Hash[T.untyped, T.untyped]
        ).returns(T::Hash[T.untyped, T.untyped])
      }
      def deep_merge!(base, other)
        other.each do |key, value|
          if base[key].is_a?(Hash) && value.is_a?(Hash)
            deep_merge!(base[key], value)
          else
            base[key] = deep_copy(value)
          end
        end
        base
      end

      sig {
        params(
          base: T::Hash[T.untyped, T.untyped],
          other: T::Hash[T.untyped, T.untyped]
        ).returns(T::Hash[T.untyped, T.untyped])
      }
      def deep_merge(base, other)
        result = base.dup
        deep_merge!(result, other)
      end

      sig { params(obj: T.untyped).returns(T.untyped) }
      def deep_copy(obj)
        case obj
        when Hash
          obj.transform_values { |v| deep_copy(v) }
        when Array
          obj.map { |item| deep_copy(item) }
        else
          begin
            obj.dup
          rescue TypeError
            obj
          end
        end
      end

      def validate_idl_scalars(node, keys, file_path)
        case node
        when Psych::Nodes::Document
          node.children.each do |child|
            validate_idl_scalars(child, [], file_path)
          end
        when Psych::Nodes::Mapping
          i = 0
          while i < node.children.size
            key_node = node.children.fetch(i)
            value_node = node.children.fetch(i + 1)
            key_text = key_node.value

            # Check if this is an IDL function key
            if key_text.is_a?(String) && key_text.end_with?(")")
              # Validate the value node
              if value_node.is_a?(Psych::Nodes::Scalar)
                # Check if it's a multiline plain scalar
                if value_node.style == Psych::Nodes::Scalar::PLAIN &&
                   value_node.end_line > value_node.start_line
                  raise "ERROR: Multiline IDL function '#{key_text}' in #{file_path} must use literal block scalar (|).\n" \
                        "Found plain scalar spanning lines #{value_node.start_line + 1}-#{value_node.end_line + 1}.\n" \
                        "Please change the YAML to use:\n" \
                        "  #{key_text}: |\n" \
                        "    <your IDL code here>"
                end
              end
            end

            # Recurse into the value
            validate_idl_scalars(value_node, keys + [key_text], file_path)
            i += 2
          end
        when Psych::Nodes::Sequence
          node.children.each_with_index do |child, idx|
            validate_idl_scalars(child, keys + [idx.to_s], file_path)
          end
        end
      end

      sig {
        params(
          keys: T::Array[String],
          contents: String,
          file: T.any(String, Pathname),
          cumulative_offsets: T::Array[Integer],
          offset_map: CommentMap,
          node: Psych::Nodes::Node
        ).void
      }
      def track_source_locations_helper(keys, contents, file, cumulative_offsets, offset_map, node)
        case node
        when Psych::Nodes::Document
          node.children.each do |child|
            track_source_locations_helper([], contents, file, cumulative_offsets, offset_map, child)
          end
        when Psych::Nodes::Mapping
          i = 0
          while i < node.children.size
            key_text = node.children.fetch(i).value
            track_source_locations_helper(keys + [key_text], contents, file, cumulative_offsets, offset_map, node.children.fetch(i + 1))
            i += 2
          end
          # Don't track source locations for mappings - only for IDL function scalar values
        when Psych::Nodes::Sequence
          node.children.each_with_index do |child, idx|
            track_source_locations_helper(keys + [idx.to_s], contents, file, cumulative_offsets, offset_map, child)
          end
          # Don't track source locations for sequences - only for IDL function scalar values
        when Psych::Nodes::Scalar
          return unless keys.any?

          is_idl_key = keys.last.is_a?(String) && T.must(keys.last).end_with?(")")
          marked_offset = cumulative_offsets.fetch(node.start_line) + node.start_column

          if is_idl_key
            actual_offset =
              if node.value.empty?
                marked_offset
              elsif node.style == Psych::Nodes::Scalar::LITERAL
                # The first content line always starts at the beginning of the line
                # immediately after the key line (node.start_line + 1).
                cumulative_offsets[node.start_line + 1]
              elsif node.style == Psych::Nodes::Scalar::PLAIN
                # Single-line plain scalar - find it directly
                contents.index(node.value, marked_offset)
              else
                style_name = case node.style
                             when Psych::Nodes::Scalar::SINGLE_QUOTED then "SINGLE_QUOTED"
                             when Psych::Nodes::Scalar::DOUBLE_QUOTED then "DOUBLE_QUOTED"
                             when Psych::Nodes::Scalar::FOLDED then "FOLDED"
                             else "UNKNOWN (#{node.style})"
                             end
                raise "ERROR: Unsupported YAML style for IDL function '#{keys.last}' in #{file}.\n" \
                  "IDL functions must use either PLAIN (single-line) or LITERAL block scalar (|) style.\n" \
                  "Examples:\n" \
                  "  PLAIN (single-line):     #{keys.last}: x = 5\n" \
                  "  LITERAL (multi-line):    #{keys.last}: |\n" \
                  "                             x = 5\n" \
                  "                             y = 10\n" \
                  "Found style: #{style_name}"
              end
            line_file_offsets =
              if node.style == Psych::Nodes::Scalar::LITERAL && !node.value.empty? && actual_offset
                build_line_file_offsets(node.value, actual_offset, contents)
              end
            offset_map.set_source_location(keys, file, node.start_line + 1, node.start_column + 1, actual_offset, line_file_offsets)
          else
            offset_map.set_source_location(keys, file, node.start_line + 1, node.start_column + 1)
          end
        end
      end

      sig {
        params(
          file_path: T.any(String, Pathname),
          comment_map: CommentMap
        ).void
      }
      def track_source_locations(file_path, comment_map)
        yaml_string = File.read(file_path, encoding: "utf-8")
        lines = yaml_string.lines

        cumulative_offsets = T.let([], T::Array[Integer])
        offset = 0
        lines.each do |line|
          cumulative_offsets << offset
          offset += line.bytesize
        end

        # Use binary encoding for all byte-offset operations so that multi-byte
        # UTF-8 characters don't cause character/byte index mismatches.
        yaml_bytes = yaml_string.b
        ast = Psych.parse(yaml_string, filename: file_path.to_s)
        track_source_locations_helper([], yaml_bytes, file_path, cumulative_offsets, comment_map, ast)
      end

      sig {
        params(
          line: String,
          value_part: T.nilable(String),
          line_num: Integer,
          lines: T::Array[String]
        ).returns(Integer)
      }
      def calculate_value_column(line, value_part, line_num, lines)
        return 0 if value_part.nil?

        colon_pos = line.index(":")
        return 0 if colon_pos.nil?

        value_stripped = value_part.strip

        if value_stripped.start_with?("|", ">")
          next_line_idx = line_num + 1
          while next_line_idx < lines.length
            next_line = lines.fetch(next_line_idx)
            if !next_line.strip.empty?
              return T.must(next_line[/^\s*/]).length
            end
            next_line_idx += 1
          end
          return colon_pos + 2
        end

        value_start = colon_pos + 1
        while value_start < line.length && line[value_start] == " "
          value_start += 1
        end

        value_start
      end

      sig {
        params(
          line: String,
          value_part: T.nilable(String),
          line_num: Integer,
          lines: T::Array[String],
          cumulative_offsets: T::Array[Integer],
          file_bytes: String
        ).returns(Integer)
      }
      def calculate_content_offset(line, value_part, line_num, lines, cumulative_offsets, file_bytes)
        return 0 if value_part.nil?

        colon_pos = line.index(":")
        return 0 if colon_pos.nil?

        value_stripped = value_part.strip

        if value_stripped.start_with?("|")
          # For literal block scalars, YAML strips the minimum common indentation from all lines.
          # We need to calculate what that indentation is and point to the content after it's stripped.

          line_lens = value_stripped.lines.map { |l| T.must(l[/^\s*/]).length }
          min_indent =
            if value_stripped[1] == "\n"
              # implicit indent, need to find min # of starting spaces
              T.must(line_lens[1..]).min
            else
              # explicit indent (e.g., "key: |2")
              value_stripped[1..].to_i
            end

          # also find the line that the content actually starts on (skipping blank lines at the beginning)

          if line_lens.size <= 1
            # Block scalar has no content lines (only the indicator line)
            raise StandardError, "Block scalar at #{@current_file_path}:#{line_num} has no content lines"
          end

          # Find the first line with actual content (non-zero indentation)
          first_content_line_num = 1
          while first_content_line_num < line_lens.size && T.must(line_lens[first_content_line_num]).zero?
            first_content_line_num += 1
          end

          if first_content_line_num >= line_lens.size
            # No content found - empty literal block
            raise StandardError, "Block scalar at #{@current_file_path}:#{line_num} has no content lines"
          end

          return cumulative_offsets.fetch(first_content_line_num) + T.must(min_indent)
        end

        # For inline plain scalar values (value on the same line as the key)
        value_start = colon_pos + 1
        value_start += 1 while value_start < line.length && line[value_start] == " "

        # Calculate the initial byte offset
        initial_offset = cumulative_offsets.fetch(line_num) + value_start

        # Check if there's actual content on this line
        if value_start < line.length && !T.must(line[value_start..]).strip.empty?
          # Value is on the same line - skip only spaces/tabs on this line, not newlines
          offset = initial_offset
          while offset < file_bytes.bytesize && [" ", "\t"].include?(file_bytes[offset])
            offset += 1
          end

          return offset
        else
          # Value is on the next line(s) - skip whitespace including newlines
          offset = initial_offset
          while offset < file_bytes.bytesize && [" ", "\t", "\n", "\r"].include?(file_bytes[offset])
            offset += 1
          end

          # If we've skipped past the end, return the initial offset
          return offset >= file_bytes.bytesize ? initial_offset : offset
        end
      end

      # Build a per-line file-offset table for a literal block scalar.
      #
      # +idl_string+ is the YAML-parsed value (indentation stripped, comments preserved).
      # +first_line_file_offset+ is the file byte offset of the first character of the first IDL line
      #   (i.e. after the stripped indentation).
      # +file_contents+ is the full raw file string.
      #
      # Returns an array where entry [i] is the file byte offset of the first character of IDL line i
      # (after stripping indentation). This correctly handles indentation stripping and empty lines.
      #
      # All offsets are byte offsets. We use String#getbyte / binary-encoded slices to avoid
      # character-vs-byte indexing mismatches with UTF-8 content.
      sig {
        params(
          idl_string: String,
          first_line_file_offset: Integer,
          file_contents: String
        ).returns(T::Array[Integer])
      }
      def build_line_file_offsets(idl_string, first_line_file_offset, file_contents)
        offsets = T.let([], T::Array[Integer])

        # Work in binary (byte) space to avoid UTF-8 character/byte index mismatches.
        file_bytes = file_contents.b

        # first_line_file_offset is the byte offset of the start of the first content line
        # in the file (i.e. cumulative_offsets[node.start_line + 1]).  Determine the
        # indentation width by counting leading spaces on the first non-empty content line.
        indent_width = 0
        scan_pos = first_line_file_offset
        while scan_pos < file_bytes.bytesize
          spaces = 0
          while scan_pos + spaces < file_bytes.bytesize &&
                file_bytes.getbyte(scan_pos + spaces) == 32
            spaces += 1
          end
          # If this line has non-whitespace content, use its indent
          if scan_pos + spaces < file_bytes.bytesize &&
             file_bytes.getbyte(scan_pos + spaces) != 10  # 10 = \n
            indent_width = spaces
            break
          end
          # Skip to next line
          nl = file_bytes.index("\n".b, scan_pos)
          scan_pos = nl ? nl + 1 : file_bytes.bytesize
        end

        # file_pos tracks the byte offset of the start of the current file line.
        file_pos = first_line_file_offset

        idl_string.each_line do |_idl_line|
          # Skip up to indent_width space bytes to reach the content start.
          # Empty file lines (just "\n") have no spaces to skip.
          content_pos = file_pos
          skipped = 0
          while skipped < indent_width &&
                content_pos < file_bytes.bytesize &&
                file_bytes.getbyte(content_pos) == 32  # 32 = ASCII space
            content_pos += 1
            skipped += 1
          end
          offsets << content_pos

          # Advance to the start of the next file line.
          newline_pos = file_bytes.index("\n".b, file_pos)
          file_pos = newline_pos ? newline_pos + 1 : file_bytes.bytesize
        end

        offsets
      end

      # Validate +resolved_obj+ against its bare $schema URI.
      # Uses the unversioned schema name so that schema enums listing bare names
      # (e.g. 'csr_schema.json#') match even when $schema contains a version prefix.
      sig {
        params(
          resolved_obj: T::Hash[String, T.untyped],
          rel_path: String
        ).void
      }
      def validate_against_schema(resolved_obj, rel_path)
        schema_uri = resolved_obj["$schema"]
        schema_file = schema_uri.split("#").first
        schema_basename = File.basename(T.must(schema_file))
        schema_path = schemas_path / schema_basename

        unless schema_path.exist?
          Udb.logger.warn "Schema file not found: #{schema_path}" unless @quiet
          return
        end

        ref_resolver = proc do |uri|
          local_path = schemas_path / File.basename(uri.to_s)
          JSON.parse(local_path.read)
        end

        schema = JSONSchemer.schema(
          JSON.parse(schema_path.read),
          regexp_resolver: "ecma",
          ref_resolver: ref_resolver,
          insert_property_defaults: false
        )

        # Convert through JSON to normalize YAML-specific types (e.g. integer keys)
        jsonified_obj = JSON.parse(JSON.generate(resolved_obj))

        # Normalize $schema to bare name so the schema enum matches bare refs
        if jsonified_obj.key?("$schema")
          bare_schema = File.basename(T.must(jsonified_obj["$schema"].split("#").first)) + "#"
          jsonified_obj["$schema"] = bare_schema
        end

        unless schema.valid?(jsonified_obj)
          errors = schema.validate(jsonified_obj).to_a
          error_msgs = errors.map { |e| "  - #{e["data_pointer"]}: #{e["type"]}" }.join("\n")
          raise "Schema validation failed for #{rel_path}:\n#{error_msgs}"
        end
      end
    end
  end
end

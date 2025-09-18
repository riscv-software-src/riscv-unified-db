#!/usr/bin/env ruby
# Copyright (c) Synopsys Inc.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true

require 'pathname'
require 'sorbet-runtime'
require 'set'

module Udb

##
# Unified renderer for all external documentation (ISA manuals and external specs)
class ExternalDocumentationRenderer
  extend T::Sig

  @@included_files = Set.new # Class variable to track main document includes only
  @@processing_stack = Set.new # Track currently processing files to prevent infinite recursion

  sig { void }
  def self.reset_included_files
    @@included_files.clear
    @@processing_stack.clear
  end

  sig { params(root_dir: Pathname).void }
  def initialize(root_dir)
    @root_dir = root_dir
  end

  sig { params(external_docs: T.nilable(T::Array[T::Hash[String, T.untyped]]), base_level: Integer).returns(String) }
  # Main method to render external documentation
  def render_external_documentation(external_docs, base_level = 3)
    return "" if external_docs.nil? || external_docs.empty?

    puts "    [INFO] Rendering #{external_docs.length} external documentation source(s)"

    content = []
    external_docs.each_with_index do |external_config, index|
      source = external_config['source'] || "unknown_#{index}"
      puts "      - Processing source: #{source}"

      doc_content = render_external_source(external_config, base_level)
      content << doc_content unless doc_content.empty?
    end

    result = content.join("\n\n")
    puts "    [INFO] External documentation rendering complete (#{result.lines.count} lines generated)"
    result
  end

  sig { params(external_config: T::Hash[String, T.untyped], base_level: Integer).returns(String) }
  # Render a single external documentation source
  def render_external_source(external_config, base_level)
    source = external_config['source'] || 'unknown'
    doc_type = external_config['type'] || 'external_spec'
    path = external_config['path']

    unless path
      return generate_missing_config_notice(source)
    end

    unless external_config['chapters']
      return generate_missing_chapters_notice(source, path)
    end

    content = []
    external_config['chapters'].each do |chapter_config|
      chapter_content = render_external_chapter(external_config, chapter_config, base_level)
      content << chapter_content unless chapter_content.empty?
    end

    content.join("\n\n")
  end

  sig { params(external_config: T::Hash[String, T.untyped], chapter_config: T::Hash[String, T.untyped], base_level: Integer).returns(String) }
  # Render a single chapter from external documentation
  def render_external_chapter(external_config, chapter_config, base_level)
    file = chapter_config['file']
    path = external_config['path']
    level_offset = chapter_config['level_offset'] || 0
    chapter_level = base_level + level_offset
    resolve_includes = external_config['resolve_includes'] || false
    doc_type = external_config['type'] || 'external_spec'

    file_path = @root_dir / path / file

    content = []

    # Add custom title if specified
    if chapter_config['title']
      content << "#{'=' * chapter_level} #{chapter_config['title']}"
      content << ""
    end

    # Check if we've already included this main file to avoid duplicates in different chapters
    file_key = file_path.to_s
    if @@included_files.include?(file_key)
      content << generate_duplicate_notice(chapter_config, file_path)
      return content.join("\n")
    end

    # Check if file exists
    unless file_path.exist?
      content << generate_missing_file_notice(file_path)
      return content.join("\n")
    end

    # Mark main file as included (but don't affect include resolution)
    @@included_files.add(file_key)

    # Read and process the file
    file_content = read_and_process_file(file_path, external_config, chapter_config, level_offset, doc_type)
    content << file_content

    content.join("\n")
  end

  private

  sig { params(chapter_config: T::Hash[String, T.untyped], file_path: Pathname).returns(String) }
  def generate_duplicate_notice(chapter_config, file_path)
    note_text = if chapter_config['title']
      "This external documentation chapter '#{chapter_config['title']}' has already been included elsewhere in the document: `#{file_path}`"
    else
      "This external documentation has already been included elsewhere in the document: `#{file_path}`"
    end

    "[NOTE]\n" +
    "====\n" +
    note_text + "\n" +
    "====\n"
  end

  sig { params(file_path: Pathname).returns(String) }
  def generate_missing_file_notice(file_path)
    "[WARNING]\n" +
    "====\n" +
    "External documentation file not found: `#{file_path}`\n\n" +
    "This content was expected but the source file is missing. Please check:\n\n" +
    "1. The external documentation submodule is properly initialized\n" +
    "2. The file path in the PRM configuration is correct\n" +
    "3. The file exists in the external documentation directory\n" +
    "====\n"
  end

  sig { params(source: String).returns(String) }
  def generate_missing_config_notice(source)
    "[WARNING]\n" +
    "====\n" +
    "External documentation configuration incomplete for source: #{source}\n\n" +
    "Missing 'path' configuration for external documentation.\n" +
    "====\n"
  end

  sig { params(source: String, path: String).returns(String) }
  def generate_missing_chapters_notice(source, path)
    "[WARNING]\n" +
    "====\n" +
    "External documentation configuration incomplete for source: #{source}\n\n" +
    "Missing 'chapters' configuration. Please specify which files to include from path: #{path}\n" +
    "====\n"
  end

  sig { params(include_path: String, base_dir: Pathname).returns(String) }
  def generate_missing_include_notice(include_path, base_dir)
    "[WARNING]\n" +
    "====\n" +
    "Include file not found: `#{include_path}`\n\n" +
    "Searched in directory: `#{base_dir}`\n" +
    "Full path attempted: `#{base_dir / include_path}`\n\n" +
    "This content was expected but the include file is missing. Please check:\n\n" +
    "1. The external documentation submodule is properly initialized\n" +
    "2. The include path in the source file is correct\n" +
    "3. The included file exists in the external documentation directory\n" +
    "====\n"
  end

  sig { params(file_path: Pathname, external_config: T::Hash[String, T.untyped], chapter_config: T::Hash[String, T.untyped], level_offset: Integer, doc_type: String).returns(String) }
  def read_and_process_file(file_path, external_config, chapter_config, level_offset, doc_type)
    begin
      content = File.read(file_path, encoding: 'UTF-8')

      # Process based on document type
      case doc_type
      when 'isa_manual'
        content = process_isa_manual_content(content, file_path, level_offset, chapter_config)
      when 'external_spec'
        content = process_external_spec_content(content, file_path, level_offset, external_config, chapter_config)
      end

      content + "\n"
    rescue StandardError => e
      "// Error reading external file: #{e.message}\n" +
      "// File path: #{file_path}\n"
    end
  end

  sig { params(content: String, file_path: Pathname, level_offset: Integer, chapter_config: T.nilable(T::Hash[String, T.untyped])).returns(String) }
  def process_isa_manual_content(content, file_path, level_offset, chapter_config = nil)
    # For ISA manual files, preserve image paths and ensure proper formatting
    content = strip_document_attributes(content)
    content = strip_conditional_blocks(content)
    content = strip_document_header(content)

    # Resolve includes first (this may include content with images)
    base_dir = file_path.parent
    content = resolve_includes(content, base_dir)

    # Apply content filtering if specified
    if chapter_config && chapter_config['exclude_content']
      content = filter_content(content, chapter_config['exclude_content'])
    end

    # Fix image paths for ISA manual (after includes are resolved)
    content = fix_image_paths(content, base_dir)

    # Adjust heading levels
    content = adjust_heading_levels(content, level_offset) if level_offset != 0

    # Make IDs unique to avoid conflicts
    content = make_ids_unique(content, file_path.basename('.adoc').to_s)

    content
  end

  sig { params(content: String, file_path: Pathname, level_offset: Integer, external_config: T::Hash[String, T.untyped], chapter_config: T::Hash[String, T.untyped]).returns(String) }
  def process_external_spec_content(content, file_path, level_offset, external_config, chapter_config)
    # For external specs, handle includes and section filtering
    content = strip_document_attributes(content)
    content = strip_document_header(content)

    # Resolve includes if requested
    if external_config['resolve_includes']
      base_dir = file_path.parent
      content = resolve_includes(content, base_dir)
    end

    # Filter content if requested
    if chapter_config['exclude_content']
      content = filter_content(content, chapter_config['exclude_content'])
    end

    # Fix image paths
    base_dir = file_path.parent
    content = fix_image_paths(content, base_dir)

    # Adjust heading levels
    content = adjust_heading_levels(content, level_offset) if level_offset != 0

    # Make IDs unique to avoid conflicts
    content = make_ids_unique(content, file_path.basename('.adoc').to_s)

    content
  end

  sig { params(content: String, base_dir: Pathname).returns(String) }
  def fix_image_paths(content, base_dir)
    # Convert relative image paths to absolute paths from workspace root
    content = content.gsub(/^image::([^:\[]+)(\[[^\]]*\])$/) do |match|
      image_path = $1
      attributes = $2

      # Skip if already absolute or a URL
      if image_path.start_with?('/') || image_path.match?(/^https?:\/\//)
        match
      else
        # Make path relative to workspace root
        absolute_path = base_dir / image_path
        relative_to_root = absolute_path.relative_path_from(@root_dir)
        "image::#{relative_to_root}#{attributes}"
      end
    end

    # Also fix include directives that reference image files (wavedrom, bytefield, etc.)
    content = content.gsub(/^include::([^:\[]+)(\[[^\]]*\])$/) do |match|
      include_path = $1
      attributes = $2

      # Only process paths that look like image includes (contain 'images/' or end with image-like extensions)
      if include_path.include?('images/') || include_path.match?(/\.(edn|svg|png|jpg|jpeg)$/)
        # Skip if already absolute or a URL
        if include_path.start_with?('/') || include_path.match?(/^https?:\/\//)
          match
        else
          # Make path relative to workspace root
          absolute_path = base_dir / include_path
          relative_to_root = absolute_path.relative_path_from(@root_dir)
          "include::#{relative_to_root}#{attributes}"
        end
      else
        match
      end
    end

    content
  end

  sig { params(content: String, base_dir: Pathname).returns(String) }
  def resolve_includes(content, base_dir)
    # Process AsciiDoc include directives
    content.gsub(/^include::([^\[]+)\[([^\]]*)\]$/) do |match|
      include_path = $1
      attributes = $2

      # Skip if absolute path or URL
      if include_path.start_with?('/') || include_path.match?(/^https?:\/\//)
        match
      else
        included_file = base_dir / include_path
        if included_file.exist?
          # Check if we're already processing this file to prevent infinite recursion
          file_key = included_file.to_s
          if @@processing_stack.include?(file_key)
            "// Circular include detected: #{include_path}\n"
          else
            # Mark as processing before reading to prevent infinite recursion
            @@processing_stack.add(file_key)

            begin
              included_content = File.read(included_file, encoding: 'UTF-8')

              # Process the included content (strip headers, fix paths, etc.)
              included_content = strip_document_attributes(included_content)
              included_content = strip_document_header(included_content)
              included_content = fix_image_paths(included_content, included_file.parent)

              # Recursively resolve includes in the included file
              resolved_content = resolve_includes(included_content, included_file.parent)

              resolved_content
            ensure
              # Always remove from processing stack when done
              @@processing_stack.delete(file_key)
            end
          end
        else
          generate_missing_include_notice(include_path, base_dir)
        end
      end
    end
  end



  sig { params(content: String, excludes: T::Array[String]).returns(String) }
  def filter_content(content, excludes)
    return content if excludes.empty?

    excludes.each do |exclude_item|
      lines = content.lines
      start_index = T.let(nil, T.nilable(Integer))
      heading_level = T.let(nil, T.nilable(Integer))

      # Find the content to exclude by AsciiDoc patterns
      lines.each_with_index do |line, index|
        match_found = T.let(false, T::Boolean)

        # Check for various AsciiDoc patterns:
        # 1. ID anchors: [[id]] or [[id,ref...]]
        # 2. ID references: [#id] or [#id,ref...]
        # 3. Section attributes: [attribute] (like [bibliography], [appendix], etc.)
        patterns = [
          /^([[#{Regexp.escape(exclude_item)}(?:,.*?)?]])\s*$/,           # [[id]] or [[id,ref...]]
          /^([##{Regexp.escape(exclude_item)}[^\]]*])\s*$/,                # [#id] or [#id,ref...]
          /^([#{Regexp.escape(exclude_item)}])\s*$/                        # [attribute]
        ]

        patterns.each do |pattern|
          if line.match(pattern)
            start_index = index
            # The next line should be the heading, get its level
            if index + 1 < lines.length
              heading_line = lines[index + 1]
              if T.must(heading_line).match(/^(=+)\s/)
                heading_level = $1.length
              end
            end
            match_found = true
            break
          end
        end

        break if match_found
      end

      if start_index && heading_level
        # Find the end (next heading of same or higher level)
        end_index = T.let(lines.length - 1, T.untyped)  # Default to end of document

        ((start_index + 2)...lines.length).each do |index|
          line = lines[index]
          if T.must(line).match(/^(=+)\s/) && $1.length <= heading_level
            end_index = index - 1
            break
          end
        end

        # Remove the content
        lines.slice!(start_index..end_index)
        content = lines.join
      end
    end

    # Clean up any extra blank lines left behind
    content.gsub(/\n\n\n+/, "\n\n")
  end



  sig { params(content: String, filename: String).returns(String) }
  def make_ids_unique(content, filename)
    # Prefix all IDs with the filename to avoid conflicts
    file_prefix = filename.gsub(/[^a-zA-Z0-9]/, '_').downcase

    # Replace explicit ID attributes
    content = content.gsub(/^\[\[([^\]]+)\]\]$/, "[[#{file_prefix}_\\1]]")
    content = content.gsub(/^(\[#)([^\]]+)(\])$/, "\\1#{file_prefix}_\\2\\3")

    # Replace cross-references to maintain links
    content = content.gsub(/<<([^,>]+)(,[^>]*)?>>/m, "<<#{file_prefix}_\\1\\2>>")

    content
  end

  sig { params(content: String).returns(String) }
  def strip_document_attributes(content)
    # Strip document-level attributes that should only appear at the top level
    content.gsub(/^:[^:]+:.*$\n?/, '')
  end

  sig { params(content: String).returns(String) }
  def strip_conditional_blocks(content)
    # Remove ifdef/ifndef blocks that are used for standalone document generation
    content.gsub(/^ifdef::[^\[]+\[\]\n.*?^endif::[^\[]+\[\]\n?/m, '')
           .gsub(/^ifndef::[^\[]+\[\]\n.*?^endif::[^\[]+\[\]\n?/m, '')
  end

  sig { params(content: String).returns(String) }
  def strip_document_header(content)
    # Remove common document header patterns
    content.gsub(/^:title-logo-image:.*\n/, '')
           .gsub(/^:doctype:.*\n/, '')
           .gsub(/^:toc:.*\n/, '')
           .gsub(/^:numbered:.*\n/, '')
  end

  sig { params(content: String, level_offset: Integer).returns(String) }
  def adjust_heading_levels(content, level_offset)
    return content if level_offset == 0

    content.gsub(/^(=+)(\s+)/) do
      equals = $1
      spaces = $2
      # Calculate new level but cap at 6 to avoid excessive nesting
      new_level_count = [equals.length + level_offset, 6].min
      new_level_count = [new_level_count, 1].max  # Ensure at least level 1
      new_level = '=' * new_level_count
      "#{new_level}#{spaces}"
    end
  end
end

end

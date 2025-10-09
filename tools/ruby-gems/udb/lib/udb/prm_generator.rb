#!/usr/bin/env ruby
# Copyright (c) Synopsys Inc.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: true
# frozen_string_literal: true
require 'erb'
require 'asciidoctor-pdf'
require 'rouge'
require 'asciidoctor-diagram'
require 'fileutils'
require 'pathname'
require 'yaml'
require 'cgi'
require 'set'
require 'open3'
require 'sorbet-runtime'
require_relative 'obj/prm'
require_relative '../../../udb_helpers/lib/udb_helpers/backend_helpers'
require_relative 'obj/non_isa_specification'
require_relative 'external_documentation_renderer'

module PrmGenerator
  # Utility to adjust heading levels in AsciiDoc content
  def self.adjust_heading_levels(content, level_offset)
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

  ##
  # Exception raised when PRM generation fails
  class GenerationError < StandardError; end

  ##
  # Main PRM generation coordinator
  #
  # The Generator class orchestrates the PRM (Processor Reference Manual) generation process.
  # It validates input parameters, loads PRM configuration, and coordinates the creation of
  # AsciiDoc and PDF documentation files. Usage involves initializing with required paths and
  # resolver, then calling `generate_adoc` and/or `generate_pdf` to produce documentation.
  # Key responsibilities:
  #   - Validating inputs and configuration
  #   - Loading PRM data and processor configuration
  #   - Generating component documentation (CSRs, instructions, extensions, non-ISA specs)
  #   - Assembling and exporting the main PRM document in AsciiDoc and PDF formats
  class Generator
    extend T::Sig

    attr_reader :prm_name, :resolver, :output_dir, :template_dir, :root_dir

    def initialize(prm_name, resolver:, output_dir:, template_dir:, root_dir:)
      @prm_name = prm_name
      @resolver = resolver
      @output_dir = Pathname.new(output_dir)
      @template_dir = Pathname.new(template_dir)
      @root_dir = Pathname.new(root_dir)

      validate_inputs
    end

    def generate_adoc
      puts "[INFO] Generating AsciiDoc files for #{prm_name}..."

      prm = load_prm
      processor_config = prm.processor_config
      adoc_output_dir = @output_dir / prm_name / "adoc"

      # Clean and create output directory
      FileUtils.rm_rf(adoc_output_dir)
      FileUtils.mkdir_p(adoc_output_dir)

      # Generate individual component files
      ComponentGenerator.new(processor_config, prm_name, adoc_output_dir, @template_dir).generate_all

      puts "[INFO] AsciiDoc generation complete for #{prm_name}"
    end

    def generate_pdf
      puts "[INFO] Generating PDF for #{prm_name}..."

      prm = load_prm
      pdf_output_dir = @output_dir / prm_name / "pdf"
      FileUtils.mkdir_p(pdf_output_dir)

      # Generate main document
      main_generator = MainDocumentGenerator.new(
        prm,
        @resolver,
        @output_dir / prm_name,
        @template_dir,
        @root_dir
      )

      main_adoc_path = pdf_output_dir / "_prm_main.adoc"
      main_content = main_generator.generate

      File.write(main_adoc_path, main_content)
      puts "[INFO] Generated main AsciiDoc: #{main_adoc_path}"

      # Generate PDF
      pdf_path = pdf_output_dir / "#{prm_name}-specification.pdf"
      PdfGenerator.new(@template_dir, @root_dir).generate(main_adoc_path, pdf_path)

      puts "[INFO] PDF generation complete: #{pdf_path}"
    end

    private

    def validate_inputs
      raise GenerationError, "PRM name cannot be empty" if prm_name.nil? || prm_name.empty?
      raise GenerationError, "Resolver is required" if resolver.nil?
      raise GenerationError, "Template directory does not exist: #{@template_dir}" unless @template_dir.exist?
      raise GenerationError, "Root directory does not exist: #{@root_dir}" unless @root_dir.exist?
    end

    def load_prm
      prm_path = @resolver.custom_path.parent / "non_isa" / "prm_example" / "#{prm_name}.yaml"
      raise GenerationError, "PRM file not found: #{prm_path}" unless prm_path.exist?

      # Load unconfigured architecture
      cfg_arch = @resolver.cfg_arch_for("_")

      # Create PRM object
      prm_data = YAML.load_file(prm_path)
      prm_data["$source"] = prm_path.to_s
      prm = Udb::Prm.new(prm_data, prm_path, cfg_arch)
      prm.resolver = @resolver

      prm
    end
  end

  ##
  # Handles generation of individual component files (CSRs, instructions, extensions)
  class ComponentGenerator
    extend T::Sig
    include Udb::Helpers::TemplateHelpers

    def initialize(processor_config, config_name, output_dir, template_dir)
      @processor_config = processor_config
      @config_name = config_name
      @output_dir = Pathname.new(output_dir)
      @template_dir = Pathname.new(template_dir)
    end

    def generate_all
      generate_csrs
      generate_instructions
      generate_extensions
      generate_non_isa_specs
      generate_config_overview
    end

    private

    def generate_csrs
      csrs_dir = @output_dir / "csrs"
      FileUtils.mkdir_p(csrs_dir)

      template_path = @template_dir / "templates" / "csr.adoc.erb"
      return unless template_path.exist?

      template = load_template(template_path)
      csrs = get_csrs
      cfg_arch = @processor_config  # Template compatibility

      puts "[INFO] Generating #{csrs.length} CSR files..."

      csrs.each do |csr|
        content = template.result(binding)
        content = ContentSanitizer.sanitize(content)
        content = LinkResolver.resolve(@processor_config, content)

        File.write(csrs_dir / "#{csr.name}.adoc", content)
      end
    end

    def generate_instructions
      insts_dir = @output_dir / "insts"
      FileUtils.mkdir_p(insts_dir)

      instructions = get_instructions
      cfg_arch = @processor_config  # Template compatibility

      puts "[INFO] Generating #{instructions.length} instruction files..."

      instructions.each do |inst|
        content = partial("common_templates/adoc/inst.adoc.erb", { inst: inst, cfg_arch: cfg_arch })
        content = ContentSanitizer.sanitize(content)
        content = LinkResolver.resolve(@processor_config, content)
        content += "\n\n<<<\n"
        File.write(insts_dir / "#{inst.name}.adoc", content)
      end
    end

    def generate_extensions
      exts_dir = @output_dir / "exts"
      FileUtils.mkdir_p(exts_dir)

      template_path = @template_dir / "templates" / "ext.adoc.erb"
      return unless template_path.exist?

      template = load_template(template_path)
      extensions = get_extensions
      cfg_arch = @processor_config  # Template compatibility

      puts "[INFO] Generating #{extensions.length} extension files..."

      extensions.each do |ext_version|
        ext = @processor_config.extension(ext_version.name)
        content = template.result(binding)
        content = ContentSanitizer.sanitize(content)
        content = LinkResolver.resolve(@processor_config, content)

        File.write(exts_dir / "#{ext.name}.adoc", content)
      end
    end

    def generate_non_isa_specs
      specs_dir = @output_dir / "non_isa"
      FileUtils.mkdir_p(specs_dir)

      template_path = @template_dir / "templates" / "non_isa_spec.adoc.erb"

      template = load_template(template_path)
      specs = get_non_isa_specs
      cfg_arch = @processor_config  # Template compatibility

      puts "[INFO] Generating #{specs.length} non-ISA specification files..."

      specs.each do |spec|
        begin
          content = template.result(binding)
          content = ContentSanitizer.sanitize(content)
          content = LinkResolver.resolve(@processor_config, content)

          File.write(specs_dir / "#{spec.name}.adoc", content)
        rescue StandardError => e
          puts "[WARN] Failed to generate non-ISA spec #{spec.name}: #{e.message}"
        end
      end
    end

    def generate_config_overview
      template_path = @template_dir / "templates" / "config.adoc.erb"
      return unless template_path.exist?

      template = load_template(template_path)
      config_name = @config_name
      cfg_arch = @processor_config  # Template compatibility

      content = template.result(binding)
      content = ContentSanitizer.sanitize(content)
      content = LinkResolver.resolve(@processor_config, content)

      File.write(@output_dir / "config.adoc", content)
    end

    def load_template(path)
      template = ERB.new(File.read(path, encoding: 'UTF-8'), trim_mode: "-")
      template.filename = path.to_s
      template
    end

    def get_csrs
      if @processor_config.fully_configured?
        @processor_config.transitive_implemented_csrs
      else
        @processor_config.possible_csrs
      end
    end

    def get_instructions
      if @processor_config.fully_configured?
        @processor_config.transitive_implemented_instructions
      else
        @processor_config.possible_instructions
      end
    end

    def get_extensions
      if @processor_config.fully_configured?
        @processor_config.transitive_implemented_extension_versions
      elsif @processor_config.partially_configured?
        @processor_config.possible_extension_versions
      else
        @processor_config.possible_extension_versions
      end
    end

    def get_non_isa_specs
      if @processor_config.fully_configured?
        @processor_config.implemented_non_isa_specs
      else
        @processor_config.possible_non_isa_specs
      end
    end
  end

  ##
  # Sanitizes content to fix HTML entities and other formatting issues
  class ContentSanitizer
    extend T::Sig

    def self.sanitize(content)
      return "" unless content.is_a?(String)

      # Fix HTML entities that cause AsciiDoctor parsing errors
      content = content.gsub(/&ne;/, '≠')
      content = content.gsub(/&ge;/, '≥')
      content = content.gsub(/&le;/, '≤')
      content = content.gsub(/&gt;/, '>')
      content = content.gsub(/&lt;/, '<')
      content = content.gsub(/&amp;/, '&')
      content = content.gsub(/&pm;/, '±')
      content = content.gsub(/&times;/, '×')
      content = content.gsub(/&divide;/, '÷')

      # Fix other common HTML entities
      content = content.gsub(/&nbsp;/, ' ')
      content = content.gsub(/&quot;/, '"')
      content = content.gsub(/&#([0-9]+);/) { [$1.to_i].pack('U*') }
      content = content.gsub(/&#x([0-9a-fA-F]+);/) { [$1.to_i(16)].pack('U*') }

      # Clean up problematic AsciiDoc constructs
      content = content.gsub(/\n\n\n+/, "\n\n")  # Remove excessive blank lines
      content = content.gsub(/\r\n/, "\n")       # Normalize line endings

      # Ensure UTF-8 encoding
      content.force_encoding('UTF-8')

      content
    rescue StandardError => e
      puts "[WARN] Content sanitization failed: #{e.message}"
      content.to_s
    end
  end

  ##
  # Handles link resolution for cross-references
  class LinkResolver
    extend T::Sig

    def self.resolve(processor_config, content)
      return "" unless content.is_a?(String)

      # Resolve %%LINK%...%% and %%UDB_DOC_LINK%...%% markup
      content = content.gsub(/%%(UDB_DOC_LINK|LINK)%([^;%]+)\s*;\s*([^;%]+)\s*;\s*([^%]+)%%/) do
        type = $2.strip
        name = $3.strip
        link_text = $4.strip

        create_asciidoc_link(type, name, link_text)
      end

      # Use processor config's link resolver if available
      if processor_config.respond_to?(:find_replace_links)
        content = processor_config.find_replace_links(content)
      end

      content
    end

    private

    def self.create_asciidoc_link(type, name, link_text)
      escaped_text = link_text.gsub(']', '\\]').gsub(',', '\\,')

      case type
      when "csr_field"
        base_csr_name, field_name = name.split('.', 2)
        "<<csr:#{base_csr_name}-#{field_name}-def,#{escaped_text}>>"
      when "func"
        "<<#{name}-func-def,#{escaped_text}>>"
      when "csr"
        "<<csr-#{name.gsub('.', '_')}-def,#{escaped_text}>>"
      when "inst"
        "<<inst-#{name.gsub('.', '_')}-def,#{escaped_text}>>"
      when "ext"
        "<<ext:#{name}-def,#{escaped_text}>>"
      else
        warn "[WARN] Unknown link type '#{type}' for link to '#{name}'"
        escaped_text
      end
    end
  end

  ##
  # Generates the main PRM document by combining all chapters and content
  class MainDocumentGenerator
    extend T::Sig

    def initialize(prm, resolver, output_base_dir, template_dir, root_dir)
      @prm = prm
      @resolver = resolver
      @output_base_dir = Pathname.new(output_base_dir)
      @template_dir = Pathname.new(template_dir)
      @root_dir = Pathname.new(root_dir)
      @processor_config = prm.processor_config
    end

    def generate
      # Reset tracking for external files
      Udb::ExternalDocumentationRenderer.reset_included_files

      template_path = @template_dir / "templates" / "prm_main.adoc.erb"
      raise GenerationError, "Main template not found: #{template_path}" unless template_path.exist?

      template = ERB.new(File.read(template_path, encoding: 'UTF-8'), trim_mode: "-")
      template.filename = template_path.to_s

      # Prepare template variables
      prepare_template_variables

      # Validate configuration before generation
      validate_configuration

      # Generate content
      content = template.result(binding)
      content = ContentSanitizer.sanitize(content)
      content = LinkResolver.resolve(@processor_config, content)

      # Validate generated content
      validate_generated_content(content)

      content
    end

    private

    def prepare_template_variables
      @config_name = @prm.name
      @prm_pdf_dir = @template_dir
      @root_path = @root_dir
      @adoc_base = @output_base_dir / "adoc"

      @chapters = @prm.chapters
      @extensions_list = get_extensions_list
      @all_instructions = get_all_instructions
      @all_csrs = get_all_csrs

      puts "[INFO] Preparing template variables:"
      puts "  - Configuration: #{@config_name}"
      puts "  - Chapters: #{@chapters.length}"
      puts "  - Extensions: #{@extensions_list.length}"
      puts "  - Instructions: #{@all_instructions.length}"
      puts "  - CSRs: #{@all_csrs.length}"

      # Create external documentation renderer
      @external_doc_renderer = Udb::ExternalDocumentationRenderer.new(@root_dir)

      # Organize content by chapter using new unified approach
      @non_isa_specs_by_chapter = organize_non_isa_specs
    end

    def get_extensions_list
      if @processor_config.fully_configured?
        @processor_config.transitive_implemented_extension_versions
      elsif @processor_config.partially_configured?
        @processor_config.possible_extension_versions
      else
        @processor_config.possible_extension_versions
      end
    end

    def get_all_instructions
      if @processor_config.fully_configured?
        @processor_config.transitive_implemented_instructions
      else
        @processor_config.possible_instructions
      end
    end

    def get_all_csrs
      if @processor_config.fully_configured?
        @processor_config.transitive_implemented_csrs
      else
        @processor_config.possible_csrs
      end
    end

    def get_all_non_isa_specs
      if @processor_config.fully_configured?
        @processor_config.implemented_non_isa_specs
      else
        @processor_config.possible_non_isa_specs
      end
    end

    def organize_non_isa_specs
      specs_by_chapter = {}

      # Process chapters defined in PRM configuration for non-ISA specs only
      @chapters.each do |chapter|
        chapter_id = chapter["id"]

        # Process non_isa_specifications defined for this chapter
        if chapter["non_isa_specifications"]
          chapter["non_isa_specifications"].each do |spec_config|
            spec_obj = nil

            if spec_config.is_a?(Hash) && spec_config.key?("name")
              # Non-ISA spec by name
              spec_name = spec_config["name"]
              discovered_specs = get_all_non_isa_specs
              spec_obj = discovered_specs.find { |s| s.name == spec_name }

              if spec_obj.nil?
                puts "[WARN] Non-ISA spec '#{spec_name}' referenced in chapter '#{chapter_id}' not found"
                next
              end

            else
              puts "[WARN] Invalid non-ISA spec configuration in chapter '#{chapter_id}': #{spec_config}"
              next
            end

            specs_by_chapter[chapter_id] ||= []
            specs_by_chapter[chapter_id] << {
              spec: spec_obj,
              config_placement: spec_config
            }
          end
        end
      end

      specs_by_chapter
    end

    # Helper method for templates to render external documentation
    def render_external_documentation(chapter_id, base_level = 3)
      chapter = @chapters.find { |c| c["id"] == chapter_id }
      return "" unless chapter

      external_docs = chapter["external_documentation"]
      return "" unless external_docs

      begin
        @external_doc_renderer.render_external_documentation(external_docs, base_level)
      rescue StandardError => e
        puts "[WARN] Failed to render external documentation for chapter '#{chapter_id}': #{e.message}"
        generate_external_doc_error_notice(chapter_id, e.message)
      end
    end

    # Helper method for templates to render non-ISA specifications
    def render_non_isa_specifications(chapter_id, base_level = 3)
      specs = @non_isa_specs_by_chapter[chapter_id]
      return "" unless specs

      content = []
      specs.each do |spec_info|
        spec = spec_info[:spec]
        begin
          rendered_content = spec.render_for_cfg(@processor_config, base_level: base_level)
          content << rendered_content if rendered_content && !rendered_content.empty?
        rescue StandardError => e
          puts "[WARN] Failed to render non-ISA spec '#{spec.name}' for chapter '#{chapter_id}': #{e.message}"
          content << generate_spec_error_notice(spec.name, e.message)
        end
      end

      content.join("\n\n")
    end

    private

    def generate_external_doc_error_notice(chapter_id, error_message)
      "[WARNING]\n" +
      "====\n" +
      "Failed to render external documentation for chapter: #{chapter_id}\n\n" +
      "Error: #{error_message}\n\n" +
      "Please check the external documentation configuration and ensure all files are accessible.\n" +
      "====\n"
    end

    def generate_spec_error_notice(spec_name, error_message)
      "[WARNING]\n" +
      "====\n" +
      "Failed to render non-ISA specification: #{spec_name}\n\n" +
      "Error: #{error_message}\n\n" +
      "Please check the specification configuration and ensure all required dependencies are available.\n" +
      "====\n"
    end

    def validate_configuration
      # Validate chapters have proper structure
      @chapters.each do |chapter|
        chapter_id = chapter["id"]
        unless chapter_id && !chapter_id.empty?
          raise GenerationError, "Chapter missing required 'id' field"
        end

        unless chapter["title"] && !chapter["title"].empty?
          raise GenerationError, "Chapter '#{chapter_id}' missing required 'title' field"
        end

        level = chapter["level"] || 2
        unless level.is_a?(Integer) && level >= 1 && level <= 6
          raise GenerationError, "Chapter '#{chapter_id}' has invalid level: #{level}. Must be 1-6."
        end
      end

      puts "[INFO] Configuration validation passed for #{@chapters.length} chapters"
    end

    def validate_generated_content(content)
      # Check for common issues in generated content
      issues = []

      # Check for excessive heading depth
      if content.match(/^=======/)
        issues << "Generated content contains level 7+ headings which may cause formatting issues"
      end

      # Check for unresolved includes
      unresolved_includes = content.scan(/^include::([^\[]+)\[/)
      unless unresolved_includes.empty?
        issues << "Unresolved include directives found: #{unresolved_includes.flatten.join(', ')}"
      end

      # Check for HTML entities that should have been sanitized
      html_entities = content.scan(/&[a-zA-Z]+;/)
      unless html_entities.empty?
        issues << "Unsanitized HTML entities found: #{html_entities.uniq.join(', ')}"
      end

      # Report issues but don't fail generation
      unless issues.empty?
        puts "[WARN] Content validation found issues:"
        issues.each { |issue| puts "  - #{issue}" }
      else
        puts "[INFO] Generated content validation passed"
      end
    end
  end

  ##
  # Handles PDF generation from AsciiDoc
  class PdfGenerator
    extend T::Sig

    def initialize(template_dir, root_dir)
      @template_dir = Pathname.new(template_dir)
      @root_dir = Pathname.new(root_dir)
    end

    def generate(adoc_path, pdf_path)
      puts "[INFO] Generating PDF: #{pdf_path}"

      # Ensure output directory exists
      FileUtils.mkdir_p(File.dirname(pdf_path))

      cmd = build_asciidoctor_command(adoc_path, pdf_path)

      puts "[INFO] Running command: #{cmd.join(' ')}"

      success = T.let(nil, T.nilable(T::Boolean))
      output = ""
      error_output = ""

      Dir.chdir(@root_dir) do
        # Capture both stdout and stderr for better error reporting
        Open3.popen3(cmd.join(" ")) do |stdin, stdout, stderr, wait_thr|
          stdin.close
          output = stdout.read
          error_output = stderr.read
          success = T.cast(wait_thr.value, Process::Status).success?
        end
      end

      # Log output for debugging
      unless output.empty?
        puts "[INFO] AsciiDoctor output:"
        puts output
      end

      unless error_output.empty?
        if success
          puts "[WARN] AsciiDoctor warnings:"
        else
          puts "[ERROR] AsciiDoctor errors:"
        end
        puts error_output
      end

      if success
        puts "[INFO] Successfully generated PDF: #{pdf_path}"
      else
        raise GenerationError, "Failed to generate PDF. Command: #{cmd.join(' ')}\nError output: #{error_output}"
      end
    end

    private

    def build_asciidoctor_command(adoc_path, pdf_path)
      [
        "asciidoctor-pdf",
        "-a", "pdf-themesdir=#{@template_dir / 'pdf-theme'}",
        "-a", "pdf-theme=custom",
        "-a", "pdf-fontsdir=#{@template_dir / 'pdf-theme' / 'fonts'}",
        "-a", "source-highlighter=rouge",
        "-a", "allow-uri-read",
        "-a", "experimental",
        "-r", "asciidoctor-diagram",
        "-o", pdf_path.to_s,
        adoc_path.to_s
      ]
    end
  end

  ##
  # Utility class for including and processing AsciiDoc files
  class FileIncluder
    extend T::Sig

    def self.include_file(file_path, heading_adjustment = 0, strip_title = false)
      return "_Documentation not available_" unless File.exist?(file_path)

      begin
        content = File.read(file_path, encoding: 'UTF-8')
        content = ContentSanitizer.sanitize(content)

        # Strip the first heading if requested (for auto-generated content)
        if strip_title
          content = content.gsub(/^=+\s+.*?\n/, '')
        end

        # Resolve relative includes
        source_dir = File.dirname(file_path)
        content = content.gsub(/^include::([^\/][^\[\]]*\.edn)\[\]$/) do
          relative_path = $1
          absolute_path = File.join(source_dir, relative_path)

          if File.exist?(absolute_path)
            "include::#{absolute_path}[]"
          else
            "include::#{relative_path}[]"  # Let AsciiDoctor handle the error
          end
        end

        # Adjust heading levels using shared utility
        if heading_adjustment != 0
          content = PrmGenerator.adjust_heading_levels(content, heading_adjustment)
        end

        content
      rescue StandardError => e
        puts "[WARN] Failed to include file #{file_path}: #{e.message}"
        "_Error loading documentation: #{e.message}_"
      end
    end
  end
end

#!/usr/bin/env ruby
# typed: false
# frozen_string_literal: true

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Script to generate the config editor HTML with embedded database

require "yaml"
require "json"
require "pathname"
require "erb"

# Find the root directory
root_dir = Pathname.new(__dir__).parent.parent
spec_dir = root_dir / "gen" / "resolved_spec" / "_"

unless spec_dir.exist?
  puts "Error: Resolved spec directory not found at #{spec_dir}"
  puts "Please run 'bin/generate' first to create the resolved spec"
  exit 1
end

# Load extensions
extensions = {}
ext_dir = spec_dir / "ext"
if ext_dir.exist?
  Dir.glob(ext_dir / "*.yaml").each do |file|
    data = YAML.load_file(file)
    name = data["name"]
    extensions[name] = {
      "name" => name,
      "longName" => data["long_name"] || name,
      "versions" => data["versions"]&.map { |v| v["version"] } || []
    }
  end
end

# Load parameters
parameters = {}
param_dir = spec_dir / "param"
if param_dir.exist?
  Dir.glob(param_dir / "*.yaml").each do |file|
    data = YAML.load_file(file)
    name = data["name"]

    # Extract schema
    schema = data["schema"] || {}

    # Extract definedBy condition
    defined_by = data["definedBy"] || data["defined_by"]

    parameters[name] = {
      "name" => name,
      "description" => data["description"] || "",
      "definedBy" => defined_by,
      "schema" => schema
    }
  end
end

# Create the database JSON
database = {
  "extensions" => extensions,
  "parameters" => parameters
}

# Read the template
template_path = Pathname.new(__dir__) / "gui.html.erb"
template = File.read(template_path)

# Generate the HTML
erb = ERB.new(template, trim_mode: "-")
output = erb.result(binding)

# Write the output
output_dir = root_dir / "gen" / "config-editor"
output_dir.mkpath
output_file = output_dir / "gui.html"
File.write(output_file, output)

puts "Generated config editor at: #{output_file}"
puts "Extensions loaded: #{extensions.size}"
puts "Parameters loaded: #{parameters.size}"
puts "\nTo use: open #{output_file}"

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

require "fileutils"
require "json"

schemas_dir, output_dir = ARGV
abort "usage: ruby_schema_serialization_oracle.rb SCHEMAS_DIR OUTPUT_DIR" unless schemas_dir && output_dir

base_url = "https://riscv.github.io/riscv-unified-db/schemas"
Dir.glob(File.join(schemas_dir, "*.json")).sort.each do |schema_file|
  schema_name = File.basename(schema_file)
  next if schema_name == "json-schema-draft-07.json"

  schema = JSON.parse(File.read(schema_file))
  version = schema["$id"]
  next if version.nil?

  schema["$id"] = "#{base_url}/#{schema_name}/#{version}/#{schema_name}"
  destination = File.join(output_dir, schema_name, version, schema_name)
  FileUtils.mkdir_p(File.dirname(destination))
  File.write(destination, JSON.pretty_generate(schema) + "\n")
end

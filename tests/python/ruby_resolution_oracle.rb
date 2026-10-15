# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Transitional test oracle for the Python YAML resolver. This deliberately
# bypasses Udb::Resolver so resolution does not construct an architecture or
# compile IDL.

repo_root = File.expand_path("../..", __dir__)
$LOAD_PATH.unshift(File.join(repo_root, "tools", "ruby-gems", "udb", "lib"))

require "udb/yaml/yaml_resolver"

input_dir, output_dir = ARGV
abort "usage: ruby_resolution_oracle.rb INPUT_DIR OUTPUT_DIR" unless input_dir && output_dir

resolver = Udb::Yaml::Resolver.new(quiet: true, compile_idl: false)
resolver.resolve_files(input_dir, output_dir, no_checks: true)
documents = resolver.instance_variable_get(:@resolved_objs).transform_values { |entry| entry.fetch(:data) }
File.write(File.join(output_dir, "oracle.json"), JSON.generate(documents))

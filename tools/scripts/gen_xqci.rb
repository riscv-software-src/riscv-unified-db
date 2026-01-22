#!/usr/bin/env ruby

# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# typed: false
# frozen_string_literal: true

# This script will create documentation for the Xqci extension

require "fileutils"
require "optparse"
require "pathname"
require "yaml"

options = {
  version: "latest",
  level: "info"
}

OptionParser.new do |parser|
  parser.banner = "Usage: #{$PROGRAM_NAME} [options]\n\nCreate documentation for Xqci"

  parser.on("-v", "--version VERSION", "Version to generate, or 'latest'") do |v|
    options[:version] = v
  end

  parser.on("-d" "--debug LEVEL", ["debug", "info", "warn", "error", "fatal"], "Debug level") do |l|
    options[:level] = l
  end

  parser.on("-h", "--help", "Print usage") do |v|
    puts parser
    exit 0
  end
end.parse!

udb_root = Pathname.new(__dir__) / ".." / ".."

xqci_spec_path = udb_root / "spec" / "custom" / "isa" / "qc_iu" / "ext" / "Xqci.yaml"

xqci_spec = YAML.load_file(xqci_spec_path)

version =
  if options[:version] == "latest"
    xqci_spec["versions"].last
  else
    xqci_spec["versions"].find { |v| v["version"] == options[:version] }
  end

if version.nil?
  warn "Version '#{options[:version]}' does not exist (must be exact match)"
  exit 1
end

FileUtils.mkdir_p "gen/ext-doc/pdf"

cmd = [
  "#{udb_root}/bin/udb-gen",
  "ext-doc",
  "--theme=#{udb_root}/tools/ruby-gems/udb-gen/themes/qc-pdf.yml",
  "--images=#{udb_root}/tools/ruby-gems/udb-gen/assets/img",
  "-o gen/ext-doc/pdf/Xqci-#{version["version"]}.pdf",
  "-c qc_iu",
  "-d #{options[:level]}",
  "-i",
  "--no-csr-field-desc",
  "Xqci@#{version["version"]}",
  version["requirements"]["extension"]["allOf"].map { |r| "#{r["name"]}@#{r["version"].gsub("=", "").strip}" }.join(" ")
].join(" ")

puts cmd
system cmd
exit $?.to_i

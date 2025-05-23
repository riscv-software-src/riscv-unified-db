# SPDX-FileCopyrightText: 2025 syedowaisalishah alishahowais@gmail.com
# SPDX-License-Identifier: BSD-2-Clause

#!/usr/bin/env ruby

require_relative '../lib/idl'  # This loads the IDL compiler and AST
require 'optparse'

options = {}
OptionParser.new do |opts|
  opts.banner = "Usage: format_idl.rb [options] file.idl"

  opts.on("-o", "--output FILE", "Write formatted output to a file") do |v|
    options[:output] = v
  end

  opts.on("-c", "--check", "Check if file is already properly formatted") do
    options[:check] = true
  end
end.parse!

input_file = ARGV[0]

unless input_file && File.exist?(input_file)
  puts "Error: Please provide a valid IDL file."
  exit 1
end

# Parse the IDL file into an AST
ast = Idl::Compiler.compile_file(input_file)

# Generate pretty-printed output (based on your own `to_pretty_idl(indent)` methods)
# If your root AST node has no to_pretty_idl method, use definitions.map...
formatted = if ast.respond_to?(:to_pretty_idl)
               ast.to_pretty_idl(0)
             elsif ast.respond_to?(:definitions)
               ast.definitions.map { |d| d.to_pretty_idl(0) }.join("\n")
             else
               raise "AST does not support pretty printing"
             end

# Optional check mode for pre-commit hooks
if options[:check]
  original = File.read(input_file)
  if original != formatted
    puts "File is not properly formatted: #{input_file}"
    exit 1
  else
    exit 0
  end
end

# Write or print the output
if options[:output]
  File.write(options[:output], formatted)
else
  puts formatted
end

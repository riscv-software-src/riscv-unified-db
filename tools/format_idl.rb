# SPDX-FileCopyrightText: 2025 syedowaisalishah alishahowais@gmail.com
# SPDX-License-Identifier: BSD-2-Clause

#!/usr/bin/env ruby

require_relative '../idl/parser'
require 'optparse'

options = {}
OptionParser.new do |opts|
  opts.banner = "Usage: format_idl.rb [options] file.idl"

  opts.on("-o", "--output FILE", "Write formatted output to a file") do |v|
    options[:output] = v
  end
end.parse!

input_file = ARGV[0]

unless input_file && File.exist?(input_file)
  puts "Error: Please provide a valid IDL file."
  exit 1
end

source = File.read(input_file)
ast = IDL.parse(source)

formatted = ast.pretty_idl(0)

if options[:output]
  File.write(options[:output], formatted)
else
  puts formatted
end

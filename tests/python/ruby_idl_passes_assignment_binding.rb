# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

root = File.expand_path("../..", __dir__)
$LOAD_PATH.unshift(File.join(root, "tools/ruby-gems/idlc/lib"))
require "idlc"
require "idlc/passes/reachable_exceptions"

table = Idl::SymbolTable.new(mxlen: 32, possible_xlens_cb: proc { [32] })
table.add("gate", Idl::Var.new("gate", Idl::Type.new(:boolean)))
compiler = Idl::Compiler.new
source = <<~IDL
  %version: 1.0
  builtin function raise {
    arguments Bits<8> code
    description { Minimal exception marker. }
  }
  function sample {
    description { An unknown AD-update flag permits an implicit write. }
    body {
      raise(5);
      Boolean adue;
      adue = gate;
      if (adue) { raise(7); }
    }
  }
IDL
isa = compiler.parser.parse(source, root: :isa).to_ast
isa.add_global_symbols(table)
body = isa.functions.find { |function| function.name == "sample" }.body
2.times do |iteration|
  context = table.deep_clone
  mask = body.reachable_exceptions(context, {})
  puts "RUBY_MINIMAL_BINDING run=#{iteration} symtab=#{context.name.inspect} mask=#{mask}"
end

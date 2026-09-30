# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Oracle for `src/udb/idl_yaml_source.py`: reproduces exactly how Ruby's
# `Idl::Compiler#compile_func_body` / `#compile_inst_scope`
# (`tools/ruby-gems/idlc/lib/idlc.rb`) report a syntax error's *file* line and
# column for IDL text extracted from a YAML field at a known
# `starting_line`/`starting_offset` -- i.e. the same two entry points
# `Udb::YamlResolver` uses when it hands a field's IDL body to the compiler.
#
# Note (confirmed by reading `idlc.rb` and Treetop's
# `runtime/compiled_parser.rb`/`ruby_extensions/string.rb`): a parse
# *failure*'s line/column are computed purely from Treetop's own
# `failure_line`/`failure_column` against the raw extracted body text (which
# never consults `line_file_offsets`); only `input_line` (== `starting_line`)
# is added back in by the caller for the line number. `starting_offset` and
# `line_file_offsets` only affect *successful* AST node source spans
# (`AstNode#lineno`/`#column`), not failure reporting.
#
# Reads {"body": str, "root": "function_body"|"instruction_operation",
# "input_file": str, "input_line": int} from stdin and writes
# {"ok": true} or {"ok": false, "line": int, "column": int, "reason": str}.

require "json"
require "pathname"

repo_root = Pathname.new(File.expand_path("../..", __dir__))
$LOAD_PATH.unshift((repo_root / "tools/ruby-gems/idlc/lib").to_s)
require "idlc"

request = JSON.parse($stdin.read)
compiler = Idl::Compiler.new
root = request.fetch("root")

result =
  begin
    case root
    when "function_body"
      compiler.compile_func_body(
        request.fetch("body"),
        name: "oracle",
        input_file: request.fetch("input_file"),
        input_line: request.fetch("input_line"),
        type_check: false
      )
    when "instruction_operation"
      compiler.compile_inst_scope(
        request.fetch("body"),
        symtab: nil,
        input_file: request.fetch("input_file"),
        input_line: request.fetch("input_line")
      )
    else
      raise ArgumentError, "unsupported root #{root}"
    end
    { "ok" => true }
  rescue SyntaxError => e
    # "While parsing <name> at <file>:<line>\n\n<reason>" (compile_func_body)
    # or "While parsing <file>:<line>\n\n<reason>" (compile_inst_scope).
    message = e.message
    location = message[/:(\d+)$/, 1] || message[/:(\d+)\n/, 1]
    { "ok" => false, "line" => location&.to_i, "message" => message }
  end

puts JSON.generate(result)

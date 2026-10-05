# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Transitional oracle for the Ruby IDL parser.
#
# Reads {"cases": [{"id": str, "root": str, "text": str}, ...]} from stdin and
# writes one result per case: either {"ok": true, "ast": <to_h>} or
# {"ok": false, "index": int, "line": int, "column": int} for syntax errors.
# Include statements cannot be serialized by Ruby's to_h and are reported as
# {"kind": "include", "filename": ...}.
#
# Accepted cases also carry two additive fields (backward compatible, existing
# keys are unchanged):
#   "to_idl":     the result of AstNode#to_idl, or null if to_idl raised.
#   "round_trip": true if to_idl succeeded, the text reparsed with the same
#                 root, and the reparsed AST's dump is structurally equal to
#                 the original dump with all "source" spans stripped. false
#                 otherwise (including when to_idl or the reparse raises).

require "json"
require "pathname"

repo_root = Pathname.new(File.expand_path("../..", __dir__))
$LOAD_PATH.unshift((repo_root / "tools/ruby-gems/idlc/lib").to_s)
require "idlc"

ROOTS = %w[isa function_body instruction_operation expression constraint_body for_loop].freeze

def dump(node)
  if node.is_a?(Idl::IncludeStatementAst)
    { "kind" => "include", "filename" => node.filename }
  elsif node.is_a?(Idl::IsaAst)
    { "kind" => "isa", "children" => node.children.map { |c| dump(c) }, "source" => node.source_yaml }
  else
    node.to_h
  end
end

# recursively strip "source" keys so two dumps can be compared modulo spans
def strip_source(obj)
  case obj
  when Hash
    obj.each_with_object({}) do |(k, v), h|
      h[k] = strip_source(v) unless k == "source"
    end
  when Array
    obj.map { |v| strip_source(v) }
  else
    obj
  end
end

input = JSON.parse($stdin.read)
parser = IdlParser.new

results = input.fetch("cases").map do |c|
  root = c.fetch("root")
  raise ArgumentError, "unsupported root #{root}" unless ROOTS.include?(root)

  parser.set_input_file(c.fetch("id"), 0, 0, nil)
  m = parser.parse(c.fetch("text"), root: root.to_sym)
  if m.nil?
    {
      "ok" => false,
      "index" => parser.failure_index,
      "line" => parser.failure_line,
      "column" => parser.failure_column
    }
  else
    begin
      ast = m.to_ast
      ast.set_input_file(c.fetch("id"), 0, 0, nil)
      dumped = dump(ast)

      to_idl = nil
      round_trip = false
      begin
        to_idl = ast.to_idl
        parser2 = IdlParser.new
        parser2.set_input_file(c.fetch("id"), 0, 0, nil)
        m2 = parser2.parse(to_idl, root: root.to_sym)
        unless m2.nil?
          ast2 = m2.to_ast
          ast2.set_input_file(c.fetch("id"), 0, 0, nil)
          dumped2 = dump(ast2)
          round_trip = (strip_source(dumped) == strip_source(dumped2))
        end
      rescue StandardError
        round_trip = false
      end

      { "ok" => true, "ast" => dumped, "to_idl" => to_idl, "round_trip" => round_trip }
    rescue StandardError => e
      { "ok" => false, "exception" => "#{e.class}: #{e.message}" }
    end
  end
end

puts JSON.generate(results)

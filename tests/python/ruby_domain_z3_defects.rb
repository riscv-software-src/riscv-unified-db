# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

require "json"
require "udb/z3"

def accepts?(schema, value)
  solver = Udb::Z3Solver.new
  parameter = Udb::Z3ParameterTerm.new("parameter", solver, schema)
  solver.assert(parameter == value)
  solver.satisfiable?
end

results = {
  # Ruby checks "unique", not the Draft 7 keyword "uniqueItems".
  "accepts_duplicate_unique_items" => accepts?(
    {
      "type" => "array",
      "items" => { "type" => "integer", "enum" => [0, 7, 16] },
      "minItems" => 1,
      "maxItems" => 3,
      "uniqueItems" => true
    },
    [0, 0]
  ),
  # Ruby applies contains to allocated slots beyond the array's logical size.
  "accepts_array_without_required_item" => accepts?(
    {
      "type" => "array",
      "items" => { "type" => "integer", "enum" => [0, 7, 16] },
      "contains" => { "const" => 0 },
      "minItems" => 1,
      "maxItems" => 3,
      "uniqueItems" => true
    },
    [7]
  ),
  # Ruby's integer constraint builder does not inspect exclusiveMinimum.
  "accepts_exclusive_lower_endpoint" => accepts?(
    { "type" => "integer", "exclusiveMinimum" => 1, "maximum" => 5 },
    1
  )
}

puts JSON.generate(results)

# SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
# SPDX-License-Identifier: BSD-3-Clause-Clear

require "json"
require "json_schemer"

input = JSON.parse($stdin.read)
schemer = JSONSchemer.schema(input.fetch("schema"), regexp_resolver: "ecma")
puts JSON.generate(input.fetch("values").map { |value| schemer.valid?(value) })

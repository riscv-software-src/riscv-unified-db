<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Standalone Python IDL tool contract

The retained `idlc` capabilities are parsing an input file to an AST,
evaluating an expression with ordered parameter definitions, and type-checking
an instruction operation with optional YAML extraction and decode variables.
The Python tool uses the accepted parser, symbol table, checker and evaluator,
not a second language implementation or a Ruby subprocess.

Initial exposure is a module CLI; final unified command names and repository
wrapper cutover remain separate integration decisions. Preserve the existing
`compile`, `eval` and `tc inst` operations and their documented options.
Standalone checking supplies 32 unknown 64-bit `X` registers, just as the old
CLI does. Defining `MXLEN` does not silently change that register-file contract.
No database, configuration discovery, Git, network or native helper is needed.

Capture the real Ruby commands before implementing this adapter. Preserve raw
stdout/stderr, exit status, arguments, source hashes and interpreter version.
Compare complete evaluation output and parsed AST data, plus actual success/
failure and meaningful located diagnostics for instruction checking. Python
AST serialization follows the public Python tree representation; YAML layout,
exception class names and Ruby backtraces are not a byte-compatibility promise.
Unexpected compiler failures must not become successful empty output.

Input and output are UTF-8. Render/validate before opening an output file.
Invalid command/input/output must report an error with a nonzero status; a
missing YAML field or non-string field is an error, not an empty operation.
Define values are full IDL expressions, including operators containing `=`;
decode widths and identifiers require explicit validation.

The initial native capture has 20 commands. Its valid fixtures use IDL `#`
comments; the preliminary probes with C-style comments remain archived under
`gen/handoff/idl-cli-initial-oracle.json`, not credited as valid parsing.
Three frontend corrections have independent native witnesses: Ruby's define
split truncates `A=1==1` to `A=1`, whereas direct native `eval '1 == 1'` prints
`true`; its Commander parser loses a bare stdin `-`, whereas `-- -` succeeds
for both normal and strict checking. Python preserves full define expressions
and accepts the documented bare stdin spelling. Raw captures are unchanged.

Evaluation stdout and complete decoded ASTs match the native cases. The Python
compiler additionally emits its existing truncation warning for fixed-width
overflow; the CLI intentionally retains that warning rather than suppressing
it to imitate Ruby's quiet output. Literal and single-line plain YAML diagnostics
reuse the accepted enclosing-file source map. Quoted/folded strings and
multiline plain scalars remain valid CLI inputs and explicitly label any
diagnostic coordinates as a decoded scalar.
Invalid arguments exit 2; input, IDL and output errors exit 1.

```shell
python -m udb.idl.cli eval -DA=8 "'hff + A"
python -m udb.idl.cli compile --format json functions.isa
python -m udb.idl.cli tc inst -d xd=5 -d xs1=5 -k 'operation()' instruction.yaml
```

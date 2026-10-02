---
sidebar_position: 15
status: in-progress
---

# The IDL Compiler

:::warning[Status: In Progress]
The command-line workflow is documented here. The Python API reference is still
being expanded.
:::

The IDL compiler is part of the Python `udb` package. It parses IDL into a
source-aware abstract syntax tree, binds symbols, evaluates compile-time values,
type-checks operations, and supplies semantic passes used by validation and
generators.

For IDL language syntax, see the [Language Reference](./overview.mdx).

## Command-line use

The installed command groups standalone compiler tools under `udb idl`:

```bash
uv run udb idl --help
```

### Parse and serialize syntax

`idl compile` parses a source file and writes its syntax tree as YAML or JSON.
Select the grammar root that matches the input:

```bash
uv run udb idl compile functions.isa
uv run udb idl compile operation.idl --root instruction_operation --format json
uv run udb idl compile expression.idl --root expression -o expression.json
```

Supported roots are `isa`, `function_body`, `instruction_operation`,
`expression`, `constraint_body`, and `for_loop`.

### Evaluate an expression

`idl eval` evaluates a standalone 64-bit expression. Repeat `-D` to provide
compile-time definitions:

```bash
uv run udb idl eval "XLEN / 8" -D XLEN=64
```

### Type-check an instruction operation

`idl check instruction` type-checks one operation body. Definitions supply
compile-time values, while `--var NAME=WIDTH` declares instruction decode
variables:

```bash
uv run udb idl check instruction operation.idl \
  -D XLEN=64 \
  --var rs1=5 \
  --var rs2=5 \
  --strict
```

Use `--key` when the input belongs to a named source field and diagnostics
should carry that key.

## Check architecture IDL

For IDL embedded in UDB instruction, CSR, and function definitions, use
architecture validation:

```bash
uv run udb validate idl --config rv64
```

Repository developers can run the equivalent maintained check through mise:

```bash
mise run check:idl -- --config rv64
```

The repository also splits full real-database coverage into bounded slow lanes;
run `mise tasks` to see the current `test:slow:idl*` tasks.

## Compilation model

The compiler performs these stages:

1. Parse the selected IDL grammar root and retain exact source locations.
2. Build the typed Python AST under `udb.idl.ast`.
3. Construct an `IdlEnvironment` containing global functions, types,
   configuration values, instruction decode variables, and CSR context.
4. Bind names and type-check expressions and statements. Non-strict checking may
   omit configuration-proven unreachable code; strict checking visits it.
5. Run consumer-specific passes such as reachability, pruning, register/CSR
   discovery, return analysis, and C++ hart lowering.

Architecture-aware compilation is provided by `ArchitectureCompiler` in
`udb.idl_architecture`. A configured architecture can compile instruction and
CSR behavior directly, and `type_check()` checks all available architecture IDL.

## Python entry points

The lower-level parser functions are exported from `udb.idl`:

```python
from udb.idl import parse_expression, parse_function_body, parse_isa

expression = parse_expression("64 / 8")
functions = parse_isa(source_text, label="functions.isa")
body = parse_function_body("return 1;")
```

For database-backed work, prefer the configured architecture and
`ArchitectureCompiler`; it supplies the correct source provider, symbol table,
configuration values, and effective XLEN. Generators should reuse compiled
architecture results instead of reparsing source independently.

Compiler errors derive from `IdlError` and preserve source location and semantic
context. Syntax, semantic, type, internal, and unknown-value failures remain
distinct so callers can report useful diagnostics without inspecting strings.

<!--
SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Ruby-to-Python command map

The Ruby command wrappers, Rake tasks, gems, and Sorbet workflows were removed.
UDB now has two supported interfaces:

- the installed `udb` command for database, IDL, authoring, validation,
  generation, and rendering operations;
- `mise run <task>` for development work tied to a repository checkout.

From a checkout, use `uv run udb ...` to invoke the installed command without
manually activating an environment. Run `uv run udb --help` and `mise tasks` for
the authoritative command lists.

| Removed command                                         | Replacement                                                     |
| ------------------------------------------------------- | --------------------------------------------------------------- |
| `bin/udb`, `bin/idlc`, `bin/udb-gen`, `bin/generate`    | `uv run udb ...`                                                |
| `bin/setup`                                             | `mise run setup`                                                |
| `bin/doctor`                                            | `mise run doctor`                                               |
| `bin/regress`, `./do test:unit`, `./do test:smoke`      | `mise run test`                                                 |
| `./do test:regress`                                     | `mise run check:all`                                            |
| `./do test:schema`                                      | `mise run check:data`                                           |
| `./do test:idl CFG=NAME`                                | `mise run check:idl -- --config NAME`                           |
| `./do test:inst_encodings`                              | `mise run check:encodings`                                      |
| `./do test:csrs`                                        | `mise run check:csrs`                                           |
| `./do gen:resolved_arch`                                | `uv run udb resolve -o DIR`                                     |
| `./do gen:schemas`                                      | `uv run udb generate schema-bundle -o DIR`                      |
| `./do gen:arch`                                         | `uv run udb author layouts --root .`                            |
| `./do gen:cfg`                                          | `mise run gen:profile-configs`                                  |
| `./do gen:c_header`                                     | `uv run udb generate c-encoding ...`                            |
| `./do gen:sverilog`                                     | `uv run udb generate sv-decode ...`                             |
| `./do gen:go`                                           | `uv run udb generate go-encoding ...`                           |
| `./do gen:cpp_hart`                                     | `uv run udb generate cpp-hart ...`                              |
| `bin/chore gen all`                                     | `mise run gen:all`                                              |
| `bin/chore gen smoke`                                   | `mise run gen:quick`                                            |
| `bin/chore gen schema-docs`                             | `mise run gen:schema-docs`                                      |
| `bin/chore gen vscode-idl`                              | `mise run gen:idl-grammar`                                      |
| `bin/chore container build/pull/remove`                 | `mise run container:build/container:pull/container:remove`      |
| `./do build:cpp_hart`, `./do build:iss`                 | `mise run build:cpp-hart`, `mise run build:iss`                 |
| `./do test:cpp_hart`                                    | `mise run test:cpp-hart`                                        |
| `./do test:riscv_tests`, `./do test:riscv_vector_tests` | `mise run test:riscv-tests`, `mise run test:riscv-vector-tests` |
| `./do test:softfloat`, `./do test:llvm`                 | `mise run test:softfloat`, `mise run test:llvm`                 |
| `./bin/aubr -C doc build`                               | `mise run docs:build site`                                      |
| `./bin/aubr -C doc start`                               | `mise run docs:build site`, then `mise run docs:serve site`     |

Ruby-only gem installation, gem release, Sorbet/RBI, YARD, and native-extension
dependency chores have no replacement. Python dependencies are declared in
`pyproject.toml` and locked by `uv.lock`; Python artifacts use the repository's
package and release tasks. Asciidoctor remains an explicit external renderer for
generated AsciiDoc and is not part of the UDB implementation.

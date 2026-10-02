SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB <https://github.com/riscv/riscv-unified-db>
SPDX-License-Identifier: BSD-3-Clause-Clear

Raw, frozen Ruby artifact evidence, captured before native implementation.
Baseline d6b06ca3.

legacy-unit.txt is a verbatim copy of:
tools/ruby-gems/udb-gen/test/unit/fixtures/inst_table/expected.txt
SHA256 39e258ef5949f18e0595d95d15d70a81a69cf7800699268987e6b2a24f01af8b

legacy-all-file.txt is a verbatim copy of:
tools/ruby-gems/udb-gen/test/integration/fixtures/inst_table/expected.txt
SHA256 84decffca54d1c359d29879e71cfd0a450c816d205a3212b8934b29f74e09cf8

native-{all,rv32,rv64,full}-stdout.txt are genuine TableBuilder.generate
captures using _, rv32, rv64 and cfgs/mc100-32-full-example.yaml respectively.
All four have 1421 lines and SHA256:
061e3526a34fe1ec43f7363d442767091b8f93f71ef6230fc59927371f8bea5a

The legacy TableBuilder enumerates all instructions, regardless of configuration.
It does not enumerate implemented_instructions or possible_instructions.
All fixtures are compared verbatim: no normalization.

These are reviewed, immutable legacy captures. The retired implementation and
capture utility are no longer present, so there is no refresh command.

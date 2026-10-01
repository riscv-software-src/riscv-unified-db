// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB
// <https://github.com/riscv/riscv-unified-db> SPDX-License-Identifier: BSD-3-Clause-Clear
#include "bits_property.hpp"

TEST_CASE("Native Bits legacy unsigned width 64", "[bits][native][legacy]") {
  bits_test::legacy_width<64>();
}
TEST_CASE("Native Bits legacy unsigned width 128", "[bits][native][legacy]") {
  bits_test::legacy_width<128>();
}

// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB
// <https://github.com/riscv/riscv-unified-db> SPDX-License-Identifier: BSD-3-Clause-Clear
#include "bits_property.hpp"

TEST_CASE("Native Bits legacy unsigned width 1", "[bits][native][legacy]") {
  bits_test::legacy_width<1>();
}
TEST_CASE("Native Bits legacy unsigned width 8", "[bits][native][legacy]") {
  bits_test::legacy_width<8>();
}
TEST_CASE("Native Bits legacy unsigned width 16", "[bits][native][legacy]") {
  bits_test::legacy_width<16>();
}
TEST_CASE("Native Bits legacy unsigned width 32", "[bits][native][legacy]") {
  bits_test::legacy_width<32>();
}

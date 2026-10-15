// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB
// <https://github.com/riscv/riscv-unified-db> SPDX-License-Identifier: BSD-3-Clause-Clear
#include "bits_property.hpp"

TEST_CASE("Native Bits signed width 1", "[bits][native][signed]") { bits_test::signed_width<1>(); }
TEST_CASE("Native Bits signed width 8", "[bits][native][signed]") { bits_test::signed_width<8>(); }
TEST_CASE("Native Bits signed width 16", "[bits][native][signed]") {
  bits_test::signed_width<16>();
}
TEST_CASE("Native Bits signed width 32", "[bits][native][signed]") {
  bits_test::signed_width<32>();
}
TEST_CASE("Native Bits signed width 64", "[bits][native][signed]") {
  bits_test::signed_width<64>();
}
TEST_CASE("Native Bits signed width 128", "[bits][native][signed]") {
  bits_test::signed_width<128>();
}

// SPDX-FileCopyrightText: 2026 Contributors to the RISCV UnifiedDB
// <https://github.com/riscv/riscv-unified-db> SPDX-License-Identifier: BSD-3-Clause-Clear
#pragma once

#include <catch2/catch_test_macros.hpp>
#include <charconv>
#include <cstdlib>
#include <random>
#include <string_view>
#include <udb/bits.hpp>

namespace bits_test {

  inline mpz_class power(unsigned width) {
    mpz_class result;
    mpz_setbit(result.get_mpz_t(), width);
    return result;
  }

  inline mpz_class truncate(const mpz_class& value, unsigned width) {
    mpz_class result;
    mpz_fdiv_r_2exp(result.get_mpz_t(), value.get_mpz_t(), width);
    return result;
  }

  inline mpz_class interpret(const mpz_class& raw, unsigned width, bool is_signed) {
    mpz_class result = truncate(raw, width);
    if (is_signed && mpz_tstbit(result.get_mpz_t(), width - 1)) {
      result -= power(width);
    }
    return result;
  }

  // Import/export the storage independently of udb's conversion helpers.
  template <class Integer>
  mpz_class integer_value(const Integer& value) {
    if constexpr (std::same_as<Integer, mpz_class>) {
      return value;
    } else {
      using Unsigned = std::make_unsigned_t<Integer>;
      const bool negative = std::is_signed_v<Integer> && value < 0;
      Unsigned magnitude = static_cast<Unsigned>(value);
      if (negative) magnitude = Unsigned{0} - magnitude;
      mpz_class result;
      mpz_import(result.get_mpz_t(), 1, 1, sizeof(magnitude), 0, 0, &magnitude);
      return negative ? -result : result;
    }
  }

  inline uint64_t seed() {
    const char* env = std::getenv("UDB_BITS_SEED");
    if (!env) return 1234;
    const std::string_view text(env);
    uint64_t result = 0;
    const auto parsed = std::from_chars(text.data(), text.data() + text.size(), result);
    if (parsed.ec != std::errc{} || parsed.ptr != text.data() + text.size()) {
      throw std::invalid_argument("UDB_BITS_SEED must be a decimal uint64");
    }
    return result;
  }

  inline mpz_class random_raw(std::mt19937_64& rng, unsigned width) {
    mpz_class result = 0;
    for (unsigned bit = 0; bit < width; bit += 64) {
      result <<= 64;
      result += rng();
    }
    return truncate(result, width);
  }

  inline std::vector<mpz_class> edges(unsigned width) {
    const mpz_class high = power(width - 1);
    const mpz_class mask = power(width) - 1;
    mpz_class alternating = 0;
    for (unsigned bit = 0; bit < width; bit += 2) {
      mpz_setbit(alternating.get_mpz_t(), bit);
    }
    std::vector<mpz_class> result;
    for (const mpz_class& value :
         std::vector<mpz_class>{0, 1, 2, 3, high - 1, high, high + 1, mask - 1, mask, alternating,
                                mask ^ alternating}) {
      const mpz_class raw = truncate(value, width);
      if (std::find(result.begin(), result.end(), raw) == result.end()) result.push_back(raw);
    }
    return result;
  }

  template <class Bits>
  Bits make(const mpz_class& raw, unsigned width) {
    constexpr bool is_signed = Bits::IsSigned;
    // Width is bounded by the declared capacity in all test factories.
    if constexpr (Bits::RuntimeWidth) {
      constexpr unsigned capacity = Bits::MaskType::width();
      return Bits{udb::_Bits<capacity, is_signed>{raw}, udb::_Bits<32, false>{width}};
    } else {
      return Bits{udb::_Bits<Bits::width(), is_signed>{raw}};
    }
  }

  template <class Lhs, class Rhs>
  void relations(const Lhs& lhs, const Rhs& rhs, const mpz_class& lv, const mpz_class& rv) {
    CHECK((lhs == rhs) == (lv == rv));
    CHECK((lhs != rhs) == (lv != rv));
    CHECK((lhs < rhs) == (lv < rv));
    CHECK((lhs <= rhs) == (lv <= rv));
    CHECK((lhs > rhs) == (lv > rv));
    CHECK((lhs >= rhs) == (lv >= rv));
    CHECK((rhs == lhs) == (rv == lv));
    CHECK((rhs != lhs) == (rv != lv));
    CHECK((rhs < lhs) == (rv < lv));
    CHECK((rhs <= lhs) == (rv <= lv));
    CHECK((rhs > lhs) == (rv > lv));
    CHECK((rhs >= lhs) == (rv >= lv));
  }

  template <bool Signed, class Result>
  void value(const Result& result, const mpz_class& expected, unsigned width) {
    STATIC_REQUIRE(Result::IsSigned == Signed);
    REQUIRE(result.width() == width);
    CHECK(integer_value(result.get()) == interpret(expected, width, Signed));
    if constexpr (Result::PossiblyUnknown) {
      CHECK(integer_value(result.unknown_mask().get()) == 0);
    }
  }

  template <class Lhs, class Rhs, class Result>
  void arithmetic_result(const Lhs& lhs, const Rhs& rhs, const Result& result, const mpz_class& lv,
                         const mpz_class& rv, const mpz_class& expected, unsigned width) {
    constexpr bool is_signed = Lhs::IsSigned && Rhs::IsSigned;
    STATIC_REQUIRE(Result::RuntimeWidth == (Lhs::RuntimeWidth || Rhs::RuntimeWidth));
    value<is_signed>(result, expected, width);
    const mpz_class result_value = interpret(expected, width, is_signed);
    relations(lhs, result, lv, result_value);
    relations(rhs, result, rv, result_value);
  }

  template <class Lhs, class Rhs>
  void arithmetic(const Lhs& lhs, const Rhs& rhs, const mpz_class& lhs_raw,
                  const mpz_class& rhs_raw) {
    const unsigned width = std::max(lhs.width(), rhs.width());
    const mpz_class lv = interpret(lhs_raw, lhs.width(), Lhs::IsSigned);
    const mpz_class rv = interpret(rhs_raw, rhs.width(), Rhs::IsSigned);
    CAPTURE(lhs.width(), rhs.width(), Lhs::IsSigned, Rhs::IsSigned);
    INFO("raw lhs=" << lhs_raw.get_str(16) << " rhs=" << rhs_raw.get_str(16));
    relations(lhs, rhs, lv, rv);
    {
      INFO("operation=+");
      arithmetic_result(lhs, rhs, lhs + rhs, lv, rv, lv + rv, width);
    }
    {
      INFO("operation=-");
      arithmetic_result(lhs, rhs, lhs - rhs, lv, rv, lv - rv, width);
    }
    {
      INFO("operation=*");
      arithmetic_result(lhs, rhs, lhs * rhs, lv, rv, lv * rv, width);
    }
    {
      INFO("operation=widening_add");
      arithmetic_result(lhs, rhs, lhs.widening_add(rhs), lv, rv, lv + rv, width + 1);
    }
    {
      INFO("operation=widening_sub");
      arithmetic_result(lhs, rhs, lhs.widening_sub(rhs), lv, rv, lv - rv, width + 1);
    }
    {
      INFO("operation=widening_mul");
      arithmetic_result(lhs, rhs, lhs.widening_mul(rhs), lv, rv, lv * rv,
                        lhs.width() + rhs.width());
    }
    if (rv != 0) {
      // Minimum signed value / -1 is undefined in native C++. It has no error contract.
      const bool native_overflow =
          Lhs::IsSigned && Rhs::IsSigned && lv == -power(width - 1) && rv == -1;
      if (!native_overflow) {
        mpz_class quotient, remainder;
        mpz_tdiv_qr(quotient.get_mpz_t(), remainder.get_mpz_t(), lv.get_mpz_t(), rv.get_mpz_t());
        {
          INFO("operation=/");
          arithmetic_result(lhs, rhs, lhs / rhs, lv, rv, quotient, width);
        }
        {
          INFO("operation=%");
          arithmetic_result(lhs, rhs, lhs % rhs, lv, rv, remainder, width);
        }
      }
    }
  }

  template <class Lhs, class Shift>
  void shifts(const Lhs& lhs, const Shift& shift, const mpz_class& raw, unsigned count) {
    const unsigned width = lhs.width();
    const mpz_class lv = interpret(raw, width, Lhs::IsSigned);
    const mpz_class rv = count;
    CAPTURE(width, count, Lhs::IsSigned);
    INFO("raw lhs=" << raw.get_str(16));
    if constexpr (!Lhs::IsSigned) relations(lhs, shift, lv, rv);
    {
      INFO("operation=<<");
      mpz_class expected;
      mpz_mul_2exp(expected.get_mpz_t(), raw.get_mpz_t(), count);
      const auto result = lhs << shift;
      value<Lhs::IsSigned>(result, expected, width);
      relations(lhs, result, lv, interpret(expected, width, Lhs::IsSigned));
      if constexpr (!Lhs::IsSigned) relations(shift, result, rv, interpret(expected, width, false));
    }
    {
      INFO("operation=>>");
      mpz_class expected;
      mpz_fdiv_q_2exp(expected.get_mpz_t(), raw.get_mpz_t(), count);
      const auto result = lhs >> shift;
      value<Lhs::IsSigned>(result, expected, width);
      relations(lhs, result, lv, interpret(expected, width, Lhs::IsSigned));
      if constexpr (!Lhs::IsSigned) relations(shift, result, rv, interpret(expected, width, false));
    }
    {
      INFO("operation=sra");
      const mpz_class signed_raw = interpret(raw, width, true);
      mpz_class expected;
      mpz_fdiv_q_2exp(expected.get_mpz_t(), signed_raw.get_mpz_t(), count);
      const auto result = lhs.sra(shift);
      value<Lhs::IsSigned>(result, expected, width);
      relations(lhs, result, lv, interpret(expected, width, Lhs::IsSigned));
      if constexpr (!Lhs::IsSigned) relations(shift, result, rv, interpret(expected, width, false));
    }
    {
      INFO("operation=widening_sll");
      mpz_class expected;
      mpz_mul_2exp(expected.get_mpz_t(), lv.get_mpz_t(), count);
      const auto result = lhs.widening_sll(shift);
      value<Lhs::IsSigned>(result, expected, width + count);
      relations(lhs, result, lv, interpret(expected, width + count, Lhs::IsSigned));
      if constexpr (!Lhs::IsSigned)
        relations(shift, result, rv, interpret(expected, width + count, false));
    }
  }

  template <template <unsigned, bool> class Family, unsigned N, bool Signed = false>
  void same_width() {
    using Bits = Family<N, Signed>;
    constexpr unsigned shift_width = N <= 128 ? N : 32;
    using Shift = Family<shift_width, false>;
    INFO("family runtime=" << Bits::RuntimeWidth << " unknown-capable=" << Bits::PossiblyUnknown);
    const uint64_t replay_seed = seed();
    CAPTURE(replay_seed, N, Signed);
    std::mt19937_64 rng(replay_seed ^ (uint64_t{N} << 32) ^ (Signed ? 0x5349474eULL : 0));
    const auto boundaries = edges(N);
    unsigned sample = 0;
    for (const auto& lhs_raw : boundaries) {
      for (const auto& rhs_raw : boundaries) {
        CAPTURE(sample);
        arithmetic(make<Bits>(lhs_raw, N), make<Bits>(rhs_raw, N), lhs_raw, rhs_raw);
        ++sample;
      }
    }
    for (unsigned i = 0; i < 64; ++i) {
      CAPTURE(sample);
      const mpz_class lhs_raw = random_raw(rng, N);
      const mpz_class rhs_raw = random_raw(rng, N);
      arithmetic(make<Bits>(lhs_raw, N), make<Bits>(rhs_raw, N), lhs_raw, rhs_raw);
      ++sample;
    }
    for (const auto& raw : boundaries) {
      for (unsigned count : {0u, 1u, N - 1, N, N + 1, 2 * N - 1}) {
        // A one-bit shift operand can only encode 0 and 1, as in the old generator.
        if (mpz_class(count) >= power(shift_width)) continue;
        shifts(make<Bits>(raw, N), make<Shift>(mpz_class(count), shift_width), raw, count);
      }
    }
    for (unsigned i = 0; i < 64; ++i) {
      CAPTURE(i);
      const mpz_class raw = random_raw(rng, N);
      const unsigned count = rng() % (2 * N);
      shifts(make<Bits>(raw, N), make<Shift>(mpz_class(count), shift_width), raw, count);
    }
  }

  template <unsigned N>
  void legacy_width() {
    same_width<udb::_Bits, N>();
    same_width<udb::_RuntimeBits, N>();
    same_width<udb::_PossiblyUnknownBits, N>();
    same_width<udb::_PossiblyUnknownRuntimeBits, N>();
  }

  template <unsigned N>
  void signed_width() {
    same_width<udb::_Bits, N, true>();
  }

}  // namespace bits_test

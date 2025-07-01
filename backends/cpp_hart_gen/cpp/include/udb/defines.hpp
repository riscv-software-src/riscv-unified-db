#pragma once

#include <algorithm>
#include <cstdlib>
#include <string_view>
#include <version>

// type to be used when you want to pass a string literal as a template
// argument
template <size_t N = 0>
struct TemplateString {
  constexpr TemplateString(const char (&str)[N]) : size(N) {
    std::copy_n(str, N, cstr_value);
  }
  constexpr char *value() const { return cstr_value; }
  constexpr std::string_view sv() const { return cstr_value; }
  const size_t size;
  char cstr_value[N == 0 ? 1 : N];
};

#if defined(__cpp_lib_source_location) && __cpp_lib_source_location >= 201907L
#include <source_location>
#endif

#if defined(__cpp_lib_unreachable) && __cpp_lib_unreachable >= 202202L
#include <utility>
#define udb_unreachable() std::unreachable()
#else
#define udb_unreachable() __builtin_unreachable()
#endif

#include <fmt/core.h>
#include <fmt/std.h>

#if defined(__cpp_lib_source_location) && __cpp_lib_source_location >= 201907L
#define __udb_assert(cond, msg)                              \
  do {                                                       \
    if (!(cond)) {                                           \
      fmt::print(stderr, "At {} :\n   Assertion failed: {}", \
                 std::source_location::current(), (msg));    \
      std::abort();                                          \
    }                                                        \
  } while (false)
#else
#define __udb_assert(cond, msg)                                           \
  do {                                                                    \
    if (!(cond)) {                                                        \
      fmt::print(stderr, "At {}:{} :\n   Assertion failed: {}", __FILE__, \
                 __LINE__, msg);                                          \
      std::abort();                                                       \
    }                                                                     \
  } while (false)
#endif

#if __has_cpp_attribute(assume) >= 202207L

#if defined(NDEBUG)
#define udb_assert(cond, msg) [[assume(cond)]]
#else
#define udb_assert(cond, msg) \
  __udb_assert(cond, msg);    \
  [[assume(cond)]]
#endif

#else  // !__has_cpp_attribute( assume )

#if defined(NDEBUG)
#define udb_assert(cond, msg)  // do nothing
#else
#define udb_assert(cond, msg) __udb_assert(cond, msg)
#endif

#endif  // __has_cpp_attribute( assume )

namespace udb {
  constexpr inline unsigned MAX_POSSIBLE_XLEN = 64;
}

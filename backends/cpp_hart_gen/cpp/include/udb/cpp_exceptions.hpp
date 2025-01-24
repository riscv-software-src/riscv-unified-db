#pragma once

#include <stdexcept>

namespace udb {
  // thrown when a input to a calculation is undefined
  class UndefinedValueError : public std::runtime_error {
   public:
    UndefinedValueError(const std::string& why) : std::runtime_error(why) {}
  };

  // thrown when the source or destination registers of an instruction
  // is dependent on the value of a register and cannot be determined statically
  class ComplexRegDetermination : public std::runtime_error {
   public:
    ComplexRegDetermination()
        : std::runtime_error(
              "Register set cannot be determined at compile time") {}
  };
}  // namespace udb

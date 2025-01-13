#pragma once

#include <stdexcept>

namespace udb {
  class UndefinedValueError : public std::runtime_error
  {
    public:
    UndefinedValueError(const std::string& why)
      : std::runtime_error(why)
    {}
  };
}

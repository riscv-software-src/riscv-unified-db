#pragma once

#include <stdexcept>

namespace udb {
  // thrown when there is an issue querying the db (e.g., asking for an enum
  // member that doesn't exist)
  class DbError : public std::runtime_error {
   public:
    DbError(const std::string& why) : std::runtime_error(why) {}
  };

  // thrown when a input to a calculation is undefined
  class UndefinedValueError : public std::runtime_error {
   public:
    UndefinedValueError(const std::string& why) : std::runtime_error(why) {}
  };

  // thrown when there is an attempt to get the indirect address of a direct CSR, or vice versa
  class CsrAddressTypeError : public std::runtime_error {
   public:
    CsrAddressTypeError(const std::string& why) : std::runtime_error(why) {}
  };

  // thrown when the source or destination registers of an instruction
  // is dependent on the value of a register and cannot be determined statically
  class ComplexRegDetermination : public std::runtime_error {
   public:
    ComplexRegDetermination()
        : std::runtime_error(
              "Register set cannot be determined at compile time") {}
  };

  // thrown when a running program exits (only occurs with certain tracers)
  class ExitEvent : public std::exception {
   public:
    ExitEvent(int exit_code) : std::exception(), m_exit_code(exit_code) {}
    virtual ~ExitEvent() = default;

    int code() const { return m_exit_code; }

   private:
    int m_exit_code;
  };

  // object that is thrown when an instruction (or fetch) encounters an
  // exception
  class AbortInstruction : public std::exception {
   public:
    const char* what() const noexcept override { return "Instruction Abort"; }
  };

  class WfiException : public std::exception {
   public:
    const char* what() const noexcept override { return "WFI instruction"; }
  };

  class PauseException : public std::exception {
   public:
    const char* what() const noexcept override { return "PAUSE instruction"; }
  };

  class UnpredictableBehaviorException : public std::exception {
   public:
    const char* what() const noexcept override {
      return "Encountered unpredictable behavior";
    }
  };
}  // namespace udb

#pragma once

#include <string>

class Elf;
namespace udb {
  // Class to read data out of an ELF file
  class Memory;
  class ElfReader {
    // ElfException is thrown when something goes wrong when reading an ELF file
    class ElfException : public std::exception {
     public:
      ElfException() = default;
      ElfException(const std::string& what) : std::exception(), m_what(what) {}
      ElfException(std::string&& what)
          : std::exception(), m_what(std::move(what)) {}

      const char* what() const noexcept override { return m_what.c_str(); }

     private:
      const std::string m_what;
    };

   public:
    ElfReader() = delete;
    ElfReader(const std::string& path);
    ~ElfReader();

    // get the address of a symbol named 'name', and put it in 'result'
    //
    // returns false if the symbol is not found, true otherwise
    bool getSym(const std::string& name, Elf64_Addr* result);

    // Loads all LOADable sections from an ELF into 'm'
    //
    // returns the start address
    uint64_t loadLoadableSegments(Memory& m);

   private:
    int m_fd;
    Elf* m_elf;
  };
}  // namespace udb

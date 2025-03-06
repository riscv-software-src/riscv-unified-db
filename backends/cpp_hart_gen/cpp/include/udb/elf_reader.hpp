#pragma once

#include <libelf.h>

#include <limits>
#include <string>
#include <utility>

#include "udb/soc_model.hpp"

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

    // return the smallest and largest address from any LOADable segment
    std::pair<uint64_t, uint64_t> mem_range();

    // return starting address
    uint64_t entry();

    // get the address of a symbol named 'name', and put it in 'result'
    //
    // returns false if the symbol is not found, true otherwise
    bool getSym(const std::string& name, Elf64_Addr* result);

    // Loads all LOADable sections from an ELF into 'm'
    //
    // returns the start address
    template <SocModel SocType>
    uint64_t loadLoadableSegments(SocType& soc);

   private:
    template <unsigned char CLASS>
    std::pair<uint64_t, uint64_t> _mem_range();

    template <unsigned char CLASS, SocModel SocType>
    uint64_t _loadLoadableSegments(SocType& soc);

   private:
    int m_fd;
    Elf* m_elf;
    unsigned char m_class;
    uint64_t m_entry;
  };

  template <unsigned char CLASS>
  std::pair<uint64_t, uint64_t> ElfReader::_mem_range() {
    std::conditional_t<CLASS == ELFCLASS32, Elf32_Phdr, Elf64_Phdr>* phdr;
    size_t n;
    uint64_t smallest_addr = std::numeric_limits<uint64_t>::max();
    uint64_t largest_addr = std::numeric_limits<uint64_t>::min();

    if (elf_getphdrnum(m_elf, &n) != 0) {
      throw ElfException("Could not find number of Program Headers");
    }

    if constexpr (CLASS == ELFCLASS32) {
      phdr = elf32_getphdr(m_elf);
    } else {
      phdr = elf64_getphdr(m_elf);
    }
    for (size_t i = 0; i < n; i++) {
      if (phdr[i].p_type == PT_LOAD) {
        if (phdr[i].p_vaddr < smallest_addr) {
          smallest_addr = phdr[i].p_vaddr;
        }
        if (phdr[i].p_vaddr + phdr[i].p_memsz > largest_addr) {
          largest_addr = phdr[i].p_vaddr + phdr[i].p_memsz;
        }
      }
    }

    return std::make_pair(smallest_addr, largest_addr);
  }

  template <unsigned char CLASS, SocModel SocType>
  uint64_t ElfReader::_loadLoadableSegments(SocType& soc) {
    std::conditional_t<CLASS == ELFCLASS32, Elf32_Phdr, Elf64_Phdr>* phdr;
    size_t n;

    if (elf_getphdrnum(m_elf, &n) != 0) {
      throw ElfException("Could not find number of Program Headers");
    }

    if constexpr (CLASS == ELFCLASS32) {
      phdr = elf32_getphdr(m_elf);
    } else {
      phdr = elf64_getphdr(m_elf);
    }
    for (size_t i = 0; i < n; i++) {
      if (phdr[i].p_type == PT_LOAD) {
        Elf_Data* d = elf_getdata_rawchunk(m_elf, phdr[i].p_offset,
                                           phdr[i].p_filesz, ELF_T_BYTE);
        soc.memcpy_from_host(phdr[i].p_vaddr,
                             reinterpret_cast<const uint8_t*>(d->d_buf),
                             d->d_size);
      }
    }

    if constexpr (CLASS == ELFCLASS32) {
      return elf32_getehdr(m_elf)->e_entry;
    } else {
      return elf64_getehdr(m_elf)->e_entry;
    }
  }

  // returns start address
  template <SocModel SocType>
  uint64_t udb::ElfReader::loadLoadableSegments(SocType& soc) {
    if (m_class == ELFCLASS32) {
      return _loadLoadableSegments<ELFCLASS32>(soc);
    } else {
      return _loadLoadableSegments<ELFCLASS64>(soc);
    }
  }
}  // namespace udb

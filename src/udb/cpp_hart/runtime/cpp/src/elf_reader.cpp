
#include <fcntl.h>
#include <gelf.h>
#include <sys/stat.h>
#include <sys/types.h>

#include <udb/elf_reader.hpp>
#include <udb/memory.hpp>

udb::ElfReader::ElfReader(const std::string& path) {
  if (elf_version(EV_CURRENT) == EV_NONE) {
    throw ElfException("Bad Elf version");
  }

  m_fd = open(path.c_str(), O_RDONLY, 0);
  if (m_fd < 0) {
    throw ElfException("Could not open ELF file");
  }

  m_elf = elf_begin(m_fd, ELF_C_READ, NULL);
  if (m_elf == nullptr) {
    throw ElfException("Could not begin reading ELF");
  }

  if (elf_kind(m_elf) != ELF_K_ELF) {
    throw ElfException("Not an ELF file");
  }

  GElf_Ehdr hdr;
  if(gelf_getehdr(m_elf, &hdr) != &hdr) {
    throw ElfException("could not get elf header");
  }
  m_entry = hdr.e_entry;
}

udb::ElfReader::~ElfReader() {
  if (m_elf != nullptr) {
    elf_end(m_elf);
    close(m_fd);
  }
}

uint64_t udb::ElfReader::entry() { return m_entry; }

bool udb::ElfReader::getSym(const std::string& name, Elf64_Addr* result) {
  size_t num_sections;
  if (elf_getshdrnum(m_elf, &num_sections) != 0) {
    throw ElfException("Could not determine number of sections");
  }
  size_t shstrtab_index;
  if (elf_getshdrstrndx(m_elf, &shstrtab_index) != 0) {
    throw ElfException("Could not get Section Header String Table");
  }
  // first, find the strtab
  int strtab_index;
  for (size_t i = 0; i < num_sections; i++) {
    auto* strtab_section = elf_getscn(m_elf, i);
    GElf_Shdr shdr;

    if (gelf_getshdr(strtab_section, &shdr) != &shdr) {
      throw ElfException("Could not get Section Header");
    }

    if (strcmp(elf_strptr(m_elf, shstrtab_index, shdr.sh_name), ".strtab") ==
        0) {
      strtab_index = i;
      break;
    }
  }
  // now, get the symtab
  for (size_t i = 0; i < num_sections; i++) {
    Elf_Scn* section;
    section = elf_getscn(m_elf, i);
    GElf_Shdr section_header;
    if (gelf_getshdr(section, &section_header) != &section_header) {
      throw ElfException("Could not get Section Header");
    }

    if (strcmp(elf_strptr(m_elf, shstrtab_index, section_header.sh_name),
               ".symtab") == 0) {
      unsigned num_syms = section_header.sh_size / section_header.sh_entsize;
      Elf_Data* data;
      if ((data = elf_getdata(section, nullptr)) == nullptr) {
        throw ElfException(fmt::format("Could not get symtab data. {}",
                                       elf_errmsg(elf_errno()))
                               .c_str());
      }

      for (unsigned j = 0; j < num_syms; j++) {
        GElf_Sym sym;
        if (gelf_getsym(data, (int)j, &sym) != &sym) {
          throw ElfException("Could not get symbol");
        }

        if (strcmp(elf_strptr(m_elf, strtab_index, sym.st_name),
                   name.c_str()) == 0) {
          *result = sym.st_value;
          return true;
        }
      }
    }
  }
  return false;
}

std::pair<uint64_t, uint64_t> udb::ElfReader::mem_range() {
  size_t n;
  uint64_t addr_lo = std::numeric_limits<uint64_t>::max();
  uint64_t addr_hi = std::numeric_limits<uint64_t>::min();

  //Make room for any section allocating memory
  if(elf_getshdrnum(m_elf, &n) == 0 && n > 0) {
    for (size_t i = 0; i < n; i++) {
      Elf_Scn* pscn = elf_getscn(m_elf, i);
      if(pscn != NULL) {
        GElf_Shdr shdr;
        if(gelf_getshdr(pscn, &shdr) != &shdr) {
          throw ElfException("Cannot get section header");
        }

        if (shdr.sh_flags & SHF_ALLOC) {
          addr_lo = std::min(addr_lo, shdr.sh_addr);
          addr_hi = std::max(addr_hi, shdr.sh_addr + shdr.sh_size);
        }
      }
    }
  }

  //No memory to be allocated
  if(addr_lo > addr_hi) {
    addr_lo = addr_hi = 0;
  }

  return std::make_pair(addr_lo, addr_hi);
}

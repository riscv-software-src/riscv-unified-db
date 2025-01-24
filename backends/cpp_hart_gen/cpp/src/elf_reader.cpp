
#include <fcntl.h>
#include <libelf.h>
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
}

udb::ElfReader::~ElfReader() {
  if (m_elf != nullptr) {
    elf_end(m_elf);
    close(m_fd);
  }
}

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
    Elf64_Shdr* header = elf64_getshdr(strtab_section);
    if (strcmp(elf_strptr(m_elf, shstrtab_index, header->sh_name), ".strtab") ==
        0) {
      strtab_index = i;
      break;
    }
  }
  // now, get the symtab
  for (size_t i = 0; i < num_sections; i++) {
    Elf_Scn* section;
    section = elf_getscn(m_elf, i);
    Elf64_Shdr* section_header = elf64_getshdr(section);
    if (strcmp(elf_strptr(m_elf, shstrtab_index, section_header->sh_name),
               ".symtab") == 0) {
      unsigned num_syms = section_header->sh_size / section_header->sh_entsize;
      Elf64_Sym* symtab;
      Elf_Data* data;
      if ((data = elf_getdata(section, nullptr)) == nullptr) {
        throw ElfException(fmt::format("Could not get symtab data. {}",
                                       elf_errmsg(elf_errno()))
                               .c_str());
      }
      symtab = (Elf64_Sym*)data->d_buf;
      for (unsigned j = 0; j < num_syms; j++) {
        if (strcmp(elf_strptr(m_elf, strtab_index, symtab[j].st_name),
                   name.c_str()) == 0) {
          *result = symtab[j].st_value;
          return true;
        }
      }
    }
  }
  return false;
}

// returns start address
uint64_t udb::ElfReader::loadLoadableSegments(Memory& m) {
  Elf64_Phdr* phdr;
  size_t n;

  if (elf_getphdrnum(m_elf, &n) != 0) {
    throw ElfException("Could not find number of Program Headers");
  }

  phdr = elf64_getphdr(m_elf);
  for (size_t i = 0; i < n; i++) {
    if (phdr[i].p_type == PT_LOAD) {
      Elf_Data* d = elf_getdata_rawchunk(m_elf, phdr[i].p_offset,
                                         phdr[i].p_filesz, ELF_T_BYTE);
      m.memcpy_from_host(phdr[i].p_vaddr, d->d_buf, d->d_size);
    }
  }

  return elf64_getehdr(m_elf)->e_entry;
}

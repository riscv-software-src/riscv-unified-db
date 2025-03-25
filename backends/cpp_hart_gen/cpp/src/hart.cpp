#include "iss/hart.hpp"

void riscv::Memory::memcpy_from_host(uint64_t guest_paddr, const void* host_ptr,
                                     size_t size) {
  const size_t SZ_64 = sizeof(uint64_t);
  auto host_ptr64 = (const uint64_t*)host_ptr;  // NOLINT
  while (size >= SZ_64) {
    write((guest_paddr += SZ_64) - SZ_64, *host_ptr64++);
    size -= SZ_64;
  }

  auto host_ptr8 = (const uint8_t*)host_ptr64;  // NOLINT
  while (size > 0) {
    write(guest_paddr++, *host_ptr8++);
    size--;
  }
}

void riscv::Memory::memcpy_to_host(void* host_ptr, uint64_t guest_paddr,
                                   size_t size) {
  const size_t SZ_64 = sizeof(uint64_t);
  auto host_ptr64 = (uint64_t*)host_ptr;  // NOLINT
  while (size >= SZ_64) {
    *(host_ptr64++) = read<uint64_t>(guest_paddr += SZ_64);
    size -= SZ_64;
  }

  auto host_ptr8 = (uint8_t*)host_ptr64;  // NOLINT
  while (size > 0) {
    *(host_ptr8++) = read<uint8_t>(guest_paddr += SZ_64);
    size--;
  }
}

void riscv::HartBase::printState(FILE* out) const {
  fprintf(out, "Hart %u:\n", m_hart_id);
  if (sizeof(XReg) == 8) {
    fprintf(out, ISS_FORMAT("PC: {:#18x}\n", m_pc).c_str());
    for (int i = 0; i < 16; i++) {
      fprintf(out, ISS_FORMAT("x{:2}: {:#18x}\tx{:2}: {:#18x}\n", i, m_xregs[i],
                              i + 16, m_xregs[16 + 1])
                       .c_str());
    }
  } else if (sizeof(XReg) == 4) {
    fprintf(out, ISS_FORMAT("PC: {:#10x}\n", m_pc).c_str());
    for (int i = 0; i < 16; i++) {
      fprintf(out, ISS_FORMAT("x{:2}: {:#10x}\tx{:2}: {:#10x}\n", i, m_xregs[i],
                              i + 16, m_xregs[16 + 1])
                       .c_str());
    }
  } else {
    assert(!"unsupported xlen");
  }
}

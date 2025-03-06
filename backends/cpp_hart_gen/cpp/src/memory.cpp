
#include "udb/memory.hpp"

void udb::Memory::memcpy_from_host(uint64_t guest_paddr, const void* host_ptr,
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

void udb::Memory::memcpy_to_host(void* host_ptr, uint64_t guest_paddr,
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

#pragma once

#include "udb/defines.hpp"

namespace udb {
  class Memory {
   public:
    Memory() = default;
    virtual ~Memory() = default;

    template <class T>
    T read(uint64_t paddr);
    template <class T>
    void write(uint64_t paddr, T data);
    void memcpy_from_host(uint64_t guest_paddr, const void* host_ptr,
                          size_t size);
    void memcpy_to_host(void* host_ptr, uint64_t guest_paddr, size_t size);
    virtual uint8_t* get_host_region_ptr(uint64_t paddr) { return nullptr; }
    virtual void reset() {}

   protected:
    // subclasses only need to override these functions:
    virtual uint64_t read(uint64_t addr, size_t bytes) {
      udb_assert(false, "Memory::read() not implemented");
      return 0;
    }
    virtual void write(uint64_t addr, uint64_t data, size_t bytes) {
      udb_assert(false, "Memory::write() not implemented");
    }

    // but may optionally override these instead:
    virtual uint8_t read1(uint64_t addr) { return read(addr, 1); }
    virtual uint16_t read2(uint64_t addr) { return read(addr, 2); }
    virtual uint32_t read4(uint64_t addr) { return read(addr, 4); }
    virtual uint64_t read8(uint64_t addr) { return read(addr, 8); }
    virtual void write1(uint64_t addr, uint8_t data) { write(addr, data, 1); }
    virtual void write2(uint64_t addr, uint16_t data) { write(addr, data, 2); }
    virtual void write4(uint64_t addr, uint32_t data) { write(addr, data, 4); }
    virtual void write8(uint64_t addr, uint64_t data) { write(addr, data, 8); }
  };
  template <>
  inline uint8_t Memory::read(uint64_t addr) {
    return read1(addr);
  }
  template <>
  inline uint16_t Memory::read(uint64_t addr) {
    return read2(addr);
  }
  template <>
  inline uint32_t Memory::read(uint64_t addr) {
    return read4(addr);
  }
  template <>
  inline uint64_t Memory::read(uint64_t addr) {
    return read8(addr);
  }
  template <>
  inline unsigned __int128 Memory::read(uint64_t addr) {
    return read8(addr) |
           (static_cast<unsigned __int128>(read8(addr + 8)) << 64);
  }
  template <>
  inline void Memory::write(uint64_t addr, uint8_t data) {
    write1(addr, data);
  }
  template <>
  inline void Memory::write(uint64_t addr, uint16_t data) {
    write2(addr, data);
  }
  template <>
  inline void Memory::write(uint64_t addr, uint32_t data) {
    write4(addr, data);
  }
  template <>
  inline void Memory::write(uint64_t addr, uint64_t data) {
    write8(addr, data);
  }
  template <>
  inline void Memory::write(uint64_t addr, unsigned __int128 data) {
    write8(addr, uint64_t(data));
    write8(addr + 8, uint64_t(data >> 64));
  }

  class MemObject {
   public:
    MemObject(uint64_t base_addr, uint64_t size)
        : m_base_addr(base_addr), m_end_addr(base_addr + size), m_size(size) {}
    virtual ~MemObject() = default;

    template <class T>
    T read(uint64_t addr);

    virtual uint8_t read1(uint64_t addr) = 0;
    virtual uint16_t read2(uint64_t addr) = 0;
    virtual uint32_t read4(uint64_t addr) = 0;
    virtual uint64_t read8(uint64_t addr) = 0;
    virtual void write(uint64_t addr, uint8_t data) = 0;
    virtual void write(uint64_t addr, uint16_t data) = 0;
    virtual void write(uint64_t addr, uint32_t data) = 0;
    virtual void write(uint64_t addr, uint64_t data) = 0;

    uint64_t base_addr() const { return m_base_addr; }
    uint64_t size() const { return m_size; }
    bool contains_addr(uint64_t addr) const {
      return addr >= m_base_addr && addr < m_end_addr;
    }
    virtual uint8_t* host_pointer() { return nullptr; }

   private:
    uint64_t m_base_addr = 0;
    uint64_t m_end_addr = 0;
    uint64_t m_size = 0;
  };
  template <>
  inline uint8_t MemObject::read(uint64_t addr) {
    return read1(addr);
  }
  template <>
  inline uint16_t MemObject::read(uint64_t addr) {
    return read2(addr);
  }
  template <>
  inline uint32_t MemObject::read(uint64_t addr) {
    return read4(addr);
  }
  template <>
  inline uint64_t MemObject::read(uint64_t addr) {
    return read8(addr);
  }

  class MemRegion : public MemObject {
   public:
    MemRegion(uint64_t base_addr, uint64_t size) : MemObject(base_addr, size) {
      m_data.resize(size);
      m_addend = &m_data[0] - base_addr;
    }

    uint8_t* host_pointer() override { return &m_data[0]; }

    // the caller must guarantee that the access falls within the region
    uint8_t read1(uint64_t addr) override {
      return *(uint8_t*)(addr + m_addend);
    }
    uint16_t read2(uint64_t addr) override {
      return *(uint16_t*)(addr + m_addend);
    }
    uint32_t read4(uint64_t addr) override {
      return *(uint32_t*)(addr + m_addend);
    }
    uint64_t read8(uint64_t addr) override {
      return *(uint64_t*)(addr + m_addend);
    }
    void write(uint64_t addr, uint8_t data) override {
      *(uint8_t*)(addr + m_addend) = data;
    }
    void write(uint64_t addr, uint16_t data) override {
      *(uint16_t*)(addr + m_addend) = data;
    }
    void write(uint64_t addr, uint32_t data) override {
      *(uint32_t*)(addr + m_addend) = data;
    }
    void write(uint64_t addr, uint64_t data) override {
      *(uint64_t*)(addr + m_addend) = data;
    }

   private:
    std::vector<uint8_t> m_data;
    uint8_t* m_addend = nullptr;
  };
}  // namespace udb

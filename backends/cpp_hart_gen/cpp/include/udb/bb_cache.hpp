#pragma once

namespace udb {
  class InstBase;

  template <unsigned SizeOfInst>
  class BasicBlock {
   public:
    static constexpr const unsigned MAX_BASIC_BLOCK_SIZE = 40;

    using InstStorage = std::array<uint8_t, SizeOfInst>;

    BasicBlock()
        : m_size(0), m_head(0), m_start_pc(~static_cast<uint64_t>(0)) {}

    void recycle(uint64_t start_pc) {
      m_start_pc = start_pc;
      m_size = 0;
      m_head = 0;
    }

    uint64_t start_pc() const { return m_start_pc; }
    unsigned size() const { return m_size; }
    void reset() { m_head = 0; }
    void invalidate() { m_start_pc = ~static_cast<uint64_t>(0); }

    bool full() const { return m_size == MAX_BASIC_BLOCK_SIZE; }

    InstBase* alloc_inst() {
      InstBase* inst = reinterpret_cast<InstBase*>(m_insts[m_size].data());
      m_size++;
      return inst;
    }

    // return the next instruction
    // does *not* check that the bb has another instruction
    InstBase* pop() {
      return reinterpret_cast<InstBase*>(m_insts[m_head++].data());
    }

   private:
    unsigned m_size;
    unsigned m_head;
    uint64_t m_start_pc;
    std::array<InstStorage, MAX_BASIC_BLOCK_SIZE> m_insts;
  };

  template <unsigned SizeOfInst>
  class BasicBlockCache {
    static const constexpr unsigned NUM_BASIC_BLOCKS = 2048;
    static_assert(__builtin_popcount(NUM_BASIC_BLOCKS) == 1,
                  "NUM_BASIC_BLOCKS must be a power of two");

   public:
    using BasicBlockType = BasicBlock<SizeOfInst>;
    static constexpr unsigned MAX_BASIC_BLOCK_SIZE =
        BasicBlockType::MAX_BASIC_BLOCK_SIZE;

    BasicBlockCache() {}

    BasicBlock<SizeOfInst>* get(uint64_t pc) {
      unsigned idx = hash(pc);
      return &m_bbs[idx];
    }

    void invalidate() {
      for (unsigned i = 0; i < NUM_BASIC_BLOCKS; i++) {
        m_bbs[i].invalidate();
      }
    }

   private:
    unsigned hash(uint64_t pc) {
      // return number between [0..NUM_BASIC_BLOCKS)
      return (pc >> 2) & (NUM_BASIC_BLOCKS - 1);
    }

   private:
    std::array<BasicBlockType, NUM_BASIC_BLOCKS> m_bbs;
  };
}  // namespace udb

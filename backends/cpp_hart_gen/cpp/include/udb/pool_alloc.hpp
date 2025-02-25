#pragma once

#include <concepts>
#include <cstdint>
#include <cstdio>

#include "udb/defines.hpp"

namespace udb {
  // simple memory pool allocator

  template <typename Klass>
  concept PoolAllocatable = (sizeof(Klass) >= sizeof(Klass*));

  struct PoolObj {
    void* m_next;
  };

  template <PoolAllocatable BaseObjType, unsigned ObjSize,
            unsigned PoolSize =
                200 /* Number of elements to grow the pool by on a resize */>
  class PoolAllocator {
   public:
    PoolAllocator()
        : m_freelist_head(nullptr)
#ifndef NDEBUG
          ,
          m_total_obj_created(0),
          m_allocated_objs(0)
#endif
    {
    }

    ~PoolAllocator() {
      // fprintf(stderr,
      //         "Warning: The pool allocator does not free memory "
      //         "on deconstruction. You probably shouldn't delete it.\n");
    }

    // allocate a single object with a custom size
    BaseObjType* allocate() noexcept {
      if (m_freelist_head == nullptr) {
        // need more objects

        m_freelist_head = (BaseObjType*)new char[PoolSize * ObjSize];

        for (unsigned i = 0; i < PoolSize; i++) {
          if (i == PoolSize - 1) {
            reinterpret_cast<PoolObj*>(&m_freelist_head[i])->m_next = nullptr;
          } else {
            reinterpret_cast<PoolObj*>(&m_freelist_head[i])->m_next =
                reinterpret_cast<BaseObjType*>(&m_freelist_head[i + 1]);
          }
        }
#ifndef NDEBUG
        m_total_obj_created += PoolSize;
#endif
      }
      BaseObjType* ret = m_freelist_head;
      m_freelist_head = reinterpret_cast<BaseObjType*>(
          reinterpret_cast<PoolObj*>(ret)->m_next);
#ifndef NDEBUG
      m_allocated_objs++;
#endif
      return ret;
    }

    void free(BaseObjType* del) noexcept {
      reinterpret_cast<PoolObj*>(del)->m_next = m_freelist_head;
      m_freelist_head = del;
#ifndef NDEBUG
      // check against double free
      udb_assert(m_allocated_objs > 0, "double free");
      m_allocated_objs--;
#endif
    }

   private:
    BaseObjType* m_freelist_head;

#ifndef NDEBUG
    uint64_t m_total_obj_created;
    uint64_t m_allocated_objs;
#endif
  };
}  // namespace udb

#include "udb/Tracer.hpp"
#include "udb/inst.hpp"

namespace udb
{
  InstructionTracer::InstructionTracer(HartBase<IssSocModel>* pHart)
  {
    m_pHart = pHart;

    //Enable events for instruction tracing
    EnableEvent(TRACE_HART_MODULE, udb::PREEXECUTE_EVENT);
    EnableEvent(TRACE_HART_MODULE, udb::EXECUTE_EVENT);

    //Attach to the Hart
    m_pHart->AttachHandler(this, TRACE_HART_MODULE);
  }

  InstructionTracer::~InstructionTracer()
  {

  }

  int InstructionTracer::OnNotification(uint8_t uiModuleId, uint64_t uiEvent, void* pData)
  {
    if(uiModuleId != TRACE_HART_MODULE)
      return 0;

    //Instruction trace
    switch(uiEvent)
    {
    case PREEXECUTE_EVENT:
      {
        udb::InstBase* pInst = (udb::InstBase*)pData;
        fmt::print("PC {:x} {}\n", m_pHart->pc(), pInst->disassemble());
        for(auto r : pInst->srcRegs())
          fmt::print("R {} {:x}\n", r.to_string(), m_pHart->xreg(r.get_num()));
      }
      break;
    case EXECUTE_EVENT:
      {
        udb::InstBase* pInst = (udb::InstBase*)pData;
        for (auto r : pInst->dstRegs())
          fmt::print("R= {} {:x}\n", r.to_string(), m_pHart->xreg(r.get_num()));
      }
      break;
    case EXCEPTION_EVENT:
    default:
      break;
    }
    return 0;
  }
}

udb::MemoryTracer::MemoryTracer(IssSocModel* pSoC)
{
  m_pSoC = pSoC;

  //Enable events for memeory accesses
  EnableEvent(TRACE_SOC_MODULE, udb::MEMREAD_EVENT);
  EnableEvent(TRACE_SOC_MODULE, udb::MEMWRITE_EVENT);

  //Attach to the Hart
  m_pSoC->AttachHandler(this, TRACE_SOC_MODULE);
}

udb::MemoryTracer::~MemoryTracer()
{

}

int udb::MemoryTracer::OnNotification(uint8_t uiModuleId, uint64_t uiEvent, void* pData)
{
  if(uiModuleId != TRACE_SOC_MODULE)
    return 0;

  //Memory access trace
  switch(uiEvent)
  {
  case MEMREAD_EVENT:
    if(pData != nullptr)
    {
      MemAccessRange* pMemAccessRange =  (MemAccessRange*)pData;
      OnPhysicalMemoryRead(pMemAccessRange->GetAddress(), pMemAccessRange->GetSize());
    }
    break;
  case MEMWRITE_EVENT:
    if(pData != nullptr)
    {
      MemAccess* pMemAccess =  (MemAccess*)pData;
      OnPhysicalMemoryWrite(pMemAccess->GetAddress(), pMemAccess->GetSize(), pMemAccess->GetData());
    }
    break;
  default:
    break;
  }
  return 0;
}

void udb::MemoryTracer::OnPhysicalMemoryRead(uint64_t addr, unsigned len)
{
  fmt::print("MEM:RD {:x}\n", addr);
}

void udb::MemoryTracer::OnPhysicalMemoryWrite(uint64_t addr, unsigned len, uint64_t data)
{
  fmt::print("MEM:WR {:x} {} bytes\n", addr, len );
}

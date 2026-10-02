#pragma once
#include <cstdint>

#include "NotificationHandler.hpp"
#include "hart.hpp"
#include "iss_soc_model.hpp"

enum TRACER_NOTIFY_MODULES
{
  TRACE_HART_MODULE = 0,
  TRACE_SOC_MODULE,
  TRACE_MODULE_COUNT
};

namespace udb
{
  // base class for tracers
  class Tracer : public NotificationHandlerEx<TRACE_MODULE_COUNT>
  {
   public:
    Tracer() {}
    virtual ~Tracer() {}
  };

  class InstructionTracer : public Tracer
  {
  public:
    InstructionTracer(HartBase<IssSocModel>* pHart);
    ~InstructionTracer();

  protected:
    virtual int OnNotification(uint8_t uiModuleId, uint64_t uiEvent, void* pData) override;

    HartBase<IssSocModel>* m_pHart;
  };


  class MemoryTracer : public Tracer
  {
  public:
    MemoryTracer(IssSocModel* pSoC);
    ~MemoryTracer();

  protected:
    virtual int OnNotification(uint8_t uiModuleId, uint64_t uiEvent, void* pData) override;
    virtual void OnPhysicalMemoryRead(uint64_t addr, unsigned len);
    virtual void OnPhysicalMemoryWrite(uint64_t addr, unsigned len, uint64_t data);

    IssSocModel* m_pSoC;
  };
}

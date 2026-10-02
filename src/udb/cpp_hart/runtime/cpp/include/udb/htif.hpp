#pragma once
#include <cstdint>
#include <fmt/core.h>

#include "udb/iss_soc_model.hpp"


typedef struct _SYSCALLBLOCK
{
  uint64_t id;
  uint64_t a[7];
} SYSCALLBLOCK, *PSYSCALLBLOCK;

union HTIFCOMMAND
{
  struct
  {
    uint64_t payload:48;
    uint8_t command:8;
    uint8_t device:8;
  };
  uint64_t value;
};

//HTIF Device base class
class HTIFDevice
{
public:
  HTIFDevice(udb::IssSocModel* pSoC);
  ~HTIFDevice();

  virtual int HandleCommand(HTIFCOMMAND cmd) = 0;
protected:
  udb::IssSocModel* m_pSoC;
};

//SysCall Device
class SysCallDevice;
typedef int (SysCallDevice::*SYSCALLHANDLER)(uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3,
                                             uint64_t a4, uint64_t a5, uint64_t a6);


class SysCallDevice : public HTIFDevice
{
public:
  SysCallDevice(udb::IssSocModel* pSoC);
  ~SysCallDevice();

  class Pass : public udb::ExitEvent
  {
  public:
    Pass() : udb::ExitEvent(0) {}

    const char* what() const noexcept override { return "Pass"; }
  };

  class Fail : public udb::ExitEvent
  {
  public:
    Fail(uint64_t testnum) : udb::ExitEvent(-1), m_testnum(testnum) {}

    const char* what() const noexcept override
    {
      return strdup(fmt::format("Test #{} failed", m_testnum).c_str());
    }
  private:
    uint64_t m_testnum;
  };

  virtual int HandleCommand(HTIFCOMMAND cmd) override;

protected:
  int exit(uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3, uint64_t a4, uint64_t a5, uint64_t a6);

  std::vector<SYSCALLHANDLER> m_cmdHandlers;
};

class BCDDevice : public HTIFDevice
{
public:
  BCDDevice(udb::IssSocModel* pSoC);
  ~BCDDevice();

  enum BCDCMD
  {
    READ = 0,
    WRITE
  };

  virtual int HandleCommand(HTIFCOMMAND cmd) override;
};


class HostTargetInterface
{
public:
  HostTargetInterface(udb::IssSocModel* pSoC, uint64_t toHostAddress, uint64_t fromHostAddress, uint64_t sigAddress, uint64_t sigLength);
  ~HostTargetInterface();

private:
  static int NotificationCallback(void* pUserParam, uint64_t uiModuleId, uint64_t uiEvent, void* pData);
  int HandleCommand(HTIFCOMMAND cmd);

  udb::IssSocModel* m_pSoC;
  uint64_t m_toHost;
  uint64_t m_fromHost;
  uint64_t m_sigAddress;
  uint64_t m_sigLength;
  std::vector<HTIFDevice*> m_devices;
  size_t m_nDevices;
  SysCallDevice m_sysCall;
  BCDDevice m_bcd;
};

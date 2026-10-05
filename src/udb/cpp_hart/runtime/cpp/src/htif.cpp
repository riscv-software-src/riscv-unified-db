
#include "udb/htif.hpp"
#include "udb/iss_soc_model.hpp"

HostTargetInterface::HostTargetInterface(udb::IssSocModel* pSoC, uint64_t toHostAddress,
                                         uint64_t fromHostAddress, uint64_t sigAddress,
                                         uint64_t sigLength) : m_sysCall(pSoC), m_bcd(pSoC)
{
  m_toHost = toHostAddress;
  m_fromHost = fromHostAddress;
  m_sigAddress = sigAddress;
  m_sigLength = sigLength;

  m_pSoC = pSoC;

  //register notification callback
  m_pSoC->AttachHandler(NotificationCallback, 0, static_cast<void*>(this));

  //create devices if needed, count up and register
  //currently onuy syscall is implemented
  m_nDevices = 2;
  m_devices.resize(m_nDevices);
  m_devices[0] = &m_sysCall;
  m_devices[1] = &m_bcd;
}

HostTargetInterface::~HostTargetInterface()
{

}

int HostTargetInterface::NotificationCallback(void* pUserParam, uint64_t uiModuleId,
                                              uint64_t uiEvent, void* pData)
{
  int result = 0;
  HostTargetInterface* pThis = static_cast<HostTargetInterface*>(pUserParam);
  if(pThis != nullptr)
  {
    switch(uiEvent)
    {
    case udb::MEMWRITE_EVENT:
      if(pData != nullptr)
      {
        udb::MemAccess* pMemAccess =  (udb::MemAccess*)pData;
        if(pMemAccess->GetAddress() == pThis->m_toHost)
        {
          HTIFCOMMAND command;
          pThis->m_pSoC->memcpy_to_host((uint8_t*)&command, pThis->m_toHost, sizeof(command));
          if(command.value != 0)
          {
            result = pThis->HandleCommand(command);
          }
        }
      }
      break;
    case udb::MEMREAD_EVENT:
    default:
      break;
    }

  }
  return result;
}

int HostTargetInterface::HandleCommand(HTIFCOMMAND cmd)
{
  if(cmd.device < m_nDevices)
  {
    m_devices[cmd.device]->HandleCommand(cmd);
  }
  else
  {

  }
  return 0;
}

HTIFDevice::HTIFDevice(udb::IssSocModel* pSoC)
{
  m_pSoC = pSoC;
}

HTIFDevice::~HTIFDevice()
{

}

SysCallDevice::SysCallDevice(udb::IssSocModel* pSoC)
  : HTIFDevice(pSoC), m_cmdHandlers(94)
{
  m_cmdHandlers[93] = &SysCallDevice::exit;
}

SysCallDevice::~SysCallDevice()
{

}

int SysCallDevice::HandleCommand(HTIFCOMMAND cmd)
{
  int result = 0;
  if(cmd.payload & 1)
  {
    //Test pass/fail
    if(cmd.payload >> 1 == 0)
      throw Pass();
    else
      throw Fail(cmd.payload >> 1);
  }
  else
  {
    SYSCALLBLOCK sysCallBlock;

    //Read the syscall from target memory
    m_pSoC->memcpy_to_host(reinterpret_cast<uint8_t*>(&sysCallBlock), cmd.payload, sizeof(sysCallBlock));

    //dispatch to syscall handler
    if(sysCallBlock.id < m_cmdHandlers.size() && m_cmdHandlers[sysCallBlock.id] != nullptr)
    {
      result = (this->*m_cmdHandlers[sysCallBlock.id])(sysCallBlock.a[0],
        sysCallBlock.a[1],
        sysCallBlock.a[2],
        sysCallBlock.a[3],
        sysCallBlock.a[4],
        sysCallBlock.a[5],
        sysCallBlock.a[6]);
    }
  }
  return result;;
}

int SysCallDevice::exit(uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3,
                        uint64_t a4, uint64_t a5, uint64_t a6) {
  ::exit(a0);
  return a0;
}

BCDDevice::BCDDevice(udb::IssSocModel* pSoC)
  : HTIFDevice(pSoC)
{

}

BCDDevice::~BCDDevice()
{

}

int BCDDevice::HandleCommand(HTIFCOMMAND cmd)
{
  switch(cmd.command)
  {
  case READ:
    //TODO:
    break;
  case WRITE:
    //TODO: use deicated console, stdout for now
    std::putchar(static_cast<int>(cmd.payload));
    break;
  default:
    break;
  }
  return 0;
}


#include <fmt/core.h>

#include <CLI/CLI.hpp>
#include <string>
#include <list>
#include <fstream>
#include <nlohmann/json.hpp>
#include <sys/param.h>

#include "udb/defines.hpp"
#include "udb/elf_reader.hpp"
#include "udb/hart_factory.hxx"
#include "udb/inst.hpp"
#include "udb/csr.hpp"
#include "udb/iss_soc_model.hpp"
#include "udb/GDBServer.hpp"
#include "udb/NotificationHandler.hpp"
#include "udb/Tracer.hpp"
#include "udb/config_validator.hpp"
#include "udb/htif.hpp"


#define RISCV_REG_GPR_FIRST 0
#define RISCV_REG_GPR_LAST  0x1f
#define RISCV_REG_PC        0x20
#define RISCV_REG_FPR_FIRST 0x21
#define RISCV_REG_FPR_LAST  0x40
#define RISCV_REG_CSR_FIRST 0x41
#define RISCV_REG_CSR_LAST  0x1040

using json = nlohmann::json;


struct Options
{
  std::string configName;
  std::filesystem::path configPath;
  std::filesystem::path memoryMapPath;
  bool showConfigs;
  std::string elfFilePath;
  bool halt;
  bool gdbMode;
  uint16_t gdbPort;
  std::vector<std::string> trace;

  Options()
  {
    //Default values
    showConfigs = false;
    halt = false;
    gdbMode = false;
    gdbPort = GDB_PORT_DEFAULT;
  }
};

typedef struct _MEMORYMAP
{
  uint64_t base;
  uint64_t size;
} MEMORYMAP, *PMEMORYMAP;

enum ISS_NOTIFY_SOURCE
{
  ISS_HART_MODULE = 0,
  ISS_SOC_MODULE,
  ISS_MODULE_COUNT
};

class InstructionSetSimulator : public GDBServer, public NotificationHandlerEx<ISS_MODULE_COUNT>
{
public:
  InstructionSetSimulator();
  InstructionSetSimulator(Options& opts);
  ~InstructionSetSimulator();
  int Run();



private:
  int CreateMemoryMap(std::filesystem::path memMapPath,
                      std::filesystem::path elfPath = "");
  void SetInitState(Options& opts);
  udb::Tracer* CreateTracer(std::string& tracer);
  HostTargetInterface* CreateHostTargetInterface(udb::IssSocModel* pSoC, std::filesystem::path elfPath);
  int OnHartNotification(uint64_t uiEvent, void* pData);
  int OnSoCNotification(uint64_t uiEvent, void* pData);
  virtual int OnExternalHalt();
  virtual int OnReadGPR(REGISTERFILE& registerFile) override;
  virtual int OnWriteGPR(REGISTERFILE& registerFile) override;
  virtual int OnReadMemory(uint64_t uiAddress, uint64_t& uiLen, void* pBuffer) override;
  virtual int OnWriteMemory(uint64_t uiAddress, uint64_t& uiLen, void* pMemBuffer) override;
  virtual int OnReadSingleRegister(int reg, uint64_t& value) override;
  virtual int OnWriteSingleRegister(int reg, uint64_t& value) override;
  virtual int OnSingleStep(uint64_t uiRangeBegin, uint64_t uiRangeEnd) override;
  virtual int OnContinue(uint64_t uiAddress = -1) override;
  virtual int OnKill(uint64_t uiProcId = 0) override;
  virtual int OnClearBreakWatchPoint(unsigned char type, uint64_t uiAddress, uint64_t uiKind) override;
  virtual int OnSetBreakWatchPoint(unsigned char type, uint64_t uiAddress, uint64_t uiKind) override;
  virtual int OnNotification(uint8_t uiModuleId, uint64_t uiEvent, void* pData) override;

  enum ISS_STATE
  {
    STATE_HALT,
    STATE_SINGLE_STEP,
    STATE_RUN,
    STATE_RUN_N,
    STATE_EXIT
  };
  Options m_opts;
  MEMORYMAP m_memMap;
  udb::IssSocModel* m_pSoC;
  udb::HartBase<udb::IssSocModel>* m_pHart;
  HostTargetInterface* m_pHTIF;
  std::vector<udb::Tracer*> m_tracers;
  ISS_STATE m_state;
  std::list<uint64_t> m_breakpointList;
  std::list<udb::MemAccessRange> m_readWatchpointList;
  std::list<udb::MemAccessRange> m_writeWatchpointList;
};

int ParseCommandLine(int argc, char *argv[], Options &options)
{
  CLI::App app("UDB ISS");

  app.add_option("-m,--model", options.configName, "Hart model");
  app.add_option("-c,--cfg", options.configPath, "Hart configuration file");
  app.add_option("--mm, --memory-map", options.memoryMapPath, "Memory map file");
  app.add_option("-p, --gdbport", options.gdbPort, "GDB port");
  app.add_option<std::vector<std::string>>("-t, --trace", options.trace, "Tracers to enable");
  app.add_flag("-l,--list-configs", options.showConfigs,
               "List available configurations");
  app.add_flag("-g,--gdb", options.gdbMode, "GDB Debugger mode");
  app.add_flag("--halt", options.halt,
               "Halt before execution and wait for debugger to attach");
  app.add_option("elf_file", options.elfFilePath, "File to run");

  CLI11_PARSE(app, argc, argv);
  return 0;
}

int main(int argc, char *argv[])
{
  Options opts;
  int result;

  result = ParseCommandLine(argc, argv, opts);
  if(result >= 0)
  {
    if (opts.showConfigs)
    {
      for (auto &config : udb::HartFactory::configs())
        fmt::print("{}\n", config);
      return 0;
    }

    if (opts.configPath.empty())
    {
      fmt::print("No configuration file provided\n");
      return -1;
    }

    //Construct the ISS from the options passed and run it
    InstructionSetSimulator iss(opts);
    result = iss.Run();

  }
  return result;
}

InstructionSetSimulator::InstructionSetSimulator()
{

}

InstructionSetSimulator::InstructionSetSimulator(Options& opts) :
  GDBServer(GDB_SUPPORT_BASE, opts.gdbPort, opts.halt), m_opts(opts)
{
  //Load and validate the config
  auto yaml = YAML::LoadFile(m_opts.configPath.string());
  json config = udb::ConfigValidator::validate(yaml);

  CreateMemoryMap(opts.memoryMapPath, opts.elfFilePath);
  m_pSoC = new udb::IssSocModel(m_memMap.size, m_memMap.base);
  if(m_pSoC)
  {
    //Create Hart with reference to SoC model
    m_pHart = udb::HartFactory::create<udb::IssSocModel>(opts.configName,
      0,
      config,
      *m_pSoC);

    if(m_pHart)
    {

      m_pHTIF = CreateHostTargetInterface(m_pSoC, opts.elfFilePath);

      for(std::string t : opts.trace)
      {
        udb::Tracer* pTracer = CreateTracer(t);
        if(pTracer != nullptr)
          m_tracers.push_back(pTracer);
        else
          fmt::print("Unknown tracer: {}\n", t);
      }


      //Attach notification handler to hart
      m_pHart->AttachHandler(this, ISS_HART_MODULE);

    }
    //Attach notifier to SoC
    m_pSoC->AttachHandler(this, ISS_SOC_MODULE);
  }

  SetInitState(opts);
}

InstructionSetSimulator::~InstructionSetSimulator()
{
  for(udb::Tracer* pT : m_tracers)
    delete pT;

  delete m_pHTIF;
  delete m_pHart;
  delete m_pSoC;
}

void InstructionSetSimulator::SetInitState(Options& opts)
{
  if(opts.gdbMode)
  {
    if(opts.halt)
    {
      m_state = STATE_HALT;
    }
    else
    {
      m_state = STATE_RUN;
    }
  }
  else
  {
    m_state = STATE_RUN_N;
  }
}

int InstructionSetSimulator::CreateMemoryMap(std::filesystem::path memMapPath,
                                             std::filesystem::path elfPath)
{
  json regions;
  uint64_t uiMemSize;

  if(!memMapPath.empty())
  {
    std::ifstream f(memMapPath);
    json data = json::parse(f);
    regions = data["regions"];

    for(const auto& region : regions)
    {
      auto type = region["type"];
      if (type == "ram")
      {
        m_memMap.base = std::stoul(static_cast<std::string>(region["base"]["value"]), nullptr, 0);
        m_memMap.size = std::stoul(static_cast<std::string>(region["size"]["value"]), nullptr, 0);
        return 0;
      }
    }
  }

  if(!elfPath.empty())
  {
    udb::ElfReader elfReader(elfPath.c_str());
    auto range = elfReader.mem_range();
    m_memMap.base = range.first;
    m_memMap.size = range.second - range.first;
    //Round up to whole page
    m_memMap.size = ((range.second - range.first) + 0xffful) & ~0xffful;
    return 0;
  }

  return -1;
}

int InstructionSetSimulator::Run()
{
  int result = 0;

  udb::ElfReader elfReader(m_opts.elfFilePath.c_str());
  auto entryPC = elfReader.loadLoadableSegments(*m_pSoC);
  m_pHart->reset(entryPC);

  if(m_opts.gdbMode)
    result = ListenForConnection();

  if(m_opts.halt)
    fmt::print("port {} - Waiting for debugger to attach...\n", m_opts.gdbPort);

  while (true)
  {
    int stopReason;
    if(m_opts.gdbMode)
    {
       //Prevent the debugger commands from
      //generating notifications
      DisableNotifications();
      result = Poll();
      EnableNotifications();
      if(result < 0)
        break;
    }

    switch(m_state)
    {
    case STATE_SINGLE_STEP:
      stopReason = m_pHart->run_one();
      m_state = STATE_HALT;
      if(m_opts.gdbMode)
      {
        // Notify debugger that single-step completed and target is halted again.
        Halt(HALT_STEP, m_pHart->hartid().get(), m_pHart->pc());
      }
      break;
    case STATE_RUN:
      stopReason = m_pHart->run_one();
      break;
    case STATE_RUN_N:
      stopReason = m_pHart->run_n(100);
      break;
    case STATE_HALT:
    default:
        stopReason = StopReason::InstLimitReached;
      break;
    }

    if (stopReason != StopReason::InstLimitReached &&
        stopReason != StopReason::Exception) {
      if (stopReason == StopReason::ExitSuccess) {
        fmt::print("SUCCESS - {}\n", m_pHart->exit_reason());
        break;
      } else if (stopReason == StopReason::ExitFailure) {
        fmt::print(stderr, "FAIL - {}\n", m_pHart->exit_reason());
        break;
      } else {
        fmt::print("EXIT - {}\n", m_pHart->exit_reason());
        break;
      }
    }
  }

  if(result == 0)
  {
    result = m_pHart->exit_code();
  }

  return result;
}

int InstructionSetSimulator::OnReadGPR(REGISTERFILE& registerFile)
{
  registerFile.nXRegs = MIN(registerFile.nXRegs, 32);
  for(int i = 0 ; i < registerFile.nXRegs ; i++)
  {
    registerFile.xReg[i] = m_pHart->xreg(i);
  }
  return 0;
}

int InstructionSetSimulator::OnWriteGPR(REGISTERFILE& registerFile)
{
  registerFile.nXRegs = MIN(registerFile.nXRegs, 32);
  for(int i = 0 ; i < registerFile.nXRegs ; i++)
  {
    m_pHart->set_xreg(i, registerFile.xReg[i]);
  }
  return 0;
}

int InstructionSetSimulator::OnReadMemory(uint64_t uiAddress, uint64_t& uiLen, void* pBuffer)
{
  try
  {
    auto translationResult = m_pHart->translate_native(uiAddress, udb::MemoryOperation{udb::MemoryOperation::Read},
      m_pHart->_get_mode(), uiAddress);

    if(m_pSoC->memcpy_to_host((uint8_t*)pBuffer, translationResult.pAddr, uiLen) >= 0)
      return 0;
    else
      return -1;
  }
  catch(const udb::AbortInstruction& e)
  {
    //memory not mapped for reading
    return -1;
  }
}

int InstructionSetSimulator::OnWriteMemory(uint64_t uiAddress, uint64_t& uiLen, void* pMemBuffer)
{
  try
  {
    auto translationResult = m_pHart->translate_native(uiAddress, udb::MemoryOperation{udb::MemoryOperation::Write},
      m_pHart->_get_mode(), uiAddress);

    if(m_pSoC->memcpy_from_host(translationResult.pAddr, (const uint8_t*)pMemBuffer, uiLen) >= 0)
      return 0;
    else
      return -1;
  }
  catch(const udb::AbortInstruction& e)
  {
    //memory not mapped for writing
    return -1;
  }
}

int InstructionSetSimulator::OnReadSingleRegister(int reg, uint64_t& value)
{
  if(reg >= RISCV_REG_GPR_FIRST && reg <= RISCV_REG_GPR_LAST)
    value = m_pHart->xreg(reg);
  else if (reg == RISCV_REG_PC)
    value = m_pHart->pc();
  else if (reg >= RISCV_REG_FPR_FIRST && reg <= RISCV_REG_FPR_LAST)
  {
    try
    {
      value = m_pHart->freg(reg - RISCV_REG_FPR_FIRST);
    }
    catch(...)
    {
      return -1;
    }
  }
  else if (reg >= RISCV_REG_CSR_FIRST && reg <= RISCV_REG_CSR_LAST)
  {
    udb::CsrBase* pCSR = m_pHart->csr(reg - RISCV_REG_CSR_FIRST);
    if(pCSR != NULL)
    {
      try
      {
        value = pCSR->sw_read(udb::Bits<7>(64)).get();
      }
      catch(...)
      {
        //Unimplemented CRS's throw illegal instruction or
        //instruction abort exceptions
        return -1;
      }

    }
    else
      return -1;
  }
  else
    return -1;

  return 0;
}

int InstructionSetSimulator::OnWriteSingleRegister(int reg, uint64_t& value)
{
  if(reg >= RISCV_REG_GPR_FIRST && reg <= RISCV_REG_GPR_LAST)
    m_pHart->set_xreg(reg, value);
  else if (reg == RISCV_REG_PC)
    m_pHart->set_next_pc(value);
  else if (reg >= RISCV_REG_FPR_FIRST && reg <= RISCV_REG_FPR_LAST)
  {
    try
    {
      m_pHart->set_freg(reg - RISCV_REG_FPR_FIRST, value);
    }
    catch(...)
    {
      return -1;
    }
  }
  else if (reg >= RISCV_REG_CSR_FIRST && reg <= RISCV_REG_CSR_LAST)
  {
    udb::CsrBase* pCSR = m_pHart->csr(reg - RISCV_REG_CSR_FIRST);
    if(pCSR == NULL)
      return -1;
    try
    {
      if(!pCSR->sw_write(udb::Bits<64>(value), udb::Bits<7>(64)))
        return -1;
    }
    catch(...)
    {
      //Unimplemented CRS's throw illegal instruction or
      //instruction abort exceptions
      return -1;
    }

  }
  else
    return -1;

  return 0;
}

int InstructionSetSimulator::OnSingleStep(uint64_t uiRangeBegin, uint64_t uiRangeEnd)
{
  //TODO: store the range and keep stepping if within begin -> end

  m_state = STATE_SINGLE_STEP;
  return 0;
}

int InstructionSetSimulator::OnContinue(uint64_t uiAddress)
{
  if(uiAddress != (uint64_t)-1)
    m_pHart->set_next_pc(uiAddress);

  m_state = STATE_RUN;
  return 0;
}

int InstructionSetSimulator::OnClearBreakWatchPoint(unsigned char type, uint64_t uiAddress,
                                                    uint64_t uiKind)
{
  int result = 0;
  switch(type)
  {
  case 0:
  case 1:
    // All breakpoints are HW breakpoints
    m_breakpointList.remove(uiAddress);
    if(m_breakpointList.size() == 0)
        DisableEvent(ISS_HART_MODULE, udb::PREFETCH_EVENT);
    break;
  case 2:
    // read watch point
    m_readWatchpointList.remove(udb::MemAccessRange(uiAddress, (size_t)uiKind));
    if(m_readWatchpointList.size() == 0)
        DisableEvent(ISS_SOC_MODULE, udb::MEMREAD_EVENT);
    break;

  case 3:
    // write watch point
    m_writeWatchpointList.remove(udb::MemAccessRange(uiAddress, (size_t)uiKind));
    if(m_writeWatchpointList.size() == 0)
        DisableEvent(ISS_SOC_MODULE, udb::MEMWRITE_EVENT);
    break;
  default:
    result = -1;
    break;
  }
  return result;
}

int InstructionSetSimulator::OnSetBreakWatchPoint(unsigned char type, uint64_t uiAddress,
                                                  uint64_t uiKind)
{
  int result = 0;
  switch(type)
  {
  case 0:
  case 1:
    {
      if(m_breakpointList.size() == 0)
        EnableEvent(ISS_HART_MODULE, udb::PREFETCH_EVENT);

      // All breakpoints are HW breakpoints
      auto it = std::find(m_breakpointList.begin(), m_breakpointList.end(), uiAddress);
      if(it == m_breakpointList.end())
      {
        m_breakpointList.push_back(uiAddress);
      }
    }
    break;
  case 2:
    // set read watch point
    if(m_readWatchpointList.size() == 0)
      EnableEvent(ISS_SOC_MODULE, udb::MEMREAD_EVENT);

    m_readWatchpointList.push_back(udb::MemAccessRange(uiAddress, (size_t)uiKind));
    break;
  case 3:
    // set write watch point
    if(m_readWatchpointList.size() == 0)
      EnableEvent(ISS_SOC_MODULE, udb::MEMREAD_EVENT);

    m_writeWatchpointList.push_back(udb::MemAccessRange(uiAddress, (size_t)uiKind));
  default:
    result = -1;
    break;
  }
  return result;
}

int InstructionSetSimulator::OnNotification(uint8_t uiModuleId, uint64_t uiEvent, void* pData)
{
  int result;
  switch(uiModuleId)
  {
  case ISS_HART_MODULE:
    result = OnHartNotification(uiEvent, pData);
    break;
  case ISS_SOC_MODULE:
    result = OnSoCNotification(uiEvent, pData);
    break;
  default:
    result = 0;
    break;
  }
  return result;
}

int InstructionSetSimulator::OnHartNotification(uint64_t uiEvent, void* pData)
{
  int result = 0;
  switch(uiEvent)
  {
  case udb::PREFETCH_EVENT:
    {
      //look for breakpoint hit
      auto it = std::find(m_breakpointList.begin(), m_breakpointList.end(), m_pHart->pc());
      if(it != m_breakpointList.end())
      {
        m_state = STATE_HALT;
        //Send break state to debug host
        result = Halt(HALT_BREAKPOINT, m_pHart->hartid().get(), m_pHart->pc());
        throw udb::AbortPreExecute();
      }
    }
    break;
  case udb::EBREAK_EVENT:
    if(m_opts.gdbMode)
    {
      m_state = STATE_HALT;
      //Send break state to debug host
      result = Halt(HALT_BREAKPOINT, m_pHart->hartid().get(), m_pHart->pc());
    }
    else
    {
      result = 0;
    }
    break;
  //events not handled, should not be enabled
  case udb::FETCH_EVENT:
  case udb::DECODE_EVENT:
  case udb::PREEXECUTE_EVENT:
  case udb::EXECUTE_EVENT:
  default:
    break;
  }

  return result;
}

int InstructionSetSimulator::OnSoCNotification(uint64_t uiEvent, void* pData)
{
  int result;
  switch(uiEvent)
  {
  case udb::MEMREAD_EVENT:
    {

      udb::MemAccessRange* pMemRange = (udb::MemAccessRange*)pData;

      //Watch points
      for(udb::MemAccessRange m : m_readWatchpointList)
      {
        if((pMemRange->GetAddress() >= m.GetAddress() && (pMemRange->GetAddress() < (m.GetAddress() + m.GetSize()))) ||
          ((pMemRange->GetAddress() + pMemRange->GetSize()) > m.GetAddress()))
        {
          m_state = STATE_HALT;
          //Send break state to debug host
          result = Halt(HALT_WATCHPOINT, m_pHart->hartid().get(), m.GetAddress());
          throw udb::AbortPreExecute();
        }
      }

      //Tracer

    }
    break;
  case udb::MEMWRITE_EVENT:
    {
      udb::MemAccess* pMemAccess =  (udb::MemAccess*)pData;

      //Watch points
      for(udb::MemAccessRange m : m_writeWatchpointList)
      {
        if((pMemAccess->GetAddress() >= m.GetAddress() && (pMemAccess->GetAddress() < (m.GetAddress() + m.GetSize()))) ||
          ((pMemAccess->GetAddress() + pMemAccess->GetSize()) > m.GetAddress()))
        {
          m_state = STATE_HALT;
          //Send break state to debug host
          result = Halt(HALT_WATCHPOINT, m_pHart->hartid().get(), m.GetAddress());
          throw udb::AbortPreExecute();
        }
      }
    }
    break;
  default:
    result = 0;
    break;
  }
  return result;
}

int InstructionSetSimulator::OnExternalHalt()
{
  m_state = STATE_HALT;
  return Halt(HALT_EXTERNAL, m_pHart->hartid().get(), m_pHart->pc());
}

int InstructionSetSimulator::OnKill(uint64_t uiProcId)
{
  // reload the elf
  udb::ElfReader elfReader(m_opts.elfFilePath.c_str());
  auto entryPC = elfReader.loadLoadableSegments(*m_pSoC);
  // reset the hart
  m_pHart->reset(entryPC);
  // set the ISS state
  SetInitState(m_opts);
  return 0;
}

udb::Tracer* InstructionSetSimulator::CreateTracer(std::string& tracer)
{
  if(tracer == "inst")
    return new udb::InstructionTracer(m_pHart);
  else if(tracer == "mem")
    return new udb::MemoryTracer(m_pSoC);

  return nullptr;
}


HostTargetInterface* InstructionSetSimulator::CreateHostTargetInterface(
    udb::IssSocModel* pSoC, std::filesystem::path elfPath)
{
  HostTargetInterface* pHTIF = nullptr;
  uint64_t toHostAddress = 0;

  udb::ElfReader elfReader(elfPath.c_str());
  if(elfReader.getSym("tohost", &toHostAddress))
  {
    uint64_t fromHostAddress = 0;
    uint64_t sigBeginAddress = 0;
    uint64_t sigEndAddress = 0;

    elfReader.getSym("fromhost", &fromHostAddress);
    elfReader.getSym("signature_begin", &sigBeginAddress);
    elfReader.getSym("signature_end", &sigEndAddress);

    pHTIF = new HostTargetInterface(pSoC, toHostAddress, fromHostAddress,
        sigBeginAddress, sigEndAddress - sigBeginAddress);
    if(pHTIF == nullptr)
      fmt::print("Error: cannot create host-target interface");
  }
  else
  {
    fmt::print("Note: elf application does not support host-target interface");
  }

  return pHTIF;
}

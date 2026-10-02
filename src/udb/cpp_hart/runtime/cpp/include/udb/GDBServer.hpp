#pragma once
#include <poll.h>
#include <cstddef>
#include <string>
#include <stdint.h>

#define GDB_PORT_DEFAULT 2159
#define MAX_CLIENTS 1
#define DBG_MAX_PKT_SIZE 768
#define NUM_XREGS 32

//ID's of supported features
#define GDB_SUPPORT_HWBREAK         (1 << 0)
#define GDB_SUPPORT_SWBREAK         (1 << 1)
#define GDB_SUPPORT_BREAKPOINTCMDS  (1 << 2)
#define GDB_SUPPORT_RCMD            (1 << 3)
#define GDB_SUPPORT_VCONT           (1 << 4)
#define GDB_SUPPORT_NOACK           (1 << 5)

#define GDB_SUPPORT_BASE (GDB_SUPPORT_HWBREAK | GDB_SUPPORT_SWBREAK | \
                          GDB_SUPPORT_BREAKPOINTCMDS | GDB_SUPPORT_RCMD |\
                          GDB_SUPPORT_VCONT | GDB_SUPPORT_NOACK)



typedef struct _REGISTERFILE
{
  int nXRegs;
  uint64_t xReg[NUM_XREGS];
} REGISTERFILE, *PREGISTERFILE;

class GDBPacket
{
public:
  GDBPacket();
  GDBPacket(unsigned char* pPacket, int len, int size = 0);
  ~GDBPacket();

  bool Validate();
  bool EndOfPacket();
  void SetBufferSize(size_t size);
  bool Seek(char c);
  bool Seek(int relPos);
  template <typename T> T Read();
  int ReadByte(unsigned char* pValue, unsigned char* pBuffer = NULL);
  char ReadChar();
  int ReadData(unsigned char* pData, int len, unsigned char* pBuffer = NULL);
  std::string ReadString();
  size_t Length();
  int Write(const std::string& str);
  int Write(const unsigned char* pData , size_t len);
  int Terminate();

  operator unsigned char *();
  unsigned char operator[](unsigned int i);

private:
  char HexCharToValue(unsigned char hexChar);

  unsigned char* m_pPacket;
  unsigned long m_len;
  size_t m_size;
  unsigned char* m_pNextPos;
  int m_checksum;
};


class GDBServer
{
public:
  enum HALTREASON
  {
    HALT_BREAKPOINT,
    HALT_WATCHPOINT,
    HALT_EXTERNAL,
    HALT_STEP
  };

  GDBServer(uint64_t uiSupport = GDB_SUPPORT_BASE, int port = GDB_PORT_DEFAULT, bool bWait = false);
  ~GDBServer();

  int ListenForConnection(void);
  int Poll(void);
  int Halt(GDBServer::HALTREASON reason, uint uiCore, uint64_t uiAddress);

protected:
  int OnReceive(int socket);
  virtual int OnExternalHalt();
  virtual int OnContinue(uint64_t uiAddress = -1);
  virtual int OnKill(uint64_t uiProcId = 0);
  virtual int OnReadGPR(REGISTERFILE& registerFile);
  virtual int OnWriteGPR(REGISTERFILE& registerFile);
  virtual int OnReadMemory(uint64_t uiAddress, uint64_t& uiLen, void* pBuffer);
  virtual int OnWriteMemory(uint64_t uiAddress, uint64_t& uiLen, void* pMemBuffer);
  virtual int OnReadSingleRegister(int reg, uint64_t& value);
  virtual int OnWriteSingleRegister(int reg, uint64_t& value);
  virtual int OnSingleStep(uint64_t uiRangeBegin = 0, uint64_t uiRangeEnd = 0);
  virtual int OnClearBreakWatchPoint(unsigned char type, uint64_t uiAddress, uint64_t uiKind);
  virtual int OnSetBreakWatchPoint(unsigned char type, uint64_t uiAddress, uint64_t uiKind);

private:
  uint64_t m_uiSupport;
  int m_serverSocket;
  int m_clientSocket;
  int m_port;
  bool m_bWait;
  bool m_ackMode;
  struct pollfd m_pollFds[MAX_CLIENTS + 1];
  int m_nPollFds;
  unsigned char m_recvBuffer[DBG_MAX_PKT_SIZE];
  unsigned char m_respBuffer[DBG_MAX_PKT_SIZE];

  int HandleSocketEvents(int socket, short events);
  int HandlePacket(GDBPacket& packet);
  int SendAck(void);
  int SendNak(void);
  int SendResponse(void* pBuffer, unsigned int len);
  int SendResponse(GDBPacket& packet);
  int SendResponse(const std::string& str);
  int SendError(int error);
  std::string GetSupportedString();
};

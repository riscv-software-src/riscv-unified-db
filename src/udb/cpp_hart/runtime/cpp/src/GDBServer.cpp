#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <errno.h>
#include <string>
#include <format>
#include <sys/param.h>

#include "udb/GDBServer.hpp"

#define GDB_CMD_PACKET_START '$'
#define GDB_CMD_PACKET_END '#'
#define GDB_CMD_BREAK '\3'
#define GDB_RSP_ACK '+'
#define GDB_RSP_NACK '-'

typedef struct _GDBFEATURE
{
  uint64_t uiId;
  std::string feature;
} GDBFEATURE, *PGDBFEATURE;


char gHexDigitTable[] = {'0', '1', '2', '3', '4', '5', '6', '7' , '8', '9',
                         'a', 'b', 'c', 'd', 'e', 'f'};

//TODO: complete table for all q/Q Features
static const GDBFEATURE gFeatureTable[] = {{GDB_SUPPORT_HWBREAK, "hwbreak"},
                                           {GDB_SUPPORT_SWBREAK, "swbreak"},
                                           {GDB_SUPPORT_BREAKPOINTCMDS, "BreakpointCommands"},
                                           {GDB_SUPPORT_VCONT, "vContSupported"},
                                           {GDB_SUPPORT_NOACK, "QStartNoAckMode"},
                                           {GDB_SUPPORT_RCMD, "Rcmd"}};

GDBServer::GDBServer(uint64_t uiSupport, int port, bool bWait)
{
  m_uiSupport = uiSupport;
  m_port = port;
  m_bWait = bWait;
  m_ackMode = true;
  m_serverSocket = -1;
  m_clientSocket = -1;
  m_nPollFds = 0;
}

GDBServer::~GDBServer()
{
  if(m_clientSocket != -1)
    close(m_clientSocket);

  if(m_serverSocket != -1)
    close(m_serverSocket);
}

int GDBServer::ListenForConnection(void)
{
  int result = 0;

  m_serverSocket =  socket(AF_INET, SOCK_STREAM, 0);
  if(m_serverSocket != -1)
  {
    sockaddr_in serverAddress;
    serverAddress.sin_family = AF_INET;
    serverAddress.sin_port = htons(m_port);
    serverAddress.sin_addr.s_addr = INADDR_ANY;

    if(bind(m_serverSocket, (struct sockaddr*)&serverAddress, sizeof(serverAddress)) != -1)
    {
      if(listen(m_serverSocket, 0) != -1)
      {
        m_pollFds[0].fd = m_serverSocket;
        m_pollFds[0].events = POLLIN;
        m_nPollFds = 1;
      }
      else
      {
        close(m_serverSocket);
        result = m_serverSocket = -1;
      }
    }
    else
    {
      close(m_serverSocket);
      result = m_serverSocket = -1;
    }
  }
  else
  {
    result = -1;
  }
  return result;
}

int GDBServer::Poll(void)
{
  int result = poll(m_pollFds, m_nPollFds, 0);
  if(result > 0)
  {
    for(int i = 0 ; i < m_nPollFds ; i++)
    {
      if(m_pollFds[i].revents != 0)
      {
        result = HandleSocketEvents(m_pollFds[i].fd, m_pollFds[i].revents);
      }
    }
  }
  else if( result == -1)
  {
    //Error
  }
  return result;
}

int GDBServer::Halt(GDBServer::HALTREASON reason, uint uiCore, uint64_t uiAddress)
{
  int result = 0;
  switch(reason)
  {
  case HALT_BREAKPOINT:
    result = SendResponse(std::format("T05hwbreak:;core:{:02x};", (uint8_t)uiCore));
    break;
  case HALT_WATCHPOINT:
    result = SendResponse(std::format("T05watch:{:x};core:{:02x};", uiAddress, (uint8_t)uiCore));
    break;
  case HALT_EXTERNAL:
  default:
    result = SendResponse("S05");
  }
  return result;
}

int GDBServer::HandleSocketEvents(int socket, short events)
{
  if(socket == m_serverSocket)
  {
    //server socket
    if(events & POLLIN)
    {
      if(m_clientSocket < 0)
      {
        //accept a new client socket
        int clientSocket;
        sockaddr_in clientAddress;
        socklen_t addressLen = sizeof(clientAddress);

        clientSocket= accept(m_serverSocket, (struct sockaddr*)&clientAddress, &addressLen);
        if(clientSocket >= 0)
        {
          m_pollFds[1].fd = clientSocket;
          m_pollFds[1].events = POLLIN;
          m_pollFds[1].revents = 0;
          m_nPollFds = 2;
          m_clientSocket = clientSocket;
          m_ackMode = true;
        }
      }
    }
  }

  if(socket == m_clientSocket)
  {
    if(events & POLLIN)
    {
      //data available to read
      if(OnReceive(socket) == 0)
      {
        //0 bytes returned when remote side terminated connection
        events |= POLLHUP;
      }
    }
    if(events & (POLLHUP | POLLERR))
    {
      //connection closed by remote or error
      close(m_clientSocket);
      m_pollFds[1].fd = -1;
      m_nPollFds = 1;
      m_clientSocket = -1;
    }
  }
  return 0;
}

int GDBServer::OnReceive(int socket)
{
  if(socket != m_clientSocket || socket == -1)
    return -1;

  int nBytesReceived = recv(socket, &m_recvBuffer[0], sizeof(m_recvBuffer), MSG_DONTWAIT);
  if(nBytesReceived > 0)
  {
    unsigned char* pRcvd = m_recvBuffer;

    while(pRcvd < &m_recvBuffer[nBytesReceived])
    {
      switch(*pRcvd)
      {
      case GDB_CMD_PACKET_START:
        {
          GDBPacket packet((unsigned char*)pRcvd, nBytesReceived - (pRcvd - &m_recvBuffer[0]));
          if(packet.Validate())
          {
            SendAck();
            HandlePacket(packet);
          }
          else
          {
            SendNak();
          }
          pRcvd += packet.Length();
        }
        break;
      case GDB_RSP_NACK:

        //...what did we send?
        pRcvd++;
        break;
      case GDB_CMD_BREAK:
        OnExternalHalt();
        pRcvd++;
        break;
      case GDB_RSP_ACK:
      default:
        pRcvd++;
        break;
      }
    }
  }
  else if(nBytesReceived < 0)
  {
    //Error or no data available
    if(errno == EWOULDBLOCK || errno == EAGAIN)
      nBytesReceived = 0;
  }
  return nBytesReceived;
}

int GDBServer::HandlePacket(GDBPacket& packet)
{
  int result;
  const unsigned char cmd = packet[1];

  switch(cmd)
  {
  case '?':
    result = SendResponse("S05");
    if(result < 0)
    {
      //error response
      result = SendError(result);
    }
    break;
  // case 'c':
  //   {
  //     //continue with optional address
  //     uint64_t uiAddress = (uint64_t)-1;
  //     if(!packet.EndOfPacket())
  //       uiAddress = packet.Read<uint64_t>();

  //     result = OnContinue(uiAddress);
  //   }
  //   break;
  case 'g':
    {
      //Read general purpose register
      REGISTERFILE regFile;
      regFile.nXRegs = 32;
      result = OnReadGPR(regFile);
      if(result >= 0)
      {
        GDBPacket responsePacket(m_respBuffer, 0, sizeof(m_respBuffer));
        result = responsePacket.Write((const unsigned char*)&regFile.xReg[0],regFile.nXRegs * sizeof(regFile.xReg[0]));
        if(result >= 0)
        {
         result = SendResponse(responsePacket);
        }
      }

      if(result < 0)
      {
        result = SendError(result);
      }
    }
    break;
  case 'G':
    {
      //Write General purpose registers
      REGISTERFILE regFile;
      regFile.nXRegs = 0;
      for(int i = 0 ; i < NUM_XREGS ; i++)
      {
        if(packet.ReadData((unsigned char*)&regFile.xReg[i], sizeof(regFile.xReg[i])) < -1)
          regFile.nXRegs++;
        else
          break;
      }
      if(regFile.nXRegs > 0)
      {
        result = OnWriteGPR(regFile);
        if(result >= 0)
        {
          SendResponse("OK");
        }
      }
      else
      {
        result = -1;
      }

      if(result < 0)
      {
        result = SendError(result);
      }
    }
    break;
  case 'k':
    result = OnKill();
    // No response here,
    break;
  case 'm':
  case 'M':
    {
      uint64_t uiAddress = packet.Read<uint64_t>();
      if(packet.Seek(','))
      {
        uint64_t uiLen = packet.Read<uint64_t>();
        if(uiLen > 0)
        {
          uint8_t* pMemBuffer = new uint8_t[uiLen];
          if(pMemBuffer != nullptr)
          {
            if(cmd == 'm') //Read memory
            {
              //Get requested range of data from SoC
              result = OnReadMemory(uiAddress, uiLen, pMemBuffer);
              if(result >= 0)
              {
                //Create the response packet;
                GDBPacket responsePacket(m_respBuffer, 0, sizeof(m_respBuffer));
                result = responsePacket.Write(pMemBuffer, uiLen);
                if(result >= 0)
                {
                  //Send the response
                  result = SendResponse(responsePacket);
                }
              }
            }
            else //Write memory
            {
              if(packet.Seek(':'))
              {
                //Provide the data to the SoC
                result = packet.ReadData(pMemBuffer, uiLen);
                if(result >= 0)
                {
                  result = OnWriteMemory(uiAddress, uiLen, pMemBuffer);
                  if(result >= 0)
                  {
                    SendResponse("OK");
                  }
                }
              }
              else
              {
                result = -1;
              }
            }
            delete pMemBuffer;
          }
          else
          {
            //Out of memory
            result = -1;
          }
        }
        else
        {
          result = -1;
        }

        if(result < 0)
        {
          result = SendError(result);
        }
      }
    }
    break;
  case 'p':
    {
      int iReg = packet.Read<int>();
      uint64_t regValue = 0;
      result = OnReadSingleRegister(iReg, regValue);
      if(result >= 0)
      {
        GDBPacket responsePacket(m_respBuffer, 0, sizeof(m_respBuffer));
        result = responsePacket.Write((unsigned char*) &regValue, sizeof(regValue));
        if(result >= 0)
        {
          //Send the response
          result = SendResponse(responsePacket);
        }
      }

      if(result < 0)
      {
        result = SendResponse("xxxxxxxxxxxxxxxx");
      }
    }
    break;
  case 'P':
    {
      int iReg = packet.Read<int>();
      if(packet.Seek('='))
      {
        uint64_t regValue;
        result = packet.ReadData((unsigned char*)&regValue, sizeof(regValue));
        if(result >= 0)
        {
          result = OnWriteSingleRegister(iReg, regValue);
          if(result >= 0)
            result = SendResponse("OK");
        }
      }
      else
      {
        result = -1;
      }

      if(result < 0)
      {
        result = SendError(result);
      }
    }
    break;
  case 'q':
    {
      std::string strCmd = packet.ReadString();
      if(strCmd == "Supported")
      {
        result = SendResponse(std::format("{:s};PacketSize={:02x}", GetSupportedString(), sizeof(m_recvBuffer)));
      }
      else if(strCmd == "Rcmd")
      {
        //TODO: Implement
      }
      else
      {
        result = SendResponse("");
      }
    }
    break;
  case 'Q':
    {
      std::string strCmd = packet.ReadString();
      if(strCmd == "StartNoAckMode")
      {
        m_ackMode = false;
        result = SendResponse("OK");
      }
      else
      {
        result = SendResponse("");
      }
    }
    break;
  // case 's':
  //   {
  //     //Deprecated for vCont
  //     uint64_t uiAddress = -1;
  //     if(!packet.EndOfPacket())
  //       uiAddress = packet.Read<uint64_t>();

  //     result = OnSingleStep(uiAddress);
  //     if(result < 0)
  //     {
  //       result = SendError(result);
  //     }
  //   }
  //   break;
  case 'v':
    {
      std::string strCmd = packet.ReadString();
      if(strCmd == "Cont")
      {
        switch(packet.ReadChar())
        {
        case '?':
          result = SendResponse("c;s;t;r");
          break;
        case ';':
          switch(packet.ReadChar())
          {
          case 'c':
            result = OnContinue();
            break;
          case 's':
            result = OnSingleStep();
            break;
          case 'r':
            result = OnSingleStep();
            break;
          default:
            result = -1;
            break;
          }
          break;
        default:
          result = -1;
          break;
        }
      }
      else if(strCmd == "Kill")
      {
        if(packet.Seek(';'))
        {
          uint64_t uiProcId = packet.Read<uint64_t>();
          result = OnKill(uiProcId);
          if(result >= 0)
          {
            result = SendResponse("OK");
          }
          else
          {
            result = SendError(result);
          }

        }
        else
        {
          result = SendResponse("");
        }
      }
      else
      {
        //No other 'v' packets are supported
        result = SendResponse("");
      }
    }
    break;
  case 'z':
  case 'Z':
    {
      unsigned char type;

      result = -1;
      type = packet.Read<unsigned char>();
      if(packet.Seek(','))
      {
        uint64_t uiAddress = packet.Read<uint64_t>();
        if(packet.Seek(','))
        {
          uint64_t uiKind = packet.Read<uint64_t>();
          if(cmd == 'z')
            result = OnClearBreakWatchPoint(type, uiAddress, uiKind);
          else
            result = OnSetBreakWatchPoint(type, uiAddress, uiKind);

          if(result >= 0)
            result = SendResponse("OK");
        }
        else
        {
          result = -1;
        }

        if(result < 0)
        {
          result = SendError(result);
        }
      }
    }
    break;
  default:
    //unknown command
    result = SendResponse("");
    break;
  }

  return result;
}


int GDBServer::SendAck(void)
{
  if(m_ackMode)
    return send(m_clientSocket, "+", 1, 0);
  else
    return 0;
}

int GDBServer::SendNak(void)
{
  if(m_ackMode)
    return send(m_clientSocket, "-", 1, 0);
  else
    return 0;
}

int GDBServer::SendResponse(void* pBuffer, unsigned int len)
{
  return send(m_clientSocket, pBuffer, len, 0);
}

int GDBServer::SendResponse(GDBPacket& packet)
{
  int result;
  result = packet.Terminate();
  if(result >= 0)
  {
    result = SendResponse((unsigned char*)packet, packet.Length());
  }
  return result;
}

int GDBServer::SendResponse(const std::string& str)
{
  GDBPacket response((unsigned char*)m_respBuffer, 0, sizeof(m_respBuffer));
  int result = response.Write(str);
  if(result > -1 )
  {
    result = SendResponse(response);
  }
  return result;
}

int GDBServer::SendError(int error)
{
  GDBPacket response((unsigned char*)m_respBuffer, 0, sizeof(m_respBuffer));
  int result = response.Write("E");
  if(result >= 0)
  {
    if(error < 0)
      error = -error;
    result = response.Write((unsigned char*)&error, sizeof(unsigned char));
    if(result >= 0)
    {
      result = SendResponse(response);
    }
  }
  return result;
}

std::string GDBServer::GetSupportedString()
{
  std::string supported;
  PGDBFEATURE pGdbFeature;
  const size_t featureCount = sizeof(gFeatureTable) / sizeof(gFeatureTable[0]);

  for(uint64_t id = 1; id != 0 && id <= m_uiSupport; id <<= 1)
  {
    for(pGdbFeature = (PGDBFEATURE)&gFeatureTable[0];
      pGdbFeature < gFeatureTable + featureCount;
      pGdbFeature++)
    {
      if(pGdbFeature->uiId == id)
      {
        if(!supported.empty())
          supported += ';';
        supported += pGdbFeature->feature;
        supported += '+';
        break;
      }
    }
  }
  return supported;
}

GDBPacket::GDBPacket()
{
  m_pPacket = NULL;
  m_len = 0;
}

GDBPacket::GDBPacket(unsigned char* pPacket, int len, int size)
{
  m_pPacket = m_pNextPos = pPacket;
  if(size > 0)
  {
    m_size = size;
    if(len == 0)
    {
      //Initialize the packet
      *m_pNextPos++ = GDB_CMD_PACKET_START;
      m_len = 1;
    }
    else
    {
      //Partial packet passed
      m_len = len;
      m_pNextPos == pPacket + m_len;
    }
  }
  else if(len > 0)
  {
    //Find terminator within the length passed
    unsigned char* pTerminator = pPacket;
    while(pTerminator <  pPacket + len)
    {
      if(*pTerminator == GDB_CMD_PACKET_END)
        break;
      pTerminator++;
    }
    if(pTerminator <  pPacket + len)
    {
      //Packet ends with '#' and 2 hex digits
      m_size = m_len = MIN((pTerminator - pPacket + 3), len);
    }
    else
    {
      //Treat the whole buffer passed as a packet.
      m_size = m_len = len;
    }
  }
  else
  {
    //Dead packet
    m_size = m_len = 0;
  }
}


GDBPacket::~GDBPacket()
{

}

bool GDBPacket::Validate()
{
  if(m_pPacket != NULL && m_len > 0 && m_pPacket[0] == GDB_CMD_PACKET_START)
  {
    unsigned char checksum;
    int i;

    for(i = 1, checksum = 0 ; i < m_len && m_pPacket[i] != GDB_CMD_PACKET_END ; i++)
      checksum += m_pPacket[i];

    if(m_pPacket[i] == GDB_CMD_PACKET_END)
    {
      if(i <= (m_len - 2))
      {
        unsigned char packetChecksum;
        //Skip over the terminator;
        i++;
        if(ReadByte(&packetChecksum, &m_pPacket[i]) != -1 &&
          packetChecksum == checksum)
        {
          return true;
        }
      }
      else
      {
        //No checksum provided
        //check packet mode flags
      }
    }
  }
  return false;
}

void GDBPacket::SetBufferSize(size_t size)
{
  m_size = size;
}

int GDBPacket::ReadByte(unsigned char* pValue, unsigned char* pBuffer)
{
  int result = -1;

  if(pBuffer != NULL)
    m_pNextPos = pBuffer;

  if(m_pNextPos >= m_pPacket && m_pNextPos < (m_pPacket + m_len))
  {
    result = HexCharToValue(m_pNextPos[0]) << 4;
    result |= HexCharToValue(m_pNextPos[1]);

    if(result >= 0)
    {
      *pValue = (unsigned char)(result & 0xff);
      m_pNextPos += 2;
    }
    else
    {
      result = -1;
    }
  }
  return result;
}

char GDBPacket::ReadChar()
{
  char c = 0;

  if(m_pNextPos >= m_pPacket && m_pNextPos < (m_pPacket + m_len))
    c = *m_pNextPos++;

  return c;
}

int GDBPacket::ReadData(unsigned char* pData, int len, unsigned char* pBuffer)
{
  int result = 0;

  if(pBuffer != NULL)
    m_pNextPos = pBuffer;

  if(m_pNextPos >= m_pPacket && m_pNextPos < (m_pPacket + m_len - 2 * len))
  {
    while(result < len && ReadByte(pData++) != -1)
      result++;

    if(result == 0) //No bytes read
      result = -1;
  }
  else
  {
    result = -1;
  }
  return result;
}

std::string GDBPacket::ReadString()
{
  std::string s;
  while(isalpha(*m_pNextPos))
    s += *m_pNextPos++;

  return s;
}

template <typename T>
inline T GDBPacket::Read()
{
  T value = 0;
  int maxLen = sizeof(value) * 2;

  while(maxLen-- && isxdigit(*m_pNextPos))
  {
    value <<= 4;
    value |= HexCharToValue(*m_pNextPos++);
  }

  // for(int iShift = 0 ; iShift < sizeof(value); iShift++)
  // {
  //   uint8_t byteValue = 0;
  //   if(isxdigit(*m_pNextPos) && m_pNextPos < &m_pPacket[m_len])
  //     byteValue = HexCharToValue(*m_pNextPos++);
  //   if(isxdigit(*m_pNextPos) && m_pNextPos < &m_pPacket[m_len])
  //   {
  //     byteValue <<= 4;
  //     byteValue |= HexCharToValue(*m_pNextPos++);
  //   }
  //   value |= (byteValue << (iShift * 8));
  // }

  return value;
}

size_t GDBPacket::Length()
{
  return m_len;
}

GDBPacket::operator unsigned char*()
{
  return m_pPacket;
}

char GDBPacket::HexCharToValue(unsigned char hexChar)
{
  char result = 0;
  if(hexChar >= '0' && hexChar <= '9')
    result = hexChar - '0';
  else if (hexChar >= 'a' && hexChar <= 'f')
    result = hexChar - 'a' + 10;
  else if (hexChar >= 'A' && hexChar <= 'F')
    result = hexChar - 'A' + 10;
  else
    result = -1;

  return result;
}

int GDBPacket::Write(const std::string& str)
{
  int len = str.length();
  if((size_t)(m_pNextPos - m_pPacket + len) > m_size)
    return -1;

  for(int i = 0 ; i < len ; i++)
  {
    *m_pNextPos++ = str[i];
  }
  m_len += len;

  return len;
}

int GDBPacket::Write(const unsigned char* pData, size_t len)
{
  if((len * 2) > (m_pNextPos - m_pPacket + m_size))
    return -1;

  //Encode binary into hex characters
  for(int i = 0 ; i < len ; i++)
  {
    *m_pNextPos++ = gHexDigitTable[pData[i] >> 4];
    *m_pNextPos++ = gHexDigitTable[pData[i] & 0xf];
  }
  m_len += len * 2;
  return len * 2;
}

int GDBPacket::Terminate()
{
  unsigned char* pData;
  unsigned char checksum;
  int result;

  if(m_len + 3 > m_size)
    return -1;

  pData = &m_pPacket[1];
  checksum = 0;

  while(pData < m_pNextPos)
  {
    checksum += *pData++;
  }
  //Write terminator and checksum
  *m_pNextPos++ = '#';
  m_len++;

  result = Write(&checksum, sizeof(checksum));
  if(result < 0)
  {
    result = 1;
  }
  else
  {
    result++;
  }

  return result;
}

unsigned char GDBPacket::operator[](unsigned int i)
{
  if(i < m_size)
  {
    if(m_len < i)
      m_len = i;

    m_pNextPos = (m_pPacket + i + 1);
    return m_pPacket[i];
  }
  return 0;
}

bool GDBPacket::Seek(char c)
{
  unsigned char* p = m_pNextPos;
  while(p < (m_pPacket + m_len))
  {
    if(*p == (unsigned char)c)
    {
      m_pNextPos = p;
      m_pNextPos++;
      return true;
    }
    p++;
  }
  return false;
}

bool GDBPacket::Seek(int relPos)
{
  if((m_pNextPos + relPos) >= m_pPacket && (m_pNextPos + relPos) <= (m_pPacket + m_len))
  {
    m_pNextPos += relPos;
    return true;
  }
  return false;
}

bool GDBPacket::EndOfPacket()
{
  if(*m_pNextPos == '#' || m_pNextPos >= m_pPacket + m_len)
    return true;
  else
    return false;
}
//Default implementations,
//override these in class inherited from GDBServer
int GDBServer::OnContinue(uint64_t uiAddress)
{

  return -1;
}
int GDBServer::OnReadGPR(REGISTERFILE& registerFile)
{
  return -1;
}

int GDBServer::OnWriteGPR(REGISTERFILE& registerFile)
{
  return -1;
}

int GDBServer::OnReadMemory(uint64_t uiAddress, uint64_t& uiLen, void* pMemBuffer)
{
  return -1;
}

int GDBServer::OnWriteMemory(uint64_t uiAddress, uint64_t& uiLen, void* pMemBuffer)
{
  return -1;
}

int GDBServer::OnReadSingleRegister(int reg, uint64_t& value)
{
  return -1;
}

int GDBServer::OnWriteSingleRegister(int reg, uint64_t& value)
{
  return -1;
}

int GDBServer::OnSingleStep(uint64_t uiRangeBegin, uint64_t uiRangeEnd)
{
  return -1;
}

int GDBServer::OnSetBreakWatchPoint(unsigned char type, uint64_t uiAddress, uint64_t uiKind)
{
  return -1;
}

int GDBServer::OnClearBreakWatchPoint(unsigned char type, uint64_t uiAddress, uint64_t uiKind)
{
  return -1;
}

int GDBServer::OnExternalHalt()
{
  return -1;
}

int GDBServer::OnKill(uint64_t uiProcId)
{
  return -1;
}

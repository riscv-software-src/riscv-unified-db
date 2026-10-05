#include "udb/NotificationHandler.hpp"

NotificationHandler::NotificationHandler()
{
  m_bEnable = true;
}

NotificationHandler::~NotificationHandler()
{
}

void NotificationHandler::EnableNotifications()
{
  m_bEnable = true;
}

void NotificationHandler::DisableNotifications()
{
  m_bEnable = false;
}

int NotificationHandler::Notify(uint8_t uiModuleId, uint64_t uiEvent, void* pData) {
  if(!m_bEnable)
    return 0;

  return OnNotification(uiModuleId, uiEvent, pData);
}

NotificationSource::NotificationSource()
{

}

NotificationSource::~NotificationSource()
{

}

int NotificationSource::AttachHandler(NotificationHandler* pHandler, uint8_t id)
{
  m_handlerList.push_back(HandlerId(pHandler, id));

  return 0;
}

int NotificationSource::AttachHandler(NOTIFYCALLBACK pNotificationCallback, uint8_t id,
                                      void* pUserParam)
{
  m_handlerList.push_back(HandlerId(pNotificationCallback, id, pUserParam));
  return 0;
}

int NotificationSource::Notify(uint64_t uiEvent, void* pData)
{
  int result = 0;
  for(auto iter = m_handlerList.begin() ; iter != m_handlerList.end(); ++iter)
  {
    if(iter->m_pCallback != nullptr)
    {
      result = iter->m_pCallback(iter->m_pParam, iter->m_id, uiEvent, pData);
    }
    else
    {
      result = static_cast<NotificationHandler*>(iter->m_pParam)->Notify(iter->m_id, uiEvent, pData);
    }
  }
  return result;
}

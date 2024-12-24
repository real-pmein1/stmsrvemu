"""I am unsure what uses these, but it is in the 2008/2009 steamclient.dll"""

def handle_ClientUpdateInvPos(unknown):
    # incoming packet uses extended header and should contain the following, order is unknown:
    #   appid(32bit), new position(32bit), itemid(64 bit)

    #the response (ClientUpdateInvPosResponse) should only contain the eResult:
    #k_EResultOK
    #k_EResultInvalidParam
    #k_EResultAccessDenied
    #k_EResultTimeout
    #k_EResultServiceUnavailable
    #k_EResultNoMatch
    pass

def handle_ClientDropItem(unknown):
    # contains appid(32bit), itemid(64bit)

    #response (ClientDropItemResponse) contains just the eresult, same as above
    pass

def handle_ClientLoadItems(unknown):
    """EItemRequestResult __cdecl MapItemResult(EResult eGenericResult)
   {
     EItemRequestResult v2; // [esp+4h] [ebp-4h]

     switch ( eGenericResult )
     {
       case EResult::k_EResultOK:
         v2 = EItemRequestResult::k_EItemRequestResultOK;
         break;
       case EResult::k_EResultInvalidParam:
         v2 = EItemRequestResult::k_EItemRequestResultInvalid;
         break;
       case EResult::k_EResultAccessDenied:
         v2 = EItemRequestResult::k_EItemRequestResultDenied;
         break;
       case EResult::k_EResultTimeout:
         v2 = EItemRequestResult::k_EItemRequestResultTimeout;
         break;
       case EResult::k_EResultServiceUnavailable:
         v2 = EItemRequestResult::k_EItemRequestResultServerError;
         break;
       case EResult::k_EResultNoMatch:
         v2 = EItemRequestResult::k_EItemRequestResultNoMatch;
         break;
       default:
         v2 = EItemRequestResult::k_EItemRequestResultUnknownError;
         break;
     }
     return v2;
   }"""
    # response is k_EMsgClientLoadItemsResponse
    pass


#message 887 and 913 have extended headers and contain the following:
#    if ( !CMsgBase_t<ExtendedClientMsgHdr_t>::BReadUintData(msg, &this->m_AppId) )
#      return 0;
#    if ( !CMsgBase_t<ExtendedClientMsgHdr_t>::BReadUintData(msg, &this->m_unDefIndex) )
#      return 0;
#    if ( !CMsgBase_t<ExtendedClientMsgHdr_t>::BReadUintData(msg, &this->m_unLevel) )
#      return 0;
#    if ( !CMsgBase_t<ExtendedClientMsgHdr_t>::BReadIntData(msg, (int32 *)&this->m_eQuality) )
#      return 0;
#    if ( !CMsgBase_t<ExtendedClientMsgHdr_t>::BReadUintData(msg, &this->m_unInventoryPos) )
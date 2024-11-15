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
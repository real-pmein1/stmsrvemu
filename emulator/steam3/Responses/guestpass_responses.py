import struct

from steam3.ClientManager.client import Client
from steam3.Types.MessageObject.GuestPass import GuestPass_Deprecated
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult
from steam3.cm_packet_utils import CMResponse
from steam3.utilities import add_time_to_current_uint32, get_current_time_uint32


def build_SendGuestPassResponse(client_obj: Client, errorcode = EResult.OK):
    packet = CMResponse(eMsgID = EMsg.ClientSendGuestPassResponse, client_obj = client_obj)

    packet.data = struct.pack('IIII',
                              client_obj.steamID * 2,
                              client_obj.clientID2,
                              client_obj.sessionID,
                              errorcode)  # errorcode

    return packet


def build_SendAckGuestPassResponse(client_obj: Client, guestpassKey, errorcode = EResult.OK):
    """
    struct MsgClientAckGuestPassResponse_t
    {
      EResult m_eResult;
      uint32 m_unPackageID;
      GID_t m_gidGuestPassID;
      uint64 m_ulGuestPassKey;
    };

    """
    packet = CMResponse(eMsgID = EMsg.ClientAckGuestPassResponse, client_obj = client_obj)

    packet.data = struct.pack('<IIII',
                              client_obj.steamID * 2,
                              client_obj.clientID2,
                              client_obj.sessionID,
                              errorcode)  # errorcode
    packageid = 0
    guestID = 0
    packet.data += struct.pack('<Iqq',
                              packageid,
                               guestID,  # guestpass id
                               guestpassKey)

    return packet


def build_RedeemGuestPassResponse(client_obj: Client, packageID, eresult = EResult.OK):
    """
    struct MsgClientRedeemGuestPassResponse_t
    {
      EResult m_eResult;
      uint32 m_unPackageID;
    };
    """
    packet = CMResponse(eMsgID = EMsg.ClientRedeemGuestPassResponse, client_obj = client_obj)

    packet.data = struct.pack('<IIIII',
                              client_obj.steamID * 2,
                              client_obj.clientID2,
                              client_obj.sessionID,
                              eresult,
                              packageID)

    return packet


def build_GetGiftTargetListResponse(cmserver_obj, client_obj: Client, packageID):
    """
    MsgClientGetGiftTargetListResponse_t
    {
      uint32 m_unPackageID;
      uint64 m_ulSteamIDFriend;
      int32 m_iPotentialGiftTarget;
      int32 m_cPotentialGiftTargetsTotal;
      uint8 m_bValidGiftTarget;
    };
    """
    # FIXME I have absolutely NO IDEA what this is supposed to do, there is NO documentation or ANY information on this besides the variable names, datatypes and sizes
    packet = CMResponse(eMsgID = EMsg.ClientRedeemGuestPassResponse, client_obj = client_obj)
    clientId2 = 0x01100001
    target_count = 0

    # only return friends who dont have this subid
    friends_steamid_list = client_obj.grab_potential_gift_targets(packageID)
    total_targets = len(friends_steamid_list)


    if total_targets > 0:
        for friendid in friends_steamid_list:
            target_count += 1
            packet.data = struct.pack('<IIIIIB',
                                      packageID,
                                      friendid* 2,
                                      clientId2,
                                      target_count,
                                      total_targets,
                                      True)

        return packet

    else:  # No valid targets
        print("NO VALID TARGETS DOUCHE KNUCKLE")
        packet.data = struct.pack('IIIIIB',
                                  packageID,
                                  0,
                                  0,
                                  0,
                                  0,
                                  0)

        return packet


def build_updated_guestpast_list_request(client_obj: Client):
    """ # guestpass data:
        def load(self, data):
            (eresult,
             self.countGuestPassesToGive,
             self.countGuestPassesToRedeem,
            ) = struct.unpack_from("<III", data)"""

    # TODO NOTE:
    #  Guest pass is a Gift if the package ID's billing type (CDR) is not GuestPass
    #  ^^^This only applies to Mid-2007 clients and later!


    packet = CMResponse(eMsgID = EMsg.ClientUpdateGuestPassesList, client_obj = client_obj)

    packet.data = struct.pack('III',
                              EResult.OK,
                              0,  # passes to give
                              0)  # passes to redeem
    # TODO grab from database
    """guest_pass_to_redeem = GuestPass_Deprecated(
            GID = 1232423443232348,
            PackageID = 292,
            TimeCreated = get_current_time_uint32(),
            TimeExpiration = add_time_to_current_uint32(12, 5, 23, 10),
            TimeSent = get_current_time_uint32(),
            TimeAcked = get_current_time_uint32(),
            TimeRedeemed = 0,
            RecipientAddress = '',
            SenderAddress = 'test@test.com',
            SenderName = 'test'
    )"""

    """guest_pass_to_send = GuestPass_Deprecated(
            GID = 1232423443232345,
            PackageID = 292,
            TimeCreated = get_current_time_uint32(),
            TimeExpiration = add_time_to_current_uint32(12, 5, 23, 10),
            TimeSent = 0,
            TimeAcked = 0,
            TimeRedeemed = 0,
            RecipientAddress = '',
            SenderAddress = '',
            SenderName = ''
    )"""

    # packet.data += guest_pass_to_send.serialize()
    return packet
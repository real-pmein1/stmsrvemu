import struct

from steam3.ClientManager import Client_Manager
from steam3.ClientManager.client import Client
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMPacket, CMResponse


def handle_P2PIntroducerMessage(cmserver_obj, packet: CMPacket, client_obj: Client):
    """
        it looks like this just gets forwarded on to the receiving client
        MsgClientP2PIntroducerData_t
        {
          uint64 m_unSteamID;
          EIntroducerRouting m_ERoutingType; 4 bytes
          uint8 m_Data[1450];
          uint32 m_cubDataLen;
        };

        VoiceIntroducer::InitiatorBase
        {
          bool m_bIsInitiator;
          netadr_t m_RelayAddress;
          uint16 m_usCandidateBlobSize;
        };

        struct Candidate
        {
          bool sent;
          CUtlString name_;
          CUtlString protocol_;
          CUtlString address_;
          unsigned __int16 port_;
          float preference_;
          CUtlString username_;
          CUtlString password_;
          CUtlString type_;
          CUtlString network_name_;
          uint32 generation_;
          int nattype_;
        };
    b'\x02\x00\x00\x00\x01\x00\x10\x01 steamID requester
    \x01\x00\x00\x00 voicechat
    \x00\x00
    \x02\x00\x00\x00\x01\x00\x10\x01 steamID requester
    \x08\x00\x00\x00\x01\x00\x10\x01 steamID receipient
    \x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
    \x01
    \x1b\x11gr
    \xb4\x03\xa8\xc0
    \x03\x00\x00\x00
    Q\x00
    valvep2p\x00
    udp\x00
    72.135.228.147\x00
    \xc7\xca
    ?\x80\x00\x00
    gzFeVaEJhSCVmKH/\x00
    8HTXIpUeRwbzQ+Rv\x00
    local\x00
    0\x00"""

    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved P2P Introducer Message Request -> Forwarding to Intended User")
    request = packet.CMRequest
    recievers_steamID, = struct.unpack("<I", request.data[22:26])
    recieving_client_obj = Client_Manager.clients_by_steamid.get(recievers_steamID // 2)
    print(f"p2p receipient account ID: {recievers_steamID}")
    if recieving_client_obj:
        packet = CMResponse(client_obj = recieving_client_obj)
        packet.eMsgID = EMsg.ClientP2PIntroducerMessage
        packet.data = b'\x08\x00\x00\x00\x01\x00\x10\x01' + request.data[16:]
        packet.length = len(packet.data)
        cmserver_obj.sendReply(recieving_client_obj, [packet])

    return -1
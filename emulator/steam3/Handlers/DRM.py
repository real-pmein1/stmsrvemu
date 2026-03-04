import globalvars
from steam3.ClientManager.client import Client
from steam3.cm_packet_utils import CMPacket
from steam3.messages.MsgClientDRMProblemReport import MsgClientDRMProblemReport
from steam3.messages.MsgClientDRMDownloadRequest import MsgClientDRMDownloadRequest
from steam3.Responses.drm_responses import build_DRMDownload_response
from steam3.messages.MsgFileXferRequest import MsgFileXferRequest
from steam3.messages.MsgFileXferDataAck import MsgFileXferDataAck
from steam3.messages.MsgClientDFSDownloadStatus import MsgClientDFSDownloadStatus
from steam3.messages.MsgClientDFSEndSession import MsgClientDFSEndSession

"""  msg=851,
  proto=False,
  gc=False,
  header=eMsgID: EMsg.ClientDRMProblemReport
headerSize: 36
headerVersion: 2
targetJobID: -1
sourceJobID: -1
headerCanary: 239
accountID: 2
clientID2: 17825793
sessionID: 0
data: b'6\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00',
  body=b'6\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'"""


def handle_DRMProblemReport(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved DRM Problem Report")

    # Later, deserialize it
    report = MsgClientDRMProblemReport()
    report.de_serialize(request.data)

    print(f"DRM Report: {report}")
    return -1

"""eMsgID: EMsg.ClientDRMDownloadRequest
headerSize: 36
headerVersion: 2
targetJobID: -1
sourceJobID: 650458754449549
headerCanary: 239
accountID: 2
clientID2: 17825793
sessionID: 0
data: b'\x1a\x00\x00\x00\x07\x00\x00\x00\x8c\xe8\xab\xa4&\x93\xd8D\x9c\xb7\xb0\x10\xaa\x12dO\xf7\xae\xc1i\xde\x82\xe5A\x88\x07\xed\xd9\x88\xf1\xbb,\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00client.dll\x00e:\servers\stmserver\clients\prerelease\steamapps\common\left 4 dead 2\left4dead2\bin\client.dll\x00'
packetid: 5485
b'\x1a\x00\x00\x00\x07\x00\x00\x00\x8c\xe8\xab\xa4&\x93\xd8D\x9c\xb7\xb0\x10\xaa\x12dO\xf7\xae\xc1i\xde\x82\xe5A\x88\x07\xed\xd9\x88\xf1\xbb,\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00client.dll\x00e:\servers\stmserver\clients\prerelease\steamapps\common\left 4 dead 2\left4dead2\bin\client.dll\x00'"""

def handle_DRMDownloadRequest(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received DRM Download Request")

    request = packet.CMRequest
    parser = MsgClientDRMDownloadRequest(data=request.data)

    cmserver_obj.log.debug(str(parser))

    import socket
    if globalvars.server_ip:
        ip = int.from_bytes(socket.inet_aton(globalvars.server_ip), 'little')
    else:
        ip = int.from_bytes(socket.inet_aton(client_address[0]), 'little')
    port = 27017
    url = parser.executable_filename or ""

    response = build_DRMDownload_response(
        client_obj,
        eresult=0,
        app_id=0,
        blob_type=0,
        merge_guid=b"\x00" * 16,
        ip=ip,
        port=port,
        url=url,
        module_path=parser.absolute_path or "",
    )
    return response


def handle_FileXferRequest(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received FileXferRequest")
    msg = MsgFileXferRequest(data=packet.CMRequest.data)
    cmserver_obj.log.debug(str(msg))
    return -1


def handle_FileXferDataAck(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.debug(f"({client_address[0]}:{client_address[1]}): Received FileXferDataAck")
    msg = MsgFileXferDataAck(data=packet.CMRequest.data)
    cmserver_obj.log.debug(str(msg))
    return -1


def handle_DFSDownloadStatus(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.debug(f"({client_address[0]}:{client_address[1]}): Received DFSDownloadStatus")
    msg = MsgClientDFSDownloadStatus(data=packet.CMRequest.data)
    cmserver_obj.log.debug(str(msg))
    return -1


def handle_DFSEndSession(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received DFSEndSession")
    msg = MsgClientDFSEndSession(data=packet.CMRequest.data)
    cmserver_obj.log.debug(str(msg))
    return -1

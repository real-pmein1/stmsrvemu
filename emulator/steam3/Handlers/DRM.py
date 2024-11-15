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
from steam3.ClientManager.client import Client
from steam3.cm_packet_utils import CMPacket
from steam3.messages.MsgClientDRMProblemReport import MsgClientDRMProblemReport

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
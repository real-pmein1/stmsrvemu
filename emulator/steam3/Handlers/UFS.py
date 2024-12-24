import struct

from steam3.ClientManager.client import Client
from steam3.Responses.ufs_responses import build_UFSGetFileListForApp_response
from steam3.cm_packet_utils import CMPacket, ExtendedMsgHdr

from steam3.protobufs.steammessages_clientserver_ufs_pb2 import CMsgClientUFSGetFileListForApp  # Import the protobuf message definition


def handle_UFSGetFileListForApp(cmserver_obj, packet: CMPacket, client_obj: Client):
    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Received UFS Get File List For App Request")

    # Check if the packet is a protobuf packet
    if not isinstance(request, ExtendedMsgHdr):
        # Deserialize using protobuf
        cmserver_obj.log.debug("Packet identified as protobuf.")
        body = CMsgClientUFSGetFileListForApp()
        body.ParseFromString(request.data)

        # Extract app IDs
        app_ids = list(body.apps_to_query)
        cmserver_obj.log.debug(f"Parsed app IDs from protobuf: {app_ids}")
    else:
        # Fallback to original deserialization logic
        cmserver_obj.log.debug("Packet identified as binary format.")
        offset = 0
        app_count = struct.unpack_from('<I', request.data, offset)[0]  # Read DWORD appCount
        offset += 4  # Move offset forward by 4 bytes

        app_ids = []
        for _ in range(app_count):
            app_id = struct.unpack_from('<I', request.data, offset)[0]  # Read each DWORD app ID
            app_ids.append(app_id)
            offset += 4  # Move offset forward for each DWORD

        cmserver_obj.log.debug(f"Parsed app IDs from binary: {app_ids}")

    # Return the response using the extracted app IDs
    return build_UFSGetFileListForApp_response(client_obj,app_ids, request.is_proto)
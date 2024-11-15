import struct

from steam3.ClientManager.client import Client
from steam3.cm_packet_utils import CMPacket


def handle_UFSGetFileListForApp(cmserver_obj, packet: CMPacket, client_obj: Client):

    client_address = client_obj.ip_port
    request = packet.CMRequest
    cmserver_obj.log.info(f"({client_address[0]}:{client_address[1]}): Recieved GS Server Type Information")
    # Create a dictionary to store the deserialized data
    result = {}

    # Position in the binary data
    offset = 0

    # Read the appCount (DWORD is a 32-bit integer, represented by 'I' in struct)
    app_count = struct.unpack_from('<I', request.data, offset)[0]  # '<I' for little-endian unsigned 32-bit integer
    offset += 4  # Move offset forward by 4 bytes (size of DWORD)

    # Initialize the appIds list
    app_ids = []

    # Read appCount number of DWORDs (32-bit integers)
    for _ in range(app_count):
        app_id = struct.unpack_from('<I', request.data, offset)[0]  # Unpack each 32-bit integer
        app_ids.append(app_id)
        offset += 4  # Move offset forward by 4 bytes for each DWORD

    # Store the appIds list in the result
    result['app_ids'] = app_ids

    return -1
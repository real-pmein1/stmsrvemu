import struct
from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse

class MsgClientAppInfoChanges:
    def __init__(self, client_obj):
        self.current_change_number = 0
        self.force_full_update = False
        self.app_ids = []
        self.client_obj = client_obj

    def to_clientmsg(self):
        """
        Serialize the object into a byte buffer.

        :return: A byte buffer containing serialized data.
        """
        packet = CMResponse(eMsgID=EMsg.ClientAppInfoChanges, client_obj=self.client_obj)

        buffer = bytearray()

        # Write current change number (4 bytes, DWORD)
        buffer.extend(struct.pack('<i', self.current_change_number))

        # Write app count (4 bytes, DWORD)
        buffer.extend(struct.pack('<I', len(self.app_ids)))

        # Write force full update flag (1 byte, bool)
        buffer.extend(struct.pack('<?', int(self.force_full_update)))

        # Write app IDs
        if len(self.app_ids) > 0:
            for app_id in self.app_ids:
                buffer.extend(struct.pack('<I', app_id))

        packet.data = bytes(buffer)
        packet.data_len = len(packet.data)

        return packet

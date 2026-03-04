import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg
from steam3.Types.MessageObject import MessageObject


class MSGClientLookupKey:
    """
    MsgClientLookupKey - Look up information about a product key/activation code

    The packet contains a MessageObject with a "Key" field containing the CD key.

    Protocol differences:
        - Protocol >= 65555: 1-byte header (m_eCmd), then MessageObject
        - Protocol < 65555: 2-byte header, then MessageObject

    Fields:
        key (str): Product key or activation code to lookup
    """

    # Protocol version threshold for new message format
    PROTOCOL_THRESHOLD = 65555

    def __init__(self, client_obj, data: bytes = None, version: int = None):
        self.client_obj = client_obj
        self.key = ""

        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        """Parse the binary data containing MessageObject with Key field"""
        if len(data) < 3:
            raise ValueError("Insufficient data for MSGClientLookupKey")

        try:
            # Determine header size based on client protocol version
            # Protocol >= 65555: MsgClientLookupKey_t has 1-byte m_eCmd field
            # Protocol < 65555: Legacy format with 2-byte header
            protocol_version = getattr(self.client_obj, 'protocol_version', 0)

            if protocol_version >= self.PROTOCOL_THRESHOLD:
                # New format: skip 1 byte (m_eCmd)
                payload = data[1:]
            else:
                # Legacy format: skip 2 bytes (header: \x00\x00)
                payload = data[2:]

            # Parse the MessageObject
            msg_obj = MessageObject(payload)

            # Extract the key from the "Key" field
            self.key = msg_obj.getValue("Key", "")

            if not self.key:
                raise ValueError("No Key field found in MessageObject")

        except Exception as e:
            raise ValueError(f"Failed to parse MSGClientLookupKey MessageObject: {e}")
    
    def to_clientmsg(self):
        """Build CMResponse packet for this message"""
        raise NotImplementedError("MSGClientLookupKey is request-only")
    
    def to_protobuf(self):
        """Return protobuf representation if available"""
        raise NotImplementedError("No protobuf equivalent for MSGClientLookupKey")
    
    def __str__(self):
        return f"MSGClientLookupKey(key='{self.key}')"
    
    def __repr__(self):
        return self.__str__()
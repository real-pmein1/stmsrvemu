import struct
from steam3.Types.emsg import EMsg


class MSGClientGetLicenses:
    """
    Message for ClientGetLicenses (EMsg 728).
    
    This is a request from the client to get their license list.
    The client sends this to request all licenses they own.
    
    This message typically has no body data or minimal data.
    """
    
    def __init__(self, client_obj, data: bytes = None, version: int = None):
        self.client_obj = client_obj
        
        if data:
            self.deserialize(data)
    
    def deserialize(self, data: bytes):
        """
        Deserialize the ClientGetLicenses request data.
        
        Args:
            data (bytes): The raw message data
        """
        # ClientGetLicenses typically has no body or minimal data
        # Some versions might include a version number or flags
        if len(data) >= 4:
            # Might contain a version or request flags
            pass  # Currently no specific parsing needed
    
    def to_clientmsg(self):
        """
        This is a request message, so client->server direction.
        Not typically used for responses.
        """
        raise NotImplementedError("ClientGetLicenses is a request message, not a response")
    
    def to_protobuf(self):
        """Serialize to protobuf format (not implemented yet)."""
        raise NotImplementedError("Protobuf serialization not implemented")
    
    def __repr__(self):
        return f"<MSGClientGetLicenses client={self.client_obj.steamID if self.client_obj else None}>"
import struct


class MsgClientEmailAddrInfo:
    def __init__(self, password_strength=0, account_security_policy_flags=0, verified_email=False, contact_email=""):
        self.password_strength = password_strength
        self.account_security_policy_flags = account_security_policy_flags
        self.verified_email = verified_email
        self.contact_email = contact_email

    def serialize(self):
        # Serialize the data using struct.pack
        data = b""
        data += struct.pack("<i", self.password_strength)  # Serialize as int32
        data += struct.pack("<i", self.account_security_policy_flags)  # Serialize as int32
        data += struct.pack("<B", 1 if self.verified_email else 0)  # Serialize as int8 (1 byte)
        data += struct.pack(f"<H{len(self.contact_email)}s", len(self.contact_email), self.contact_email.encode("utf-8"))  # Serialize length-prefixed string
        return data
import struct
from io import BytesIO

class MsgClientVACResponse:
    def __init__(self):
        self.m_nGameID = 0
        self.m_cubResponse = 0
        self.pubResponse = b''

    def parse(self, byte_buffer):
        """Parses the VAC response message from the provided byte string."""
        stream = BytesIO(byte_buffer)

        try:
            # Read m_nGameID (int32)
            self.m_nGameID = struct.unpack('<I', stream.read(4))[0]

            # Read m_cubResponse (int32)
            self.m_cubResponse = struct.unpack('<I', stream.read(4))[0]

            # Read the VAC response data (based on the size of cubResponse)
            self.pubResponse = stream.read(self.m_cubResponse)

        except Exception as e:
            print(f"Error during parsing: {e}")

        # Check if there are extra bytes
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Extra bytes in buffer: {remaining_bytes.hex()}")

        return self

    def __repr__(self):
        return (f"MsgClientVACResponse(GameID={self.m_nGameID}, "
                f"ResponseLength={self.m_cubResponse}, Response={self.pubResponse.hex()})")


# Example usage
packet = b'\xc0\x02\x00\x00 m\x88\x00\x01\x00\x10\x01-\xaa \x02\x00\x00\x00\x00\x08\x01\x00\x00$-\x85u\xca\x88x\x87\xc58l\x89B\xc7H\xf0\xf4\x9d\x0c\xb8\xecM\x84\xbd\x05\xcb\x00M\xa8M\x01\xe7\xce\xc7\xa1\x1c\x89\xd8\x97\x97X\xf5\x8c\x92\xb7E\x85\xff\xce\xc7\xa1\x1c\x89\xd8\x97\x97X\xf5\x8c\x92\xb7E\x85\xff\xde%\rj^\xee>\x1d\xf09\xe1\xa7X*\xe4,\xf9\x08?\xba\xd9(\xe9\xd4\xff\x904\xe8\xb8-\xb5u\xc9E\xaau\x18v\xe0\xb4\xff\x904\xe8\xb8-\xb5u\xc9E\xaau\x18v\xe0\xb4\xa7nO_cQ}}\xb3\x94\xf9LF\xc1w\xe7)l\x1d8\xb1\x15\xa3\xb1,\xd6\xcao\xcb\x83gz\xd2h}\xfd\x85te\xe7`5\xaaP\x8c\xca\xb48\xed\xcc`\x8cF\x8a\xa4Z3\xaf\xce1\xac\x16\xda~\xe4\x90\'\x88S\xc0"8\xaaZc\xbbpq~c\xfb\xfd\xa8=KdPRY\x98\xfc\x95\x17\x0b\xf6w-\xdc\xb6\x0b\x91Y]\x8d$\x85\xe7\xfa\x1f(\xd8pr/\xdb\xb0u\x1a%\x9ci%D\x1d\xe8\x84\x1ei\x17\xdd%\x9c2\xbe\x99Di:p\xdb\x8d\xe8\xfa\x01'
print(len(bytes.fromhex('242d8575ca887887c5386c8942c748f0f49d0cb8ec4d84bd05cb004da84d01e7cec7a11c89d8979758f58c92b74585ffcec7a11c89d8979758f58c92b74585ffde250d6a5eee3e1df039e1a7582ae42cf9083fbad928e9d4ff9034e8b82db575c945aa751876e0b4ff9034e8b82db575c945aa751876e0b4a76e4f5f63517d7db394f94c46c177e7296c1d38b115a3b12cd6ca6fcb83677ad2687dfd857465e76035aa508ccab438edcc608c468aa45a33afce31ac16da7ee490278853c02238aa5a63bb70717e63fbfda83d4b6450525998fc95170bf6772ddcb60b91595d8d2485e7fa1f28d870722fdbb0751a259c6925441de8841e6917dd259c32be9944693a70db8de8fa01')))

print(packet[16:])
vac_response = MsgClientVACResponse()
vac_response.parse(packet[16:])

# Output the parsed data
print(vac_response)
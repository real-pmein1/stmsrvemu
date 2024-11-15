import struct

from steam3.Types.MessageObject import MessageObject


class ClientAnonUserLogOn_Deprecated:
    def __init__(self, byte_buffer):
        self.byte_buffer = byte_buffer
        self.protocolVersion = None
        self.privateIp = None
        self.publicIp = None
        self.steamGlobalId = None
        self.steamGlobalId_tbd = None
        self.accountName = None
        self.authenticationField = None
        self.clientAppVersion = None
        self.bootStrapperVersion = None
        self.cellId = None
        self.unused = None
        self.machineIDInfoAvailable = None
        self.qosLevel = None
        self.interfaceLanguage = None
        self.machineIDInfo = None

        self._parse_byte_buffer()

    def _parse_byte_buffer(self):
        offset = 0

        self.protocolVersion, = struct.unpack_from('<I', self.byte_buffer, offset)
        offset += 4

        self.privateIp, = struct.unpack_from('<I', self.byte_buffer, offset)
        self.privateIp ^= 0xBAADF00D
        offset += 4

        self.publicIp, = struct.unpack_from('<I', self.byte_buffer, offset)
        offset += 4

        self.steamGlobalId, = struct.unpack_from('<Q', self.byte_buffer, offset)
        offset += 8

        self.steamGlobalId_tbd, = struct.unpack_from('<Q', self.byte_buffer, offset)
        offset += 8

        self.accountName = self.byte_buffer[offset:offset + 0x40] # Should always be null
        offset += 0x40

        self.authenticationField = self.byte_buffer[offset:offset + 0x14]  # Should always be null
        offset += 0x14

        self.clientAppVersion, = struct.unpack_from('<I', self.byte_buffer, offset)
        offset += 4

        self.bootStrapperVersion, = struct.unpack_from('<I', self.byte_buffer, offset)
        offset += 4

        self.cellId, = struct.unpack_from('<I', self.byte_buffer, offset)
        offset += 4

        self.unused, = struct.unpack_from('<I', self.byte_buffer, offset)
        offset += 4

        self.machineIDInfoAvailable, = struct.unpack_from('<B', self.byte_buffer, offset)
        offset += 1

        self.qosLevel, = struct.unpack_from('<B', self.byte_buffer, offset)
        offset += 1
        #print(self.byte_buffer[offset:])
        self.interfaceLanguage = self.byte_buffer[offset:].split(b'\x00', 1)[0].decode('latin-1')
        offset += len(self.interfaceLanguage) + 1

        if bool(self.machineIDInfoAvailable):
            self.machineIDInfo = MessageObject(self.data[offset:])
            self.machineIDInfo.parse()
            index = self.data.find(b"\x08\x08", offset)
            if index == -1:
                raise ValueError("MachineID sequence not found")
            offset = index + 2
        else:
            self.machineIDInfo = None

    def __repr__(self):
        return (
                f"SteamData(protocolVersion={self.protocolVersion}, privateIp={self.privateIp}, "
                f"publicIp={self.publicIp}, steamGlobalId={self.steamGlobalId}, steamGlobalId_tbd={self.steamGlobalId_tbd}, "
                f"clientAppVersion={self.clientAppVersion}, bootStrapperVersion={self.bootStrapperVersion}, "
                f"cellId={self.cellId}, unused={self.unused}, machineIDInfoAvailable={self.machineIDInfoAvailable}, "
                f"qosLevel={self.qosLevel}, interfaceLanguage={self.interfaceLanguage}, "
                f"machineIDInfo={self.machineIDInfo})"
        )

    def __str__(self):
        return self.__repr__()


"""byte_buffer = b'\x01' * 150  # Replace this with actual byte buffer data
steam_data = ClientAnonUserLogOn_Deprecated(byte_buffer)
print(steam_data)
"""
"""    packetid: 5409
b'\x16\x00\x01\x00
\xca\x1c*\xf2
\x00\x00\x00\x00
\x00\x00\x00\x00\x00\x00\x00\x00
\x00\x00\x00\x00\x00\x00\x00\x00
\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00
\xb8\x03\x00\x00
6\x00\x00\x00
\x00\x00\x00\x00
\x00\x00\x00\x00
\x00
\x00
english\x00'
    (b'\x1b\x00\x01\x00'
     b'\xca\x1c'
     b'*\xf2'
     b'\x00\x00\x00\x00\x00\x00\x00\x00'
     b'\x00\x00\x00\x00\x00\x00\x00\x00'
     b'\x00\x00\x00\x00'
     b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
     steamui version b'\xd6\x04\x00\x00'
     bootstrap version b'=\x00\x00\x00'
     cellid b'\x00\x00\x00\x00'
     unused b'\x00\x00\x00\x00'
     use_machineid b'\x00'
     qos b'\x00'
     language b'english\x00')"""
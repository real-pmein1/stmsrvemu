import struct


class MsgClientVACStatusResponse:
    """
    Parser for MsgClientVACStatusResponse_t.

    Layout implemented:
        uint32  m_uVACStatusModule
        uint32  m_cbOutboundChallenge
        uint16  m_cVACInstances
        uint8   m_bOutstandingChallenge
        uint8   _pad0                    (assumed for 4-byte alignment)
        uint32  m_RTime32ChallengeRecieved
        uint32  m_RTime32ChallengeDelivered
        uint32  m_RTime32ChallengeAnswered
        uint32  m_cbInboundResponse
    """

    _U32 = struct.Struct("<I")
    _U16 = struct.Struct("<H")
    _U8  = struct.Struct("<B")

    def __init__(self, data: bytes):
        self.data = data
        self.parse()

    def parse(self):
        offset = 0

        # uint32 m_uVACStatusModule
        self.m_uVACStatusModule, = self._U32.unpack_from(self.data, offset)
        offset += 4

        # uint32 m_cbOutboundChallenge
        self.m_cbOutboundChallenge, = self._U32.unpack_from(self.data, offset)
        offset += 4

        # uint16 m_cVACInstances
        self.m_cVACInstances, = self._U16.unpack_from(self.data, offset)
        offset += 2

        # uint8 m_bOutstandingChallenge
        self.m_bOutstandingChallenge, = self._U8.unpack_from(self.data, offset)
        offset += 1

        # uint8 pad (very likely, so the next uint32 is aligned)
        # If your captures prove otherwise, delete this and adjust offsets.
        if offset < len(self.data):
            self._pad0, = self._U8.unpack_from(self.data, offset)
        else:
            self._pad0 = 0
        offset += 1

        # uint32 m_RTime32ChallengeRecieved
        self.m_RTime32ChallengeRecieved, = self._U32.unpack_from(self.data, offset)
        offset += 4

        # uint32 m_RTime32ChallengeDelivered
        self.m_RTime32ChallengeDelivered, = self._U32.unpack_from(self.data, offset)
        offset += 4

        # uint32 m_RTime32ChallengeAnswered
        self.m_RTime32ChallengeAnswered, = self._U32.unpack_from(self.data, offset)
        offset += 4

        # uint32 m_cbInboundResponse
        self.m_cbInboundResponse, = self._U32.unpack_from(self.data, offset)
        offset += 4

        # Anything remaining (futureproofing / unknown trailing fields)
        self._trailing = self.data[offset:]

    def __str__(self):
        return str({
            "m_uVACStatusModule": self.m_uVACStatusModule,
            "m_cbOutboundChallenge": self.m_cbOutboundChallenge,
            "m_cVACInstances": self.m_cVACInstances,
            "m_bOutstandingChallenge": self.m_bOutstandingChallenge,
            "m_RTime32ChallengeRecieved": self.m_RTime32ChallengeRecieved,
            "m_RTime32ChallengeDelivered": self.m_RTime32ChallengeDelivered,
            "m_RTime32ChallengeAnswered": self.m_RTime32ChallengeAnswered,
            "m_cbInboundResponse": self.m_cbInboundResponse,
            "trailing_len": len(self._trailing),
            "trailing_hex": self._trailing.hex(),
        })

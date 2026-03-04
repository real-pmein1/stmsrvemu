import struct

from steam3.Types.emsg import EMsg
from steam3.cm_packet_utils import CMResponse


class MsgClientVTTCert:
    """
    MsgClientVTTCert_t

    Inferred body layout:
        uint32 m_cVTTCertTotal
        uint32 m_cVTTCertTotalBad
        uint8  m_cVTTCert              (bool)
        uint8  _pad0
        uint16 _pad1
        uint32 m_cubVTTCert            (0 or 140)

    Followed by variable-length data (if m_cVTTCert != 0 and m_cubVTTCert == 140):
        uint8  rsa_public_key[140]
    """

    PUBKEY_SIZE = 140

    # Pad after the bool to keep the next uint32 aligned.
    BODY_FORMAT = "<IIBBHI"
    BODY_SIZE = struct.calcsize(BODY_FORMAT)

    def __init__(
        self,
        client_obj,
        total: int = 0,
        total_bad: int = 0,
        found: bool = False,
        rsa_public_key: bytes = b"",
    ):
        self.client_obj = client_obj
        self.m_cVTTCertTotal = int(total)
        self.m_cVTTCertTotalBad = int(total_bad)
        self.m_cVTTCert = bool(found)

        if self.m_cVTTCert:
            if rsa_public_key and len(rsa_public_key) != self.PUBKEY_SIZE:
                raise ValueError(f"rsa_public_key must be {self.PUBKEY_SIZE} bytes when found=True")
            self.rsa_public_key = rsa_public_key or (b"\x00" * self.PUBKEY_SIZE)
            self.m_cubVTTCert = self.PUBKEY_SIZE
        else:
            self.rsa_public_key = b""
            self.m_cubVTTCert = 0

        # internal padding fields, not meaningful
        self._pad0 = 0
        self._pad1a = 0
        self._pad1b = 0

    def deSerialize(self, buffer: bytes, offset: int = 0) -> int:
        """
        Parse body + optional variable data from buffer.
        Returns new offset.
        """
        if len(buffer) < offset + self.BODY_SIZE:
            raise ValueError(f"Buffer too small for MsgClientVTTCert body: need {self.BODY_SIZE} bytes")

        (self.m_cVTTCertTotal,
         self.m_cVTTCertTotalBad,
         found_u8,
         self._pad0,
         pad16,
         self.m_cubVTTCert) = struct.unpack_from(self.BODY_FORMAT, buffer, offset)

        self.m_cVTTCert = bool(found_u8)

        # split pad16 just so __str__ doesn't look haunted
        self._pad1a = pad16 & 0xFF
        self._pad1b = (pad16 >> 8) & 0xFF

        offset += self.BODY_SIZE

        # Optional RSA key in varlen data
        self.rsa_public_key = b""
        if self.m_cVTTCert and self.m_cubVTTCert:
            if self.m_cubVTTCert != self.PUBKEY_SIZE:
                raise ValueError(f"Unexpected m_cubVTTCert={self.m_cubVTTCert} (expected {self.PUBKEY_SIZE})")

            end = offset + self.m_cubVTTCert
            if len(buffer) < end:
                raise ValueError(
                    f"Buffer too small for VTTCert public key: need {self.m_cubVTTCert} bytes, have {len(buffer) - offset}"
                )

            self.rsa_public_key = buffer[offset:end]
            offset = end

        return offset

    def to_clientmsg(self) -> CMResponse:
        """
        Serialize body + optional variable data into CMResponse.
        """
        found_u8 = 1 if self.m_cVTTCert else 0

        if self.m_cVTTCert:
            if len(self.rsa_public_key) != self.PUBKEY_SIZE:
                raise ValueError(f"rsa_public_key must be exactly {self.PUBKEY_SIZE} bytes when found=True")
            self.m_cubVTTCert = self.PUBKEY_SIZE
        else:
            self.m_cubVTTCert = 0
            self.rsa_public_key = b""

        packet = CMResponse(eMsgID=EMsg.ClientVTTCert, client_obj=self.client_obj)

        body = struct.pack(
            self.BODY_FORMAT,
            int(self.m_cVTTCertTotal),
            int(self.m_cVTTCertTotalBad),
            int(found_u8),
            0,      # _pad0
            0,      # _pad1 (uint16)
            int(self.m_cubVTTCert),
        )

        packet.data = body + (self.rsa_public_key if self.m_cVTTCert else b"")
        packet.length = len(packet.data)
        return packet

    def __str__(self):
        return str({
            "m_cVTTCertTotal": self.m_cVTTCertTotal,
            "m_cVTTCertTotalBad": self.m_cVTTCertTotalBad,
            "m_cVTTCert": self.m_cVTTCert,
            "m_cubVTTCert": self.m_cubVTTCert,
            "rsa_public_key_len": len(self.rsa_public_key),
            "rsa_public_key_hex": self.rsa_public_key.hex(),
        })

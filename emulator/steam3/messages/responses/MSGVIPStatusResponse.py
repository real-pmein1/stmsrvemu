import struct
from steam3.cm_packet_utils import CMResponse
from steam3.Types.emsg import EMsg
from steam3.Types.steam_types import EResult, EPaymentMethod


class MSGVIPStatusResponse:
    """
    MsgVIPStatusResponse - Response containing VIP status for a payment method.

    Based on IDA analysis of steamclient_linux.so:

    struct MsgVIPStatusResponse_t {
        EResult m_EResult;           // 4 bytes - offset 0x00
        EPaymentMethod m_ePaymentMethod;  // 4 bytes - offset 0x04
        bool m_bVipUser;             // 1 byte  - offset 0x08
    };  // Total: 9 bytes

    The client's CClientJobVIPStatusResponse::BYieldingRunClientJob reads:
    - m_EResult -> callback.m_EResult
    - m_bVipUser -> callback.m_bUseVIP
    - Only processes if m_ePaymentMethod == k_EPaymentMethodClickAndBuy
    """

    def __init__(self, client_obj, data: bytes = None, version: int = None):
        self.client_obj = client_obj
        self.result = EResult.Invalid
        self.payment_method = EPaymentMethod.CreditCard
        self.is_vip = False

        if data:
            self.deserialize(data)

    def deserialize(self, data: bytes):
        """Parse the binary data (9 bytes)."""
        if len(data) < 9:
            raise ValueError(f"Insufficient data for MSGVIPStatusResponse: {len(data)} < 9")

        result_raw, payment_method_raw, is_vip_byte = struct.unpack_from("<IIB", data, 0)

        self.result = EResult(result_raw)
        self.payment_method = EPaymentMethod(payment_method_raw)
        self.is_vip = bool(is_vip_byte)

    def to_clientmsg(self):
        """
        Build CMResponse packet for this message.
        Matches MsgVIPStatusResponse_t structure (9 bytes).
        """
        packet = CMResponse(EMsg.ClientVIPStatusResponse, self.client_obj)

        # Pack exactly 9 bytes as expected by the client
        packet.data = struct.pack("<IIB",
                                  int(self.result),
                                  int(self.payment_method),
                                  int(self.is_vip))

        packet.length = len(packet.data)
        return packet

    def to_protobuf(self):
        """Return protobuf representation if available"""
        raise NotImplementedError("No protobuf equivalent for MSGVIPStatusResponse")

    def __str__(self):
        return (f"MSGVIPStatusResponse(result={self.result}, "
                f"payment_method={self.payment_method}, is_vip={self.is_vip})")

    def __repr__(self):
        return self.__str__()
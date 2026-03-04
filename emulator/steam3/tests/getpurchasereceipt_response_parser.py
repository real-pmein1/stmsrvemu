import struct
from io import BytesIO

class MsgClientGetPurchaseReceiptsResponse:
    def __init__(self):
        self.m_cReceipts = 0
        self.receipts = []

    def deserialize(self, buffer: bytes):
        """
        Parses the byte buffer to extract MsgClientGetPurchaseReceiptsResponse fields.
        """
        stream = BytesIO(buffer)

        # Read the number of receipts (4 bytes, int32)
        self.m_cReceipts = struct.unpack('<I', stream.read(4))[0]

        # Process each receipt if there are any
        if self.m_cReceipts > 0:
            for _ in range(self.m_cReceipts):
                receipt = self._read_receipt(stream)
                if receipt:
                    self.receipts.append(receipt)

        return self

    def _read_receipt(self, stream):
        """
        Simulates reading a receipt from the stream.
        The structure and details of the receipt are unknown here,
        so this is a placeholder method that would need to be adapted
        based on the actual format of each receipt.
        """
        try:
            # Example: Reading a receipt's data (this depends on the actual structure)
            # For now, let's just simulate reading a 4-byte integer as the receipt.
            receipt_data = struct.unpack('<I', stream.read(4))[0]  # Assuming 4-byte data per receipt
            return receipt_data
        except Exception as e:
            print(f"Failed to read receipt: {e}")
            return None


# Example buffer (replace this with actual data)
"""packet = (
    struct.pack('<I', 3) +  # m_cReceipts (example: 3 receipts)
    struct.pack('<I', 1001) +  # Receipt 1 data
    struct.pack('<I', 1002) +  # Receipt 2 data
    struct.pack('<I', 1003)    # Receipt 3 data
)"""
packet = b'\x16\x03\x00\x00$\x02\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xef\xc4\xa0\x9b\x01\x01\x00\x10\x01\x00v/\x00\x00\x00\x00\x00'


packet = packet[36:]
# Deserialize the example buffer
response = MsgClientGetPurchaseReceiptsResponse()
response.deserialize(packet)

# Output the parsed data
print(f"Number of Receipts: {response.m_cReceipts}")
print(f"Receipts: {response.receipts}")
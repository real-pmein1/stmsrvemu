import struct
from io import BytesIO


class MsgClientUFSGetFileListForAppResponse:
    def __init__(self):
        self.m_nFiles = 0

    def parse(self, buffer):
        stream = BytesIO(buffer)

        # Read the number of files
        self.m_nFiles = struct.unpack('<I', stream.read(4))[0]
        print(f"Number of files: {self.m_nFiles}")

        # Parse each file information
        files = []
        for i in range(self.m_nFiles):
            app_id = struct.unpack('<I', stream.read(4))[0]
            file_name = stream.read(260).rstrip(b'\x00').decode('utf-8')
            sha_digest = stream.read(20)  # SHA digest is 20 bytes
            timestamp = struct.unpack('<Q', stream.read(8))[0]  # 8-byte timestamp
            file_size = struct.unpack('<I', stream.read(4))[0]  # 4-byte file size

            # Store file information as a dictionary
            files.append({
                    'app_id':    app_id,
                    'file_name': file_name,
                    'sha_digest':sha_digest,
                    'timestamp': timestamp,
                    'file_size': file_size,
            })

            print(f"File {i + 1}:")
            print(f"  App ID: {app_id}")
            print(f"  File Name: {file_name}")
            print(f"  SHA Digest: {sha_digest.hex()}")
            print(f"  Timestamp: {timestamp}")
            print(f"  File Size: {file_size} bytes")

        # If buffer has more data, print remaining bytes
        remaining_bytes = stream.read()
        if remaining_bytes:
            print(f"Extra bytes in buffer: {remaining_bytes.hex()}")

        return files


# Example usage
"""buffer = b'\x02\x00\x00\x00' + b'\x01\x00\x00\x00' + b'file1.txt'.ljust(260, b'\x00') + b'\x12' * 20 + struct.pack('<Q', 1633036800) + struct.pack('<I', 1024) + \
         b'\x02\x00\x00\x00' + b'file2.txt'.ljust(260, b'\x00') + b'\x34' * 20 + struct.pack('<Q', 1633036810) + struct.pack('<I', 2048)
"""


packet = b'W\x14\x00\x00$\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\xefmw\xea\x02\x01\x00\x10\x01\xfc\xdf\x8b\x00\x00\x00\x00\x00'

packet = packet[36:]
parser = MsgClientUFSGetFileListForAppResponse()
parser.parse(packet)
from struct import pack, unpack

class MsgClientServersAvailable:
    def __init__(self):
        self.body = {
            "servers": []
        }

    def add_server(self, server_type: int):
        """
        Adds a server type to the servers list.

        :param server_type: Integer representing the server type.
        """
        self.body["servers"].append(server_type)

    def deserialize(self, data: bytes):
        """
        Deserialize data from a byte string.

        :param data: Byte string containing serialized data.
        :raises Exception: If the supposed count does not match the available size.
        """
        offset = 0
        count, = unpack('<I', data[offset:offset + 4])
        offset += 4

        expected_size = count * 4
        if len(data[offset:]) != expected_size:
            raise Exception("supposed count != available size")

        self.body["servers"] = [
            unpack('<I', data[offset + i * 4:offset + (i + 1) * 4])[0]
            for i in range(count)
        ]

    def serialize(self) -> bytes:
        """
        Serialize data into a byte string.

        :return: Byte string containing serialized data.
        """
        count = len(self.body["servers"])
        data = pack('<I', count)
        data += b''.join(pack('<I', server) for server in self.body["servers"])
        return data


# Note: The InputStream and OutputStream classes need to be implemented
# with methods like `read_int32`, `available`, and `write_int32` for this
# class to function properly.

"""# Original string buffer
original_string_buffer = "Hello, World!"

# Convert the string to bytes using UTF-8 encoding
buffer_bytes = original_string_buffer.encode('utf-8')

# Create a NetworkBuffer object with the bytes
network_buffer = NetworkBuffer(buffer_bytes)

# Now you can use the network_buffer object as shown in the previous example
"""
import struct


class NetworkBuffer(object):
    def __init__(self, buffer_data=None):
        if buffer_data is None:
            self.buffer = bytearray()
        else:
            self.buffer = bytearray(buffer_data)
        self.cursor = 0

    def check_buffer(self, size):
        if self.cursor + size > len(self.buffer):
            raise ValueError(f"Not enough bytes in buffer. Required: {size}, Available: {len(self.buffer) - self.cursor}")

    def append_u8(self, value):
        self.buffer.append(value)
        self.cursor += 1

    def append_u16(self, value):
        self.buffer.append(value & 0xFF)
        self.buffer.append((value >> 8) & 0xFF)
        self.cursor += 2

    def append_u32(self, value):
        for shift in (0, 8, 16, 24):
            self.buffer.append((value >> shift) & 0xFF)
        self.cursor += 4

    def append_u64(self, value):
        for i in range(8):
            self.buffer.append((value >> (i * 8)) & 0xFF)
        self.cursor += 8

    def append_string(self, string):
        encoded = string.encode('latin-1')
        self.buffer.extend(encoded + b'\x00')
        self.cursor += len(encoded) + 1

    def append_gap(self, size):
        self.buffer.extend(b'\x00' * size)
        self.cursor += size

    def append_buffer(self, size):
        data = self.buffer[self.cursor:self.cursor + size]
        self.cursor += size
        return data

    def extract_u8(self):
        self.check_buffer(1)
        value = self.buffer[self.cursor]
        self.cursor += 1
        return value

    def extract_u16(self):
        self.check_buffer(2)
        value = self.buffer[self.cursor] | (self.buffer[self.cursor + 1] << 8)
        self.cursor += 2
        return value

    def extract_u32(self):
        self.check_buffer(4)
        value = (self.buffer[self.cursor] |
                 (self.buffer[self.cursor + 1] << 8) |
                 (self.buffer[self.cursor + 2] << 16) |
                 (self.buffer[self.cursor + 3] << 24))
        self.cursor += 4
        return value

    def extract_u64(self):
        self.check_buffer(8)
        value = (self.buffer[self.cursor] |
                 (self.buffer[self.cursor + 1] << 8) |
                 (self.buffer[self.cursor + 2] << 16) |
                 (self.buffer[self.cursor + 3] << 24) |
                 (self.buffer[self.cursor + 4] << 32) |
                 (self.buffer[self.cursor + 5] << 40) |
                 (self.buffer[self.cursor + 6] << 48) |
                 (self.buffer[self.cursor + 7] << 56))
        self.cursor += 8
        return value

    def extract_fixed_string(self, length):
        """
        Extract exactly 'length' bytes from the buffer and return the string up to
        the first null terminator. This prevents your code from reading garbage if the
        field isn't fully padded.
        """
        self.check_buffer(length)
        data = self.buffer[self.cursor:self.cursor + length]
        self.cursor += length
        # Return bytes up to the first null terminator (if any)
        return data.split(b'\x00', 1)[0]

    def extract_string(self):
        """
        Extract a null-terminated string. If no null terminator is found, raise an error.
        """
        end = self.buffer.find(b'\x00', self.cursor)
        if end == -1:
            raise ValueError("Null terminator not found in buffer.")
        data = self.buffer[self.cursor:end]
        self.cursor = end + 1
        return data

    def extract_float(self):
        self.check_buffer(4)
        value = struct.unpack('<f', self.buffer[self.cursor:self.cursor+4])[0]
        self.cursor += 4
        return value

    def extract_buffer(self, size):
        self.check_buffer(size)
        data = self.buffer[self.cursor:self.cursor + size]
        self.cursor += size
        return data

    def extract_remaining(self):
        data = self.buffer[self.cursor:]
        self.cursor = len(self.buffer)
        return data

    def finish_extracting(self):
        remaining = len(self.buffer) - self.cursor
        if remaining != 0:
            raise ValueError(f"Buffer extraction not complete. {remaining} bytes remaining.")

    def parse_next(self):
        data_type = self.extract_u8()
        if data_type == 0x05:
            key = self.extract_buffer(self.buffer[self.cursor:].index(b'\x00')).rstrip(b'\x00')
            size = 6
            value = self.extract_buffer(6)
        elif data_type == 0x01:
            key = self.extract_buffer(self.buffer[self.cursor:].index(b'\x00')).rstrip(b'\x00')
            size = int(self.extract_u16())
            value = self.extract_buffer(size)
        else:
            raise ValueError("Unknown data type: {}".format(data_type))
        return key, value, size

    def get_buffer(self):
        return bytes(self.buffer)

    def get_buffer_from_cursor(self):
        return self.buffer[self.cursor:]

    def remaining_length(self):
        return len(self.get_buffer_from_cursor())
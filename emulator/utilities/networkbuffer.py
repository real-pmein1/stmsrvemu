"""# Original string buffer
original_string_buffer = "Hello, World!"

# Convert the string to bytes using UTF-8 encoding
buffer_bytes = original_string_buffer.encode('utf-8')

# Create a NetworkBuffer object with the bytes
network_buffer = NetworkBuffer(buffer_bytes)

# Now you can use the network_buffer object as shown in the previous example
"""


class NetworkBuffer(object):
    def __init__(self, buffer_data=None):
        if buffer_data is None:
            self.buffer = bytearray()
        else:
            self.buffer = bytearray(buffer_data)
        self.cursor = 0

    def append_u8(self, value):
        self.buffer.append(value)
        self.cursor += 1

    def append_u16(self, value):
        self.buffer.append(value & 0xFF)
        self.buffer.append((value >> 8) & 0xFF)
        self.cursor += 2

    def append_u32(self, value):
        self.buffer.append(value & 0xFF)
        self.buffer.append((value >> 8) & 0xFF)
        self.buffer.append((value >> 16) & 0xFF)
        self.buffer.append((value >> 24) & 0xFF)
        self.cursor += 4

    def append_u64(self, value):
        for i in range(8):
            self.buffer.append((value >> (i * 8)) & 0xFF)
        self.cursor += 8

    def append_string(self, string):
        self.buffer.extend(string.encode('latin-1') + b'\x00')  # Append the string with a null terminator
        self.cursor += len(string) + 1

    def append_gap(self, size):
        for _ in range(size):
            self.buffer.append(0)
        self.cursor += size

    def append_buffer(self, size):
        data = self.buffer[self.cursor:self.cursor + size]
        self.cursor += size
        return data

    def check_buffer(self, size):
        remaining_space = len(self.buffer) - self.cursor
        if remaining_space < size:
            raise ValueError("Not enough space in buffer. Required: {}, Available: {}".format(size, remaining_space))

    def extract_u16(self):
        value = self.buffer[self.cursor] | (self.buffer[self.cursor + 1] << 8)
        self.cursor += 2
        return value

    def extract_u8(self):
        value = self.buffer[self.cursor]
        self.cursor += 1
        return value

    def extract_u32(self):
        value = self.buffer[self.cursor] | (self.buffer[self.cursor + 1] << 8) | (self.buffer[self.cursor + 2] << 16) | (self.buffer[self.cursor + 3] << 24)
        self.cursor += 4
        return value

    def extract_u64(self):
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

    def extract_gap(self, size):
        self.cursor += size

    def extract_buffer(self, size):
        data = self.buffer[self.cursor:self.cursor + size]
        self.cursor += size
        return data

    def extract_string(self):
        end = self.buffer.find(b'\x00', self.cursor)
        if end == -1:
            raise ValueError("Null terminator not found in buffer.")

        string = self.buffer[self.cursor:end + 1]  # Include the null terminator
        self.cursor = end + 1  # Move cursor to the byte after the null terminator
        return string

    def extract_remaining(self):
        remaining_data = self.buffer[self.cursor:]
        self.cursor = len(self.buffer)  # Move the cursor to the end
        return remaining_data

    def parse_next(self):  # this is specific to 2004 friends network protocol
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

    def finish_extracting(self):
        remaining_bytes = len(self.buffer) - self.cursor
        if remaining_bytes != 0:
            raise ValueError(f"Buffer extraction not complete. {remaining_bytes} bytes remaining.")
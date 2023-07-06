import struct

class NetworkBuffer:
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
        value = self.buffer[self.cursor] | (self.buffer[self.cursor + 1] << 8) | \
                (self.buffer[self.cursor + 2] << 16) | (self.buffer[self.cursor + 3] << 24)
        self.cursor += 4
        return value

    def extract_gap(self, size):
        self.cursor += size

    def extract_buffer(self, size):
        data = self.buffer[self.cursor:self.cursor + size]
        self.cursor += size
        return data

    def finish_extracting(self):
        remaining_bytes = len(self.buffer) - self.cursor
        if remaining_bytes != 0:
            raise ValueError("Buffer extraction not complete. {} bytes remaining.".format(remaining_bytes))
